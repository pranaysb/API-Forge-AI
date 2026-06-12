import psycopg
from langgraph.checkpoint.postgres import PostgresSaver

with psycopg.connect("postgresql://pranaysb@localhost:5432/apiforge", autocommit=True) as conn:
    checkpointer = PostgresSaver(conn)
    checkpointer.setup()
