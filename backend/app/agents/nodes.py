from app.agents.state import AgentState
from app.services.llm_factory import get_llm
from app.services.reliability import ReliabilityManager
from app.core.config import settings
from pydantic import BaseModel, Field
from app.services.executor import get_executor
from langchain_core.prompts import ChatPromptTemplate
import ast

class PlannerOutput(BaseModel):
    reasoning: str = Field(description="Reasoning about the SDK structure and models.")
    client_code: str = Field(description="The initial apiforge_sdk/client.py file containing the main API client class and methods for all endpoints.")
    models_code: str = Field(description="The initial apiforge_sdk/models.py file containing Pydantic models for request/response payloads.")
    init_code: str = Field(description="The initial apiforge_sdk/__init__.py file containing explicit exports of the ApiClient and all Pydantic models.")

class CoderOutput(BaseModel):
    reasoning: str = Field(description="Reasoning about how to test this specific endpoint using the generated SDK.")
    python_code: str = Field(description="A complete Python script using the generated SDK (`import apiforge_sdk`) to test the endpoint. Make sure to instantiate the client, call the method, and assert that the response is correct (e.g. valid Pydantic model).")

class Patch(BaseModel):
    file_name: str = Field(description="Must be exactly 'client.py' or 'models.py'.")
    search_string: str = Field(description="The exact string in the file to be replaced. Must match exactly.")
    replace_string: str = Field(description="The string to replace it with.")

class DiagnoserOutput(BaseModel):
    likely_cause: str = Field(description="The likely cause of the failure based on the execution logs.")
    error_category: str = Field(description="Must be one of: 'sdk_error', 'schema_error', 'test_error'.")
    mutation_instructions: str = Field(description="Specific instructions for what was wrong.")
    patches: list[Patch] = Field(description="List of text replacement patches to apply to the SDK files.", default_factory=list)

class SchemaValidatorOutput(BaseModel):
    python_code: str = Field(description="A short python script using `httpx` to fetch a real payload from the API, import the correct Pydantic model from `apiforge_sdk.models`, and run `Model.model_validate()` against it.")

def planner_node(state: AgentState) -> dict:
    """Analyzes spec and determines execution order."""
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert Python SDK Generator. Analyze the OpenAPI spec and generate the foundational SDK code. Generate complete, production-ready code for `client.py` using httpx and `models.py` using Pydantic based on the endpoints. MUST USE Pydantic v2 (`model_validate`, not `parse_obj` or `**kwargs` or `User(**item)`). When configuring Pydantic models, you MUST use Pydantic V2 `model_config = ConfigDict(populate_by_name=True, extra='forbid')` as a direct class attribute, and NEVER use the Pydantic V1 `class Config:` block. Make sure to import `ConfigDict` from `pydantic`. The client methods MUST return the instantiated Pydantic models (e.g., `return [User.model_validate(item) for item in response.json()]`). You MUST include `response.raise_for_status()` after every request. You MUST add a default `timeout=10.0` configuration to the ApiClient initialization. You MUST use relative imports inside the package (e.g., `from .models import User`). Generate fully nested Pydantic models for ALL nested JSON objects (e.g., if a User has an Address or Company, you MUST define `Address` and `Company` models instead of using `dict`). Generate `__init__.py` that explicitly defines `__all__ = [...]` (this is mandatory) and exports all generated models and the client without wildcard imports."),
        ("user", "OpenAPI Spec:\n{spec_content}\nBase URL: {base_url}\nEndpoints: {endpoints}")
    ])
    
    try:
        input_vars = {
            "spec_content": state.get("spec_content", ""),
            "base_url": state.get("base_url", ""),
            "endpoints": [f"{ep.get('method')} {ep.get('path')}" for ep in state.get("endpoints", [])]
        }
        
        result, updates = ReliabilityManager.invoke(prompt, PlannerOutput, input_vars, state)
        
        sdk_files = {
            "client.py": result.client_code,
            "models.py": result.models_code,
            "__init__.py": result.init_code
        }
        
        return {"current_endpoint_index": 0, "sdk_files": sdk_files, **updates}
    except Exception as e:
        return {"errors": [f"Planner error: {str(e)}"], "current_endpoint_index": 0, "sdk_files": {}}

def validate_sdk_consistency(sdk_files: dict) -> list[str]:
    errors = []
    init_content = sdk_files.get("__init__.py", "")
    client_content = sdk_files.get("client.py", "")
    models_content = sdk_files.get("models.py", "")
    
    def get_defined_symbols(code: str):
        try:
            tree = ast.parse(code)
            return {node.name for node in tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))} | \
                   {t.id for node in tree.body if isinstance(node, ast.Assign) for t in node.targets if isinstance(t, ast.Name)}
        except SyntaxError:
            return None
            
    client_symbols = get_defined_symbols(client_content)
    models_symbols = get_defined_symbols(models_content)
    
    if client_symbols is None:
        return ["SyntaxError in client.py"]
    if models_symbols is None:
        return ["SyntaxError in models.py"]

    try:
        init_tree = ast.parse(init_content)
        for node in init_tree.body:
            if isinstance(node, ast.ImportFrom):
                module = node.module
                if module == "client":
                    for alias in node.names:
                        if alias.name != "*" and alias.name not in client_symbols:
                            errors.append(f"__init__.py exports '{alias.name}' from .client, but it does not exist in client.py")
                elif module == "models":
                    for alias in node.names:
                        if alias.name != "*" and alias.name not in models_symbols:
                            errors.append(f"__init__.py exports '{alias.name}' from .models, but it does not exist in models.py")
    except SyntaxError:
        errors.append("SyntaxError in __init__.py")
        
    return errors

def lint_test_script(code: str, require_mock_transport: bool = True) -> list[str]:
    """Statically validates a generated test script: syntax, banned imports,
    and (optionally) that httpx.MockTransport is used so no real network
    calls are made."""
    errors = []
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return [f"SyntaxError: {str(e)}"]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if 'pytest' in alias.name:
                    errors.append("BANNED_IMPORT: 'pytest' is not allowed. Use standard assert statements.")
        elif isinstance(node, ast.ImportFrom):
            if node.module and 'pytest' in node.module:
                errors.append("BANNED_IMPORT: 'pytest' is not allowed. Use standard assert statements.")

    if require_mock_transport:
        has_mock_transport = any(
            (isinstance(node, ast.Attribute) and node.attr == 'MockTransport') or
            (isinstance(node, ast.Name) and node.id == 'MockTransport')
            for node in ast.walk(tree)
        )
        if not has_mock_transport:
            errors.append("MISSING_MOCK: You must use `httpx.MockTransport(handler)` to mock the API response. Real network calls are not allowed in this validation mode.")

    return errors

def sdk_validator_node(state: AgentState) -> dict:
    """Pre-execution validation stage: Validates SDK syntax and imports."""
    sdk_files = state.get("sdk_files", {})
    endpoints = state.get("endpoints", [])
    
    # 1. Compile checks
    compile_errors = []
    for filename, code in sdk_files.items():
        try:
            compile(code, filename, 'exec')
        except SyntaxError as e:
            compile_errors.append(f"SyntaxError in {filename}: {str(e)}")
            
    # 2. Consistency checks
    consistency_errors = validate_sdk_consistency(sdk_files)
    
    all_errors = compile_errors + consistency_errors
    
    if all_errors:
        error_msg = "SDK Validation Failed:\n" + "\n".join(all_errors)
        for ep in endpoints:
            ep["status"] = "FAILED_PERMANENTLY"
            ep["agent_reasoning"] = error_msg
            ep["execution_stderr"] = error_msg
        
        return {"endpoints": endpoints, "errors": all_errors}
    
    return {"endpoints": endpoints}

def schema_validator_node(state: AgentState) -> dict:
    """Fetches a real API sample and runs model_validate against it."""
    idx = state.get("current_endpoint_index", 0)
    endpoints = state.get("endpoints", [])
    if idx >= len(endpoints):
        return {}
    
    current_ep = endpoints[idx]
    
    if current_ep.get("schema_validated"):
        return {"endpoints": endpoints}
        
    if current_ep.get("status") == "FAILED_PERMANENTLY":
        return {"current_endpoint_index": idx + 1, "endpoints": endpoints}
        
    method = current_ep.get("method", "GET").upper()
    has_auth = state.get("auth_credentials") is not None
    
    is_safe_method = method in ["GET", "HEAD", "OPTIONS"]
    
    if is_safe_method and has_auth:
        validation_mode = "REAL"
        system_prompt = "You are a Schema Validator. Write a short Python script to fetch a real payload from the API and validate it using the generated Pydantic models. Use `httpx.get` (or appropriate method). Do NOT use the generated ApiClient, just raw httpx. Import the correct model from `apiforge_sdk.models` and run `Model.model_validate(item)`. If it's a list, validate one item. Do not use markdown blocks, just raw python string."
    else:
        validation_mode = "SYNTHETIC"
        system_prompt = "You are a Schema Validator. Write a short Python script to synthetically generate a dummy payload based EXACTLY on the OpenAPI schema for this endpoint, and validate it using the generated Pydantic models. You MUST use `httpx.MockTransport(handler)` to mock the API response. Do NOT make a real network request. Import the correct model from `apiforge_sdk.models` and run `Model.model_validate(item)`. Write plain multi-line Python with normal newlines and indentation — never compress statements onto one line with semicolons. Do not use markdown blocks, just raw python string."

    current_ep["validation_mode"] = validation_mode

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "Endpoint: {method} {path}\nBase URL: {base_url}\nModels:\n{models_py}\nPrevious Diagnostic Feedback:\n{diagnostic_feedback}\nPrevious Failed Script (fix its mistakes, do not repeat them):\n{previous_script}\nPrevious Error Output:\n{previous_stderr}")
    ])

    try:
        sdk_files = state.get("sdk_files", {})
        input_vars = {
            "method": current_ep.get("method"),
            "path": current_ep.get("path"),
            "base_url": state.get("base_url"),
            "models_py": sdk_files.get("models.py", ""),
            "diagnostic_feedback": current_ep.get("diagnostic_feedback") or "None",
            "previous_script": current_ep.get("generated_code") or "None",
            "previous_stderr": current_ep.get("execution_stderr") or "None"
        }

        result, updates = ReliabilityManager.invoke(prompt, SchemaValidatorOutput, input_vars, state)

        # Lint before executing: schema scripts previously ran unchecked, so a
        # SyntaxError or a real network call could slip straight to the executor.
        lint_errors = lint_test_script(result.python_code, require_mock_transport=(validation_mode == "SYNTHETIC"))
        if lint_errors:
            current_ep["status"] = "SCHEMA_FAILED"
            current_ep["generated_code"] = result.python_code
            current_ep["execution_stdout"] = ""
            current_ep["execution_stderr"] = "Schema Validation Script Linter Failed:\n" + "\n".join(lint_errors)
            current_ep["agent_reasoning"] = "Linter rejected the schema validation script. Routing to Diagnoser."
            return {"endpoints": endpoints, **updates}

        executor = get_executor()
        success, stdout, stderr = executor.execute_sdk_test(sdk_files, result.python_code)
        
        if success:
            current_ep["status"] = "SCHEMA_VALIDATED"
            current_ep["schema_validated"] = True
            current_ep["execution_stdout"] = stdout
            current_ep["execution_stderr"] = stderr
            current_ep["diagnostic_feedback"] = ""
            current_ep["agent_reasoning"] = "Schema validation passed."
        else:
            current_ep["status"] = "SCHEMA_FAILED"
            current_ep["execution_stdout"] = stdout
            current_ep["execution_stderr"] = stderr
            current_ep["generated_code"] = result.python_code
            current_ep["agent_reasoning"] = "Schema validation failed. Routing to Diagnoser."
            
    except Exception as e:
        current_ep["agent_reasoning"] = f"Schema validator error: {str(e)}"
        updates = {}
        
    return {"endpoints": endpoints, **updates}

def coder_node(state: AgentState) -> dict:
    """Generates Python test script for the current endpoint."""
    idx = state.get("current_endpoint_index", 0)
    endpoints = state.get("endpoints", [])
    if idx >= len(endpoints):
        return {}
    
    current_ep = endpoints[idx]
    
    sdk_files = state.get("sdk_files", {})
    consistency_errors = validate_sdk_consistency(sdk_files)
    if consistency_errors:
        current_ep["status"] = "FAILED"
        current_ep["execution_stderr"] = "SDK Consistency Validation Failed:\n" + "\n".join(consistency_errors)
        current_ep["agent_reasoning"] = "SDK structure is invalid. Bypassing test generation."
        return {"endpoints": endpoints}
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert Python SDK Tester. Write a complete, plain runnable Python script that imports and tests the generated SDK. Do not infer SDK interfaces. Read the generated SDK source code and use the exact method names, model names, constructor signatures, field names, and httpx APIs present in the generated files. The SDK is located in the `apiforge_sdk` package. Instantiate the client with the base URL, call the SDK method for the target endpoint, and make deep assertions on the returned payload (e.g. `assert isinstance(result, User)`). CRITICAL REQUIREMENTS: 1) Ban pytest completely; use standard `assert` statements in a plain executable script. 2) Require tests to run with only the dependencies already installed in the executor environment. 3) Ban `MockTransport(responses=...)`. You MUST use the `httpx.MockTransport(handler)` syntax only to mock HTTP requests so the test does not depend on a running server. Never make a real network request. Inject the mock transport into the `ApiClient` instance. Do not use markdown blocks for the code, just pure raw python string."),
        ("user", "Endpoint to test: {method} {path}\nBase URL: {base_url}\nGenerated SDK client.py:\n{client_py}\nGenerated SDK models.py:\n{models_py}\nPrevious Diagnostic Feedback:\n{diagnostic_feedback}")
    ])
    
    try:
        sdk_files = state.get("sdk_files", {})
        input_vars = {
            "method": current_ep.get("method"),
            "path": current_ep.get("path"),
            "base_url": state.get("base_url"),
            "client_py": sdk_files.get("client.py", ""),
            "models_py": sdk_files.get("models.py", ""),
            "diagnostic_feedback": current_ep.get("diagnostic_feedback", "None")
        }
        
        result, updates = ReliabilityManager.invoke(prompt, CoderOutput, input_vars, state)
        
        current_ep["agent_reasoning"] = result.reasoning
        
        # Test Script AST Validation
        try:
            tree = ast.parse(result.python_code)
            has_httpx_import = any(isinstance(n, ast.Import) and any(alias.name == 'httpx' for alias in n.names) for n in tree.body)
            has_httpx_import_from = any(isinstance(n, ast.ImportFrom) and n.module == 'httpx' for n in tree.body)
            
            if 'httpx' in result.python_code and not (has_httpx_import or has_httpx_import_from):
                # We can't immediately fail or modify here, but we can set it to FAILED to go to diagnoser,
                # or just modify it ourselves. Since we're in coder, let's just prepend the import.
                result.python_code = "import httpx\n" + result.python_code
            
            # Additional validation (reject malformed) could be checked here. AST parsing already checks syntax.
            current_ep["generated_code"] = result.python_code
        except SyntaxError as e:
            current_ep["status"] = "FAILED"
            current_ep["execution_stderr"] = f"Test script SyntaxError: {e}"
            current_ep["agent_reasoning"] = "Syntax error in generated test script. Routing to diagnoser."
            
    except Exception as e:
        current_ep["agent_reasoning"] = f"Coder error: {str(e)}"
        updates = {}
        
    return {"endpoints": endpoints, **updates}

def test_linter_node(state: AgentState) -> AgentState:
    """Statically verifies the generated test script before execution."""
    print("--- TEST LINTER ---")
    endpoints = state.get("endpoints", [])
    idx = state.get("current_endpoint_index", 0)
    if idx >= len(endpoints):
        return state
        
    current_ep = endpoints[idx]
    code = current_ep.get("generated_code", "")

    errors = lint_test_script(code, require_mock_transport=True)

    if errors:
        current_ep["status"] = "LINTER_FAILED"
        current_ep["execution_stderr"] = "Test Script Linter Failed:\n" + "\n".join(errors)
        current_ep["agent_reasoning"] = "Linter rejected the test script. Routing to Diagnoser."
        print(f"Linter failed: {errors}")
    else:
        print("Linter passed.")
        
    return {"endpoints": endpoints}

def executor_node(state: AgentState) -> AgentState:
    print("--- EXECUTOR ---")
    endpoints = state["endpoints"]
    idx = state["current_endpoint_index"]
    current_ep = endpoints[idx]
    
    code = current_ep.get("generated_code")
    sdk_files = state.get("sdk_files", {})
    if not code or not sdk_files:
        current_ep["status"] = "FAILED"
        return state
        
    executor = get_executor()
    success, stdout, stderr = executor.execute_sdk_test(sdk_files, code)
    
    current_ep["execution_stdout"] = stdout
    current_ep["execution_stderr"] = stderr
    
    if success:
        current_ep["status"] = "SUCCESS"
        return {"endpoints": endpoints, "current_endpoint_index": idx + 1}
    else:
        current_ep["status"] = "FAILED"
        return {"endpoints": endpoints}

def diagnoser_node(state: AgentState) -> dict:
    """Analyzes errors and plans fixes."""
    idx = state.get("current_endpoint_index", 0)
    endpoints = state.get("endpoints", [])
    if idx >= len(endpoints):
        return {}
    
    current_ep = endpoints[idx]
    
    attempts = current_ep.get("attempts", 0) + 1
    current_ep["attempts"] = attempts
    
    if current_ep.get("status") == "SUCCESS":
        return {"current_endpoint_index": idx + 1, "endpoints": endpoints}
        
    if attempts >= 5:
        current_ep["status"] = "FAILED_PERMANENTLY"
        current_ep["agent_reasoning"] = "Max retries exceeded. Moving to next endpoint."
        return {"current_endpoint_index": idx + 1, "endpoints": endpoints}
        
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an API Debugging Expert. Analyze the execution logs. If the error is an 'SDK Consistency Validation Failed' error OR if a test fails because the SDK returns a raw httpx.Response instead of a Pydantic model (e.g. AssertionError on the return type), the SDK IS FLAWED and you MUST fix the SDK files (`client.py` or `models.py`). NEVER downgrade `model_validate()` to `User(**item)` unless `model_validate` causes an actual runtime failure. Ensure that relative imports are used inside the SDK (e.g. `from .models import User`). When configuring Pydantic models, you MUST use Pydantic V2 `model_config = ConfigDict(populate_by_name=True, extra='forbid')` as a direct class attribute, and NEVER use the Pydantic V1 `class Config:` block. Make sure to import `ConfigDict` from `pydantic`. Select the correct `error_category` ('sdk_error', 'schema_error', 'test_error'). Only modify the files relevant to the error category. You MUST provide specific string replacement patches. The `search_string` MUST match exactly a contiguous block of text in the file."),
        ("user", "Endpoint: {method} {path}\nExecution Logs:\n{logs}\nTest Script:\n{code}\nSDK client.py:\n{client_py}\nSDK models.py:\n{models_py}")
    ])
    
    try:
        sdk_files = state.get("sdk_files", {})
        input_vars = {
            "method": current_ep.get("method"),
            "path": current_ep.get("path"),
            "logs": f"STDOUT:\n{current_ep.get('execution_stdout', '')}\nSTDERR:\n{current_ep.get('execution_stderr', '')}",
            "code": current_ep.get("generated_code"),
            "client_py": sdk_files.get("client.py", ""),
            "models_py": sdk_files.get("models.py", "")
        }
        
        result, updates = ReliabilityManager.invoke(prompt, DiagnoserOutput, input_vars, state)

        # Guard against misdiagnosis: a SyntaxError raised by the test script
        # itself can never be an SDK problem, so don't let the LLM patch the
        # SDK for it. (Observed: it blamed models.py for a one-line script.)
        stderr = current_ep.get("execution_stderr", "") or ""
        if "SyntaxError" in stderr and "test_script.py" in stderr and "models.py" not in stderr and "client.py" not in stderr:
            result.error_category = "test_error"
            result.patches = []

        current_ep["agent_reasoning"] = f"Diagnosed failure: {result.likely_cause}. Category: {result.error_category}"

        feedback = result.mutation_instructions
        
        # Apply the fixed SDK files to the state based on patches
        if result.error_category in ["sdk_error", "schema_error"]:
            for patch in result.patches:
                fname = patch.file_name
                if fname in sdk_files:
                    if patch.search_string in sdk_files[fname]:
                        sdk_files[fname] = sdk_files[fname].replace(patch.search_string, patch.replace_string)
                    else:
                        feedback += f"\n\n[Warning: Patch search string not found in {fname}]"
                        
            feedback += f"\n\n[Diagnoser applied patches in memory. Category: {result.error_category}]"
            print("--- DIAGNOSER PATCHED SDK ---")
            print(f"client.py:\n{sdk_files.get('client.py', '')[:500]}...")
            
        current_ep["diagnostic_feedback"] = feedback
            
    except Exception as e:
        current_ep["agent_reasoning"] = f"Diagnoser error: {str(e)}"
        current_ep["diagnostic_feedback"] = f"Diagnoser failed to generate valid fix: {str(e)}"
        
        # Stop the infinite loop immediately if the Diagnoser LLM throws an unrecoverable exception
        current_ep["status"] = "FAILED_PERMANENTLY"
        updates = {}
        
    return {"endpoints": endpoints, "sdk_files": sdk_files, **updates}
