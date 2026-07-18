# Root-Cause Audit Report: SDK Pipeline Hardening

This document summarizes the sweeping changes applied to the SDK Generation Pipeline to eliminate catastrophic runtime discoveries and ensure structural integrity before test execution.

## 1. Files Modified
- `backend/app/agents/nodes.py`: Major overhaul of Prompts, Output Schemas, and introduced two new nodes (`sdk_validator_node`, `schema_validator_node`).
- `backend/app/agents/graph.py`: Modified the LangGraph definition to route through new validation stages.
- `backend/app/api/stream.py`: Upgraded the final integrity quality gate to execute real API test scripts and rigorously check Pydantic model validity.

## 2. New Validation Stages Added

### Pre-Execution Validation (`sdk_validator_node`)
**Position in Graph:** Immediately after `planner`.
**Behavior:**
- Runs `ast.parse()` and `compile()` on all generated Python files (`client.py`, `models.py`, `__init__.py`).
- Verifies that all symbols declared in `__all__` or imported via `from .models import ...` actually exist in the compiled source code.
- **Fail-Fast Action:** If a `SyntaxError` or import mismatch is detected, the entire job is immediately flagged as `FAILED_PERMANENTLY`, preventing the agent loop from fighting over irrecoverable foundational errors.

### Schema Validation (`schema_validator_node`)
**Position in Graph:** Between `sdk_validator_node` and `coder_node`.
**Behavior:**
- Instructs the LLM to write a targeted raw `httpx` script for each endpoint.
- Fetches real data payloads directly from the target API.
- Instantiates the specific Pydantic model (e.g. `User.model_validate(payload)`).
- **Fail-Fast Action:** If Pydantic throws a `ValidationError` (e.g. due to missing nested fields or bad type hints), the graph short-circuits directly to the `diagnoser_node` for immediate repair. No test scripts are written for broken schemas.

### Test Script AST Validation
**Position in Graph:** Inside `coder_node` before execution.
**Behavior:**
- Parses the generated test script using Python AST.
- Enforces the presence of `import httpx` to prevent spurious `NameError: name 'httpx' is not defined` loops.

### Final SDK Quality Gate
**Position in Graph:** `stream.py` after the entire LangGraph workflow succeeds.
**Behavior:**
- Dynamically imports `apiforge_sdk` and instantiates the `ApiClient`.
- Iterates over the client's callable methods, executes one against the real API, and validates the strict return type.
- Ensures the return type is a valid `pydantic.BaseModel` and explicitly NOT an `httpx.Response`.
- Aborts artifact ZIP generation if this gate fails.

## 3. Example Failures Now Caught Before Execution
- **Missing Models / Missing Exports:** Caught instantly by the AST checker in `sdk_validator_node`. 
- **Dict Instead of Nested Object:** Caught instantly by `schema_validator_node` when Pydantic tries to map a complex JSON payload onto `address: dict`, triggering a repair loop to construct nested BaseModels.
- **`httpx.Response` Return Type:** Banned by Planner prompt structure and tested rigorously by the Coder. If it slips through, the Final Quality Gate will reject the artifact entirely.
- **Syntax Errors in generated tests:** Caught inside `coder_node` before the Executor can waste time running it.

## 4. Remaining Weaknesses in the Pipeline
- **API Sandbox Limitations:** The schema validator requires outbound internet access. If the target API is behind auth or firewalled from the Agentic framework, the schema validation will fail and the job could halt.
- **Model Overfitting:** If the target API returns an optional field that happens to be present in the sample payload fetched by `schema_validator`, the Pydantic model might enforce it as mandatory, causing intermittent failures on different data.
- **LLM Context Limits:** Enforcing fully nested sub-models requires longer context windows. Very complex OpenAPI specs (e.g. nested deeply by 5+ layers) might hit token limits or cause the Planner to drop attributes.

## 5. JSONPlaceholder Readiness
The generated SDK for JSONPlaceholder should now pass the spec with minimal to **no runtime repair loops**. 
The Planner has been constrained so heavily towards Pydantic v2 conventions and relative imports that the initial generation should be 90-100% syntactically valid. The introduction of `Address` and `Company` models directly addresses the only remaining flaw in the Planner's previous generation logic.
