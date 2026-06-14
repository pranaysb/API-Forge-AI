from app.core.config import settings
from app.services.llm_factory import get_llm
from app.agents.state import AgentState

class ReliabilityManager:
    # Keys should ideally be pulled dynamically, but static list matches requirement
    KEYS = []
    
    MODELS = [
        "llama-3.3-70b-versatile",
        "openai/gpt-oss-120b",
        "qwen/qwen3-32b",
        "llama-3.1-8b-instant"
    ]
    
    _initialized = False
    
    @classmethod
    def _init_keys(cls):
        if not cls.KEYS:
            cls.KEYS = [k for k in [
                settings.GROQ_API_KEY, 
                settings.GROQ_API_KEY_1, 
                settings.GROQ_API_KEY_2
            ] if k]
        
        if not cls._initialized:
            print(f"Loaded keys count = {len(cls.KEYS)}")
            print(f"Available fallback models = {cls.MODELS}")
            cls._initialized = True

    @classmethod
    def invoke(cls, prompt, output_schema, input_vars, state: AgentState):
        cls._init_keys()
        
        key_idx = state.get("current_key_index", 0)
        model_idx = state.get("current_model_index", 0)
        provider_failovers = state.get("provider_failovers", 0)
        model_failovers = state.get("model_failovers", 0)
        
        max_attempts = len(cls.KEYS) * len(cls.MODELS)
        attempts = 0
        attempts_for_current_model = 0
        
        while attempts < max_attempts:
            if model_idx >= len(cls.MODELS):
                break
                
            current_key = cls.KEYS[key_idx % len(cls.KEYS)] if cls.KEYS else None
            current_model = cls.MODELS[model_idx]
            
            llm = get_llm(provider="GROQ", model_name=current_model, api_key_override=current_key)
            if not llm:
                return None, {"errors": ["No LLM configured or missing API keys."]}
                
            chain = prompt | llm.with_structured_output(output_schema)
            
            try:
                result = chain.invoke(input_vars)
                
                # Successful execution, return result and updated indexes
                updates = {
                    "current_key_index": key_idx % len(cls.KEYS) if cls.KEYS else 0,
                    "current_model_index": model_idx,
                    "provider_failovers": provider_failovers,
                    "model_failovers": model_failovers,
                    "global_context": {
                        **state.get("global_context", {}),
                        "final_model_used": current_model,
                        "final_key_index": key_idx % len(cls.KEYS) if cls.KEYS else 0
                    }
                }
                return result, updates
                
            except Exception as e:
                error_str = str(e).lower()
                
                # Check for decommissioned models
                if any(x in error_str for x in ["model_decommissioned", "decommissioned", "does not exist", "model not found"]):
                    old_model = current_model
                    model_idx += 1
                    model_failovers += 1
                    attempts_for_current_model = 0
                    key_idx = 0 
                    
                    if model_idx < len(cls.MODELS):
                        new_model = cls.MODELS[model_idx]
                        print(f"[MODEL FALLBACK]\nOld model: {old_model}\nNew model: {new_model}")
                    else:
                        print(f"[MODEL FALLBACK]\nOld model: {old_model}\nNew model: None (Exhausted)")
                    continue

                # Check for rate limit
                elif "429" in error_str or "rate limit" in error_str or "quota" in error_str:
                    attempts += 1
                    attempts_for_current_model += 1
                    
                    key_idx = (key_idx + 1) % len(cls.KEYS) if cls.KEYS else 0
                    provider_failovers += 1
                    
                    print(f"[KEY ROTATION]\nCurrent model: {current_model}\nCurrent key: {key_idx}")
                    
                    # If we have exhausted all keys for the current model
                    if attempts_for_current_model >= len(cls.KEYS):
                        old_model = current_model
                        model_idx += 1
                        model_failovers += 1
                        attempts_for_current_model = 0
                        key_idx = 0
                        
                        if model_idx < len(cls.MODELS):
                            new_model = cls.MODELS[model_idx]
                            print(f"[MODEL FALLBACK]\nOld model: {old_model}\nNew model: {new_model}")
                        else:
                            print(f"[MODEL FALLBACK]\nOld model: {old_model}\nNew model: None (Exhausted)")
                    
                    continue # Retry loop
                else:
                    # Non-rate-limit exception
                    raise e
                    
        # Exceeded max attempts
        raise Exception("ReliabilityManager exhausted all keys and models due to repeated errors.")
