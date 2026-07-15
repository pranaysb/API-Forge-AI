"""Tests for the deterministic (non-LLM) logic in the agent nodes:
the shared test-script linter, SDK consistency validation, and graph routing."""
from app.agents.nodes import lint_test_script, validate_sdk_consistency
from app.agents.nodes import test_linter_node as linter_node  # aliased so pytest doesn't collect it
from app.agents.graph import (
    route_after_schema_validator,
    route_after_linter,
    route_after_executor,
    route_after_diagnoser,
)

GOOD_SCRIPT = """
import httpx

def handler(request):
    return httpx.Response(200, json={"id": 1})

transport = httpx.MockTransport(handler)
assert transport is not None
"""

# --- lint_test_script ---

def test_lint_passes_valid_mocked_script():
    assert lint_test_script(GOOD_SCRIPT) == []

def test_lint_rejects_syntax_error():
    errors = lint_test_script("def broken(:\n  pass")
    assert len(errors) == 1 and "SyntaxError" in errors[0]

def test_lint_rejects_pytest_import():
    errors = lint_test_script("import pytest\nimport httpx\nt = httpx.MockTransport(None)")
    assert any("BANNED_IMPORT" in e for e in errors)

def test_lint_rejects_missing_mock_transport():
    errors = lint_test_script("import httpx\nr = httpx.get('http://x')")
    assert any("MISSING_MOCK" in e for e in errors)

def test_lint_mock_not_required_when_disabled():
    errors = lint_test_script("import httpx\nr = httpx.get('http://x')", require_mock_transport=False)
    assert errors == []

# --- validate_sdk_consistency ---

def test_consistency_ok_for_matching_exports():
    sdk = {
        "client.py": "class ApiClient:\n    pass",
        "models.py": "class User:\n    pass",
        "__init__.py": "from .client import ApiClient\nfrom .models import User",
    }
    assert validate_sdk_consistency(sdk) == []

def test_consistency_flags_phantom_export():
    sdk = {
        "client.py": "class ApiClient:\n    pass",
        "models.py": "class User:\n    pass",
        "__init__.py": "from .models import Ghost",
    }
    errors = validate_sdk_consistency(sdk)
    assert any("Ghost" in e for e in errors)

def test_consistency_flags_syntax_error_in_client():
    sdk = {"client.py": "class :", "models.py": "", "__init__.py": ""}
    assert validate_sdk_consistency(sdk) == ["SyntaxError in client.py"]

# --- test_linter_node ---

def _state_with_code(code):
    return {
        "current_endpoint_index": 0,
        "endpoints": [{"path": "/users", "method": "GET", "generated_code": code}],
    }

def test_linter_node_passes_good_script():
    state = _state_with_code(GOOD_SCRIPT)
    result = linter_node(state)
    assert result["endpoints"][0].get("status") != "LINTER_FAILED"

def test_linter_node_fails_unmocked_script():
    state = _state_with_code("import httpx\nhttpx.get('http://real.example.com')")
    result = linter_node(state)
    assert result["endpoints"][0]["status"] == "LINTER_FAILED"

# --- routing functions ---

def test_route_schema_validator_to_diagnoser_on_failure():
    state = {"current_endpoint_index": 0, "endpoints": [{"status": "SCHEMA_FAILED"}]}
    assert route_after_schema_validator(state) == "diagnoser"

def test_route_schema_validator_to_coder_on_success():
    state = {"current_endpoint_index": 0, "endpoints": [{"status": "SCHEMA_VALIDATED"}]}
    assert route_after_schema_validator(state) == "coder"

def test_route_ends_when_endpoints_exhausted():
    state = {"current_endpoint_index": 2, "endpoints": [{}, {}]}
    assert route_after_schema_validator(state) == "end"
    assert route_after_linter(state) == "end"
    assert route_after_executor(state) == "end"
    assert route_after_diagnoser(state) == "end"

def test_route_executor_failure_goes_to_diagnoser():
    state = {"current_endpoint_index": 0, "endpoints": [{"status": "FAILED"}]}
    assert route_after_executor(state) == "diagnoser"
