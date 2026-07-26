from __future__ import annotations

from unittest.mock import patch

from core.draft.draft import DeclarationDraft, InvoiceLine, Party
from services.import_workflow.apply_service import apply_import_plan
from services.import_workflow.decision_models import (
    InvoiceDecision,
    OriginDialogResolution,
    OriginDialogResponse,
)
from services.import_workflow.decision_service import make_empty_decisions
from services.import_workflow.models import ImportCandidate
from services.import_workflow.plan_models import DraftOperation, OriginDialogType
from services.import_workflow.prepare_service import prepare_import


def _line(invoice_number="", tariff="08052190", bruto=0.0, neto=0.0, country=""):
    return InvoiceLine(
        invoice_number=invoice_number,
        tarifni_broj=tariff,
        naziv_robe="Test proizvod",
        zemlja_porijekla=country,
        bruto_kg=bruto,
        neto_kg=neto,
        iznos=100.0,
        kolicina=2,
        jm="kom",
    )


def _candidate(
    source_path="/tmp/INV-001.pdf",
    invoice_number="INV-001",
    lines=None,
    bruto=10.0,
    neto=9.0,
    exporter=None,
    importer=None,
    currency="EUR",
    incoterm_code="",
    has_origin_statement=False,
):
    import os
    from pathlib import Path

    return ImportCandidate(
        source_path=source_path,
        normalized_path=os.path.normcase(str(Path(source_path).resolve())),
        file_type="PDF",
        parser="test",
        invoice_lines=lines if lines is not None else [_line(invoice_number=invoice_number)],
        explicit_invoice_number=invoice_number,
        display_name=invoice_number or Path(source_path).name,
        bruto_kg=bruto,
        neto_kg=neto,
        exporter=exporter or Party(name="Exporter d.o.o.", address="Export 1", city="Berlin", country="DE"),
        importer=importer or Party(name="Importer d.o.o.", address="Import 1", city="Bijeljina", country="BA", vat_or_id="JIB1"),
        currency=currency,
        incoterm_code=incoterm_code,
        has_origin_statement=has_origin_statement,
    )


def test_apply_adds_invoice_lines_weights_header_and_source_files():
    draft = DeclarationDraft()
    candidate = _candidate(
        lines=[_line(invoice_number="", bruto=0.0, neto=0.0)],
        incoterm_code="CIP",
    )
    plan = prepare_import([candidate])

    result = apply_import_plan(draft, plan, make_empty_decisions())

    assert result.success is True
    assert result.added_invoices == 1
    assert result.total_items == 1
    assert len(draft.invoice_lines) == 1
    assert draft.invoice_lines[0].invoice_number == "INV-001"
    assert draft.invoice_lines[0].bruto_kg == 10.0
    assert draft.invoice_lines[0].neto_kg == 9.0
    assert draft.invoice_weights["inv-001"] == (10.0, 9.0)
    assert draft.izvoznik_naziv == "Exporter d.o.o."
    assert draft.primalac_id == "JIB1"
    # Rb.20 "Uslovi isporuke" - regresioni test za bug otkriven uzivo
    # (medicopharm faktura sa "PARITET: CIP BIJELJINA" u tekstu, unified
    # workflow uopste nije prenosio incoterm_code do ImportCandidate/
    # PreparedInvoice, pa je Rb.20 ostajao prazan iako je legacy put radio)
    assert draft.uslovi_kod == "CIP"
    assert draft.source_files == ["/tmp/INV-001.pdf"]
    assert draft.dirty is True


def test_apply_replace_removes_existing_invoice_lines_and_weight():
    draft = DeclarationDraft()
    draft.invoice_lines = [
        _line(invoice_number="INV-001", tariff="11111111"),
        _line(invoice_number="INV-002", tariff="22222222"),
    ]
    draft.invoice_weights = {"inv-001": (1.0, 1.0), "inv-002": (2.0, 2.0)}
    candidate = _candidate(
        invoice_number="INV-001",
        lines=[_line(invoice_number="", tariff="33333333")],
        bruto=30.0,
        neto=27.0,
    )
    plan = prepare_import([candidate], existing_invoice_keys={"INV-001"})

    result = apply_import_plan(draft, plan, make_empty_decisions())

    assert result.success is True
    assert result.replaced_invoices == 1
    assert result.replaced_items == 1
    assert [line.tarifni_broj for line in draft.invoice_lines] == ["22222222", "33333333"]
    assert draft.invoice_weights["inv-001"] == (30.0, 27.0)
    assert draft.invoice_weights["inv-002"] == (2.0, 2.0)


def test_apply_respects_skip_operation_from_plan():
    draft = DeclarationDraft()
    c1 = _candidate(source_path="/tmp/INV-001.pdf", invoice_number="INV-001")
    c2 = _candidate(source_path="/tmp/INV-001-copy.pdf", invoice_number="INV-001")
    plan = prepare_import([c1, c2])

    result = apply_import_plan(draft, plan, make_empty_decisions())

    assert result.success is True
    assert result.skipped_invoices == 1
    assert len(draft.invoice_lines) == 1
    assert all(inv.draft_operation in (DraftOperation.ADD, DraftOperation.SKIP) for inv in plan.invoices)


def test_apply_rolls_back_on_unexpected_error():
    draft = DeclarationDraft()
    draft.invoice_lines = [_line(invoice_number="OLD", tariff="11111111")]
    draft.invoice_weights = {"old": (1.0, 1.0)}
    candidate = _candidate(lines=[_line(invoice_number="", bruto=0.0, neto=0.0)])
    plan = prepare_import([candidate])

    with patch(
        "services.import_workflow.apply_service.MassCalculator.calculate_masses",
        side_effect=RuntimeError("boom"),
    ):
        result = apply_import_plan(draft, plan, make_empty_decisions())

    assert result.success is False
    assert [line.invoice_number for line in draft.invoice_lines] == ["OLD"]
    assert draft.invoice_weights == {"old": (1.0, 1.0)}
    assert draft.dirty is False


def test_apply_does_not_mutate_when_required_decision_is_missing():
    draft = DeclarationDraft()
    candidate = _candidate(
        lines=[_line(invoice_number="INV-001", country="DE")],
        has_origin_statement=True,
    )
    plan = prepare_import([candidate])

    result = apply_import_plan(draft, plan, make_empty_decisions())

    assert result.success is False
    assert draft.invoice_lines == []
    assert "PE2" in result.errors[0]


def test_apply_origin_response_only_when_applied():
    draft = DeclarationDraft()
    candidate = _candidate(
        lines=[_line(invoice_number="INV-001", country="DE")],
        has_origin_statement=True,
    )
    plan = prepare_import([candidate])
    key = plan.invoices[0].internal_key
    prepared_de = plan.invoices[0].invoice_lines[0]
    decisions = make_empty_decisions()
    decisions.invoice_decisions[key] = InvoiceDecision(
        invoice_key=key,
        origin_response=OriginDialogResponse(
            invoice_key=key,
            dialog_type=OriginDialogType.PE2,
            resolution=OriginDialogResolution.APPLIED,
            dialog_data={"povlastica": "EUPR", "eur1_number": "INV-001", "has_origin_statement": True},
        ),
    )

    result = apply_import_plan(draft, plan, decisions)

    assert result.success is True
    assert draft.invoice_lines[0].povlastica == "EUPR"
    assert draft.invoice_lines[0].eur1_number == "INV-001"
    assert draft.invoice_lines[0].has_origin_statement is True


def test_apply_origin_response_supports_grouped_dialog_data():
    draft = DeclarationDraft()
    line_de = _line(invoice_number="INV-001", country="DE")
    line_it = _line(invoice_number="INV-001", country="IT")
    candidate = _candidate(
        lines=[line_de, line_it],
        has_origin_statement=True,
    )
    plan = prepare_import([candidate])
    key = plan.invoices[0].internal_key
    prepared_de = plan.invoices[0].invoice_lines[0]
    decisions = make_empty_decisions()
    decisions.invoice_decisions[key] = InvoiceDecision(
        invoice_key=key,
        origin_response=OriginDialogResponse(
            invoice_key=key,
            dialog_type=OriginDialogType.PE2,
            resolution=OriginDialogResolution.APPLIED,
            dialog_data={
                "DE": {
                    "code": "PE2",
                    "preference": "EUPR",
                    "invoice_number": "INV-001",
                    "items": [prepared_de],
                }
            },
        ),
    )

    result = apply_import_plan(draft, plan, decisions)

    assert result.success is True
    assert draft.invoice_lines[0].povlastica == "EUPR"
    assert draft.invoice_lines[0].eur1_number == "INV-001"
    assert draft.invoice_lines[0].has_origin_statement is True
    assert draft.invoice_lines[1].povlastica == ""


def test_apply_keeps_existing_header_values():
    draft = DeclarationDraft(izvoznik_naziv="Postojeci izvoznik", primalac_id="POSTOJECI")
    candidate = _candidate()
    plan = prepare_import([candidate])

    apply_import_plan(draft, plan, make_empty_decisions())

    assert draft.izvoznik_naziv == "Postojeci izvoznik"
    assert draft.primalac_id == "POSTOJECI"
