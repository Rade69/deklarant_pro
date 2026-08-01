from __future__ import annotations

import pytest

from core.draft.draft import DeclarationDraft, InvoiceLine, Party
from importers.import_result import ImportResult
from services.faktura.import_workflow_service import ImportWorkflowService


def _line(invoice_number: str = "INV-001", tariff: str = "08052190") -> InvoiceLine:
    return InvoiceLine(
        invoice_number=invoice_number,
        tarifni_broj=tariff,
        naziv_robe="Test roba",
        kolicina=1,
        iznos=10.0,
    )


def test_existing_invoice_keys_uzima_tezine_i_stavke():
    draft = DeclarationDraft()
    draft.invoice_weights["inv-001"] = (1.0, 1.0)
    draft.invoice_lines = [_line("INV-002")]

    keys = ImportWorkflowService().existing_invoice_keys(draft)

    assert keys == {"inv-001", "inv-002"}


def test_expected_import_partners_uzima_runtime_pa_draft_fallback():
    draft = DeclarationDraft()
    draft.izvoznik_naziv = "Draft izvoznik"
    draft.primalac_naziv = "Draft primalac"
    service = ImportWorkflowService()

    assert service.expected_import_partners(draft) == (
        "Draft izvoznik",
        "Draft primalac",
    )
    assert service.expected_import_partners(draft, "Runtime izvoznik", "") == (
        "Runtime izvoznik",
        "Draft primalac",
    )


def test_batch_record_to_candidate_cuva_parser_warnings_i_deepcopy():
    line = _line("INV-003")
    result = ImportResult(items=[line], bruto_kg=2.0, neto_kg=1.5, invoice_name="INV-003")
    record = {
        "filepath": "INV-003.pdf",
        "items": [line],
        "bruto_kg": 3.0,
        "neto_kg": 2.5,
        "parser_warnings": ["Provjeri tarifu"],
        "_import_result": result,
    }

    candidate = ImportWorkflowService().batch_record_to_import_candidate(record)

    assert candidate.bruto_kg == pytest.approx(3.0)
    assert candidate.neto_kg == pytest.approx(2.5)
    assert candidate.warnings == ["Provjeri tarifu"]
    assert candidate.invoice_lines == [line]
    assert candidate.invoice_lines[0] is not line


def test_prepare_manual_import_plan_koristi_postojece_kljuceve_za_replace():
    draft = DeclarationDraft()
    draft.invoice_lines = [_line("INV-004")]
    result = ImportResult(
        items=[_line("INV-004", tariff="3824993")],
        bruto_kg=4.0,
        neto_kg=3.0,
        invoice_name="INV-004",
    )

    plan = ImportWorkflowService().prepare_manual_import_plan(
        result, "INV-004.pdf", draft
    )

    assert plan.expected_replace_count == 1
    assert plan.expected_add_count == 0
    assert plan.expected_total_items == 1


def test_sync_state_after_apply_vraca_mase_i_zadnju_fakturu():
    from services.import_workflow.apply_service import apply_import_plan
    from services.import_workflow.decision_models import InvoiceDecision, UserDecisions

    draft = DeclarationDraft()
    result = ImportResult(
        items=[_line("INV-005")],
        bruto_kg=5.0,
        neto_kg=4.0,
        invoice_name="INV-005",
    )
    result.exporter = Party(name="Izvoznik")
    result.importer = Party(name="Uvoznik")

    service = ImportWorkflowService()
    plan = service.prepare_manual_import_plan(result, "INV-005.pdf", draft)
    decisions = UserDecisions()
    decisions.invoice_decisions[plan.invoices[0].internal_key] = InvoiceDecision(
        invoice_key=plan.invoices[0].internal_key
    )
    apply_result = apply_import_plan(draft, plan, decisions)

    state = service.sync_state_after_apply(draft, plan, apply_result)

    assert state.accumulated_bruto_kg == pytest.approx(5.0)
    assert state.accumulated_neto_kg == pytest.approx(4.0)
    assert state.last_invoice_name == "INV-005"
    assert state.last_import_count == 1
    assert state.expected_exporter == "Izvoznik"
    assert state.expected_importer == "Uvoznik"
