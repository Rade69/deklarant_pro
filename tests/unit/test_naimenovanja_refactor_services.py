from core.draft.draft import DeclarationDraft, NaimenovanjeDraft
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


def test_trading_names_are_not_truncated_in_gui_service():
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

    assert name in result
    assert not result.endswith("...")


def test_tab_factory_passes_registered_singleton_service(qtbot):
    factory = TabFactory()
    expected = factory.get_di_container().resolve(NaimenovanjaService)
    draft = DeclarationDraft()
    draft.items = [NaimenovanjeDraft(item_id="1", ordinal_no=1)]

    tab = factory.create_tab("naimenovanja", draft=draft)
    qtbot.addWidget(tab)

    assert tab._service is expected
    assert tab.controller.service is expected
