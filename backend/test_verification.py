from fastapi.testclient import TestClient
from app.main import app
import json
import httpx

client = TestClient(app)

print("--- 1 & 2: Backend Startup ---")
try:
    response = client.get("/health")
    if response.status_code == 200:
        print("PASS: Backend started successfully")
    else:
        print(f"FAIL: /health returned {response.status_code}")
except Exception as e:
    print(f"FAIL: Backend failed to start. {e}")

print("\n--- 7, 8 & 9: OpenAPI Upload and Parsing ---")
spec_yaml = """
openapi: 3.0.0
info:
  title: Sample API
  version: 1.0.0
paths:
  /users:
    get:
      summary: Get users
      operationId: getUsers
    post:
      summary: Create user
      operationId: createUser
"""
try:
    response = client.post("/api/upload", files={"file": ("spec.yaml", spec_yaml, "text/yaml")})
    if response.status_code == 200:
        data = response.json()
        print(f"PASS: Upload successful. Response: {data}")
        spec_id = data.get("spec_id")
    else:
        print(f"FAIL: Upload returned {response.status_code} - {response.text}")
        spec_id = None
except Exception as e:
    print(f"FAIL: Upload error. {e}")
    spec_id = None

print("\n--- 11: SSE Stream ---")
try:
    if spec_id:
        response = client.get(f"/api/stream/{spec_id}")
        if response.status_code == 200 and "text/event-stream" in response.headers["content-type"]:
            print("PASS: SSE stream endpoint works")
        else:
            print(f"FAIL: Stream returned {response.status_code}")
    else:
        print("FAIL: No spec_id available for stream test")
except Exception as e:
    print(f"FAIL: Stream error. {e}")

print("\n--- 10: SDK Generation ---")
try:
    if spec_id:
        response = client.get(f"/api/download/{spec_id}")
        if response.status_code == 200 and "application/x-zip-compressed" in response.headers["content-type"]:
            print("PASS: SDK generated and downloaded successfully")
        else:
            print(f"FAIL: Download returned {response.status_code}")
    else:
        print("FAIL: No spec_id available for download test")
except Exception as e:
    print(f"FAIL: Download error. {e}")
