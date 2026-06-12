import sys
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool
from app.core.config import settings
from typing import TypedDict

class State(TypedDict):
    val: int

def node_a(state: State):
    return {"val": state.get("val", 0) + 1}

def node_b(state: State):
    return {"val": state.get("val", 0) + 1}

pool = ConnectionPool(conninfo=settings.SQLALCHEMY_DATABASE_URI, max_size=5, open=True)
checkpointer = PostgresSaver(pool)

workflow = StateGraph(State)
workflow.add_node("A", node_a)
workflow.add_node("B", node_b)
workflow.add_edge(START, "A")
workflow.add_edge("A", "B")
workflow.add_edge("B", END)
graph = workflow.compile(checkpointer=checkpointer)

config = {"configurable": {"thread_id": "test-stream-interrupt-1"}}

print("--- Initial Run ---")
try:
    for s in graph.stream({"val": 0}, config):
        print("Completed node:", list(s.keys())[0])
        # Simulate SSE drop after node A
        if "A" in s:
            print("Simulating SSE disconnect...")
            raise KeyboardInterrupt
except KeyboardInterrupt:
    pass

state = graph.get_state(config)
print("Next after A:", state.next)

print("--- Resume Run ---")
for s in graph.stream(None, config):
    print("Completed node:", list(s.keys())[0])

state = graph.get_state(config)
print("Next after B:", state.next)

pool.close()
