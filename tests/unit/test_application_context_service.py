from core.draft.draft import DeclarationDraft, InvoiceLine, NaimenovanjeDraft
from gui.tabs.agent.services.chat_intent_handler import _application_context_scope
from services.agent.application_context_service import ApplicationContextService


def test_snapshot_sees_invoice_lines_and_missing_fields():
    draft = DeclarationDraft()
    draft.invoice_lines = [
        InvoiceLine(
            invoice_number="A-1",
            naziv_robe="Roba jedan",
            tarifni_broj="21069098",
            zemlja_porijekla="RS",
            iznos=10,
            bruto_kg=2,
            neto_kg=1,
        ),
        InvoiceLine(
            invoice_number="B-2",
            naziv_robe="Roba dva",
            iznos=0,
        ),
    ]

    snapshot = ApplicationContextService(draft).snapshot()

    invoice = snapshot["invoice_lines"]
    assert invoice["count"] == 2
    assert invoice["invoice_count"] == 2
    assert invoice["total_amount"] == 10
    assert invoice["missing"]["tariff"] == [2]
    assert invoice["missing"]["country"] == [2]
    assert invoice["missing"]["amount"] == [2]


def test_format_naimenovanja_contains_core_fields():
    draft = DeclarationDraft()
    draft.items = [
        NaimenovanjeDraft(
            item_id="1",
            ordinal_no=7,
            tariff_code="21069098",
            origin_country_code="RS",
            preference_code="CEFTAR",
            goods_description="Opis robe za rubriku 31",
            attached_document4="PE1 A",
            gross_mass_kg=3,
            net_mass_kg=2,
            item_value=50,
        )
    ]

    html = ApplicationContextService(draft).format_html("naimenovanja")

    assert "Naimenovanja tab" in html
    assert "Rb.7" in html
    assert "21069098" in html
    assert "CEFTAR" in html
    assert "PE1 A" in html


def test_format_scope_faktura_does_not_include_naimenovanja_section():
    draft = DeclarationDraft()
    draft.invoice_lines = [
        InvoiceLine(invoice_number="A-1", naziv_robe="Roba jedan", iznos=5)
    ]
    draft.items = [
        NaimenovanjeDraft(item_id="1", ordinal_no=1, tariff_code="21069098")
    ]

    html = ApplicationContextService(draft).format_html("faktura")

    assert "Faktura tab" in html
    assert "Naimenovanja tab" not in html


def test_application_context_scope_routes_view_requests_only():
    assert _application_context_scope("Pogledaj tab faktura") == "faktura"
    assert _application_context_scope("Pregledaj naimenovanja u tabu") == "naimenovanja"
    assert _application_context_scope("Šta je učitano u aplikaciji") == "all"
    assert _application_context_scope("Predloži tarifu za 7 naimenovanje") == ""
