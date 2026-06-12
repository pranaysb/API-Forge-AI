import yaml
import json
from typing import Dict, Any, List

def parse_spec_content(content: str) -> Dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return yaml.safe_load(content)

def extract_endpoints(spec_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    endpoints = []
    paths = spec_json.get("paths", {})
    for path, path_item in paths.items():
        for method, operation in path_item.items():
            if method.lower() not in ["get", "post", "put", "delete", "patch", "options", "head"]:
                continue
            endpoints.append({
                "path": path,
                "method": method.upper(),
                "operation_id": operation.get("operationId"),
                "summary": operation.get("summary"),
            })
    return endpoints

def determine_dependencies(endpoints: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return endpoints
