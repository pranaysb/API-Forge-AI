import yaml
import json
from typing import Dict, Any, List

def parse_spec_content(content: str) -> Dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return yaml.safe_load(content)

def validate_openapi_spec(spec_json: Any) -> List[str]:
    """Returns a list of human-readable problems; empty list means the document
    looks like a usable OpenAPI/Swagger spec."""
    errors = []
    if not isinstance(spec_json, dict):
        return ["Document is not a mapping/object — not an OpenAPI spec."]
    if "openapi" not in spec_json and "swagger" not in spec_json:
        errors.append("Missing 'openapi' (3.x) or 'swagger' (2.0) version field.")
    paths = spec_json.get("paths")
    if not isinstance(paths, dict) or not paths:
        errors.append("Spec has no 'paths' — nothing to generate an SDK from.")
    return errors

def extract_endpoints(spec_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    endpoints = []
    paths = spec_json.get("paths", {})
    if not isinstance(paths, dict):
        return endpoints
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in ["get", "post", "put", "delete", "patch", "options", "head"]:
                continue
            if not isinstance(operation, dict):
                continue
            endpoints.append({
                "path": path,
                "method": method.upper(),
                "operation_id": operation.get("operationId"),
                "summary": operation.get("summary"),
            })
    return endpoints
