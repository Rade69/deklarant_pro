from core.draft import DeclarationDraft, InvoiceLine, NaimenovanjeDraft
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

    import services.tariff.tarifa_service as tarifa_service

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

    import services.tariff.tarifa_service as tarifa_service

    monkeypatch.setattr(
        tarifa_service,
        "validiraj_tarifni_broj",
        lambda code: {"valid": True, "naziv": "opis"},
    )

    handled = handler._resolve_contextual_request(ctrl, "63079098")

    assert handled
    assert "63079098" in ctrl.chat.messages[-1]
    assert "3x" in ctrl.chat.messages[-1]


def test_tariff_suggestion_for_naimenovanje_uses_ordinal_not_literal_search(monkeypatch):
    draft = DeclarationDraft()
    draft.items = [
        NaimenovanjeDraft(
            item_id="7",
            ordinal_no=7,
            tariff_code="21069098",
            goods_description="DIXI dekstroza bomboni",
            origin_country_code="RS",
        )
    ]
    ctrl = _Ctrl(draft)
    calls = []

    def fake_alt(ctrl_arg, item_query="", item_ordinal=None, is_alt=False):
        calls.append((item_query, item_ordinal, is_alt))

    monkeypatch.setattr(handler, "_alternativni_tarifni_za_stavku", fake_alt)

    handled = handler._resolve_contextual_request(ctrl, "Predloži tarifu za 7 naimenovanje")

    assert handled
    assert calls == [("", 7, False)]
    assert ctrl._conversation_context["last_product_name"] == "DIXI dekstroza bomboni"
    assert ctrl._conversation_context["last_tariff_code"] == "21069098"


def test_database_lookup_can_use_previous_naimenovanje_context(monkeypatch):
    draft = DeclarationDraft()
    draft.items = [
        NaimenovanjeDraft(
            item_id="7",
            ordinal_no=7,
            tariff_code="21069098",
            goods_description="DIXI dekstroza bomboni",
        )
    ]
    ctrl = _Ctrl(draft)
    looked_up = []
    monkeypatch.setattr(handler, "_pronadji_slicne_proizvode", lambda _, naziv: looked_up.append(naziv))

    handler._resolve_contextual_request(ctrl, "Naimenovanje broj 7")
    handled = handler._resolve_contextual_request(ctrl, "Pogledaj u bazi podataka za taj proizvod")

    assert handled
    assert looked_up == ["DIXI dekstroza bomboni"]


def test_database_lookup_followup_accepts_ordinal(monkeypatch):
    draft = DeclarationDraft()
    draft.items = [
        NaimenovanjeDraft(
            item_id="7",
            ordinal_no=7,
            tariff_code="21069098",
            goods_description="DIXI dekstroza bomboni",
        )
    ]
    ctrl = _Ctrl(draft)
    looked_up = []
    monkeypatch.setattr(handler, "_pronadji_slicne_proizvode", lambda _, naziv: looked_up.append(naziv))

    first = handler._resolve_contextual_request(ctrl, "Pogledaj u bazi podataka za taj proizvod")
    second = handler._resolve_contextual_request(ctrl, "Iz sedmog naimenovanja")

    assert first
    assert second
    assert looked_up == ["DIXI dekstroza bomboni"]


def test_database_lookup_with_ordinal_does_not_fall_back_to_plain_review(monkeypatch):
    draft = DeclarationDraft()
    draft.items = [
        NaimenovanjeDraft(
            item_id="7",
            ordinal_no=7,
            tariff_code="21069098",
            goods_description="DIXI dekstroza bomboni",
        )
    ]
    ctrl = _Ctrl(draft)
    looked_up = []
    monkeypatch.setattr(handler, "_pronadji_slicne_proizvode", lambda _, naziv: looked_up.append(naziv))

    handled = handler._resolve_contextual_request(ctrl, "Pogledaj u bazi podataka za 7 naimenovanje")

    assert handled
    assert looked_up == ["DIXI dekstroza bomboni"]
    assert ctrl.chat.messages == []


def test_tariff_usage_for_specific_naimenovanje_uses_item_tariff(monkeypatch):
    draft = DeclarationDraft()
    draft.items = [
        NaimenovanjeDraft(
            item_id="7",
            ordinal_no=7,
            tariff_code="21069098",
            goods_description="DIXI dekstroza bomboni",
        )
    ]
    ctrl = _Ctrl(draft)
    used_codes = []
    monkeypatch.setattr(handler, "_prikazi_statistiku_tarife", lambda _, code: used_codes.append(code))

    handled = handler._resolve_contextual_request(
        ctrl,
        "Koliko puta je korišten tarifni broj za sedmo naimenovanje",
    )

    assert handled
    assert used_codes == ["21069098"]


def test_specific_naimenovanje_validation_reports_missing_required_fields():
    draft = DeclarationDraft()
    draft.items = [
        NaimenovanjeDraft(
            item_id="7",
            ordinal_no=7,
            tariff_code="21069098",
            goods_description="DIXI dekstroza bomboni",
        )
    ]
    ctrl = _Ctrl(draft)

    handled = handler._resolve_contextual_request(ctrl, "Provjeri sedmo naimenovanje")

    assert handled
    assert "Rb.7" in ctrl.chat.messages[-1]
    assert "nije kompletno" in ctrl.chat.messages[-1]
    assert "Rb.34" in ctrl.chat.messages[-1]


def test_invoice_tab_specific_line_request_shows_line_not_summary():
    draft = DeclarationDraft()
    draft.invoice_lines = [
        InvoiceLine(invoice_number="IF-1", naziv_robe=f"Roba {i}", iznos=i)
        for i in range(1, 26)
    ]
    draft.invoice_lines[24].naziv_robe = "SVEŽI PEKARSKI KVASAC"
    draft.invoice_lines[24].tarifni_broj = ""
    draft.invoice_lines[24].zemlja_porijekla = "RS"
    draft.invoice_lines[24].kolicina = 30
    draft.invoice_lines[24].iznos = 1932
    draft.invoice_lines[24].bruto_kg = 60
    draft.invoice_lines[24].neto_kg = 60
    ctrl = _Ctrl(draft)

    handled = handler._resolve_contextual_request(ctrl, "Pogledaj u tabu faktura 25 stavku")

    assert handled
    message = ctrl.chat.messages[-1]
    assert "Faktura tab — stavka 25" in message
    assert "SVEŽI PEKARSKI KVASAC" in message
    assert "1932.00 EUR" in message
    assert "Fakture:" not in message


def test_tariff_suggestion_followup_uses_last_invoice_line(monkeypatch):
    draft = DeclarationDraft()
    draft.invoice_lines = [
        InvoiceLine(invoice_number="IF-1", naziv_robe=f"Roba {i}", iznos=i)
        for i in range(1, 26)
    ]
    draft.invoice_lines[24].naziv_robe = "SVEŽI PEKARSKI KVASAC"
    ctrl = _Ctrl(draft)
    calls = []

    def fake_alt(ctrl_arg, item_query="", item_ordinal=None, is_alt=False):
        calls.append((item_query, item_ordinal, is_alt))

    monkeypatch.setattr(handler, "_alternativni_tarifni_za_stavku", fake_alt)

    first = handler._resolve_contextual_request(ctrl, "Provjeri stavku 25 u tabu faktura")
    second = handler._resolve_contextual_request(ctrl, "Predloži mi tarifni broj za ovu stavku")

    assert first
    assert second
    assert calls == [("SVEŽI PEKARSKI KVASAC", None, False)]
    assert ctrl._conversation_context["last_product_name"] == "SVEŽI PEKARSKI KVASAC"


def test_explicit_tariff_insert_updates_last_invoice_line_and_can_save():
    draft = DeclarationDraft()
    draft.invoice_lines = [
        InvoiceLine(invoice_number="IF-1", naziv_robe=f"Roba {i}", iznos=i)
        for i in range(1, 26)
    ]
    draft.invoice_lines[24].naziv_robe = "SVEŽI PEKARSKI KVASAC"
    ctrl = _Ctrl(draft)
    learned = []

    class _TariffSvc:
        def learn_tariff(self, naziv_robe, tarifni_broj):
            learned.append((naziv_robe, tarifni_broj))

    ctrl.tariff_svc = _TariffSvc()

    handler._resolve_contextual_request(ctrl, "Provjeri stavku 25 u tabu faktura")
    handled = handler._resolve_contextual_request(
        ctrl,
        "21021000 ubaci ovaj tarifni broj i sačuvaj u bazi podataka za ubuduće",
    )

    assert handled
    assert draft.invoice_lines[24].tarifni_broj == "21021000"
    assert learned == [("SVEŽI PEKARSKI KVASAC", "21021000")]
    assert ctrl._conversation_context["last_tariff_code"] == "21021000"


def test_insert_that_number_uses_last_tariff_and_last_invoice_line():
    draft = DeclarationDraft()
    draft.invoice_lines = [
        InvoiceLine(invoice_number="IF-1", naziv_robe=f"Roba {i}", iznos=i)
        for i in range(1, 26)
    ]
    draft.invoice_lines[24].naziv_robe = "SVEŽI PEKARSKI KVASAC"
    ctrl = _Ctrl(draft)

    handler._resolve_contextual_request(ctrl, "Provjeri stavku 25 u tabu faktura")
    handler._remember_tariff_context(ctrl, "21021000", product_name="SVEŽI PEKARSKI KVASAC")
    handled = handler._resolve_contextual_request(ctrl, "Ubaci taj taj broj u tabelu tabu faktira")

    assert handled
    assert draft.invoice_lines[24].tarifni_broj == "21021000"


def test_origin_lookup_uses_last_invoice_line_with_typo(monkeypatch):
    draft = DeclarationDraft()
    draft.invoice_lines = [
        InvoiceLine(invoice_number="639/26", naziv_robe="DEPIWHITE ADV.KREM 40 ml", tarifni_broj="33049900")
    ]
    ctrl = _Ctrl(draft)
    looked_up = []
    monkeypatch.setattr(handler, "_pretrazi_porijeklo", lambda _, naziv: looked_up.append(naziv))

    first = handler._resolve_contextual_request(ctrl, "pogledaj stavku 1 u tabu faktura")
    second = handler._resolve_contextual_request(
        ctrl,
        "Potraži u bazi znanja zemlju porijkla za zaj proizvod",
    )

    assert first
    assert second
    assert looked_up == ["DEPIWHITE ADV.KREM 40 ml"]


def test_origin_lookup_extracts_product_before_misspelled_origin(monkeypatch):
    ctrl = _Ctrl(DeclarationDraft())
    looked_up = []
    monkeypatch.setattr(handler, "_pretrazi_porijeklo", lambda _, naziv: looked_up.append(naziv))

    handled = handler._resolve_contextual_request(
        ctrl,
        "Potraći za DEPIWHITE ADV.KREM 40 ml kojeg je prijekla u ranijim deklaracijama",
    )

    assert handled
    assert looked_up == ["DEPIWHITE ADV.KREM 40 ml"]


def test_missing_country_question_lists_invoice_rows_not_origin_search(monkeypatch):
    draft = DeclarationDraft()
    draft.invoice_lines = [
        InvoiceLine(invoice_number="639/26", naziv_robe="VITIX gel 20ml", tarifni_broj="33049900", zemlja_porijekla="FR"),
        InvoiceLine(invoice_number="639/26", naziv_robe="DEPIWHITE ADV.KREM 40 ml", tarifni_broj="33049900", zemlja_porijekla=""),
        InvoiceLine(invoice_number="639/26", naziv_robe="VITICOLOR gel 50ml", tarifni_broj="33049900", zemlja_porijekla=""),
    ]
    ctrl = _Ctrl(draft)
    looked_up = []
    monkeypatch.setattr(handler, "_pretrazi_porijeklo", lambda _, naziv: looked_up.append(naziv))

    handler._pregled_stanja_aplikacije(ctrl, "faktura")
    handled = handler._resolve_contextual_request(
        ctrl,
        "Ima li neka stavka da nema zemlju porijekla u toj tabeli",
    )

    assert handled
    assert looked_up == []
    message = ctrl.chat.messages[-1]
    assert "Faktura tab — stavke bez zemlje porijekla" in message
    assert "Ukupno: <b>2</b>" in message
    assert "Rb.2" in message
    assert "Rb.3" in message


def test_missing_country_request_with_typos_does_not_become_origin_lookup(monkeypatch):
    draft = DeclarationDraft()
    draft.invoice_lines = [
        InvoiceLine(invoice_number="639/26", naziv_robe="VITIX gel 20ml", tarifni_broj="33049900", zemlja_porijekla="FR"),
        InvoiceLine(invoice_number="639/26", naziv_robe="DEPIWHITE ADV.KREM 40 ml", tarifni_broj="33049900", zemlja_porijekla=""),
    ]
    ctrl = _Ctrl(draft)
    looked_up = []
    monkeypatch.setattr(handler, "_pretrazi_porijeklo", lambda _, naziv: looked_up.append(naziv))

    handled = handler._resolve_contextual_request(
        ctrl,
        "U tabu faktira u tabeli nađi stvake bez zemlje porijekla",
    )

    assert handled
    assert looked_up == []
    assert "Faktura tab — stavke bez zemlje porijekla" in ctrl.chat.messages[-1]
    assert "DEPIWHITE ADV.KREM 40 ml" in ctrl.chat.messages[-1]


def test_missing_country_request_is_not_extracted_as_origin_product_query():
    assert handler._extract_origin_product_query(
        "U tabu faktira u tabeli nađi stvake bez zemlje porijekla"
    ) == ""
