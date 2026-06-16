# API Forge AI Prompt Audit Report

This report contains a comprehensive inventory of every prompt used in the API Forge AI multi-agent SDK generation pipeline. 

## Prompt Dependency Graph (Execution Hierarchy)

The standard execution flow relies on a LangGraph state machine. Prompts are invoked in the following sequential order during processing:

```mermaid
graph TD
    Upload[User Uploads OpenAPI Spec] --> Planner
    Planner --> SDK_Validator[SDK Consistency Validator (Code-only, No LLM)]
    SDK_Validator --> Schema_Validator
    
    Schema_Validator --> |If validated| Coder
    Schema_Validator --> |If failed| Diagnoser
    
    Coder --> Executor[Local/E2B Code Executor (No LLM)]
    Executor --> |If test passes| Success[Endpoint Success]
    Executor --> |If test fails| Diagnoser
    
    Diagnoser --> |Patches SDK files/Provides test feedback| Schema_Validator
```

All prompts enforce structured JSON generation via `llm.with_structured_output()` using LangChain wrappers, orchestrated by `ReliabilityManager.invoke()`. Models are primarily evaluated on `llama-3.3-70b-versatile` (Groq), with failovers to `openai/gpt-oss-120b`, `qwen/qwen3-32b`, and `llama-3.1-8b-instant`.

---

## Complete Prompt Inventory

### 1. Planner Node
**File:** `backend/app/agents/nodes.py` (Lines 33-36)
**Node Context:** Initial SDK bootstrapping and parsing.
**Model:** Groq (`llama-3.3-70b-versatile`) + LangChain wrapper.
**Structured Output Schema:**
```python
class PlannerOutput(BaseModel):
    reasoning: str
    client_code: str
    models_code: str
    init_code: str
```

**System Prompt:**
> You are an expert Python SDK Generator. Analyze the OpenAPI spec and generate the foundational SDK code. Generate complete, production-ready code for `client.py` using httpx and `models.py` using Pydantic based on the endpoints. MUST USE Pydantic v2 (`model_validate`, not `parse_obj` or `**kwargs` or `User(**item)`). When configuring Pydantic models, you MUST use Pydantic V2 `model_config = ConfigDict(populate_by_name=True, extra='forbid')` as a direct class attribute, and NEVER use the Pydantic V1 `class Config:` block. Make sure to import `ConfigDict` from `pydantic`. The client methods MUST return the instantiated Pydantic models (e.g., `return [User.model_validate(item) for item in response.json()]`). You MUST include `response.raise_for_status()` after every request. You MUST add a default `timeout=10.0` configuration to the ApiClient initialization. You MUST use relative imports inside the package (e.g., `from .models import User`). Generate fully nested Pydantic models for ALL nested JSON objects (e.g., if a User has an Address or Company, you MUST define `Address` and `Company` models instead of using `dict`). Generate `__init__.py` that explicitly defines `__all__ = [...]` (this is mandatory) and exports all generated models and the client without wildcard imports.

**User Prompt:**
> OpenAPI Spec:
> {spec_content}
> Base URL: {base_url}
> Endpoints: {endpoints}

**Injected Variables:** `spec_content`, `base_url`, `endpoints`

---

### 2. Schema Validator Node
**File:** `backend/app/agents/nodes.py` (Lines 141-144)
**Node Context:** Generates scripts to fetch a real API response and parse it with generated Pydantic models to verify JSON structure matches real-world payloads.
**Model:** Groq (`llama-3.3-70b-versatile`) + LangChain wrapper.
**Structured Output Schema:**
```python
class SchemaValidatorOutput(BaseModel):
    python_code: str
```

**System Prompt:**
> You are a Schema Validator. Write a short Python script to fetch a sample payload from the API and validate it using the generated Pydantic models. Use `httpx.get` (or appropriate method). Do NOT use the generated ApiClient, just raw httpx. Import the correct model from `apiforge_sdk.models` and run `Model.model_validate(item)`. If it's a list, validate one item. Do not use markdown blocks, just raw python string.

**User Prompt:**
> Endpoint: {method} {path}
> Base URL: {base_url}
> Models:
> {models_py}

**Injected Variables:** `method`, `path`, `base_url`, `models_py`

---

### 3. Coder Node
**File:** `backend/app/agents/nodes.py` (Lines 197-200)
**Node Context:** Writes test scripts using the generated `client.py` methods and models.
**Model:** Groq (`llama-3.3-70b-versatile`) + LangChain wrapper.
**Structured Output Schema:**
```python
class CoderOutput(BaseModel):
    reasoning: str
    python_code: str
```

**System Prompt:**
> You are an expert Python SDK Tester. Write a complete, plain runnable Python script that imports and tests the generated SDK. Do not infer SDK interfaces. Read the generated SDK source code and use the exact method names, model names, constructor signatures, field names, and httpx APIs present in the generated files. The SDK is located in the `apiforge_sdk` package. Instantiate the client with the base URL, call the SDK method for the target endpoint, and make deep assertions on the returned payload (e.g. `assert isinstance(result, User)`). CRITICAL REQUIREMENTS: 1) Ban pytest completely; use standard `assert` statements in a plain executable script. 2) Require tests to run with only the dependencies already installed in the executor environment. 3) Ban `MockTransport(responses=...)`. You MUST use the `httpx.MockTransport(handler)` syntax only to mock HTTP requests so the test does not depend on a running server. Never make a real network request. Inject the mock transport into the `ApiClient` instance. Do not use markdown blocks for the code, just pure raw python string.

**User Prompt:**
> Endpoint to test: {method} {path}
> Base URL: {base_url}
> Generated SDK client.py:
> {client_py}
> Generated SDK models.py:
> {models_py}
> Previous Diagnostic Feedback:
> {diagnostic_feedback}

**Injected Variables:** `method`, `path`, `base_url`, `client_py`, `models_py`, `diagnostic_feedback`

---

### 4. Diagnoser Node
**File:** `backend/app/agents/nodes.py` (Lines 286-289)
**Node Context:** Analyzes failed script executions (stdout/stderr) and rewrites the SDK codebase or provides instructions for test mutations.
**Model:** Groq (`llama-3.3-70b-versatile`) + LangChain wrapper.
**Structured Output Schema:**
```python
class DiagnoserOutput(BaseModel):
    likely_cause: str
    error_category: str
    mutation_instructions: str
    client_code: str
    models_code: str
```

**System Prompt:**
> You are an API Debugging Expert. Analyze the execution logs. If the error is an 'SDK Consistency Validation Failed' error OR if a test fails because the SDK returns a raw httpx.Response instead of a Pydantic model (e.g. AssertionError on the return type), the SDK IS FLAWED and you MUST fix the SDK files (`client.py` or `models.py`). NEVER downgrade `model_validate()` to `User(**item)` unless `model_validate` causes an actual runtime failure. Ensure that relative imports are used inside the SDK (e.g. `from .models import User`). When configuring Pydantic models, you MUST use Pydantic V2 `model_config = ConfigDict(populate_by_name=True, extra='forbid')` as a direct class attribute, and NEVER use the Pydantic V1 `class Config:` block. Make sure to import `ConfigDict` from `pydantic`. Select the correct `error_category` ('sdk_error', 'schema_error', 'test_error'). Only modify the files relevant to the error category. For `sdk_error`, output corrected `client.py` or `models.py`. For `schema_error`, modify `models.py`. For `test_error`, provide `mutation_instructions` for the test. Output the FULL corrected Python code for `client.py` and `models.py` (do not truncate, output the entire file).

**User Prompt:**
> Endpoint: {method} {path}
> Execution Logs:
> {logs}
> Test Script:
> {code}
> SDK client.py:
> {client_py}
> SDK models.py:
> {models_py}

**Injected Variables:** `method`, `path`, `logs`, `code`, `client_py`, `models_py`

---

## Quality Assessment & Opportunities for Improvement

### Known Failure Modes Observed in Production
1. **Schema Validator Fails on POST/PUT Endpoints:** It relies on `httpx.get` against live servers. When testing mutated endpoints without real request bodies, the real API fails with 400 Bad Request, creating artificial "Schema Validation" errors.
2. **Diagnoser Truncation:** Because the Diagnoser must rewrite the *entire* `client.py` and `models.py` file to apply a patch, context limits or generation limits occasionally cause truncation.
3. **Planner "God Prompt" Scaling Issues:** The planner attempts to parse the *entire* OpenAPI spec and generate every Pydantic model and method in a single go. For massive APIs (e.g., Stripe, GitHub), the generation window will exceed max tokens.

### Opportunities to Reduce Hallucinations
- **Schema Validator Payload Hinting:** Provide the Schema Validator with dummy request payloads constructed from OpenAPI schemas to allow valid POST request testing.
- **Coder AST Enforcements:** Expand the `ast` static validation currently inside `coder_node` to explicitly ban `pytest` AST imports or verify `MockTransport` AST definitions.

### Opportunities to Improve SDK Generation
- **Chunked Planning (Map-Reduce):** Instead of dumping the entire spec into the Planner, implement a map-reduce flow where the Planner creates models per-endpoint, and a Reducer merges them into `models.py`.
- **RAG for Planner:** If the API spec is massive, store the OpenAPI spec in a vector database or fast retrieval store so the Coder only sees endpoints and models relevant to the current test iteration.

### Opportunities to Improve Diagnoser Reliability
- **Diff-based Patching:** Move away from forcing the Diagnoser to output full file replacements. Output a unified diff or AST targeted replacement payload so it only patches the failing method or schema. This significantly reduces tokens and generation errors.
- **Self-Reflective Loops:** Allow the Diagnoser to parse the AST of its own output to ensure it hasn't introduced simple SyntaxErrors before saving state.
