from typing import TypedDict, List, Dict, Any, Optional

class EndpointState(TypedDict, total=False):
    id: str
    path: str
    method: str
    status: str
    attempts: int
    e2b_logs: str
    agent_reasoning: str
    success: bool
    generated_code: str
    diagnostic_feedback: str

class AgentState(TypedDict):
    spec_content: str
    base_url: str
    endpoints: List[EndpointState]
    current_endpoint_index: int
    errors: List[str]
    global_context: Dict[str, Any]
    sdk_files: Dict[str, str]
    current_key_index: int
    current_model_index: int
    provider_failovers: int
    model_failovers: int
