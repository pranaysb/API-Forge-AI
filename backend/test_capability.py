import os
import json
from app.agents.graph import graph
from app.services.sdk_builder import generate_sdk_zip

spec = """
openapi: 3.0.0
info:
  title: Secure API
  version: 1.0.0
paths:
  /api/v1/secure-data:
    get:
      summary: Get Secure Data
      responses:
        '200':
          description: OK
        '401':
          description: Unauthorized
"""

initial_state = {
    "spec_content": spec,
    "base_url": "http://127.0.0.1:8001",
    "endpoints": [{"method": "GET", "path": "/api/v1/secure-data", "status": "PENDING", "attempts": 0, "id": "sec-1"}],
    "current_endpoint_index": 0,
    "errors": [],
    "global_context": {}
}

print("==================================================")
print("RUNNING CAPABILITY VERIFICATION: LOCAL EXECUTION")
print("==================================================\n")

full_state = initial_state.copy()
for s in graph.stream(initial_state, {"recursion_limit": 15}):
    node_name = list(s.keys())[0]
    state_after = list(s.values())[0]
    
    # Accumulate state
    for k, v in state_after.items():
        if v is not None:
            full_state[k] = v
            
    if "endpoints" in full_state and full_state["endpoints"]:
        ep = full_state["endpoints"][0]
        attempts = ep.get("attempts", 0)
        print(f"\n[ NODE EXECUTED: {node_name.upper()} | ATTEMPT: {attempts} ]")
        
        if node_name == "planner":
            print(f"-> Planner established execution plan.")
        
        if node_name == "coder":
            print(f"-> Agent Reasoning:\n{ep.get('agent_reasoning', 'None')}")
            print(f"-> Generated Python Code:\n{ep.get('generated_code', 'None')}")
            
        if node_name == "executor":
            success = ep.get('success', False)
            print(f"-> Execution Result: {'SUCCESS' if success else 'FAILED'}")
            print(f"-> Logs:\n{ep.get('e2b_logs', '')}")
            
        if node_name == "diagnoser":
            print(f"-> Diagnoser Feedback:\n{ep.get('diagnostic_feedback', 'None')}")

print("\n==================================================")
print("EXECUTION GRAPH COMPLETE")
print("==================================================\n")

if full_state:
    ep = full_state["endpoints"][0]
    print(f"Final Endpoint Status: {ep.get('status')}")
    print(f"Total Attempts: {ep.get('attempts')}")
    
    if ep.get('status') == 'SUCCESS':
        print("\nGenerating SDK...")
        # Add required dummy values to pass list comprehension
        ep["success"] = True 
        zip_buffer = generate_sdk_zip([ep], spec)
        print(f"SDK Zip generated successfully. Size: {zip_buffer.getbuffer().nbytes} bytes")
        
        # Extract files for proof
        import zipfile
        with zipfile.ZipFile(zip_buffer, "r") as z:
            for filename in z.namelist():
                print(f"\n--- {filename} ---")
                print(z.read(filename).decode('utf-8'))
