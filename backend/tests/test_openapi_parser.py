import json
from app.services.openapi_parser import parse_spec_content, extract_endpoints, validate_openapi_spec

VALID_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "t", "version": "1"},
    "paths": {
        "/users": {
            "get": {"operationId": "listUsers", "summary": "List"},
            "post": {"operationId": "createUser"},
            "parameters": [{"name": "x", "in": "query"}],
        },
        "/health": {"get": {}},
    },
}

def test_parse_json_content():
    assert parse_spec_content(json.dumps(VALID_SPEC))["openapi"] == "3.0.0"

def test_parse_yaml_content():
    assert parse_spec_content("openapi: 3.0.0\npaths: {}")["openapi"] == "3.0.0"

def test_extract_endpoints_finds_http_methods_only():
    eps = extract_endpoints(VALID_SPEC)
    assert {(e["method"], e["path"]) for e in eps} == {
        ("GET", "/users"), ("POST", "/users"), ("GET", "/health"),
    }

def test_extract_endpoints_skips_path_level_parameters_key():
    eps = extract_endpoints(VALID_SPEC)
    assert all(e["method"] != "PARAMETERS" for e in eps)

def test_extract_endpoints_tolerates_malformed_path_items():
    spec = {"paths": {"/a": ["not", "a", "dict"], "/b": {"get": "not-a-dict"}}}
    assert extract_endpoints(spec) == []

def test_validate_accepts_real_spec():
    assert validate_openapi_spec(VALID_SPEC) == []

def test_validate_rejects_arbitrary_yaml_document():
    assert validate_openapi_spec({"hello": "world"}) != []

def test_validate_rejects_non_mapping():
    assert validate_openapi_spec("just a string") != []

def test_validate_rejects_missing_paths():
    assert validate_openapi_spec({"openapi": "3.0.0", "paths": {}}) != []
