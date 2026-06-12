import sys
import asyncio
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool
from app.core.config import settings
from typing import TypedDict

class State(TypedDict):
    val: int

def node_a(state: State):
    print("Running A")
    return {"val": state.get("val", 0) + 1}

def node_b(state: State):
    print("Running B")
    if state.get("val") == 1:
        raise Exception("Interrupt at B")
    return {"val": state.get("val", 0) + 1}

def node_c(state: State):
    print("Running C")
    return {"val": state.get("val", 0) + 1}

pool = ConnectionPool(conninfo=settings.SQLALCHEMY_DATABASE_URI, max_size=5, open=True)
checkpointer = PostgresSaver(pool)

workflow = StateGraph(State)
workflow.add_node("A", node_a)
workflow.add_node("B", node_b)
workflow.add_node("C", node_c)
workflow.add_edge(START, "A")
workflow.add_edge("A", "B")
workflow.add_edge("B", "C")
workflow.add_edge("C", END)
graph = workflow.compile(checkpointer=checkpointer)

config = {"configurable": {"thread_id": "test-thread-1"}}

print("--- Initial Run ---")
try:
    for s in graph.stream({"val": 0}, config):
        print(s)
except Exception as e:
    print("Exception caught:", e)

print("\n--- Getting State ---")
state = graph.get_state(config)
print("Type:", type(state))
print("Values:", state.values)
print("Next:", state.next)

print("\n--- Resuming Run (with None) ---")
try:
    # Need to manually update state to avoid exception again
    graph.update_state(config, {"val": 2})
    
    print("\n--- State after update ---")
    state2 = graph.get_state(config)
    print("Values:", state2.values)
    print("Next:", state2.next)
    
    for s in graph.stream(None, config):
        print(s)
except Exception as e:
    print("Exception caught on resume:", e)
    
pool.close()
