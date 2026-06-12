from app.services.e2b_executor import execute_python_code
from langchain_core.tools import tool

@tool
def run_api_test(code: str, target_url: str, api_key: str = "") -> dict:
    """
    Executes an API test script in a secure sandbox.
    Returns stdout and stderr.
    """
    env_vars = {
        "TARGET_BASE_URL": target_url,
        "API_KEY": api_key
    }
    return execute_python_code(code, env_vars)
