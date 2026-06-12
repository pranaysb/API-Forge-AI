from langgraph.graph import StateGraph, START, END
from app.agents.state import AgentState
from app.agents.nodes import planner_node, coder_node, executor_node, diagnoser_node, sdk_validator_node, schema_validator_node

def route_after_diagnoser(state: AgentState) -> str:
    idx = state.get("current_endpoint_index", 0)
    endpoints = state.get("endpoints", [])
    
    if idx >= len(endpoints):
        return "end"
        
    return "schema_validator"

def route_after_sdk_validator(state: AgentState) -> str:
    if state.get("errors"):
        return "end"
    return "schema_validator"
    
def route_after_schema_validator(state: AgentState) -> str:
    idx = state.get("current_endpoint_index", 0)
    endpoints = state.get("endpoints", [])
    if idx >= len(endpoints):
        return "end"
        
    current_ep = endpoints[idx]
    if current_ep.get("status") == "SCHEMA_FAILED":
        return "diagnoser"
        
    return "coder"

def route_after_executor(state: AgentState) -> str:
    idx = state.get("current_endpoint_index", 0)
    endpoints = state.get("endpoints", [])
    
    if idx >= len(endpoints):
        return "end"
        
    current_ep = endpoints[idx]
    if current_ep.get("status") == "FAILED":
        return "diagnoser"
    
    return "coder"

def build_graph(checkpointer=None):
    workflow = StateGraph(AgentState)

    workflow.add_node("planner", planner_node)
    workflow.add_node("sdk_validator", sdk_validator_node)
    workflow.add_node("schema_validator", schema_validator_node)
    workflow.add_node("coder", coder_node)
    workflow.add_node("executor", executor_node)
    workflow.add_node("diagnoser", diagnoser_node)

    workflow.add_edge(START, "planner")
    workflow.add_edge("planner", "sdk_validator")
    
    workflow.add_conditional_edges(
        "sdk_validator",
        route_after_sdk_validator,
        {
            "schema_validator": "schema_validator",
            "end": END
        }
    )
    
    workflow.add_conditional_edges(
        "schema_validator",
        route_after_schema_validator,
        {
            "diagnoser": "diagnoser",
            "coder": "coder",
            "end": END
        }
    )
    
    workflow.add_edge("coder", "executor")
    
    workflow.add_conditional_edges(
        "executor",
        route_after_executor,
        {
            "diagnoser": "diagnoser",
            "coder": "coder",
            "end": END
        }
    )
    
    workflow.add_conditional_edges(
        "diagnoser",
        route_after_diagnoser,
        {
            "schema_validator": "schema_validator",
            "end": END
        }
    )

    return workflow.compile(checkpointer=checkpointer)

# Default graph without persistence for simple tests
graph = build_graph()
