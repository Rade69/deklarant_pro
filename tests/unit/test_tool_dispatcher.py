from services.agent.chat.tool_dispatcher import (
    ToolDispatcherWorker,
    route_local_tool,
)
from gui.tabs.agent.widgets.chat_worker import ChatWorker


def test_local_routes_application_scope_faktura():
    call = route_local_tool("pogledaj tab faktura")

    assert call is not None
    assert call.name == "pregled_stanja_aplikacije"
    assert call.arguments == {"scope": "faktura"}


def test_local_routes_application_scope_zaglavlje():
    call = route_local_tool("sta je u zaglavlju")

    assert call is not None
    assert call.name == "pregled_stanja_aplikacije"
    assert call.arguments == {"scope": "zaglavlje"}


def test_local_routes_tariff_validation():
    call = route_local_tool("jesu li tarifni brojevi ispravni")

    assert call is not None
    assert call.name == "provjeri_tarife"
    assert call.arguments == {}


def test_local_routes_single_tariff_search():
    call = route_local_tool("koji je tarifni broj za startno uze")

    assert call is not None
    assert call.name == "pretrazi_tarifu"
    assert call.arguments == {"naziv": "startno uze"}


def test_local_routes_batch_tariff_proposals():
    call = route_local_tool("popuni sve tarifne brojeve")

    assert call is not None
    assert call.name == "predlozi_tarife"
    assert call.arguments == {}


def test_local_routes_origin_lookup():
    call = route_local_tool("zemlja porijekla za kondenzator GCVC")

    assert call is not None
    assert call.name == "pretrazi_porijeklo"
    assert call.arguments == {"naziv": "kondenzator GCVC"}


def test_local_routes_historical_tariff_analysis():
    call = route_local_tool("uporedi tarifne sa istorijom")

    assert call is not None
    assert call.name == "analiziraj_tarifne"
    assert call.arguments == {}


def test_local_routes_similar_products():
    call = route_local_tool("slicni proizvodi za grejac 2000w")

    assert call is not None
    assert call.name == "pronadji_slicne_proizvode"
    assert call.arguments == {"naziv": "grejac 2000w"}


def test_local_unknown_returns_none():
    assert route_local_tool("dobar dan, kako si") is None


def test_dispatch_uses_local_router_before_llm(monkeypatch):
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("LLM provider should not be imported for local routes")

    monkeypatch.setattr(
        "gui.tabs.agent.widgets.llm_provider.LLMProvider",
        fail_if_called,
    )

    result = ToolDispatcherWorker._dispatch("provjeri tarife")

    assert result.error == ""
    assert result.tool_call is not None
    assert result.tool_call.name == "provjeri_tarife"


def test_chat_worker_prompt_forbids_unknown_hallucination():
    prompt = ChatWorker("koji je tarifni broj za X")._system_prompt("servis: unknown")

    assert "servis vrati nepoznato/unknown" in prompt
    assert "nemoj izmišljati šifru" in prompt
