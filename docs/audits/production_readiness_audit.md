# API Forge AI: Production Readiness Audit

## 1. OpenAPI Coverage

| Issue | Severity | Location | Description & Reproduction | Recommendation |
| :--- | :--- | :--- | :--- | :--- |
| **Missing Authentication Handling** | High | `app/agents/nodes.py` (`planner_node` prompt) | The prompt does not instruct the Planner to parse Security schemes (Bearer, API Key, Basic) or generate `ApiClient` methods to accept and inject tokens. SDKs for protected APIs will fail with 401s. | Update the planner prompt to explicitly mandate authentication parameters in the `ApiClient` constructor and `httpx.Client(headers=...)`. |
| **Missing Pagination Support** | Medium | `app/agents/nodes.py` (`planner_node` prompt) | Array-returning endpoints do not generate paginated iterators. | Add instructions to detect `limit`/`offset` or `page` cursors and generate generator-based methods. |
| **Complex Schema Fallbacks** | Low | `app/services/openapi_parser.py` | `parse_spec_content` does not resolve `$ref` pointers before passing the spec to the LLM. If the spec relies heavily on external or deeply nested `$refs`, the LLM may hallucinate schemas. | Implement a pre-processing step using `prance` or `openapi-schema-validator` to bundle/dereference the spec before feeding it to the Planner. |

## 2. SDK Correctness

| Issue | Severity | Location | Description & Reproduction | Recommendation |
| :--- | :--- | :--- | :--- | :--- |
| **Weak Array Validation** | Medium | `app/agents/nodes.py` (`coder_node` prompt) | The `coder_node` prompt instructs the LLM to write assertions. If an endpoint returns an empty array `[]`, the test will trivially pass without validating the inner Pydantic model structure. | Enforce that the test script seeds the API or handles empty lists strictly (e.g., failing if validation cannot be proven). |
| **Missing Request Body Strictness** | Medium | `app/agents/nodes.py` (`planner_node` prompt) | The prompt enforces `extra='forbid'` on response models but doesn't explicitly mandate strictness on outgoing request models. | Add instructions to enforce type validation on all `POST`/`PUT` payload models. |

## 3. Agent Workflow

| Issue | Severity | Location | Description & Reproduction | Recommendation |
| :--- | :--- | :--- | :--- | :--- |
| **Schema Validator Mutation Failures** | High | `app/agents/nodes.py` (`schema_validator_node`) | The validator relies on an LLM to generate a script using `httpx` to hit the real API. If the endpoint is a `POST` requiring complex payloads, the LLM often generates a 400 Bad Request payload, causing a false positive validation failure. | Provide the `schema_validator` with access to a Faker library or instruct it to explicitly skip validation for destructive/state-mutating `POST`/`DELETE` endpoints. |
| **Executor False Successes** | Medium | `app/api/stream.py` (Final Quality Gate) | The integrity script skips endpoints requiring arguments and passes automatically. If an SDK *only* has `POST` endpoints, it effectively bypasses runtime integrity checks. | If no zero-argument methods exist, invoke `ast` or `inspect` to verify the presence of required models instead of skipping entirely. |

## 4. Artifact Quality

| Issue | Severity | Location | Description & Reproduction | Recommendation |
| :--- | :--- | :--- | :--- | :--- |
| **Missing Packaging Files** | High | `app/services/sdk_builder.py` | The artifact is just a `.zip` of raw Python files (`client.py`, `models.py`, `__init__.py`). It lacks `setup.py`, `pyproject.toml`, or `requirements.txt`. Users cannot pip install it. | Update `sdk_builder.py` to auto-generate a `pyproject.toml` containing `httpx` and `pydantic` dependencies. |

## 5. Reliability Layer

| Issue | Severity | Location | Description & Reproduction | Recommendation |
| :--- | :--- | :--- | :--- | :--- |
| **Silent Exception Bubbling** | Medium | `app/services/reliability.py` | Non-rate-limit exceptions (like API timeouts or JSON decoding errors from the provider) immediately raise out of the `ReliabilityManager` instead of retrying, causing immediate job failure. | Implement exponential backoff for 500/502/503/504 errors before raising exceptions. |

## 6. Deployment Readiness

| Issue | Severity | Location | Description & Reproduction | Recommendation |
| :--- | :--- | :--- | :--- | :--- |
| **No Database Migrations** | High | `app/core/db.py` / `models/` | The codebase likely relies on SQLAlchemy `metadata.create_all()`. Making schema changes in production will drop data or crash. | Initialize `alembic` and create an initial migration script. |
| **Unbounded File Uploads** | High | `app/api/upload.py` (`upload_spec`) | `file.read()` loads the entire file into memory without a size limit. A malicious user uploading a 5GB file will cause an OOM crash. | Implement a `SpooledTemporaryFile` limit and check file sizes before reading (e.g., max 10MB). |
| **Missing Rate Limiting** | High | `app/main.py` | Endpoints like `/api/upload` and `/api/jobs/{id}/stream` have no rate limiting. Generating SDKs is extremely expensive (LLM calls). | Add `slowapi` or Redis-based rate limiting per IP or user. |
| **Hardcoded CORS Origins** | Medium | `app/main.py` | CORS is hardcoded to `localhost:3000`. This will block frontend requests in staging/production environments. | Move CORS origins to `app.core.config.settings.CORS_ORIGINS` and load via `.env`. |
| **Missing Containerization** | High | Project Root | No `Dockerfile` or `docker-compose.yml` exists. | Add a standard FastAPI Dockerfile utilizing `gunicorn` with `uvicorn` workers. |
| **Unstructured Logging** | Low | Entire Codebase | Uses `print()` for critical events (e.g., `print(f"[KEY ROTATION]")`). Logs cannot be easily ingested by Datadog or ELK. | Replace `print()` with Python's `logging` module or `structlog` outputting JSON. |

---

## 7. Testing Matrix

Before deployment, execute integration jobs using the following specific OpenAPI specifications to prove the system works across the spectrum of API designs:

- [ ] **A. Simple GET endpoint:** Validates basic client generation and Pydantic response parsing.
- [ ] **B. Nested object endpoint:** Validates the Planner's ability to recursively extract nested JSON definitions into independent Pydantic models.
- [ ] **C. Array response endpoint:** Validates that methods return `List[Model]` instead of single objects, and that iterators work.
- [ ] **D. POST endpoint:** Validates request body model generation, payload passing (`json=...`), and zero-argument bypass logic.
- [ ] **E. Path parameter endpoint:** Validates that variables like `/users/{id}` are correctly transformed into Python method arguments (`def get_user(id: int)`).
- [ ] **F. Query parameter endpoint:** Validates handling of optional search parameters (`?limit=10&sort=desc`).
- [ ] **G. Mixed CRUD API:** A full standard spec (like Petstore) to ensure the execution loop scales up to 10+ endpoints without graph context limits crashing.
- [ ] **H. Authentication-protected API:** Validates header injection (Bearer tokens or API Keys) at the client instantiation level.
