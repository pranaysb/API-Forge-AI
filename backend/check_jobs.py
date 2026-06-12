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

jobs = db.query(IntegrationJob).order_by(IntegrationJob.created_at.desc()).limit(3).all()

pool = ConnectionPool(settings.SQLALCHEMY_DATABASE_URI)
with pool.connection() as conn:
    saver = PostgresSaver(conn)
    graph = build_graph(checkpointer=saver)
    
    for job in jobs:
        print(f"\n--- Job ID: {job.id} ---")
        config = {"configurable": {"thread_id": str(job.id)}}
        state = graph.get_state(config)
        if state:
            print("Graph Path (Next):", state.next)
            print("Errors in state:", state.values.get("errors"))
            ep_status = [ep.get("status") for ep in state.values.get("endpoints", [])]
            print("Endpoint statuses:", ep_status)
        else:
            print("No state found")
