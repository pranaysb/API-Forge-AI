from app.agents.state import AgentState
from app.services.llm_factory import get_llm
from app.core.config import settings
from pydantic import BaseModel, Field
from app.services.executor import get_executor
from langchain_core.prompts import ChatPromptTemplate
import ast

llm = get_llm(provider="GROQ", model_name="llama-3.3-70b-versatile")

class PlannerOutput(BaseModel):
    reasoning: str = Field(description="Reasoning about the SDK structure and models.")
    client_code: str = Field(description="The initial apiforge_sdk/client.py file containing the main API client class and methods for all endpoints.")
    models_code: str = Field(description="The initial apiforge_sdk/models.py file containing Pydantic models for request/response payloads.")
    init_code: str = Field(description="The initial apiforge_sdk/__init__.py file containing explicit exports of the ApiClient and all Pydantic models.")

class CoderOutput(BaseModel):
    reasoning: str = Field(description="Reasoning about how to test this specific endpoint using the generated SDK.")
    python_code: str = Field(description="A complete Python script using the generated SDK (`import apiforge_sdk`) to test the endpoint. Make sure to instantiate the client, call the method, and assert that the response is correct (e.g. valid Pydantic model).")

class DiagnoserOutput(BaseModel):
    likely_cause: str = Field(description="The likely cause of the failure based on the execution logs.")
    error_category: str = Field(description="Must be one of: 'sdk_error', 'schema_error', 'test_error'.")
    mutation_instructions: str = Field(description="Specific instructions for what was wrong.")
    client_code: str = Field(description="The FULL, CORRECTED apiforge_sdk/client.py code. If no changes needed, output the original.")
    models_code: str = Field(description="The FULL, CORRECTED apiforge_sdk/models.py code. If no changes needed, output the original.")

class SchemaValidatorOutput(BaseModel):
    python_code: str = Field(description="A short python script using `httpx` to fetch a real payload from the API, import the correct Pydantic model from `apiforge_sdk.models`, and run `Model.model_validate()` against it.")

def planner_node(state: AgentState) -> dict:
    """Analyzes spec and determines execution order."""
    if not llm: return {"errors": ["No LLM configured."]}
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert Python SDK Generator. Analyze the OpenAPI spec and generate the foundational SDK code. Generate complete, production-ready code for `client.py` using httpx and `models.py` using Pydantic based on the endpoints. MUST USE Pydantic v2 (`model_validate`, not `parse_obj` or `**kwargs` or `User(**item)`). The client methods MUST return the instantiated Pydantic models (e.g., `return [User.model_validate(item) for item in response.json()]`). You MUST include `response.raise_for_status()` after every request. You MUST add a default `timeout=10.0` configuration to the ApiClient initialization. You MUST use relative imports inside the package (e.g., `from .models import User`). Generate fully nested Pydantic models for ALL nested JSON objects (e.g., if a User has an Address or Company, you MUST define `Address` and `Company` models instead of using `dict`). Generate `__init__.py` that explicitly defines `__all__ = [...]` (this is mandatory) and exports all generated models and the client without wildcard imports."),
        ("user", "OpenAPI Spec:\n{spec_content}\nBase URL: {base_url}\nEndpoints: {endpoints}")
    ])
    
    chain = prompt | llm.with_structured_output(PlannerOutput)
    
    try:
        result = chain.invoke({
            "spec_content": state.get("spec_content", ""),
            "base_url": state.get("base_url", ""),
            "endpoints": [f"{ep.get('method')} {ep.get('path')}" for ep in state.get("endpoints", [])]
        })
        
        sdk_files = {
            "client.py": result.client_code,
            "models.py": result.models_code,
            "__init__.py": result.init_code
        }
        
        return {"current_endpoint_index": 0, "sdk_files": sdk_files}
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
    if idx >= len(endpoints) or not llm:
        return {}
    
    current_ep = endpoints[idx]
    
    if current_ep.get("schema_validated"):
        return {"endpoints": endpoints}
        
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a Schema Validator. Write a short Python script to fetch a sample payload from the API and validate it using the generated Pydantic models. Use `httpx.get` (or appropriate method). Do NOT use the generated ApiClient, just raw httpx. Import the correct model from `apiforge_sdk.models` and run `Model.model_validate(item)`. If it's a list, validate one item. Do not use markdown blocks, just raw python string."),
        ("user", "Endpoint: {method} {path}\nBase URL: {base_url}\nModels:\n{models_py}")
    ])
    
    chain = prompt | llm.with_structured_output(SchemaValidatorOutput)
    
    try:
        sdk_files = state.get("sdk_files", {})
        result = chain.invoke({
            "method": current_ep.get("method"),
            "path": current_ep.get("path"),
            "base_url": state.get("base_url"),
            "models_py": sdk_files.get("models.py", "")
        })
        
        executor = get_executor()
        success, stdout, stderr = executor.execute_sdk_test(sdk_files, result.python_code)
        
        if success:
            current_ep["schema_validated"] = True
            current_ep["agent_reasoning"] = "Schema validation passed."
        else:
            current_ep["status"] = "SCHEMA_FAILED"
            current_ep["execution_stdout"] = stdout
            current_ep["execution_stderr"] = stderr
            current_ep["generated_code"] = result.python_code
            current_ep["agent_reasoning"] = "Schema validation failed. Routing to Diagnoser."
            
    except Exception as e:
        current_ep["agent_reasoning"] = f"Schema validator error: {str(e)}"
        
    return {"endpoints": endpoints}

def coder_node(state: AgentState) -> dict:
    """Generates Python test script for the current endpoint."""
    idx = state.get("current_endpoint_index", 0)
    endpoints = state.get("endpoints", [])
    if idx >= len(endpoints) or not llm:
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
        ("system", "You are an expert Python SDK Tester. Write a complete, runnable Python test script that imports and tests the generated SDK. The SDK is located in the `apiforge_sdk` package. You can import from `apiforge_sdk.client` or `apiforge_sdk.models`. Instantiate the client with the base URL, call the SDK method for the target endpoint, and make deep assertions on the returned payload. You MUST assert that the return type is NOT a raw httpx response (e.g., `assert not isinstance(result, httpx.Response)`). You MUST assert that the result is the expected Pydantic model (e.g., `assert isinstance(result, User)` or `assert isinstance(result[0], User)`). You MUST write strong assertions verifying specific nested fields (e.g., `assert isinstance(result[0].id, int)` and `assert isinstance(result[0].address.city, str)`). If the SDK is incorrect or missing the method, DO NOT try to fix the SDK here, just write the test as it *should* work. Do not use markdown blocks for the code, just pure raw python string."),
        ("user", "Endpoint to test: {method} {path}\nBase URL: {base_url}\nGenerated SDK client.py:\n{client_py}\nGenerated SDK models.py:\n{models_py}\nPrevious Diagnostic Feedback:\n{diagnostic_feedback}")
    ])
    
    chain = prompt | llm.with_structured_output(CoderOutput)
    
    try:
        sdk_files = state.get("sdk_files", {})
        result = chain.invoke({
            "method": current_ep.get("method"),
            "path": current_ep.get("path"),
            "base_url": state.get("base_url"),
            "client_py": sdk_files.get("client.py", ""),
            "models_py": sdk_files.get("models.py", ""),
            "diagnostic_feedback": current_ep.get("diagnostic_feedback", "None")
        })
        
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
    
    if not llm:
        current_ep["agent_reasoning"] = "No LLM for diagnoser."
        return {"endpoints": endpoints}
        
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an API Debugging Expert. Analyze the execution logs. If the error is an 'SDK Consistency Validation Failed' error OR if a test fails because the SDK returns a raw httpx.Response instead of a Pydantic model (e.g. AssertionError on the return type), the SDK IS FLAWED and you MUST fix the SDK files (`client.py` or `models.py`). NEVER downgrade `model_validate()` to `User(**item)` unless `model_validate` causes an actual runtime failure. Ensure that relative imports are used inside the SDK (e.g. `from .models import User`). Select the correct `error_category` ('sdk_error', 'schema_error', 'test_error'). Only modify the files relevant to the error category. For `sdk_error`, output corrected `client.py` or `models.py`. For `schema_error`, modify `models.py`. For `test_error`, provide `mutation_instructions` for the test. Output the FULL corrected Python code for `client.py` and `models.py` (do not truncate, output the entire file)."),
        ("user", "Endpoint: {method} {path}\nExecution Logs:\n{logs}\nTest Script:\n{code}\nSDK client.py:\n{client_py}\nSDK models.py:\n{models_py}")
    ])
    
    chain = prompt | llm.with_structured_output(DiagnoserOutput)
    
    try:
        sdk_files = state.get("sdk_files", {})
        result = chain.invoke({
            "method": current_ep.get("method"),
            "path": current_ep.get("path"),
            "logs": f"STDOUT:\n{current_ep.get('execution_stdout', '')}\nSTDERR:\n{current_ep.get('execution_stderr', '')}",
            "code": current_ep.get("generated_code"),
            "client_py": sdk_files.get("client.py", ""),
            "models_py": sdk_files.get("models.py", "")
        })
        
        current_ep["agent_reasoning"] = f"Diagnosed failure: {result.likely_cause}. Category: {result.error_category}"
        
        feedback = result.mutation_instructions
        
        # Apply the fixed SDK files to the state based on category
        if result.error_category in ["sdk_error", "schema_error"]:
            sdk_files["client.py"] = result.client_code
            sdk_files["models.py"] = result.models_code
            feedback += f"\n\n[Diagnoser patched sdk_files in memory. Category: {result.error_category}]"
            print("--- DIAGNOSER PATCHED SDK ---")
            print(f"client.py:\n{sdk_files['client.py'][:500]}...")
            
        current_ep["diagnostic_feedback"] = feedback
            
    except Exception as e:
        current_ep["agent_reasoning"] = f"Diagnoser error: {str(e)}"
        current_ep["diagnostic_feedback"] = "Unknown error during diagnosis."
        
    return {"endpoints": endpoints, "sdk_files": sdk_files}
