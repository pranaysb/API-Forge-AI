import asyncio
import httpx
import sys
import uuid
import json
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from app.models.domain import IntegrationJob

engine = create_engine("postgresql://pranaysb@localhost:5432/apiforge")
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

# Find an existing job to copy the spec from
existing_job = db.query(IntegrationJob).first()
if not existing_job:
    print("No existing job found")
    sys.exit()

new_job_id = str(uuid.uuid4())

job = IntegrationJob(
    id=new_job_id,
    spec_content=existing_job.spec_content,
    status="PENDING",
    project_id=existing_job.project_id
)
db.add(job)
db.commit()

print(f"Created job: {new_job_id}")

async def run_and_disconnect_after(node_to_wait_for, label):
    print(f"\n--- TEST: Disconnect after {node_to_wait_for} ({label}) ---")
    try:
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", f"http://127.0.0.1:8000/api/jobs/{new_job_id}/stream", timeout=None) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        status = data.get("status")
                        print(f"Received: {status}")
                        if status == node_to_wait_for:
                            print(f"Target node '{node_to_wait_for}' reached. Forcing disconnect!")
                            return
    except Exception as e:
        print(f"Client disconnected: {e}")

async def main():
    # 1. Start fresh, disconnect after planner
    await run_and_disconnect_after("planner", "fresh run")
    await asyncio.sleep(2) # Give backend a moment to clean up lock
    
    # 2. Resume, disconnect after schema_validator
    await run_and_disconnect_after("schema_validator", "resume run")
    await asyncio.sleep(2)
    
    # 3. Resume, disconnect after coder
    await run_and_disconnect_after("coder", "resume run")
    await asyncio.sleep(2)
    
    # 4. Resume, disconnect after executor
    await run_and_disconnect_after("executor", "resume run")
    await asyncio.sleep(2)
    
    # 5. Full run to completion
    print("\n--- TEST: Run to completion ---")
    async with httpx.AsyncClient(timeout=100.0) as client:
        async with client.stream("GET", f"http://127.0.0.1:8000/api/jobs/{new_job_id}/stream") as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    print(f"Received: {data.get('status')}")

if __name__ == "__main__":
    asyncio.run(main())
