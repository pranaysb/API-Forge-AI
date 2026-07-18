# API Forge AI: Truth Audit

## Executive Summary
This audit is based on empirical end-to-end benchmarks run against small and medium OpenAPI specifications (`petstore.json` and `jsonplaceholder.json`). Large specifications (`github.json`, `stripe.json`) were previously proven to instantly crash the system due to LLM context window exhaustion.

The benchmark results for small APIs yielded a **0% end-to-end success rate**.

---

## Claim Verification

1. **Autonomous SDK Generation**: `FALSE`
   While the system generates Python source code, it fails 100% of the time to produce a working, verified SDK due to test execution failures.
2. **Self-Healing Graph**: `FALSE`
   The Diagnoser node is invoked repeatedly (22 times for Petstore, 15 times for JSONPlaceholder), but fails entirely to fix the `MISSING_MOCK` linter errors. It blindly retries until it hits the hard retry limit and marks endpoints as `FAILED_PERMANENTLY`.
3. **Automated Mocking**: `FALSE`
   The LLM consistently hallucinates the `httpx.MockTransport` syntax (using `responses=[...]` instead of a handler function). This breaks the validation step entirely.
4. **Installable Package Generation**: `FALSE`
   Because the execution pipeline forcibly aborts when any endpoint fails testing, the workflow never reaches the final SDK packaging phase. No `pyproject.toml` or installable package is ever generated.
5. **Production-Ready SDK Generation**: `FALSE`
   The system cannot handle enterprise-scale APIs due to 400 Bad Request token limits, and cannot handle small APIs due to hallucinated test syntax.

---

## A) What definitely works
* **OpenAPI Parsing (Small Specs)**: Successfully ingests and extracts endpoints from small specifications (< 1MB).
* **Initial Code Generation**: The Planner and Coder nodes successfully write the initial `client.py` and `models.py` to the sandbox.
* **Execution Sandbox & SSE**: The system correctly spins up an execution environment and accurately streams Server-Sent Events (SSE) back to the client.
* **Test Linter (Quality Gate)**: The linter correctly identifies that the LLM is hallucinating mock network calls and blocks the bad code.

## B) What sometimes works
* Nothing end-to-end.

## C) What is unproven
* **Installable Package Generation**: The codebase contains logic for zipping and packaging, but it is unreachable dead code in production because the tests never pass.
* **Schema Validation Reliability**: Because execution is permanently blocked by test mocking failures, we cannot verify if the generated Pydantic schemas actually align with real-world payloads.

## D) What should be removed from README immediately
* *"generates a robust Python ApiClient and Pydantic V2 models"* -> Change to "generates experimental..."
* *"Self-Healing Graph ... until all tests pass"* -> The graph loops, but does not successfully heal.
* *"Automated Mocking ... to validate endpoints"* -> This is the exact feature breaking the pipeline.
* *"Final SDK output is bundled with pyproject.toml and ready for pip install ."* -> Remove until the packaging step is actually reachable.

## E) What can safely be claimed in interviews
* "API Forge AI is an experimental LangGraph state-machine that orchestrates multiple LLMs to attempt SDK generation."
* "The system features a strict Test Linter and Executor sandbox that prevents hallucinated, broken code from being packaged."
* "We are currently working on resolving context-window limits for large OpenAPI specs and improving the Diagnoser's ability to fix hallucinated `httpx` mock transports."
