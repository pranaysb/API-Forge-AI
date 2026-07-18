# Validation Policy Audit

## Overview
Recent benchmark runs confirmed a 0% success rate caused directly by the strict enforcement of `httpx.MockTransport` across all endpoints. Historical runs succeeded because they executed real network requests against public APIs. This audit evaluates the architectural tradeoffs between synthetic mocking and real execution, and proposes a policy that maximizes honesty and pass rates while minimizing LLM hallucinations.

---

## 1. Public GET Endpoints (No Side Effects)

**Is real network validation actually safer and more reliable than synthetic mocking?**
**Yes.** From a correctness standpoint, real network validation is significantly superior. When an LLM writes a synthetic mock, it tests the generated Pydantic models against *its own hallucinated assumptions* of what the data looks like. By executing a real `GET` request, the generated SDK is validated against the **true production data structures**. Additionally, as our benchmarks prove, LLMs are reliable at writing standard HTTP requests but highly unreliable at writing complex mock handlers. Allowing real requests eliminates the hallucination loop.

**What risks remain?**
* **Flakiness & Rate Limits:** Public APIs may rate-limit the test runner, resulting in flaky pipeline failures (e.g., HTTP 429 Too Many Requests).
* **Network Latency/Timeouts:** Real calls introduce external network dependencies, meaning the validation phase takes longer and is vulnerable to transient internet issues.
* **Undocumented Auth:** Many endpoints documented as "public" still require an API key in practice, which will cause real validation to fail with HTTP 401/403.
* **Data Volatility:** The structure of live data can occasionally drift or contain unexpected edge cases not covered by the OpenAPI spec, causing the strict Pydantic models to fail parsing.

---

## 2. POST / PUT / PATCH / DELETE Endpoints

**Should synthetic validation remain mandatory?**
**Yes, absolutely.** Allowing automated LLM agents to execute unguided, mutating requests against a live API is extremely dangerous. It risks data corruption, accidental deletion of production records, and unexpected billing charges. Synthetic validation must remain mandatory for any endpoint with side effects.

However, the current implementation—forcing the *LLM* to write the synthetic mock logic—is fundamentally flawed and must be retired, as it leads to a 0% pass rate.

---

## 3. Recommended Validation Policy

To maximize correctness, honesty, and benchmark pass rates while entirely eliminating the LLM mocking hallucination, we recommend the **Framework-Level Mock Injection Policy**.

### The Policy
1. **Permissive Real Testing (GET/HEAD/OPTIONS):**
   * Remove the strict `MISSING_MOCK` linter rule for safe methods.
   * Instruct the LLM to write normal, real network calls. 
   * If the API does not require authentication (or test credentials are provided), execute the real call to guarantee 100% schema accuracy against true data.
2. **Transparent Synthetic Mocking (POST/PUT/PATCH/DELETE):**
   * The LLM is **no longer responsible** for writing `httpx.MockTransport` code. It should write standard, real-looking API calls.
   * Behind the scenes, the *Executor Node* (our Python sandbox framework) intercepts these calls using an auto-generated, OpenAPI-schema-backed Mock framework (such as Respx or an injected custom transport).
   * The LLM believes it is hitting a real endpoint, while the execution layer silently routes the mutating call to a mock server that returns valid schema data.

### Tradeoffs
* **Pros:**
  * **Zero Mock Hallucinations:** The LLM never has to write a mock again, instantly curing the infinite Diagnoser loop.
  * **Maximum Honesty:** We can truthfully claim that "SDKs are verified against real live data for GET endpoints, and safely mocked for mutating endpoints."
  * **High Pass Rate:** Restores the historical SUCCESS status for small/public APIs without compromising the safety of POST/DELETE operations.
* **Cons:**
  * **Framework Complexity:** Requires building a robust interceptor/mock engine in the `Executor` node based dynamically on the OpenAPI spec.
  * **Schema Drift on POSTs:** Because POST requests are synthetically mocked by our framework, any discrepancy between the OpenAPI spec and the actual server implementation won't be caught during SDK generation.

### Evidence from Benchmarks
* **The Hallucination Trap:** Benchmarks generated 22 consecutive failures for Petstore solely because the LLM could not guess the correct `MockTransport(handler)` syntax.
* **The Success Baseline:** When the system previously allowed real requests, the generated Pydantic models and `ApiClient` were empirically proven to work correctly. The LLM *can* write functional SDKs, it just *cannot* write test infrastructure. The new policy shifts the burden of test infrastructure back to the API Forge AI framework, where it belongs.
