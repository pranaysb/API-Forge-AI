from app.agents.graph import graph
import json

spec = """
openapi: 3.0.0
info:
  title: Sample
  version: 1.0.0
paths:
  /hello:
    get:
      summary: Say Hello
"""

initial_state = {
    "spec_content": spec,
    "base_url": "http://localhost:8000",
    "endpoints": [{"method": "GET", "path": "/hello", "status": "PENDING", "attempts": 0, "id": "test-123"}],
    "current_endpoint_index": 0,
    "errors": [],
    "global_context": {}
}

print("Running Real LangGraph Workflow...")
for s in graph.stream(initial_state, {"recursion_limit": 10}):
    print(f"\n--- Node Executed: {list(s.keys())[0]} ---")
    state_after = list(s.values())[0]
    
    if "endpoints" in state_after and state_after["endpoints"]:
        ep = state_after["endpoints"][0]
        print(f"Agent Reasoning: {ep.get('agent_reasoning', 'None')}")
        print(f"Generated Code:\n{ep.get('generated_code', 'None')}")
        print(f"Diagnostic Feedback: {ep.get('diagnostic_feedback', 'None')}")
        print(f"E2B Logs:\n{ep.get('e2b_logs', 'None')}")
        print(f"Status: {ep.get('status', 'None')}")
