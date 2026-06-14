import sys
import os

# Add backend to path so we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.config import settings
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver

def setup_checkpoints():
    if settings.SQLALCHEMY_DATABASE_URI.startswith("sqlite"):
        print("Using SQLite. No Postgres checkpointer setup needed.")
        return
        
    print("Setting up LangGraph PostgresSaver tables...")
    # Use session pooler port (5432) for DDL table creation if using Supabase
    db_url = settings.SQLALCHEMY_DATABASE_URI
    if ":6543" in db_url:
        db_url = db_url.replace(":6543", ":5432")
        
    # PostgresSaver.setup() creates tables safely with IF NOT EXISTS
    with ConnectionPool(conninfo=db_url, max_size=2) as pool:
        checkpointer = PostgresSaver(pool)
        checkpointer.setup()
    print("LangGraph PostgresSaver tables setup successfully!")

if __name__ == "__main__":
    setup_checkpoints()
