# Deployment Compatibility & Security Audit

**Date**: 2026-06-14
**Status**: **NOT DEPLOYABLE IN CURRENT STATE** ❌

This audit examines the current state of the API Forge AI repository for compatibility with Render Free (Backend), Supabase (Database), and Vercel (Frontend). 

---

## 1. Infrastructure & Database Compatibility

**Current State**: 
The application strictly connects to PostgreSQL, but relies on a hardcoded local connection string.
- `backend/app/core/config.py` lines 9-10:
  ```python
  SQLALCHEMY_DATABASE_URI: str = "postgresql://pranaysb@localhost:5432/apiforge"
  ```
- `backend/app/core/db.py`: Used exclusively across the app (unlike the unused `database.py`). It does not use `check_same_thread=False`, which correctly avoids SQLite thread-sharing bugs, but strictly enforces Postgres.

**Render/Supabase Impact**: 
Requires immediately replacing the hardcoded string with `os.getenv("DATABASE_URL")`. Supabase will work flawlessly via `db.py`, but the LangGraph Postgres checkpointing pool (`backend/app/api/stream.py` line 22) is initialized with `max_size=20`. Supabase Free tier allows max 15 direct connections or requires the IPv4 Transaction Pooler (port 6543).

**External Queues**:
- None. `config.py` defines `REDIS_URL: str = ""` but it is unused. There is no Celery or RabbitMQ.

---

## 2. Job Execution Architecture & Render Timeout Risk

**Current State**:
Integration Jobs are NOT executed in the background. They are synchronously tied to the Server-Sent Events (SSE) HTTP request lifecycle.
- `backend/app/api/upload.py` creates the job and marks it `PENDING`.
- `backend/app/api/stream.py` (lines 27-245) executes the LangGraph workflow (`stream_generator = graph.stream(initial_state, config)`) inside the `real_event_generator` async function.

**Render Timeout Risks (CRITICAL)**:
Render has a strict **100-second idle timeout** for HTTP requests. If an LLM node (e.g., `diagnoser_node` doing heavy reasoning on a large payload) takes more than 100 seconds to yield an SSE byte (`yield f"data: ..."` in `stream.py`), Render will terminate the connection with a 502 Bad Gateway. 

**Frontend Refresh Impact**:
Because execution runs inside the SSE stream generator, **refreshing the frontend terminates the running job node**. 
- *Evidence*: If the frontend disconnects, FastAPI raises `asyncio.CancelledError`. The `stream.py` generator drops out, hitting the `finally: pass` block (line 244), and the execution dies instantly.
- *Recovery*: It can resume from the last LangGraph Postgres Checkpoint if the user re-opens the page (`Action: RESUMING from checkpoint` on line 88), but any in-progress LLM request will be permanently lost and billed.

---

## 3. SDK Generation Pipeline (Disk I/O)

**Current State**:
Highly compatible with Render's ephemeral storage limits.
- `backend/app/services/sdk_builder.py` (lines 14-65) writes the generated SDK ZIP entirely to memory using `io.BytesIO()`.
- `backend/app/services/executor/local.py` (lines 43-70) writes test scripts and Python modules to standard `tempfile.mkdtemp()` and `tempfile.NamedTemporaryFile()` directories, securely executing and cleaning them up (`shutil.rmtree`). 
- **Verdict**: No persistent disk requirements. Render Free ephemeral `/tmp` is sufficient.

---

## 4. Frontend Vercel Deployment

**Current State**:
**NOT DEPLOYABLE**. The frontend contains hardcoded `localhost` URLs in multiple production components.
- `frontend/src/app/page.tsx` line 22: `fetch("http://localhost:8000/api/upload")`
- `frontend/src/app/dashboard/page.tsx` lines 26, 37.
- `frontend/src/app/jobs/[id]/page.tsx` lines 30, 41, 56, 106.
- `frontend/src/components/AgentTerminal.tsx` lines 17, 76.

**Vercel Impact**:
Vercel builds will succeed, but the production UI will attempt to ping the user's local `localhost:8000` from their browser and completely fail to reach the Render backend.

---

## 5. Environment Variables & Security

**Security Check**: 
No API keys are committed. However, `backend/app/api/stream.py` (line 53) has a hardcoded localhost fallback:
```python
raw_url = parsed_json.get("servers", [{"url": "http://127.0.0.1:8001"}])[0].get("url", "http://127.0.0.1:8001")
```

**Required Environment Variables (.env.example)**:
```env
# Backend Required
DATABASE_URL=postgresql://postgres.xxxxx:password@aws-0-region.pooler.supabase.com:6543/postgres
GROQ_API_KEY=gsk_...

# Backend Optional (if multi-key failover is used)
GROQ_API_KEY_1=...
GROQ_API_KEY_2=...
OPENAI_API_KEY=...
E2B_API_KEY=...

# Frontend Required
NEXT_PUBLIC_API_URL=https://your-backend-app.onrender.com
```

---

## 6. Final Deployment Verdict: NO ❌

This project **cannot** be deployed immediately on Render Free + Supabase + Vercel. 

### Blocking Issues (Priority Order):
1. **Frontend Localhost Hardcoding**: All `fetch` and `EventSource` calls in `frontend/src/` must be replaced with a `NEXT_PUBLIC_API_URL` environment variable.
2. **Backend Postgres Hardcoding**: `SQLALCHEMY_DATABASE_URI` in `backend/app/core/config.py` must use `os.getenv("DATABASE_URL")`.
3. **Database Connection Pooling**: Decrease the Postgres pool `max_size=20` in `stream.py` to `10` or use Supabase's IPv4 Transaction Pooler, or the Supabase DB will reject connections from the checkpointer.
4. **CORS Configuration**: `backend/app/main.py` hardcodes `http://localhost:3000`. You must add the Vercel production URL to `allow_origins`.

### Architectural Risks (Post-Deployment):
- **Render HTTP 100s Timeout**: Because execution is bound to the SSE stream, a slow LLM response > 100s will cause Render to forcefully kill the connection, requiring the user to refresh the page to restart from the checkpoint. True background workers (Celery/Redis) would fix this, but the current checkpointing architecture acts as a decent failsafe mechanism.
