"""
Faza 8 (2026-06-12) + Faza B agent mode plana (2026-07-19): LLM provider
fallback (402/429/timeout) i complete_with_tools() — regresioni testovi.

Pokriva:
- 402 "Insufficient Balance" -> jasna poruka na srpskom, bez stack trace-a.
- Lokalni tool rezultat ima prioritet -> LLM se ne poziva ako route_local_tool pogodi.
- Provider fallback (Groq -> Gemini) je ogranicen, bez beskonacnih retry petlji.
  OpenRouter i DeepSeek su uklonjeni iz lanca 2026-07-19 (Faza B) - vidi
  docs/agent/AGENT_MODE_IMPROVEMENT_IMPLEMENTATION_PLAN.md.
- complete_with_tools(): Groq -> Gemini tool-use, nevazeci JSON, nepoznat
  alat, koji je provider stvarno zavrsio poziv (audit).

Bez LLM-a, bez API kljuca - sve LLM/API pozivi su mockovani.
"""
import pytest

from gui.tabs.agent.widgets.llm_provider import LLMProvider, ProviderToolResponse, parse_llm_error
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


def test_parse_llm_error_ne_pominje_uklonjene_providere():
    """OpenRouter/DeepSeek su uklonjeni iz lanca - poruke ih ne smiju spominjati."""
    exc = Exception("Error code: 401 - invalid_api_key")
    msg = parse_llm_error(exc)
    assert "OPENROUTER" not in msg.upper()
    assert "DEEPSEEK" not in msg.upper()


# ── LLMProvider vise nema OpenRouter/DeepSeek (Faza B) ──────────────────────

def test_llm_provider_nema_openrouter_deepseek_metode():
    provider = LLMProvider()
    assert not hasattr(provider, "has_openrouter")
    assert not hasattr(provider, "has_deepseek")
    assert not hasattr(provider, "openrouter_key")
    assert not hasattr(provider, "deepseek_key")


def test_active_provider_ogranicen_na_groq_gemini(monkeypatch):
    monkeypatch.setattr(LLMProvider, "has_groq", lambda self: False)
    monkeypatch.setattr(LLMProvider, "has_gemini", lambda self: False)
    provider = LLMProvider()
    assert provider.active_provider() == "none"


# ── Bounded provider fallback (bez beskonacnih retry petlji) ───────────────

@pytest.fixture
def all_providers_configured(monkeypatch):
    monkeypatch.setattr(LLMProvider, "has_groq", lambda self: True)
    monkeypatch.setattr(LLMProvider, "has_gemini", lambda self: True)


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

    provider = LLMProvider()

    with pytest.raises(RuntimeError, match="gemini down"):
        list(provider.stream_chat([{"role": "user", "content": "test"}]))

    assert calls == ["groq", "gemini"]


def test_complete_tries_each_provider_exactly_once_then_raises(
    monkeypatch, all_providers_configured
):
    calls: list[str] = []
    monkeypatch.setattr(LLMProvider, "_groq_complete", _raising(calls, "groq"))
    monkeypatch.setattr(LLMProvider, "_gemini_complete", _raising(calls, "gemini"))

    provider = LLMProvider()

    with pytest.raises(RuntimeError, match="gemini down"):
        provider.complete([{"role": "user", "content": "test"}])

    assert calls == ["groq", "gemini"]


def test_stream_chat_raises_clear_error_when_no_provider_configured(monkeypatch):
    monkeypatch.setattr(LLMProvider, "has_groq", lambda self: False)
    monkeypatch.setattr(LLMProvider, "has_gemini", lambda self: False)

    provider = LLMProvider()

    with pytest.raises(RuntimeError, match="Nema dostupnog AI providera"):
        list(provider.stream_chat([{"role": "user", "content": "test"}]))


# ── complete_with_tools() — Faza B ──────────────────────────────────────────

class _FakeToolCallFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _FakeGroqToolCall:
    def __init__(self, name, arguments):
        self.function = _FakeToolCallFunction(name, arguments)


class _FakeGroqMessage:
    def __init__(self, tool_calls=None, content=""):
        self.tool_calls = tool_calls
        self.content = content


class _FakeGroqChoice:
    def __init__(self, message):
        self.message = message


class _FakeGroqResponse:
    def __init__(self, message):
        self.choices = [_FakeGroqChoice(message)]


def _fake_groq_client_factory(response=None, exc=None):
    class _FakeCompletions:
        def create(self, **kwargs):
            if exc:
                raise exc
            return response

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeGroq:
        def __init__(self, *args, **kwargs):
            self.chat = _FakeChat()

    return _FakeGroq


def test_complete_with_tools_groq_returns_tool_call(monkeypatch):
    monkeypatch.setattr(LLMProvider, "has_groq", lambda self: True)
    monkeypatch.setattr(LLMProvider, "has_gemini", lambda self: False)

    msg = _FakeGroqMessage(tool_calls=[
        _FakeGroqToolCall("pretrazi_tarifu", '{"naziv": "čelik"}')
    ])
    monkeypatch.setattr("groq.Groq", _fake_groq_client_factory(_FakeGroqResponse(msg)))

    provider = LLMProvider()
    result = provider.complete_with_tools(
        [{"role": "user", "content": "tarifa za čelik"}], tools=[]
    )

    assert isinstance(result, ProviderToolResponse)
    assert result.tool_name == "pretrazi_tarifu"
    assert result.tool_arguments == {"naziv": "čelik"}
    assert result.provider == "groq"
    assert result.error == ""


def test_complete_with_tools_invalid_json_vraca_prazne_argumente(monkeypatch):
    monkeypatch.setattr(LLMProvider, "has_groq", lambda self: True)
    monkeypatch.setattr(LLMProvider, "has_gemini", lambda self: False)

    msg = _FakeGroqMessage(tool_calls=[
        _FakeGroqToolCall("upisi_u_kolonu", "nije-validan-json{{{")
    ])
    monkeypatch.setattr("groq.Groq", _fake_groq_client_factory(_FakeGroqResponse(msg)))

    provider = LLMProvider()
    result = provider.complete_with_tools([{"role": "user", "content": "x"}], tools=[])

    assert result.tool_name == "upisi_u_kolonu"
    assert result.tool_arguments == {}


def test_complete_with_tools_plain_text_kad_nema_tool_call(monkeypatch):
    monkeypatch.setattr(LLMProvider, "has_groq", lambda self: True)
    monkeypatch.setattr(LLMProvider, "has_gemini", lambda self: False)

    msg = _FakeGroqMessage(tool_calls=None, content="Zdravo, kako mogu pomoći?")
    monkeypatch.setattr("groq.Groq", _fake_groq_client_factory(_FakeGroqResponse(msg)))

    provider = LLMProvider()
    result = provider.complete_with_tools([{"role": "user", "content": "zdravo"}], tools=[])

    assert result.tool_name is None
    assert result.content == "Zdravo, kako mogu pomoći?"
    assert result.provider == "groq"


def test_complete_with_tools_pada_na_gemini_kad_groq_ne_uspije(monkeypatch):
    """Audit: response.provider mora pokazati provider koji je STVARNO završio poziv."""
    monkeypatch.setattr(LLMProvider, "has_groq", lambda self: True)
    monkeypatch.setattr(LLMProvider, "has_gemini", lambda self: True)
    monkeypatch.setattr(
        LLMProvider, "_groq_complete_with_tools",
        lambda self, messages, tools, max_tokens: (_ for _ in ()).throw(RuntimeError("groq down")),
    )
    monkeypatch.setattr(
        LLMProvider, "_gemini_complete_with_tools",
        lambda self, messages, tools, max_tokens: ProviderToolResponse(
            content="odgovor sa gemini", provider="gemini"
        ),
    )

    provider = LLMProvider()
    result = provider.complete_with_tools([{"role": "user", "content": "x"}], tools=[])

    assert result.provider == "gemini"
    assert result.content == "odgovor sa gemini"


def test_complete_with_tools_bez_providera_vraca_jasnu_gresku(monkeypatch):
    monkeypatch.setattr(LLMProvider, "has_groq", lambda self: False)
    monkeypatch.setattr(LLMProvider, "has_gemini", lambda self: False)

    provider = LLMProvider()
    result = provider.complete_with_tools([{"role": "user", "content": "x"}], tools=[])

    assert result.error
    assert "GROQ_API_KEY" in result.error or "GEMINI_API_KEY" in result.error


# ── ToolDispatcher: lokalni tool prvo, LLM 402 -> civilizovana poruka ──────

def test_dispatch_returns_402_message_without_stack_trace(monkeypatch):
    """Kad Groq vrati 402 Insufficient Balance, dispatcher to prevodi
    u jasnu poruku (bez stack trace-a) umjesto da propagira izuzetak."""
    monkeypatch.setattr(LLMProvider, "has_groq", lambda self: True)
    monkeypatch.setattr(LLMProvider, "has_gemini", lambda self: False)

    exc = Exception(
        "Error code: 402 - {'error': {'message': 'Insufficient Balance', "
        "'type': 'unknown_error'}}"
    )
    monkeypatch.setattr("groq.Groq", _fake_groq_client_factory(exc=exc))

    # Poruka koja NE pogađa route_local_tool (vidi test_tool_dispatcher.py)
    result = ToolDispatcherWorker._dispatch("dobar dan, kako si")

    assert result.tool_call is None
    assert result.plain_text == ""
    assert "💳" in result.error
    assert "Traceback" not in result.error


def test_dispatch_ne_zahtijeva_deepseek_kljuc(monkeypatch):
    """Dispatcher radi sa samo GROQ_API_KEY - DEEPSEEK_API_KEY vise nije potreban."""
    monkeypatch.setattr(LLMProvider, "has_groq", lambda self: True)
    monkeypatch.setattr(LLMProvider, "has_gemini", lambda self: False)

    msg = _FakeGroqMessage(tool_calls=None, content="ok")
    monkeypatch.setattr("groq.Groq", _fake_groq_client_factory(_FakeGroqResponse(msg)))

    result = ToolDispatcherWorker._dispatch("dobar dan, kako si")

    assert result.error == ""
    assert result.plain_text == "ok"


def test_dispatch_odbija_nepoznat_alat_od_providera(monkeypatch):
    """Ako LLM 'izmisli' ime alata koje nije u tool_policy registry-ju,
    dispatcher to tretira kao grešku, ne kao validan tool_call (fail-closed,
    vidi services/agent/chat/tool_policy.py — Faza A)."""
    monkeypatch.setattr(LLMProvider, "has_groq", lambda self: True)
    monkeypatch.setattr(LLMProvider, "has_gemini", lambda self: False)

    msg = _FakeGroqMessage(tool_calls=[
        _FakeGroqToolCall("izmisljeni_alat_koji_ne_postoji", "{}")
    ])
    monkeypatch.setattr("groq.Groq", _fake_groq_client_factory(_FakeGroqResponse(msg)))

    result = ToolDispatcherWorker._dispatch("dobar dan, kako si")

    assert result.tool_call is None
    assert "nepoznat alat" in result.error.lower()
