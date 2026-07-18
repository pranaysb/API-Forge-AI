# API Forge AI: Interview-Safe Description

**Goal:** Describe the project with maximum honesty, using only benchmark-backed claims.

### Elevator Pitch
"API Forge AI is an experimental, agentic workflow engine built with LangGraph, designed to explore automated Python SDK generation from OpenAPI specifications."

### System Capabilities & Current State
"The system successfully orchestrates a multi-agent state machine consisting of a Planner, Coder, Executor, and Diagnoser. In its current state, it can successfully ingest small-to-medium OpenAPI schemas, extract endpoint definitions, and leverage LLMs to generate initial `client.py` and Pydantic `models.py` source files within an isolated sandbox environment."

### Architectural Safeguards
"To prevent broken code from reaching the user, API Forge AI employs a strict validation pipeline. We built an Executor node and a custom Test Linter that evaluates the generated SDK. Currently, this strict quality gate successfully catches LLM hallucinations—specifically preventing the system from using invalid `httpx.MockTransport` syntax."

### Known Limitations (Honest Disclosures)
"Because we prioritize correctness over shipping broken code, the system currently has a 0% end-to-end success rate on our benchmarks. The pipeline intentionally halts because the LLM struggles to generate valid mock test handlers, and our Self-Healing Diagnoser node currently loops without resolving the specific `MISSING_MOCK` syntax error. Furthermore, we are actively working on 'Chunked Planning' to support large enterprise APIs (like Stripe or GitHub), which currently exceed standard LLM context window limits."

### What I Built (The Developer's Achievement)
"While the LLM output reliability remains a challenge, the underlying infrastructure I built—the LangGraph orchestration, the isolated code execution sandbox, the Server-Sent Events (SSE) streaming architecture, and the strict validation gates—is fully functional and actively prevents hallucinated SDKs from being packaged."
