from app.core.config import settings

def get_llm(provider: str = "GROQ", model_name: str = None, api_key_override: str = None):
    """
    Returns the appropriate ChatModel based on the provider configuration.
    """
    provider = provider.upper()
    
    if provider == "OPENAI":
        from langchain_openai import ChatOpenAI
        api_key = api_key_override or settings.OPENAI_API_KEY
        if not api_key:
            return None
        return ChatOpenAI(model=model_name or "gpt-4o", api_key=api_key)
        
    elif provider == "GROQ":
        from langchain_groq import ChatGroq
        api_key = api_key_override or settings.GROQ_API_KEY
        if not api_key:
            return None
        return ChatGroq(model=model_name or "llama-3.3-70b-versatile", api_key=api_key)
        
    elif provider == "ANTHROPIC":
        from langchain_anthropic import ChatAnthropic
        api_key = api_key_override or settings.ANTHROPIC_API_KEY
        if not api_key:
            return None
        return ChatAnthropic(model_name=model_name or "claude-3-opus-20240229", api_key=api_key)
        
    return None
