# SDK Packaging Failure Report

## Investigation Summary
During the benchmark run for large OpenAPI specifications (Discord and Stripe), the execution rapidly failed with `ModuleNotFoundError: No module named 'apiforge_sdk.client'`. 

By tracing the execution path from the Planner through to the Executor Sandbox, the root cause has been identified as a swallowed exception in the `planner_node` combined with unconditional post-graph validation logic.

## Packaging Flow Analysis

### 1. Was `client.py` generated?
**No.** The `planner_node` never generated `client.py` or any other SDK files. 

### 2. Was `__init__.py` generated?
**No.** The entire `sdk_files` dictionary returned by the `planner_node` was empty.

### 3. Was `apiforge_sdk` copied into the executor workspace?
**Yes, but it was empty.** The `LocalExecutor.execute_sdk_test()` method always calls `os.makedirs(os.path.join(temp_dir, "apiforge_sdk"))`. It then loops over the `sdk_files` dictionary to write files. Since the dictionary was empty, no files were written into the directory.

### 4. What exact files exist inside the executor before test execution?
Only two files/directories existed in the sandbox:
1. `apiforge_sdk/` (An empty directory)
2. `test_script.py` (The hardcoded script from the Final SDK Quality Gate in `stream.py`)

### 5. Why import resolution fails
The `ModuleNotFoundError` is a symptom of a failure earlier in the pipeline:
1. **Planner Exception:** The `planner_node` attempts to pass the massive Discord (1.1MB) and Stripe (7.4MB) specs to the LLM. This triggers an exception in `ReliabilityManager.invoke` (likely a context window/token limit exhaustion).
2. **Error State:** `planner_node` catches the exception and returns `{"errors": ["Planner error: ..."], "sdk_files": {}}`.
3. **Graph Abort:** `sdk_validator_node` runs, finds no syntax errors (since there are no files), and the conditional edge `route_after_sdk_validator` checks `state.get("errors")`. Seeing the planner error, it routes the graph directly to `end`.
4. **Unconditional Quality Gate:** After the LangGraph stream finishes, `stream.py` unconditionally runs the "Final SDK Quality Gate" using `executor.execute_sdk_test()`.
5. **Masking the True Error:** Because the endpoints array was untouched (no endpoints were executed), `any_failed` evaluates to `False`. The test script immediately throws a `ModuleNotFoundError`, and `stream.py` emits the `Integrity error` over SSE instead of surfacing the underlying Planner token exhaustion error.

## Root Cause
The root cause is that the `planner_node` gracefully catches LLM exceptions and populates `state["errors"]`, effectively skipping graph execution. However, `stream.py` unconditionally runs the Final SDK Quality Gate test script against the (empty) SDK state without first checking if the graph aborted early due to fatal errors. This masks the true `Planner error` and surfaces an `Integrity error: ModuleNotFoundError` to the client instead.
