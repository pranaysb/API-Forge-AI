// Shared descriptions of each LangGraph agent node, used by both the
// homepage pipeline explainer and the job timeline glossary so the two
// stay in sync.
//
// NOTE: Tailwind color classes are intentionally NOT stored here. Classes
// referenced only from a plain .ts file (not .tsx) were silently dropped by
// the build's content scanner in this project (confirmed: identical classes
// defined in a .tsx file compiled fine). Each component that needs a color
// per node defines its own literal, statically-scanned class map instead —
// see NODE_DOT_COLOR in page.tsx / jobs/[id]/page.tsx.
export interface NodeInfo {
  key: string;
  label: string;
  short: string;
  detail: string;
}

export const PIPELINE_NODES: NodeInfo[] = [
  {
    key: "planner",
    label: "Planner",
    short: "Reads your spec and drafts the SDK",
    detail:
      "Analyzes the OpenAPI schema and generates the initial client.py (HTTP methods) and models.py (Pydantic V2 data models) for every endpoint.",
  },
  {
    key: "sdk_validator",
    label: "SDK Validator",
    short: "Checks the SDK compiles and imports match",
    detail:
      "Compiles the generated files and confirms every symbol exported from __init__.py actually exists in client.py / models.py before any tests run.",
  },
  {
    key: "schema_validator",
    label: "Schema Validator",
    short: "Confirms the data models fit real payloads",
    detail:
      "Fetches a real or synthetic sample payload per endpoint and validates it against the generated Pydantic model, catching shape mismatches early.",
  },
  {
    key: "coder",
    label: "Coder",
    short: "Writes a test for the endpoint",
    detail:
      "Generates a mocked, runnable Python test script that calls the SDK method for this endpoint and asserts the response shape.",
  },
  {
    key: "test_linter",
    label: "Test Linter",
    short: "Rejects unsafe or invalid test scripts",
    detail:
      "Statically checks the generated test for syntax errors, banned imports (pytest), and enforces httpx.MockTransport so no real network calls slip through.",
  },
  {
    key: "executor",
    label: "Executor",
    short: "Runs the test in a sandbox",
    detail:
      "Executes the test script against the SDK in an isolated environment and captures stdout/stderr.",
  },
  {
    key: "diagnoser",
    label: "Diagnoser",
    short: "Fixes failures and retries",
    detail:
      "On failure, reads the error logs and patches the SDK or test script in memory, then loops back for another attempt (up to 5 tries per endpoint).",
  },
];

export function nodeInfo(key: string): NodeInfo | undefined {
  return PIPELINE_NODES.find((n) => n.key === key);
}
