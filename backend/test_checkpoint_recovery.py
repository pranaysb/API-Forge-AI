from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
import uuid
import sys
from app.models.domain import IntegrationJob
from app.services.openapi_parser import parse_spec_content, extract_endpoints
from app.agents.state import AgentState
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver
from app.agents.graph import build_graph
from app.core.config import settings

engine = create_engine("postgresql://pranaysb@localhost:5432/apiforge")
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

existing_job = db.query(IntegrationJob).first()
if not existing_job:
    print("No existing job found")
    sys.exit()

# 1. Setup new job
job_id = str(uuid.uuid4())
spec_content = existing_job.spec_content

job = IntegrationJob(
    id=job_id,
    spec_content=spec_content,
    status="PENDING",
    project_id=existing_job.project_id
)
db.add(job)
db.commit()

print(f"--- INIT TEST FOR JOB {job_id} ---")

parsed_json = parse_spec_content(spec_content)
endpoints_data = extract_endpoints(parsed_json)
initial_state = AgentState({
    "spec_content": spec_content,
    "base_url": parsed_json.get("servers", [{"url": "http://127.0.0.1:8001"}])[0].get("url"),
    "endpoints": endpoints_data,
    "current_endpoint_index": 0
})

pool = ConnectionPool(conninfo=settings.SQLALCHEMY_DATABASE_URI, max_size=20, open=True)
checkpointer = PostgresSaver(pool)
checkpointer.setup()
graph = build_graph(checkpointer=checkpointer)
config = {"configurable": {"thread_id": job_id}, "recursion_limit": 50}

def print_checkpoint_audit(config):
    existing_state = graph.get_state(config)
    print(f"--- CHECKPOINT AUDIT ---")
    if existing_state:
        print(f"Existing State Values: {bool(existing_state.values)}")
        print(f"Existing State Next: {existing_state.next}")
        return existing_state
    else:
        print("Existing State: None")
        return None

# 2. Start fresh, break after planner
print("\n>>> TEST 1: Run until planner finishes, then interrupt")
stream_generator = graph.stream(initial_state, config)
for s in stream_generator:
    node_name = list(s.keys())[0]
    print(f"Executed node: {node_name}")
    if node_name == "planner":
        print("INTERRUPTING execution after planner!")
        break

state_after_planner = print_checkpoint_audit(config)

# 3. Resume, break after schema_validator
print("\n>>> TEST 2: Resume, run until schema_validator finishes, then interrupt")
if state_after_planner and state_after_planner.values and state_after_planner.next:
    print(f"RESUMING from checkpoint at {state_after_planner.next[0]}")
    stream_generator = graph.stream(None, config)
    for s in stream_generator:
        node_name = list(s.keys())[0]
        print(f"Executed node: {node_name}")
        if node_name == "schema_validator":
            print("INTERRUPTING execution after schema_validator!")
            break

state_after_schema = print_checkpoint_audit(config)

# 4. Resume, break after coder
print("\n>>> TEST 3: Resume, run until coder finishes, then interrupt")
if state_after_schema and state_after_schema.values and state_after_schema.next:
    print(f"RESUMING from checkpoint at {state_after_schema.next[0]}")
    stream_generator = graph.stream(None, config)
    for s in stream_generator:
        node_name = list(s.keys())[0]
        print(f"Executed node: {node_name}")
        if node_name == "coder":
            print("INTERRUPTING execution after coder!")
            break

state_after_coder = print_checkpoint_audit(config)

# 5. Resume, run until executor
print("\n>>> TEST 4: Resume, run until executor finishes, then interrupt")
if state_after_coder and state_after_coder.values and state_after_coder.next:
    print(f"RESUMING from checkpoint at {state_after_coder.next[0]}")
    stream_generator = graph.stream(None, config)
    for s in stream_generator:
        node_name = list(s.keys())[0]
        print(f"Executed node: {node_name}")
        if node_name == "executor":
            print("INTERRUPTING execution after executor!")
            break

print_checkpoint_audit(config)

print("\nAll tests completed.")
pool.close()
