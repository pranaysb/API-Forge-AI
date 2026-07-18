# Benchmark Suite Implementation Plan

This plan details the creation and execution of the benchmark suite using four real-world OpenAPI specifications, as requested.

## Proposed Steps

### 1. File Structure Setup
- Create `benchmarks/` and `benchmarks/results/` directories.
- Write a Python script to download the following specifications into `benchmarks/`:
  - `petstore.json` (Swagger)
  - `github.json` (GitHub REST API)
  - `discord.json` (Discord API)
  - `stripe.json` (Stripe API)

### 2. Benchmark Runner Implementation
I will create a comprehensive Python script (`benchmarks/run_benchmark.py`) that acts exactly like a user interacting with the platform:
- The script assumes the backend is running locally on `http://localhost:8000`.
- For each spec, it will attempt an HTTP `POST` to `/api/upload`.
- If upload succeeds, it will connect to `/api/jobs/{job_id}/stream` to trigger execution and consume Server-Sent Events (SSE).
- The script will track events to calculate runtime, diagnoser invocations (retries), and final success status.
- It will also query the database (`apiforge.db` via sqlite3) to extract node-level state deltas to ascertain Schema Validation and Test Generation success.
- If upload fails (e.g., 413 Request Entity Too Large, since the backend enforces a 10MB limit and Github/Stripe exceed this), it will record the HTTP error code as the failure reason.

### 3. Report Generation
After running all 4 specs, the script will output two files:
- `benchmarks/results/benchmark_report.md` (Table of API, Success, Runtime, Retries, Failure Reason)
- `benchmarks/results/improvement_priority.md` (Ranking bugs by impact, frequency, cost, and next recommendation based on empirical failures).

## User Review Required

> [!WARNING]
> **10MB Upload Limit:** The `upload.py` route explicitly rejects files larger than 10MB. The GitHub API (12.5MB) and Stripe API (7.8MB, sometimes larger depending on format) might hit this limit or memory limits. Since you instructed me to "Upload the spec exactly as a normal user would" and "Do not modify architecture", I will leave this limit in place. The benchmark report will naturally document these as `413 Payload Too Large` failures. Do you approve?

## Verification Plan
1. Ensure the backend is running via `poetry run uvicorn app.main:app --port 8000 &`.
2. Run `poetry run python benchmarks/run_benchmark.py`.
3. Verify the generated markdown artifacts.
