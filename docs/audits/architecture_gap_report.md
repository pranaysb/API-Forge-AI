# Architecture Gap Report

This report analyzes the current LangGraph architecture of API Forge AI, evaluating the reliability mechanisms, solved/unsolved failure modes, and remaining risks for each execution node.

---

## Node Analysis

### 1. Planner
* **Current reliability mechanisms**: Uses `ReliabilityManager` with `with_structured_output`, enforcing a strict Pydantic schema for `client.py`, `models.py`, and `__init__.py`. Includes up to 3 local parsing retries and cross-model/key rotation failover.
* **Failure modes that are now solved**: Truncated/unparsable JSON outputs are caught and retried automatically.
* **Remaining unsolved failure modes**: Context window exhaustion. Massive OpenAPI specs (e.g., >1MB) will exceed token limits or cause the LLM to skip/truncate endpoints during the initial generation.
* **Dependence**: **Prompt-following** (relies entirely on the LLM to map the OpenAPI spec to Python code accurately).
* **Can malformed LLM output break execution?**: **No**. The Pydantic structured output parser prevents malformed JSON from advancing. If it fails completely after retries, execution cleanly halts.
* **Are infinite loops possible?**: **No**. It executes once at `START`.
* **Confidence Score**: **85/100**

### 2. SDK Validator
* **Current reliability mechanisms**: Uses Python's `ast` module to statically verify the syntax of the generated SDK and ensures `__init__.py` exports match the symbols defined in `client.py` and `models.py`.
* **Failure modes that are now solved**: Catches hallucinated `__init__.py` exports and basic syntax errors before hitting the sandbox.
* **Remaining unsolved failure modes**: Does not verify type hinting accuracy or runtime logical flaws in the generated client.
* **Dependence**: **Deterministic validation** (Python AST parsing).
* **Can malformed LLM output break execution?**: **No**. It strictly analyzes strings via AST.
* **Are infinite loops possible?**: **No**. A failure here permanently fails the generation (`route_after_sdk_validator` routes to `END` on error).
* **Confidence Score**: **95/100**

### 3. Schema Validator
* **Current reliability mechanisms**: Dual-mode execution (Real vs Synthetic). Only runs live queries on safe methods (`GET`, `HEAD`, `OPTIONS`) when auth is provided. Otherwise, forces synthetic generation using `httpx.MockTransport`.
* **Failure modes that are now solved**: Destructive production mutations (e.g., `DELETE` requests) during the validation phase are completely eliminated.
* **Remaining unsolved failure modes**: "Echo chamber validation." During synthetic validation, the LLM generates the dummy payload based on the OpenAPI schema. If the schema is flawed, the payload will mirror the flaw, passing validation without proving real-world API compatibility.
* **Dependence**: **Hybrid**. Depends on **prompt-following** to write the synthetic payload, but **deterministic validation** (Pydantic `model_validate()`) executes it.
* **Can malformed LLM output break execution?**: **No**. If the validator script is malformed, it fails execution and routes to the Diagnoser.
* **Are infinite loops possible?**: **Yes (Bounded)**. It can cycle with the Diagnoser, but is guarded by the global endpoint `attempts >= 5` limit.
* **Confidence Score**: **80/100**

### 4. Coder
* **Current reliability mechanisms**: Strict system prompts banning `pytest` and enforcing `httpx.MockTransport(handler)`. Reads the actual `client.py` and `models.py` state directly from memory context.
* **Failure modes that are now solved**: Hallucinated test frameworks. The prompt strictness combined with the new linter heavily suppresses invalid testing paradigms.
* **Remaining unsolved failure modes**: Interface hallucinations. The LLM may still invent methods (e.g., `client.get_user_by_id()` instead of `client.get_user()`) if it loses attention on the `client.py` context.
* **Dependence**: **Prompt-following**.
* **Can malformed LLM output break execution?**: **No**. Caught by the linter/executor.
* **Are infinite loops possible?**: **Yes (Bounded)**. Loops with Diagnoser up to 5 attempts.
* **Confidence Score**: **75/100**

### 5. Test Linter
* **Current reliability mechanisms**: Python `ast` parsing to strictly block the import of `pytest` and mandate the presence of `MockTransport` in the generated test script.
* **Failure modes that are now solved**: Ensures test isolation by blocking live network execution scripts and unsupported test runners from reaching the Sandbox.
* **Remaining unsolved failure modes**: The linter is naive; it checks for the *presence* of `MockTransport` but doesn't verify if it's actually mounted to the `httpx.Client` correctly.
* **Dependence**: **Deterministic validation**.
* **Can malformed LLM output break execution?**: **No**.
* **Are infinite loops possible?**: **Yes (Bounded)**. It routes back to Diagnoser on failure.
* **Confidence Score**: **90/100**

### 6. Executor
* **Current reliability mechanisms**: Sandboxed execution environment (Local or E2B) that captures standard output and standard error.
* **Failure modes that are now solved**: Host machine contamination.
* **Remaining unsolved failure modes**: Infinite `while True` loops in the generated test script could cause sandbox timeouts if strict execution limits aren't enforced at the OS level.
* **Dependence**: **Deterministic validation**.
* **Can malformed LLM output break execution?**: **No**. Sandbox absorbs the crash.
* **Are infinite loops possible?**: **No** (at the graph level, it advances to Diagnoser on failure).
* **Confidence Score**: **95/100**

### 7. Diagnoser
* **Current reliability mechanisms**: Patch-based mutation generation. Outputs precise `search_string` and `replace_string` patches instead of rewriting entire files.
* **Failure modes that are now solved**: Truncation of large SDK files during rewriting, and excessive token usage during the debugging loop.
* **Remaining unsolved failure modes**: Patch collision/misses. If the LLM generates a `search_string` that doesn't exactly match the file (due to whitespace or indentation differences), the patch will silently fail to apply.
* **Dependence**: **Prompt-following**.
* **Can malformed LLM output break execution?**: **No**. Unmatched patches emit a warning and don't crash the Python runner.
* **Are infinite loops possible?**: **No**. Explicitly guarded by `if attempts >= 5: return FAILED_PERMANENTLY`.
* **Confidence Score**: **70/100**

---

## Global System Risks

### 🚨 Single Highest-Risk Failure Mode Remaining
**Diagnoser Patch Misapplication.** 
Because the Diagnoser relies on exact string matching (`search_string in sdk_files[fname]`), any slight hallucination of indentation, trailing commas, or whitespace by the LLM will cause the patch to fail. When patches fail to apply, the exact same broken code is sent back to the Executor, causing the Diagnoser to burn through its 5 retry attempts pointlessly. *Recommendation: Implement a fuzzy-matching patch algorithm or use Unified Diff format with a robust diff-applier.*

### 🧠 Single Most Likely Source of Hallucinations
**The Coder Node Inferring SDK Interfaces.**
Despite being fed the actual `client.py` code, LLMs are heavily biased by their pre-training data. When asked to test a `/users/{id}` endpoint, the LLM is highly likely to default to `client.get_user()` rather than reading the generated code to discover the method is actually named `client.get_users_by_id()`. 

### 📈 Single Biggest Scalability Bottleneck
**The Planner Node processing Large OpenAPI Specs.**
The Planner currently attempts to read the entire OpenAPI specification and generate the complete `client.py` and `models.py` in a single pass. For enterprise APIs (e.g., Stripe or AWS with hundreds of endpoints and massive component schemas), this will instantly exceed the output context window of the LLM. *Recommendation: Implement a Chunked Planning strategy where models and endpoints are generated iteratively or batched by tag/resource.*
