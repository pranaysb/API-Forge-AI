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
from datetime import datetime
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver
from app.core.config import settings

router = APIRouter()

# Connection pool for langgraph checkpointer
pool = ConnectionPool(conninfo=settings.SQLALCHEMY_DATABASE_URI, max_size=20, open=False)

# In-memory lock to prevent concurrent executions for the same job
job_locks = {}

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
            yield f"data: {json.dumps({'status': 'complete', 'message': 'Job execution finished'})}\n\n"
            return
            
        job.status = "RUNNING"
        db.commit()

        try:
            parsed_json = parse_spec_content(job.spec_content)
            endpoints_data = extract_endpoints(parsed_json)
            
            initial_state = AgentState({
                "spec_content": job.spec_content,
                "base_url": parsed_json.get("servers", [{"url": "http://127.0.0.1:8001"}])[0].get("url"),
                "endpoints": endpoints_data,
                "current_endpoint_index": 0
            })

            pool.open()
            checkpointer = PostgresSaver(pool)
            graph = build_graph(checkpointer=checkpointer)
            config = {"configurable": {"thread_id": job.id}, "recursion_limit": 50}
            
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
            for s in stream_generator:
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
                
            # Final SDK Quality Gate
            test_script = """
    import httpx
    from apiforge_sdk.client import ApiClient
    from pydantic import BaseModel

    client = ApiClient()
    methods = [m for m in dir(client) if not m.startswith('_') and callable(getattr(client, m))]
    if not methods:
        raise Exception("No methods found in ApiClient")

    method_name = methods[0]
    method = getattr(client, method_name)
    result = method()

    if isinstance(result, httpx.Response):
        raise Exception(f"Method {method_name} returned raw httpx.Response instead of a Pydantic model")

    if isinstance(result, list) and len(result) > 0:
        item = result[0]
        if not isinstance(item, BaseModel):
            raise Exception(f"Method {method_name} returned a list of {type(item)}, expected BaseModel")
    elif not isinstance(result, list) and result is not None:
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
                yield f"data: {json.dumps({'status': 'complete', 'message': msg})}\n\n"
                return
                
            # Graph complete, build SDK
            yield f"data: {json.dumps({'status': 'generating', 'message': 'Generating SDK artifacts'})}\n\n"
            zip_bytes = generate_sdk_zip(full_state.get("sdk_files", {}))
            
            artifact = Artifact(job_id=job.id, zip_data=zip_bytes.getvalue())
            db.add(artifact)
            
            job.status = "SUCCESS"
            job.completed_at = datetime.utcnow()
            db.commit()
            
            yield f"data: {json.dumps({'status': 'complete', 'message': 'Job execution finished'})}\n\n"
        finally:
            pass # lock is released automatically by async with

@router.get("/jobs/{job_id}/stream")
async def stream_job_progress(job_id: str, db: Session = Depends(get_db)):
    return StreamingResponse(real_event_generator(job_id, db), media_type="text/event-stream")
