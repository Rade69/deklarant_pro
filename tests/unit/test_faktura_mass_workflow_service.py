import pytest

from core.draft import DeclarationDraft, InvoiceLine
from services.faktura.mass_workflow_service import MassWorkflowService
from services.faktura.models import CalculateMassesRequest


def _line(invoice_number="", kolicina=1.0, bruto_kg=0.0, neto_kg=0.0, iznos=0.0):
    return InvoiceLine(
        naziv_robe="Test",
        invoice_number=invoice_number,
        kolicina=kolicina,
        bruto_kg=bruto_kg,
        neto_kg=neto_kg,
        iznos=iznos,
    )


def test_per_invoice_raspodjela_koristi_sacuvane_tezine():
    draft = DeclarationDraft()
    draft.invoice_lines = [
        _line("A-1", kolicina=1, iznos=100),
        _line("A-1", kolicina=1, iznos=300),
        _line("B-1", kolicina=1, iznos=200),
    ]
    draft.invoice_weights = {
        "A-1": (40.0, 38.0),
        "B-1": (20.0, 19.0),
    }

    result = MassWorkflowService().calculate(
        draft,
        CalculateMassesRequest(bruto_total=60.0, neto_total=57.0),
    )

    assert result.success is True
    assert result.updated_count == 3
    assert sum(line.bruto_kg for line in draft.invoice_lines[:2]) == pytest.approx(40.0)
    assert draft.invoice_lines[2].bruto_kg == pytest.approx(20.0)


def test_toolbar_neto_fallback_rasporedjuje_neto_kad_fakture_nemaju_neto():
    draft = DeclarationDraft()
    draft.invoice_lines = [
        _line("A-1", kolicina=1),
        _line("B-1", kolicina=1),
    ]
    draft.invoice_weights = {
        "A-1": (30.0, 0.0),
        "B-1": (70.0, 0.0),
    }

    result = MassWorkflowService().calculate(
        draft,
        CalculateMassesRequest(bruto_total=100.0, neto_total=90.0),
    )

    assert result.success is True
    assert draft.invoice_lines[0].neto_kg == pytest.approx(27.0)
    assert draft.invoice_lines[1].neto_kg == pytest.approx(63.0)


def test_sumnjiv_fallback_bez_dozvole_ne_mijenja_stavke_bez_fakture():
    draft = DeclarationDraft()
    draft.invoice_lines = [
        _line("A-1", kolicina=1),
        _line("", kolicina=1),
    ]
    draft.invoice_weights = {"A-1": (10.0, 9.0)}

    result = MassWorkflowService().calculate(
        draft,
        CalculateMassesRequest(
            bruto_total=100.0,
            neto_total=90.0,
            allow_suspicious_fallback=False,
        ),
    )

    assert result.success is True
    assert result.fallback_skipped == 1
    assert draft.invoice_lines[1].bruto_kg == 0.0


def test_sumnjiv_fallback_sa_dozvolom_koristi_toolbar_total():
    draft = DeclarationDraft()
    draft.invoice_lines = [
        _line("A-1", kolicina=1),
        _line("", kolicina=1),
    ]
    draft.invoice_weights = {"A-1": (10.0, 9.0)}

    result = MassWorkflowService().calculate(
        draft,
        CalculateMassesRequest(
            bruto_total=100.0,
            neto_total=90.0,
            allow_suspicious_fallback=True,
        ),
    )

    assert result.success is True
    assert result.fallback_skipped == 0
    assert draft.invoice_lines[1].bruto_kg == pytest.approx(100.0)


def test_missing_invoice_weights_vraca_strukturisan_noop():
    draft = DeclarationDraft()
    draft.invoice_lines = [_line("A-1", kolicina=1)]
    draft.invoice_weights = {}

    result = MassWorkflowService().calculate(
        draft,
        CalculateMassesRequest(bruto_total=10.0, neto_total=9.0),
    )

    assert result.success is False
    assert result.reason == "missing_invoice_weights"
    assert result.no_weight_invoices == ["a-1"]
