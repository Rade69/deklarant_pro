from core.draft import DeclarationDraft, NaimenovanjeDraft
from gui.tabs.agent.services import chat_intent_handler as handler


class _Chat:
    def __init__(self):
        self.messages = []
        self.activities = []

    def add_agent_message(self, message):
        self.messages.append(message)

    def add_activity(self, message):
        self.activities.append(message)


class _View:
    def __init__(self, chat):
        self._chat = chat

    def get_chat_panel(self):
        return self._chat


class _Ctrl:
    def __init__(self, draft):
        self.draft = draft
        self.chat = _Chat()
        self.view = _View(self.chat)


def test_naimenovanje_request_remembers_tariff_context():
    draft = DeclarationDraft()
    draft.items = [
        NaimenovanjeDraft(
            item_id="18",
            ordinal_no=18,
            tariff_code="63079098",
            goods_description="BORT 112900 B.R.Z.palac lev XL",
            origin_country_code="DE",
        )
    ]
    ctrl = _Ctrl(draft)

    handled = handler._resolve_contextual_request(ctrl, "Naimenovanje broj 18")

    assert handled
    assert ctrl._conversation_context["last_naimenovanje_ordinal"] == 18
    assert ctrl._conversation_context["last_tariff_code"] == "63079098"
    assert "Rb.33" in ctrl.chat.messages[-1]


def test_followup_usage_question_uses_last_tariff_context(monkeypatch):
    draft = DeclarationDraft()
    draft.items = [
        NaimenovanjeDraft(
            item_id="18",
            ordinal_no=18,
            tariff_code="63079098",
            goods_description="BORT 112900 B.R.Z.palac lev XL",
        )
    ]
    ctrl = _Ctrl(draft)
    handler._resolve_contextual_request(ctrl, "Naimenovanje broj 18")

    monkeypatch.setattr(
        handler,
        "_tariff_usage_stats",
        lambda code: {
            "total_usage": 13,
            "rows": 2,
            "suppliers": 1,
            "examples": [
                {
                    "naziv_robe": "BORT 112900 B.R.Z.palac lev XL",
                    "supplier": "MEDIKO",
                    "zemlja_porijekla": "DE",
                    "usage_count": 13,
                }
            ],
        },
    )

    import services.tarifa_service as tarifa_service

    monkeypatch.setattr(
        tarifa_service,
        "validiraj_tarifni_broj",
        lambda code: {"valid": True, "naziv": "- - - - ostali"},
    )

    handled = handler._resolve_contextual_request(
        ctrl,
        "Koliko puta je korišten taj tarifni broj",
    )

    assert handled
    assert "63079098" in ctrl.chat.messages[-1]
    assert "13x" in ctrl.chat.messages[-1]


def test_pending_usage_question_uses_next_numeric_message(monkeypatch):
    ctrl = _Ctrl(DeclarationDraft())

    handled = handler._resolve_contextual_request(
        ctrl,
        "Šta istorijski stoji za taj tarifni broj",
    )

    assert handled
    assert ctrl._conversation_context["last_offered_action"]["action"] == "tariff_usage"

    monkeypatch.setattr(
        handler,
        "_tariff_usage_stats",
        lambda code: {"total_usage": 3, "rows": 1, "suppliers": 1, "examples": []},
    )

    import services.tarifa_service as tarifa_service

    monkeypatch.setattr(
        tarifa_service,
        "validiraj_tarifni_broj",
        lambda code: {"valid": True, "naziv": "opis"},
    )

    handled = handler._resolve_contextual_request(ctrl, "63079098")

    assert handled
    assert "63079098" in ctrl.chat.messages[-1]
    assert "3x" in ctrl.chat.messages[-1]
