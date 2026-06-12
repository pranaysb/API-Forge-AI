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
job_id = str(uuid.uuid4())
spec_content = existing_job.spec_content

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

print("Running graph normally...")
stream_generator = graph.stream(initial_state, config, stream_mode="values")
for s in stream_generator:
    state = graph.get_state(config)
    print(f"State keys: {s.keys()}")
    print(f"State.next is now: {state.next}")

