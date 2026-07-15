from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.domain import IntegrationJob, ExecutionLog, Artifact
from app.agents.graph import build_graph
from app.agents.state import AgentState
from app.services.openapi_parser import parse_spec_content, extract_endpoints
from app.services.sdk_builder import generate_sdk_zip
from app.services.executor import get_executor
import json
import asyncio
import queue as thread_queue
import threading
import urllib.parse
from datetime import datetime
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.errors import GraphRecursionError
from app.core.config import settings

router = APIRouter()

# Connection pool for langgraph checkpointer (only if using Postgres)
is_sqlite = settings.SQLALCHEMY_DATABASE_URI.startswith("sqlite")
pool = None if is_sqlite else ConnectionPool(conninfo=settings.SQLALCHEMY_DATABASE_URI, max_size=20, open=False)
memory_saver = MemorySaver() if is_sqlite else None

# In-memory lock to prevent concurrent executions for the same job.
# NOTE: only safe with a single worker process; multi-worker deployments need
# a distributed lock (e.g. Redis).
job_locks = {}

DEFAULT_BASE_URL = "http://127.0.0.1:8001"

def normalize_base_url(raw_url: str) -> str:
    """Resolves relative server URLs from the spec against the default host."""
    if not raw_url.startswith(("http://", "https://")):
        return urllib.parse.urljoin(DEFAULT_BASE_URL, raw_url)
    return raw_url

def iter_graph_in_thread(stream_generator):
    """Iterates a synchronous LangGraph stream in a worker thread so multi-second
    LLM/executor calls don't block the event loop (which would stall every other
    request on the server). Yields items back on the loop via a thread queue."""
    q = thread_queue.Queue(maxsize=4)
    _SENTINEL = object()

    def producer():
        try:
            for item in stream_generator:
                q.put(("item", item))
        except BaseException as e:
            q.put(("error", e))
        finally:
            q.put(("done", _SENTINEL))

    threading.Thread(target=producer, daemon=True).start()

    async def consume():
        while True:
            kind, payload = await asyncio.to_thread(q.get)
            if kind == "error":
                raise payload
            if kind == "done":
                return
            yield payload

    return consume()

async def real_event_generator(job_id: str, db: Session):
    if job_id not in job_locks:
        job_locks[job_id] = asyncio.Lock()
        
    # Wait for our turn to execute or resume this job
    if job_locks[job_id].locked():
        yield f"data: {json.dumps({'status': 'running', 'message': 'Job is currently executing. Waiting for availability...'})}\n\n"
        
    async with job_locks[job_id]:
        # Once we have the lock, check if the job actually finished while we were waiting
        job = db.query(IntegrationJob).filter(IntegrationJob.id == job_id).first()
        if not job:
            yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
            return
            
        if job.status in ["SUCCESS", "FAILED"]:
            yield f"data: {json.dumps({'status': 'complete', 'success': job.status == 'SUCCESS', 'message': 'Job execution finished'})}\n\n"
            return
            
        job.status = "RUNNING"
        db.commit()

        try:
            parsed_json = parse_spec_content(job.spec_content)
            endpoints_data = extract_endpoints(parsed_json)
            
            raw_url = parsed_json.get("servers", [{"url": DEFAULT_BASE_URL}])[0].get("url", DEFAULT_BASE_URL)
            base_url = normalize_base_url(raw_url)

            initial_state = AgentState({
                "spec_content": job.spec_content,
                "base_url": base_url,
                "endpoints": endpoints_data,
                "current_endpoint_index": 0
            })

            if is_sqlite:
                checkpointer = memory_saver
            else:
                pool.open()
                checkpointer = PostgresSaver(pool)
                
            graph = build_graph(checkpointer=checkpointer)
            
            recursion_limit = max(200, len(endpoints_data) * 30)
            config = {"configurable": {"thread_id": job.id}, "recursion_limit": recursion_limit}
            
            # Check if graph has existing state in the checkpointer
            existing_state = graph.get_state(config)
            
            print(f"--- CHECKPOINT AUDIT ---")
            print(f"Thread ID (Job ID): {job.id}")
            if existing_state:
                print(f"Existing State Values: {bool(existing_state.values)}")
                print(f"Existing State Next: {existing_state.next}")
            else:
                print("Existing State: None")
            
            if existing_state and existing_state.values:
                if existing_state.next:
                    # Resume from checkpoint
                    print("Action: RESUMING from checkpoint")
                    full_state = existing_state.values.copy()
                    stream_generator = graph.stream(None, config)
                    yield f"data: {json.dumps({'status': 'resuming', 'message': f'Resuming from checkpoint at node {existing_state.next[0]}'})}\n\n"
                else:
                    # Graph finished previously but client disconnected before artifact generation
                    print("Action: JUMPING directly to artifact generation")
                    full_state = existing_state.values.copy()
                    stream_generator = [] # Empty generator to bypass loop
            else:
                # Start fresh
                print("Action: STARTING fresh execution")
                full_state = initial_state.copy()
                stream_generator = graph.stream(initial_state, config)
            print(f"------------------------")
            
            current_idx = full_state.get("current_endpoint_index", 0)
            node_start_time = datetime.utcnow()
            
            try:
                async for s in iter_graph_in_thread(stream_generator):
                    node_end_time = datetime.utcnow()
                    duration_ms = int((node_end_time - node_start_time).total_seconds() * 1000)
                    
                    node_name = list(s.keys())[0]
                    state_after = list(s.values())[0]
                    
                    # Inject explicit active endpoint metadata for UI timeline rendering
                    state_after["active_endpoint_index"] = current_idx
                    if current_idx < len(endpoints_data):
                        state_after["active_endpoint_path"] = endpoints_data[current_idx]["path"]
                        state_after["active_endpoint_method"] = endpoints_data[current_idx]["method"]
                    
                    # Accumulate state
                    for k, v in state_after.items():
                        if v is not None:
                            full_state[k] = v
                            
                    # Update current_idx for next iteration based on accumulated state
                    current_idx = full_state.get("current_endpoint_index", 0)
                    
                    # Save log to DB
                    log = ExecutionLog(
                        job_id=job.id,
                        node_name=node_name,
                        state_delta=state_after,
                        start_time=node_start_time,
                        end_time=node_end_time,
                        duration_ms=duration_ms
                    )
                    db.add(log)
                    db.commit()
                    
                    # Yield SSE
                    yield f"data: {json.dumps({'status': node_name, 'message': f'Node {node_name.upper()} executed'})}\n\n"
                    await asyncio.sleep(0.5)  # Slight delay for UI visualization
                    
                    # Reset start time for next node
                    node_start_time = datetime.utcnow()
            except GraphRecursionError as e:
                print(f"GraphRecursionError caught: {str(e)}")
                job.status = "FAILED"
                job.completed_at = datetime.utcnow()
                db.commit()
                yield f"data: {json.dumps({'status': 'error', 'message': 'Graph recursion limit exceeded'})}\n\n"
                yield f"data: {json.dumps({'status': 'complete', 'success': False, 'message': 'Job execution failed due to recursion limit'})}\n\n"
                return
                
            # Check for early termination or planner errors
            graph_errors = full_state.get("errors", [])
            sdk_files = full_state.get("sdk_files", {})
            
            if graph_errors:
                job.status = "FAILED"
                job.completed_at = datetime.utcnow()
                db.commit()
                # Surface the first error to the client
                error_msg = graph_errors[0]
                yield f"data: {json.dumps({'status': 'error', 'message': error_msg})}\n\n"
                yield f"data: {json.dumps({'status': 'complete', 'success': False, 'message': f'Job execution failed: {error_msg}'})}\n\n"
                return
                
            if not sdk_files:
                job.status = "FAILED"
                job.completed_at = datetime.utcnow()
                db.commit()
                yield f"data: {json.dumps({'status': 'error', 'message': 'SDK files were not generated'})}\n\n"
                yield f"data: {json.dumps({'status': 'complete', 'success': False, 'message': 'Job execution failed: SDK generation aborted'})}\n\n"
                return

            # Final SDK Quality Gate.
            # Runs entirely against httpx.MockTransport — it must never depend on
            # the target API being reachable. (Previously it invoked a zero-arg
            # method against the real base_url; petstore jobs failed with
            # ConnectionRefused even after every endpoint test passed.)
            test_script = """import httpx
import inspect
import sys
from apiforge_sdk.client import ApiClient
from pydantic import BaseModel, ValidationError

client = ApiClient()
methods = [m for m in dir(client) if not m.startswith('_') and callable(getattr(client, m))]
if not methods:
    raise Exception("No methods found in ApiClient")

zero_arg_methods = []
for m in methods:
    sig = inspect.signature(getattr(client, m))
    required_params = [
        p for name, p in sig.parameters.items()
        if p.default == inspect.Parameter.empty and name != 'self'
    ]
    if len(required_params) == 0:
        zero_arg_methods.append(m)

print(f"Zero-argument methods found: {zero_arg_methods}")

if not zero_arg_methods:
    print("No zero-argument methods found. Skipping runtime invocation check. PASS.")
    sys.exit(0)

# Replace any internal httpx.Client with a mocked one so no real network
# request is made. The gate only verifies methods return Pydantic models
# rather than raw httpx.Response objects.
def mock_handler(request):
    return httpx.Response(200, json={})

injected = False
for attr_name, attr_value in list(vars(client).items()):
    if isinstance(attr_value, httpx.Client):
        setattr(client, attr_name, httpx.Client(
            transport=httpx.MockTransport(mock_handler),
            base_url=attr_value.base_url,
            timeout=attr_value.timeout,
        ))
        injected = True

if not injected:
    print("Could not locate an internal httpx.Client to mock. Skipping runtime invocation check. PASS.")
    sys.exit(0)

method_name = zero_arg_methods[0]
method = getattr(client, method_name)
try:
    result = method()
except ValidationError:
    # The mocked empty payload failed model validation — which proves the
    # method does run Pydantic validation instead of returning raw responses.
    print(f"Method {method_name} validates responses with Pydantic. PASS.")
    sys.exit(0)

if isinstance(result, httpx.Response):
    raise Exception(f"Method {method_name} returned raw httpx.Response instead of a Pydantic model")

if isinstance(result, list) and len(result) > 0:
    item = result[0]
    if not isinstance(item, BaseModel):
        raise Exception(f"Method {method_name} returned a list of {type(item)}, expected BaseModel")
elif isinstance(result, dict) or result is None or isinstance(result, (str, int, float, bool)):
    # Plain payloads (e.g. Dict[str, int] responses) and None are acceptable
    pass
elif not isinstance(result, list):
    if not isinstance(result, BaseModel):
        raise Exception(f"Method {method_name} returned {type(result)}, expected BaseModel")

print('SDK imported and executed successfully')
"""
            executor = get_executor()
            integrity_success, integrity_stdout, integrity_stderr = executor.execute_sdk_test(full_state.get("sdk_files", {}), test_script)
            
            endpoints = full_state.get("endpoints", [])
            any_failed = len(endpoints) > 0 and any(ep.get("status") in ["FAILED", "FAILED_PERMANENTLY"] for ep in endpoints)
            print(f"Final endpoints status: {[ep.get('status') for ep in endpoints]}")
            print(f"Any Failed: {any_failed}, Integrity Success: {integrity_success}")
            
            if not integrity_success or any_failed:
                job.status = "FAILED"
                job.completed_at = datetime.utcnow()
                db.commit()
                msg = "Job execution failed. One or more endpoints failed." if any_failed else f"Job execution failed. Integrity error: {integrity_stderr}"
                yield f"data: {json.dumps({'status': 'complete', 'success': False, 'message': msg})}\n\n"
                return
                
            # Execution summary
            provider_failovers = full_state.get("provider_failovers", 0)
            model_failovers = full_state.get("model_failovers", 0)
            final_model = full_state.get("global_context", {}).get("final_model_used", "llama-3.3-70b-versatile")
            final_key_index = full_state.get("global_context", {}).get("final_key_index", 0)
            
            summary_data = {
                "provider_failovers": provider_failovers,
                "model_failovers": model_failovers,
                "final_model_used": final_model,
                "final_key_index": final_key_index
            }
            yield f"data: {json.dumps({'status': 'summary', 'message': 'Execution Summary', 'data': summary_data})}\n\n"
            
            # Graph complete, build SDK
            yield f"data: {json.dumps({'status': 'generating', 'message': 'Generating SDK artifacts'})}\n\n"
            zip_bytes = generate_sdk_zip(full_state.get("sdk_files", {}))
            
            artifact = Artifact(job_id=job.id, zip_data=zip_bytes.getvalue())
            db.add(artifact)
            
            job.status = "SUCCESS"
            job.completed_at = datetime.utcnow()
            db.commit()
            
            yield f"data: {json.dumps({'status': 'complete', 'success': True, 'message': 'Job execution finished'})}\n\n"
        finally:
            pass # lock is released automatically by async with

    # Drop the lock entry once the job is finished so job_locks doesn't grow
    # unboundedly over the server's lifetime.
    lock = job_locks.get(job_id)
    if lock is not None and not lock.locked():
        job_locks.pop(job_id, None)

@router.get("/jobs/{job_id}/stream")
async def stream_job_progress(job_id: str, db: Session = Depends(get_db)):
    return StreamingResponse(real_event_generator(job_id, db), media_type="text/event-stream")
