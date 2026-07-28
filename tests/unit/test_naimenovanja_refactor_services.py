from core.draft.draft import DeclarationDraft, InvoiceLine, NaimenovanjeDraft
from gui.tabs.naimenovanja_controller import NaimenovanjaController
from gui.tabs.tab_factory import TabFactory
from services.naimenovanja.naimenovanja_service import NaimenovanjaService


def test_statistical_value_keeps_existing_cost_formula():
    draft = DeclarationDraft()
    draft.kurs = 2
    draft.trosak_1 = "30"
    draft.items = [
        NaimenovanjeDraft(item_id="1", ordinal_no=1, item_value=100),
        NaimenovanjeDraft(item_id="2", ordinal_no=2, item_value=200),
    ]

    result = NaimenovanjaService.compute_statistical_value(draft.items[0], draft)

    assert result == "210.00"


def test_trading_names_respect_rub31_limit_and_keep_invoice_reference():
    draft = DeclarationDraft()
    draft.items = [NaimenovanjeDraft(item_id="1", ordinal_no=1)]
    name = "A" * 300
    line = type(
        "InvoiceLineStub",
        (),
        {
            "assigned_naimenovanje_ordinal": 1,
            "naziv_robe": name,
            "invoice_number": "INV-1",
            "line_no": 1,
        },
    )()
    draft.invoice_lines = [line]

    result = NaimenovanjaService.format_trading_names(draft, 0)

    assert len(result) <= 280
    assert name not in result
    assert "Faktura: INV-1 (rb. 1)" in result
    assert "..." in result


def test_tab_factory_passes_registered_singleton_service(qtbot):
    factory = TabFactory()
    expected = factory.get_di_container().resolve(NaimenovanjaService)
    draft = DeclarationDraft()
    draft.items = [NaimenovanjeDraft(item_id="1", ordinal_no=1)]

    tab = factory.create_tab("naimenovanja", draft=draft)
    qtbot.addWidget(tab)

    assert tab._service is expected
    assert tab.controller.service is expected


def test_assigned_invoice_lines_support_grouped_naimenovanje():
    draft = DeclarationDraft()
    item = NaimenovanjeDraft(item_id="1", ordinal_no=3)
    draft.items = [item]
    draft.invoice_lines = [
        InvoiceLine(naziv_robe="A", assigned_naimenovanje_ordinal=3),
        InvoiceLine(naziv_robe="B", assigned_naimenovanje_ordinal=3),
        InvoiceLine(naziv_robe="C", assigned_naimenovanje_ordinal=4),
    ]

    lines = NaimenovanjaService.assigned_invoice_lines(draft, item)

    assert [line.naziv_robe for line in lines] == ["A", "B"]


def test_pe_document_requires_preference_and_rebuilds_header():
    draft = DeclarationDraft()
    draft.items = [
        NaimenovanjeDraft(
            item_id="1", ordinal_no=1, preference_code="100",
            attached_document4="PE1 123",
        ),
        NaimenovanjeDraft(
            item_id="2", ordinal_no=2, preference_code="",
            attached_document4="PE2 456",
        ),
    ]

    result = NaimenovanjaService().apply_pe_document(draft, 0, "pe1   123")

    assert draft.items[0].attached_document4 == "PE1 123"
    assert draft.items[1].attached_document4 == ""
    assert [(doc.code, doc.number) for doc in draft.header_attached_documents] == [
        ("PE1", "123")
    ]
    assert result.documents == [{"code": "PE1", "number": "123"}]


def test_accepted_tariff_suggestion_does_not_change_origin_or_preference(
    qtbot, monkeypatch
):
    draft = DeclarationDraft()
    draft.items = [
        NaimenovanjeDraft(
            item_id="1",
            ordinal_no=1,
            origin_country_code="CN",
            preference_code="",
        )
    ]
    controller = NaimenovanjaController(lambda: draft)
    qtbot.addWidget(controller.parent()) if controller.parent() else None

    class View:
        current_item_index = 0
        on_dirty = None
        rendered = False

        def render_current_item(self):
            self.rendered = True

    monkeypatch.setattr(
        "services.tariff_facade.TariffFacade.get_instance",
        lambda: type("Facade", (), {"increment_usage": lambda *args: None})(),
    )
    view = View()

    controller.accept_tariff_suggestion(
        view,
        {
            "tarifni_broj": "0805.21.90",
            "zemlja_porijekla": "DE",
            "povlastica": "100",
        },
    )

    assert draft.items[0].tariff_code == "08052190"
    assert draft.items[0].origin_country_code == "CN"
    assert draft.items[0].preference_code == ""
    assert view.rendered is True


def test_tariff_documents_are_deduplicated(monkeypatch):
    draft = DeclarationDraft()
    monkeypatch.setattr(
        "services.tariff_controls_service.get_required_docs",
        lambda code: [{"code": "Y900", "name": "Kontrola"}],
    )
    history = type(
        "History",
        (),
        {
            "get_suggested_docs": lambda self, code, min_count: [
                {"code": "Y900", "name": "Kontrola", "count": 4},
                {"code": "N380", "name": "Faktura", "count": 8},
            ]
        },
    )()
    monkeypatch.setattr(
        "services.tariff_doc_history_service.get_tariff_doc_history_service",
        lambda: history,
    )

    added = NaimenovanjaService.add_tariff_documents(draft, "08052190")

    assert added == 2
    assert [doc.code for doc in draft.header_attached_documents] == [
        "Y900",
        "N380",
    ]
