import os
from app.services.e2b_executor import execute_python_code

print("--- Phase 2: E2B Validation ---")
# Manually override API key check if we want to see the exact E2B SDK error
api_key = os.getenv("E2B_API_KEY")
if not api_key:
    print("WARNING: Using invalid/missing API key. Execution will fail at E2B API level.")

code = "print('Hello from E2B Sandbox!')"
print("Attempting to run simple Python code...")
result = execute_python_code(code)
print("Result:", result)

code_http = "import httpx; r = httpx.get('https://example.com'); print(r.status_code)"
print("\nAttempting to run HTTP request...")
result_http = execute_python_code(code_http)
print("Result:", result_http)
