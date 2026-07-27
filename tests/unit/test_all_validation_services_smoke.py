"""
Smoke test za sve validacione servise — Faza 10 (evaluacija i release hardening).

Provjerava da svi servisi iz Faza 3-9 rade sa praznim i minimalno popunjenim draftom.
"""
from __future__ import annotations

from core.draft.draft import DeclarationDraft, InvoiceLine, NaimenovanjeDraft


def _make_minimal_draft():
    d = DeclarationDraft()
    d.deklaracija_tip = "IM"
    d.izvoznik_naziv = "Exporter d.o.o."
    d.primalac_naziv = "Importer d.o.o."
    d.deklarant_naziv = "Deklarant d.o.o."
    d.valuta = "EUR"
    d.invoice_lines = [InvoiceLine(
        naziv_robe="Test proizvod", tarifni_broj="08052190",
        bruto_kg=100.0, neto_kg=90.0, iznos=500.0,
        kolicina=10, jm="kom", zemlja_porijekla="DE",
    )]
    d.items = [NaimenovanjeDraft(
        item_id="1", ordinal_no=1,
        tariff_code="08052190", goods_description="Test proizvod",
        origin_country_code="DE", gross_mass_kg=100.0, net_mass_kg=90.0,
    )]
    return d


class TestAllValidationServices:
    """Svi servisi iz Faza 3-9 rade sa minimalno popunjenim draftom."""

    def test_invoice_review_service(self):
        from services.agent.validation.invoice_review_service import provjeri_fakturu
        d = _make_minimal_draft()
        summary = provjeri_fakturu(d)
        assert summary.target == "invoice"

    def test_items_review_service(self):
        from services.agent.validation.items_review_service import provjeri_naimenovanja
        d = _make_minimal_draft()
        summary = provjeri_naimenovanja(d)
        assert summary.target == "items"

    def test_header_review_service(self):
        from services.agent.validation.header_review_service import provjeri_zaglavlje
        d = _make_minimal_draft()
        summary = provjeri_zaglavlje(d)
        assert summary.target == "header"

    def test_cross_tab_service(self):
        from services.agent.validation.header_review_service import provjeri_usklađenost_tabova
        d = _make_minimal_draft()
        summary = provjeri_usklađenost_tabova(d)
        assert summary.target == "declaration"

    def test_xml_readiness_service(self):
        from services.agent.validation.xml_readiness_service import provjeri_spremnost_za_xml
        d = _make_minimal_draft()
        result = provjeri_spremnost_za_xml(d)
        assert result.status is not None
        assert len(result.summaries) >= 4

    def test_renderer(self):
        from services.agent.validation.renderer import render_summary_html
        from services.agent.validation.finding_model import ValidationSummary
        summary = ValidationSummary(target="invoice", ready=True)
        html = render_summary_html(summary)
        assert "Spremno" in html

    def test_plan_validator_zero_errors(self):
        from services.agent.planning.plan_validator import validate_plan, build_workflow_plan
        plan = build_workflow_plan("test")
        errors = validate_plan(plan)
        assert errors == []

    def test_automation_levels(self):
        from services.agent.workflow.automation_levels import requires_human_confirmation, AutomationLevel
        assert requires_human_confirmation("unconfirmed_tariff", AutomationLevel.CONTROLLED) is True
        assert requires_human_confirmation("safe_operation", AutomationLevel.CONTROLLED) is False

    def test_prazan_draft_ne_pada(self):
        """Nijedan servis ne smije pasti na potpuno praznom draftu."""
        d = DeclarationDraft()
        from services.agent.validation.invoice_review_service import provjeri_fakturu
        from services.agent.validation.items_review_service import provjeri_naimenovanja
        from services.agent.validation.header_review_service import provjeri_zaglavlje, provjeri_usklađenost_tabova
        provjeri_fakturu(d)
        provjeri_naimenovanja(d)
        provjeri_zaglavlje(d)
        provjeri_usklađenost_tabova(d)
