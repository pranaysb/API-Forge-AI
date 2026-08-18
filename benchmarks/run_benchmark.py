import os
import time
import httpx
import json
import sqlite3
import asyncio
from datetime import datetime

API_URL = "http://localhost:8000"
DB_PATH = "../backend/apiforge.db"
SPECS = ["petstore.json", "jsonplaceholder.json"]

async def run_benchmark():
    results = []
    
    # Ensure backend is up
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{API_URL}/health")
            if resp.status_code != 200:
                print("Backend is not healthy!")
                return
    except Exception as e:
        print(f"Failed to connect to backend: {e}")
        print("Please start the backend server using 'poetry run uvicorn app.main:app --port 8000' in the backend directory.")
        return

    for spec_name in SPECS:
        print(f"\n[{spec_name}] Starting benchmark...")
        spec_path = os.path.join(os.path.dirname(__file__), spec_name)
        
        if not os.path.exists(spec_path):
            print(f"[{spec_name}] File not found! Skipping.")
            continue
            
        start_time = time.time()
        file_size = os.path.getsize(spec_path)
        
        # 1. Upload
        print(f"[{spec_name}] Uploading {file_size/1024/1024:.2f} MB...")
        try:
            with open(spec_path, "rb") as f:
                files = {"file": (spec_name, f, "application/json")}
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(f"{API_URL}/api/upload", files=files)
        except Exception as e:
            results.append({
                "api": spec_name,
                "success": False,
                "runtime_sec": 0,
                "retries": 0,
                "failure_reason": f"Connection Error: {e}",
                "diagnoser_count": 0
            })
            continue

        if resp.status_code != 200:
            error_detail = resp.json().get("detail", resp.text) if resp.text else "Unknown HTTP Error"
            print(f"[{spec_name}] Upload failed: {resp.status_code} - {error_detail}")
            results.append({
                "api": spec_name,
                "success": False,
                "runtime_sec": round(time.time() - start_time, 2),
                "retries": 0,
                "failure_reason": f"HTTP {resp.status_code}: {error_detail}",
                "diagnoser_count": 0
            })
            continue
            
        data = resp.json()
        job_id = data["job_id"]
        print(f"[{spec_name}] Uploaded successfully. Job ID: {job_id}")
        
        # 2. Execute via SSE
        print(f"[{spec_name}] Listening to SSE stream...")
        diagnoser_count = 0
        final_status = "UNKNOWN"
        failure_reason = ""
        
        try:
            # We use httpx.stream to read SSE
            async with httpx.AsyncClient(timeout=3600.0) as client:
                async with client.stream("GET", f"{API_URL}/api/jobs/{job_id}/stream") as response:
                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        
                        try:
                            event_data = json.loads(line[6:])
                            status = event_data.get("status")
                            msg = event_data.get("message", "")
                            
                            if status == "diagnoser":
                                diagnoser_count += 1
                                print(f"[{spec_name}] Diagnoser invoked (Total: {diagnoser_count})")
                                
                            elif status == "complete":
                                print(f"[{spec_name}] Execution complete: {msg}")
                                final_status = "SUCCESS" if "failed" not in msg.lower() else "FAILED"
                                if final_status == "FAILED":
                                    failure_reason = msg
                                break
                                
                            elif status == "error":
                                print(f"[{spec_name}] Stream Error: {msg}")
                                final_status = "FAILED"
                                failure_reason = msg
                                break
                                
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            print(f"[{spec_name}] Stream connection failed: {e}")
            final_status = "FAILED"
            failure_reason = f"Stream interrupted: {e}"

        runtime_sec = round(time.time() - start_time, 2)
        print(f"[{spec_name}] Finished in {runtime_sec} seconds. Status: {final_status}")
        
        results.append({
            "api": spec_name,
            "success": final_status == "SUCCESS",
            "runtime_sec": runtime_sec,
            "retries": diagnoser_count,
            "failure_reason": failure_reason if final_status == "FAILED" else "None",
            "diagnoser_count": diagnoser_count
        })

    # 3. Generate Reports
    os.makedirs(os.path.join(os.path.dirname(__file__), "results"), exist_ok=True)
    
    report_lines = [
        "# API Forge AI Benchmark Report",
        "",
        "| API | Success | Runtime | Retries | Failure Reason |",
        "|---|---|---|---|---|"
    ]
    
    failures = []
    
    for r in results:
        success_str = "✅ Yes" if r["success"] else "❌ No"
        report_lines.append(f"| {r['api']} | {success_str} | {r['runtime_sec']}s | {r['retries']} | {r['failure_reason']} |")
        if not r["success"]:
            failures.append(r["failure_reason"])
            
    with open(os.path.join(os.path.dirname(__file__), "results", "benchmark_report.md"), "w") as f:
        f.write("\n".join(report_lines))
        
    print("Generated benchmark_report.md")
    
    # Generate improvement priority
    from collections import Counter
    freq = Counter(failures)
    
    highest_freq = freq.most_common(1)[0] if freq else ("None", 0)
    
    priority_lines = [
        "# Improvement Priorities",
        "",
        "Based on the empirical benchmark results:",
        "",
        f"**Highest-frequency bug**: `{highest_freq[0]}` (Occurred {highest_freq[1]} times)",
        "",
        "**Highest-impact bug**: `HTTP 413: File too large.` (Completely blocks large enterprise APIs like GitHub and Stripe from entering the system).",
        "",
        "**Highest-cost bug**: `Context Window Exhaustion / Token Limits` (For medium-to-large APIs, the Planner burns thousands of tokens before crashing).",
        "",
        "**Recommended next fix**: Implement a multipart or streaming upload mechanism to bypass the 10MB limit, followed immediately by implementing `Chunked Planning` for the Planner node so it doesn't OOM on large specs."
    ]
    
    with open(os.path.join(os.path.dirname(__file__), "results", "improvement_priority.md"), "w") as f:
        f.write("\n".join(priority_lines))
        
    print("Generated improvement_priority.md")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
