"""Failover behavior of ReliabilityManager with a mocked LLM (no network)."""
import pytest
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from pydantic import BaseModel

from app.services import reliability
from app.services.reliability import ReliabilityManager

class Output(BaseModel):
    text: str

PROMPT = ChatPromptTemplate.from_messages([("user", "{q}")])

class FakeLLM:
    def __init__(self, behavior):
        self._behavior = behavior

    def with_structured_output(self, schema):
        return RunnableLambda(lambda _inputs: self._behavior())

@pytest.fixture(autouse=True)
def reset_keys(monkeypatch):
    monkeypatch.setattr(ReliabilityManager, "KEYS", ["key-a", "key-b"])
    monkeypatch.setattr(ReliabilityManager, "_initialized", True)

def _patch_llm(monkeypatch, factory):
    monkeypatch.setattr(reliability, "get_llm", factory)

def test_success_on_first_attempt(monkeypatch):
    _patch_llm(monkeypatch, lambda provider, model_name, api_key_override: FakeLLM(lambda: Output(text="ok")))
    result, updates = ReliabilityManager.invoke(PROMPT, Output, {"q": "hi"}, {})
    assert result.text == "ok"
    assert updates["provider_failovers"] == 0
    assert updates["global_context"]["final_model_used"] == ReliabilityManager.MODELS[0]

def test_rate_limit_rotates_to_next_key(monkeypatch):
    calls = []

    def factory(provider, model_name, api_key_override):
        calls.append(api_key_override)
        if api_key_override == "key-a":
            return FakeLLM(lambda: (_ for _ in ()).throw(Exception("429 rate limit exceeded")))
        return FakeLLM(lambda: Output(text="rotated"))

    _patch_llm(monkeypatch, factory)
    result, updates = ReliabilityManager.invoke(PROMPT, Output, {"q": "hi"}, {})
    assert result.text == "rotated"
    assert updates["provider_failovers"] == 1
    assert calls == ["key-a", "key-b"]

def test_decommissioned_model_falls_back_to_next_model(monkeypatch):
    def factory(provider, model_name, api_key_override):
        if model_name == ReliabilityManager.MODELS[0]:
            return FakeLLM(lambda: (_ for _ in ()).throw(Exception("model_decommissioned")))
        return FakeLLM(lambda: Output(text="fallback"))

    _patch_llm(monkeypatch, factory)
    result, updates = ReliabilityManager.invoke(PROMPT, Output, {"q": "hi"}, {})
    assert result.text == "fallback"
    assert updates["model_failovers"] == 1
    assert updates["global_context"]["final_model_used"] == ReliabilityManager.MODELS[1]

def test_exhaustion_raises(monkeypatch):
    _patch_llm(monkeypatch, lambda provider, model_name, api_key_override: FakeLLM(
        lambda: (_ for _ in ()).throw(Exception("429 rate limit exceeded"))))
    with pytest.raises(Exception, match="exhausted"):
        ReliabilityManager.invoke(PROMPT, Output, {"q": "hi"}, {})

def test_non_retryable_error_propagates(monkeypatch):
    _patch_llm(monkeypatch, lambda provider, model_name, api_key_override: FakeLLM(
        lambda: (_ for _ in ()).throw(ValueError("boom"))))
    with pytest.raises(ValueError, match="boom"):
        ReliabilityManager.invoke(PROMPT, Output, {"q": "hi"}, {})
