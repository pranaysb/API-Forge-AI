# Benchmark Validation Report

## Objective
Reconcile the recent `truth_audit.md` findings (0% end-to-end success rate) with historical production runs that successfully generated downloadable SDK artifacts. 

## Investigation Findings

We evaluated the benchmark methodology, the environment, and recent architectural changes to determine the root cause of the discrepancy.

### 1. Benchmark Methodology & Environment
* **Is the benchmark runner incorrect?** No. The `run_benchmark.py` script correctly listens to the SSE stream and accurately parses the final status.
* **Does the environment differ?** No. The benchmark runs against the exact same FastAPI endpoints and LangGraph state machine as the production frontend.
* **Are the success criteria too strict?** The success criteria accurately reflect the current pipeline logic: if `any_failed` is True (meaning any endpoint failed testing), the job is marked as `FAILED` and the zip generation is aborted.

### 2. The True Cause: Recent Code Regressions
The 0% success rate is an **accurate reflection of the current product behavior**, caused by recent architectural changes—specifically the implementation of the "Dual-Mode Validation Strategy" and the "Test Linter" (from Request #5).

#### Historical Runs (Why they worked):
Prior to the implementation of the Test Linter, the LLM-generated tests for small, unauthenticated APIs (like Petstore and JSONPlaceholder) would simply execute real network calls against the live APIs. Because these APIs are public and functional, the `httpx` requests succeeded. The Executor marked the endpoints as `SUCCESS`, the integrity check passed, and the SDK zip was successfully generated.

#### Current Runs (Why they fail):
1. **Overly Strict Linter:** The newly added `test_linter_node` (in `backend/app/agents/nodes.py`) introduced a blanket rule that unconditionally blocks any test script lacking the `MockTransport` AST node, emitting the `MISSING_MOCK` error.
2. **Broken Dual-Mode Validation:** Although the prompt asked for "Mode 1: Real API Validation" for GET/HEAD/OPTIONS endpoints, the Python linter logic does not respect this. It strictly enforces synthetic mocking for *everything*.
3. **Hallucination Loop:** Because real network calls are blocked by the linter, the LLM is forced to use `httpx.MockTransport`. However, the LLM consistently hallucinates the usage (e.g., `MockTransport(responses=[...])`). This causes either the Linter or the Executor to reject the code, sending it to the Diagnoser. The Diagnoser fails to fix the hallucination, loops repeatedly, and eventually marks the endpoint as `FAILED_PERMANENTLY`.

## Conclusion
The 0% success rate reported in the Truth Audit is **correct** and not a methodology flaw. 

The historical success was heavily reliant on the system's ability to make real, live network requests. By introducing strict, mandatory synthetic validation (mocking) to protect production systems, we exposed a critical capability gap: the LLM's inability to correctly write `httpx` mock handlers. The recent code changes transformed successful real-world executions into failing synthetic executions.
