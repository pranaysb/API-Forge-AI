from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver
from app.agents.graph import build_graph
from app.core.config import settings

pool = ConnectionPool(settings.SQLALCHEMY_DATABASE_URI)
with pool.connection() as conn:
    saver = PostgresSaver(conn)
    graph = build_graph(checkpointer=saver)
    config = {"configurable": {"thread_id": "ec03a11c-4b3c-459b-af62-371cb2f8a0d4"}}
    state = graph.get_state(config)
    if state:
        print("Graph Path (Next):", state.next)
        print("Errors in state:", state.values.get("errors"))
        print("Endpoint statuses:", [ep.get("status") for ep in state.values.get("endpoints", [])])
    else:
        print("No state")
