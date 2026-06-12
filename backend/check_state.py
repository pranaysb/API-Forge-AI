from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from app.models.domain import IntegrationJob
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver
from app.agents.graph import build_graph
from app.core.config import settings

engine = create_engine(settings.SQLALCHEMY_DATABASE_URI)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

job = db.query(IntegrationJob).order_by(IntegrationJob.created_at.desc()).first()
print(f"Latest Job ID: {job.id}")

pool = ConnectionPool(settings.SQLALCHEMY_DATABASE_URI)
with pool.connection() as conn:
    saver = PostgresSaver(conn)
    graph = build_graph(checkpointer=saver)
    config = {"configurable": {"thread_id": str(job.id)}}
    state = graph.get_state(config)
    
    if state:
        print("Graph Path (Next):", state.next)
        print("Errors in state:", state.values.get("errors"))
        print("Endpoints count:", len(state.values.get("endpoints", [])))
        print("SDK files count:", len(state.values.get("sdk_files", {})))
        if state.values.get("sdk_files"):
            print("SDK files present:", list(state.values.get("sdk_files").keys()))
        
        ep_status = [ep.get("status") for ep in state.values.get("endpoints", [])]
        print("Endpoint statuses:", ep_status)
        if state.values.get("errors"):
            print("Specific Errors:", state.values.get("errors"))
    else:
        print("No state found")
