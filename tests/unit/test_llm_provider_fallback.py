"""
Faza 8: LLM provider fallback (402/429/timeout) — regresioni testovi.

Pokriva pravila iz agent_tasks/2026-06-10_plan_unapredjenja_carinskog_agenta.md:
- 402 "Insufficient Balance" -> jasna poruka na srpskom, bez stack trace-a.
- Lokalni tool rezultat ima prioritet -> LLM se ne poziva ako route_local_tool pogodi.
- Provider fallback (Groq -> Gemini -> OpenRouter -> DeepSeek) je ogranicen,
  bez beskonacnih retry petlji.

Bez LLM-a, bez API kljuca - sve LLM/API pozivi su mockovani.
"""
import pytest

from gui.tabs.agent.widgets.llm_provider import LLMProvider, parse_llm_error
from services.agent.chat.tool_dispatcher import ToolDispatcherWorker


# ── parse_llm_error — poruke po tipu greske ─────────────────────────────────

def test_parse_llm_error_402_insufficient_balance():
    exc = Exception(
        "Error code: 402 - {'error': {'message': 'Insufficient Balance', "
        "'type': 'unknown_error'}}"
    )
    msg = parse_llm_error(exc)

    assert "💳" in msg
    assert "402" in msg
    assert "Traceback" not in msg
    assert len(msg) < 300


def test_parse_llm_error_429_with_used_and_limit():
    exc = Exception(
        "Error: 429 rate_limit_exceeded. Used 12345 of Limit 100000. "
        "Please try again in 2m30s."
    )
    msg = parse_llm_error(exc)

    assert "Dnevni limit tokena iskorišten (12345/100000)" in msg
    assert "2m30s" in msg


def test_parse_llm_error_429_without_used_and_limit():
    exc = Exception("429 Too Many Requests. Please try again in 5 seconds.")
    msg = parse_llm_error(exc)

    assert msg.startswith("⏳ AI limit dostignut.")
    assert "5 seconds" in msg


def test_parse_llm_error_401_invalid_api_key():
    exc = Exception("Error code: 401 - invalid_api_key")
    msg = parse_llm_error(exc)

    assert "🔑" in msg
    assert "GROQ_API_KEY" in msg


def test_parse_llm_error_timeout():
    exc = Exception("Connection timeout while contacting API")
    msg = parse_llm_error(exc)

    assert "🌐" in msg


def test_parse_llm_error_generic_fallback_is_truncated():
    exc = Exception("X" * 500)
    msg = parse_llm_error(exc)

    assert msg.startswith("⚠️ AI greška:")
    assert len(msg) < 250


# ── Bounded provider fallback (bez beskonacnih retry petlji) ───────────────

@pytest.fixture
def all_providers_configured(monkeypatch):
    monkeypatch.setattr(LLMProvider, "has_groq", lambda self: True)
    monkeypatch.setattr(LLMProvider, "has_gemini", lambda self: True)
    monkeypatch.setattr(LLMProvider, "has_openrouter", lambda self: True)
    monkeypatch.setattr(LLMProvider, "has_deepseek", lambda self: True)


def _raising(calls: list, name: str):
    def _inner(self, *args, **kwargs):
        calls.append(name)
        raise RuntimeError(f"{name} down")
    return _inner


def test_stream_chat_tries_each_provider_exactly_once_then_raises(
    monkeypatch, all_providers_configured
):
    calls: list[str] = []
    monkeypatch.setattr(LLMProvider, "_groq_stream", _raising(calls, "groq"))
    monkeypatch.setattr(LLMProvider, "_gemini_stream", _raising(calls, "gemini"))
    monkeypatch.setattr(LLMProvider, "_openrouter_stream", _raising(calls, "openrouter"))
    monkeypatch.setattr(LLMProvider, "_deepseek_stream", _raising(calls, "deepseek"))

    provider = LLMProvider()

    with pytest.raises(RuntimeError, match="deepseek down"):
        list(provider.stream_chat([{"role": "user", "content": "test"}]))

    assert calls == ["groq", "gemini", "openrouter", "deepseek"]


def test_complete_tries_each_provider_exactly_once_then_raises(
    monkeypatch, all_providers_configured
):
    calls: list[str] = []
    monkeypatch.setattr(LLMProvider, "_groq_complete", _raising(calls, "groq"))
    monkeypatch.setattr(LLMProvider, "_gemini_complete", _raising(calls, "gemini"))
    monkeypatch.setattr(LLMProvider, "_openrouter_complete", _raising(calls, "openrouter"))
    monkeypatch.setattr(LLMProvider, "_deepseek_complete", _raising(calls, "deepseek"))

    provider = LLMProvider()

    with pytest.raises(RuntimeError, match="deepseek down"):
        provider.complete([{"role": "user", "content": "test"}])

    assert calls == ["groq", "gemini", "openrouter", "deepseek"]


def test_stream_chat_raises_clear_error_when_no_provider_configured(monkeypatch):
    monkeypatch.setattr(LLMProvider, "has_groq", lambda self: False)
    monkeypatch.setattr(LLMProvider, "has_gemini", lambda self: False)
    monkeypatch.setattr(LLMProvider, "has_openrouter", lambda self: False)
    monkeypatch.setattr(LLMProvider, "has_deepseek", lambda self: False)

    provider = LLMProvider()

    with pytest.raises(RuntimeError, match="Nema dostupnog AI providera"):
        list(provider.stream_chat([{"role": "user", "content": "test"}]))


# ── ToolDispatcher: lokalni tool prvo, LLM 402 -> civilizovana poruka ──────

def test_dispatch_returns_402_message_without_stack_trace(monkeypatch):
    """Kad DeepSeek vrati 402 Insufficient Balance, dispatcher to prevodi
    u jasnu poruku (bez stack trace-a) umjesto da propagira izuzetak."""
    monkeypatch.setattr(LLMProvider, "has_deepseek", lambda self: True)

    class _FakeCompletions:
        def create(self, **kwargs):
            raise Exception(
                "Error code: 402 - {'error': {'message': 'Insufficient Balance', "
                "'type': 'unknown_error'}}"
            )

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeOpenAI:
        def __init__(self, *args, **kwargs):
            self.chat = _FakeChat()

    monkeypatch.setattr("openai.OpenAI", _FakeOpenAI)

    # Poruka koja NE pogađa route_local_tool (vidi test_tool_dispatcher.py)
    result = ToolDispatcherWorker._dispatch("dobar dan, kako si")

    assert result.tool_call is None
    assert result.plain_text == ""
    assert "💳" in result.error
    assert "Traceback" not in result.error
