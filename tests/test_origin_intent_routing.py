import importlib.util
from pathlib import Path


MODULE_PATH = (
    Path(__file__).parent.parent
    / "gui"
    / "tabs"
    / "agent"
    / "services"
    / "chat_intent_handler.py"
)
spec = importlib.util.spec_from_file_location("chat_intent_handler_for_test", MODULE_PATH)
chat_intent_handler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chat_intent_handler)
_extract_origin_product_query = chat_intent_handler._extract_origin_product_query
_extract_web_search_subject = chat_intent_handler._extract_web_search_subject
_resolve_followup = chat_intent_handler._resolve_followup


def test_extract_origin_query_from_product_prefix():
    message = "KONDENZATOR GCVC RD 045.2/24-53,potraži porijeklo ovog proizvoda"

    assert _extract_origin_product_query(message) == "KONDENZATOR GCVC RD 045.2/24-53"


def test_extract_origin_query_after_origin_phrase():
    message = "Potraži zemlju porijekla za KONDENZATOR GCVC RD 045.2/24-53"

    assert _extract_origin_product_query(message) == "KONDENZATOR GCVC RD 045.2/24-53"


def test_origin_query_does_not_intercept_column_update():
    message = "upiši porijeklo TR u fakturu"

    assert _extract_origin_product_query(message) == ""


def test_extract_web_search_uses_previous_subject_when_pronoun_only():
    message = "Možeš li ga potražiti na internetu"

    assert _extract_web_search_subject(message) == ""


def test_followup_web_request_sets_archive_action_from_last_subject():
    ctrl = _DummyCtrl()
    ctrl._conversation_context = {
        "last_subject": "KONDENZATOR GCVC RD 045.2/24-53"
    }

    handled = _resolve_followup(ctrl, "Možeš li ga potražiti na internetu")

    assert handled is True
    assert ctrl._conversation_context["last_offered_action"]["action"] == "search_archive"
    assert ctrl._conversation_context["last_offered_action"]["subject"] == "KONDENZATOR GCVC RD 045.2/24-53"
    assert "Pretraži" in ctrl.view.chat.messages[-1]


def test_followup_confirmation_executes_last_offered_archive_action(monkeypatch):
    ctrl = _DummyCtrl()
    ctrl._conversation_context = {
        "last_subject": "KONDENZATOR GCVC RD 045.2/24-53",
        "last_offered_action": {
            "action": "search_archive",
            "subject": "KONDENZATOR GCVC RD 045.2/24-53",
        },
    }
    calls = []

    def fake_search(inner_ctrl, subject):
        calls.append((inner_ctrl, subject))

    monkeypatch.setattr(chat_intent_handler, "_pretrazi_arhiv_za_proizvod", fake_search)

    handled = _resolve_followup(ctrl, "Pretraži")

    assert handled is True
    assert calls == [(ctrl, "KONDENZATOR GCVC RD 045.2/24-53")]
    assert "last_offered_action" not in ctrl._conversation_context


class _DummyChat:
    def __init__(self):
        self.messages = []

    def add_agent_message(self, text):
        self.messages.append(text)


class _DummyView:
    def __init__(self):
        self.chat = _DummyChat()

    def get_chat_panel(self):
        return self.chat


class _DummyCtrl:
    def __init__(self):
        self.view = _DummyView()
