"""
Testovi za korisničke odluke (Faza 4).

Plan §16 Faza 4:
  - collect_required_decisions: identifikuje šta View mora prikupiti
  - validate_decisions: provjerava kompletnost odluka
  - invoices_to_apply: filtrira fakture na osnovu odluka
  - abort: odustajanje završava bez izmjene drafta
"""
from __future__ import annotations

from core.draft.draft import InvoiceLine, Party
from services.import_workflow.decision_models import (
    CurrencyConflictResponse,
    InvoiceDecision,
    OriginDialogResolution,
    OriginDialogResponse,
    PartnerConflictResolution,
    PartnerConflictResponse,
    UserDecisions,
)
from services.import_workflow.decision_service import (
    collect_required_decisions,
    invoices_to_apply,
    make_aborted_decisions,
    make_empty_decisions,
    validate_decisions,
)
from services.import_workflow.models import ImportCandidate
from services.import_workflow.plan_models import (
    DraftOperation,
    ImportPlan,
    OriginDialogType,
    PartnerConflict,
    PreparedInvoice,
)
from services.import_workflow.prepare_service import prepare_import


def _make_line(invoice_number="INV-001", tarifni_broj="08052190",
               zemlja_porijekla=""):
    return InvoiceLine(
        tarifni_broj=tarifni_broj,
        naziv_robe="Test proizvod",
        zemlja_porijekla=zemlja_porijekla,
        bruto_kg=10.0,
        neto_kg=9.0,
        iznos=100.0,
        kolicina=5,
        jm="kom",
        invoice_number=invoice_number,
    )


def _make_candidate(source_path="/tmp/INV-001.pdf", invoice_number="INV-001",
                    has_origin_statement=False, is_authorized_exporter=False,
                    exporter=None, currency="EUR"):
    import os
    from pathlib import Path
    if exporter is None:
        exporter = Party(name="Exporter d.o.o.", address="", country="DE")
    return ImportCandidate(
        source_path=source_path,
        normalized_path=os.path.normcase(str(Path(source_path).resolve())),
        file_type="PDF",
        parser="test",
        invoice_lines=[_make_line(invoice_number=invoice_number)],
        explicit_invoice_number=invoice_number,
        display_name=invoice_number or "test.pdf",
        bruto_kg=100.0,
        neto_kg=90.0,
        exporter=exporter,
        importer=Party(name="Importer d.o.o.", address="", country="BA"),
        currency=currency,
        has_origin_statement=has_origin_statement,
        is_authorized_exporter=is_authorized_exporter,
        is_combined=False,
        consumed_paths=[],
    )


def _make_plan_with_origin_dialog(dialog_type=OriginDialogType.PE2):
    """Kreira plan sa jednom fakturom koja ima origin dialog."""
    c = _make_candidate(has_origin_statement=True,
                        is_authorized_exporter=(dialog_type == OriginDialogType.PE3))
    return prepare_import([c])


def _make_plan_with_partner_conflict():
    """Kreira plan sa konfliktom partnera."""
    c1 = _make_candidate(exporter=Party(name="Izvoznik A", address="", country="DE"))
    c2 = _make_candidate(source_path="/tmp/INV-002.pdf", invoice_number="INV-002",
                         exporter=Party(name="Potpuno Drugi", address="", country="TR"))
    return prepare_import([c1, c2])


def _make_plan_with_currency_conflict():
    """Kreira plan sa konfliktom valute."""
    c1 = _make_candidate(currency="EUR")
    c2 = _make_candidate(source_path="/tmp/INV-002.pdf", invoice_number="INV-002",
                         currency="USD")
    return prepare_import([c1, c2])


def _make_simple_plan():
    """Kreira jednostavan plan bez konflikata ni dijaloga."""
    c = _make_candidate(invoice_number="INV-001")
    return prepare_import([c])


# ── collect_required_decisions ─────────────────────────────────────────────


class TestCollectRequiredDecisions:
    def test_prazan_plan_nema_odluka(self):
        plan = ImportPlan()
        required = collect_required_decisions(plan)
        assert required.is_empty is True

    def test_plan_bez_konflikta_nema_odluka(self):
        plan = _make_simple_plan()
        required = collect_required_decisions(plan)
        assert required.is_empty is True

    def test_plan_sa_partner_konfliktom(self):
        plan = _make_plan_with_partner_conflict()
        required = collect_required_decisions(plan)
        assert len(required.partner_conflicts) > 0
        assert required.is_empty is False

    def test_plan_sa_currency_konfliktom(self):
        plan = _make_plan_with_currency_conflict()
        required = collect_required_decisions(plan)
        assert required.currency_conflict is not None
        assert required.is_empty is False

    def test_plan_sa_origin_dialogom(self):
        plan = _make_plan_with_origin_dialog(OriginDialogType.PE3)
        required = collect_required_decisions(plan)
        assert len(required.origin_dialogs) == 1
        assert required.origin_dialogs[0][1] == OriginDialogType.PE3

    def test_origin_dialog_sadrzi_display_name(self):
        plan = _make_plan_with_origin_dialog(OriginDialogType.PE2)
        required = collect_required_decisions(plan)
        assert len(required.origin_dialogs) == 1
        # display_name treba biti invoice_number ("INV-001")
        assert required.origin_dialogs[0][2] == "INV-001"


# ── validate_decisions ────────────────────────────────────────────────────


class TestValidateDecisions:
    def test_validno_sa_praznim_odlukama_kad_nema_potrebe(self):
        plan = _make_simple_plan()
        decisions = make_empty_decisions()
        errors = validate_decisions(plan, decisions)
        assert errors == []

    def test_nedostaje_partner_odluka(self):
        plan = _make_plan_with_partner_conflict()
        decisions = make_empty_decisions()
        errors = validate_decisions(plan, decisions)
        assert len(errors) > 0
        assert any("konflikt partnera" in e for e in errors)

    def test_partner_odluka_prisutna_validno(self):
        plan = _make_plan_with_partner_conflict()
        decisions = make_empty_decisions()
        # Dodaj odgovor za prvi konflikt
        if plan.partner_conflicts:
            conflict = plan.partner_conflicts[0]
            decisions.partner_conflict_responses.append(PartnerConflictResponse(
                invoice_key=conflict.invoice_key,
                field_name=conflict.field_name,
                expected=conflict.expected,
                actual=conflict.actual,
                resolution=PartnerConflictResolution.CONTINUE,
            ))
        errors = validate_decisions(plan, decisions)
        assert errors == []

    def test_nedostaje_currency_odluka(self):
        plan = _make_plan_with_currency_conflict()
        decisions = make_empty_decisions()
        errors = validate_decisions(plan, decisions)
        assert any("konflikt valute" in e for e in errors)

    def test_currency_odluka_prisutna_validno(self):
        plan = _make_plan_with_currency_conflict()
        decisions = make_empty_decisions()
        if plan.currency_conflict:
            conflict = plan.currency_conflicts[0]
            decisions.currency_conflict_response = CurrencyConflictResponse(
                invoice_key=conflict.invoice_key,
                expected=conflict.expected,
                actual=conflict.actual,
                resolution=PartnerConflictResolution.CONTINUE,
            )
        errors = validate_decisions(plan, decisions)
        assert errors == []

    def test_nedostaje_origin_dialog_odgovor(self):
        plan = _make_plan_with_origin_dialog(OriginDialogType.PE3)
        decisions = make_empty_decisions()
        errors = validate_decisions(plan, decisions)
        assert any("PE3" in e for e in errors)

    def test_origin_dialog_odgovor_prisutan_validno(self):
        plan = _make_plan_with_origin_dialog(OriginDialogType.PE3)
        decisions = make_empty_decisions()
        if plan.origin_dialogs_needed:
            key, _ = plan.origin_dialogs_needed[0]
            decisions.invoice_decisions[key] = InvoiceDecision(
                invoice_key=key,
                origin_response=OriginDialogResponse(
                    invoice_key=key,
                    dialog_type=OriginDialogType.PE3,
                    resolution=OriginDialogResolution.APPLIED,
                ),
            )
        errors = validate_decisions(plan, decisions)
        assert errors == []

    def test_origin_dialog_skip_je_validan(self):
        plan = _make_plan_with_origin_dialog(OriginDialogType.PE2)
        decisions = make_empty_decisions()
        if plan.origin_dialogs_needed:
            key, _ = plan.origin_dialogs_needed[0]
            decisions.invoice_decisions[key] = InvoiceDecision(
                invoice_key=key,
                origin_response=OriginDialogResponse(
                    invoice_key=key,
                    dialog_type=OriginDialogType.PE2,
                    resolution=OriginDialogResolution.SKIPPED,
                ),
            )
        errors = validate_decisions(plan, decisions)
        assert errors == []

    def test_aborted_preskace_validaciju(self):
        plan = _make_plan_with_partner_conflict()
        decisions = make_aborted_decisions()
        errors = validate_decisions(plan, decisions)
        assert errors == []


# ── invoices_to_apply ──────────────────────────────────────────────────────


class TestInvoicesToApply:
    def test_sve_fakture_bez_odluka(self):
        plan = _make_simple_plan()
        decisions = make_empty_decisions()
        result = invoices_to_apply(plan, decisions)
        assert len(result) == 1

    def test_aborted_vraca_prazno(self):
        plan = _make_simple_plan()
        decisions = make_aborted_decisions()
        result = invoices_to_apply(plan, decisions)
        assert result == []

    def test_preskocene_fakture_se_ne_primjenjuju(self):
        c1 = _make_candidate(source_path="/tmp/INV-001.pdf", invoice_number="INV-001")
        c2 = _make_candidate(source_path="/tmp/INV-002.pdf", invoice_number="INV-002")
        plan = prepare_import([c1, c2])
        decisions = make_empty_decisions()
        # Preskoči prvu fakturu
        if plan.invoices:
            decisions.invoice_decisions[plan.invoices[0].internal_key] = InvoiceDecision(
                invoice_key=plan.invoices[0].internal_key,
                apply=False,
            )
        result = invoices_to_apply(plan, decisions)
        assert len(result) == 1
        assert result[0].invoice_number == "INV-002"

    def test_sve_fakture_kada_nema_eksplicitnih_odluka(self):
        c1 = _make_candidate(source_path="/tmp/INV-001.pdf", invoice_number="INV-001")
        c2 = _make_candidate(source_path="/tmp/INV-002.pdf", invoice_number="INV-002")
        plan = prepare_import([c1, c2])
        decisions = make_empty_decisions()
        result = invoices_to_apply(plan, decisions)
        assert len(result) == 2

    def test_draft_operation_skip_se_ne_primjenjuje(self):
        c1 = _make_candidate(source_path="/tmp/INV-001.pdf", invoice_number="INV-001")
        c2 = _make_candidate(source_path="/tmp/INV-002.pdf", invoice_number="INV-001")
        plan = prepare_import([c1, c2])
        decisions = make_empty_decisions()
        result = invoices_to_apply(plan, decisions)
        assert len(result) == 1
        assert result[0].draft_operation == DraftOperation.ADD

    def test_partner_skip_invoice_se_ne_primjenjuje(self):
        plan = _make_plan_with_partner_conflict()
        conflict = plan.partner_conflicts[0]
        decisions = make_empty_decisions()
        decisions.partner_conflict_responses.append(PartnerConflictResponse(
            invoice_key=conflict.invoice_key,
            field_name=conflict.field_name,
            expected=conflict.expected,
            actual=conflict.actual,
            resolution=PartnerConflictResolution.SKIP_INVOICE,
        ))
        result = invoices_to_apply(plan, decisions)
        assert all(inv.internal_key != conflict.invoice_key for inv in result)

    def test_partner_abort_vraca_prazno(self):
        plan = _make_plan_with_partner_conflict()
        conflict = plan.partner_conflicts[0]
        decisions = make_empty_decisions()
        decisions.partner_conflict_responses.append(PartnerConflictResponse(
            invoice_key=conflict.invoice_key,
            field_name=conflict.field_name,
            expected=conflict.expected,
            actual=conflict.actual,
            resolution=PartnerConflictResolution.ABORT,
        ))
        assert invoices_to_apply(plan, decisions) == []

    def test_currency_skip_invoice_se_ne_primjenjuje(self):
        plan = _make_plan_with_currency_conflict()
        conflict = plan.currency_conflicts[0]
        decisions = make_empty_decisions()
        decisions.currency_conflict_responses.append(CurrencyConflictResponse(
            invoice_key=conflict.invoice_key,
            expected=conflict.expected,
            actual=conflict.actual,
            resolution=PartnerConflictResolution.SKIP_INVOICE,
        ))
        result = invoices_to_apply(plan, decisions)
        assert all(inv.internal_key != conflict.invoice_key for inv in result)

    def test_currency_abort_vraca_prazno(self):
        plan = _make_plan_with_currency_conflict()
        conflict = plan.currency_conflicts[0]
        decisions = make_empty_decisions()
        decisions.currency_conflict_responses.append(CurrencyConflictResponse(
            invoice_key=conflict.invoice_key,
            expected=conflict.expected,
            actual=conflict.actual,
            resolution=PartnerConflictResolution.ABORT,
        ))
        assert invoices_to_apply(plan, decisions) == []


# ── make_aborted / make_empty ──────────────────────────────────────────────


class TestDecisionFactories:
    def test_make_aborted_oznacava_odustajanje(self):
        decisions = make_aborted_decisions()
        assert decisions.aborted is True

    def test_make_empty_nije_aborted(self):
        decisions = make_empty_decisions()
        assert decisions.aborted is False

    def test_make_empty_nema_odluka(self):
        decisions = make_empty_decisions()
        assert decisions.invoice_decisions == {}
        assert decisions.partner_conflict_responses == []
        assert decisions.currency_conflict_response is None


# ── UserDecisions helper metode ────────────────────────────────────────────


class TestUserDecisionsHelpers:
    def test_get_invoice_decision_default(self):
        decisions = make_empty_decisions()
        dec = decisions.get_invoice_decision("nonexistent")
        assert dec.apply is True
        assert dec.origin_response is None

    def test_get_invoice_decision_eksplicitna(self):
        decisions = make_empty_decisions()
        decisions.invoice_decisions["key1"] = InvoiceDecision(
            invoice_key="key1", apply=False
        )
        dec = decisions.get_invoice_decision("key1")
        assert dec.apply is False

    def test_is_invoice_aborted_kad_je_aborted(self):
        decisions = make_aborted_decisions()
        assert decisions.is_invoice_aborted("any") is True

    def test_is_invoice_aborted_kad_je_eksplicitno_preskocena(self):
        decisions = make_empty_decisions()
        decisions.invoice_decisions["key1"] = InvoiceDecision(
            invoice_key="key1", apply=False
        )
        assert decisions.is_invoice_aborted("key1") is True

    def test_is_invoice_aborted_kad_nije_preskocena(self):
        decisions = make_empty_decisions()
        assert decisions.is_invoice_aborted("key1") is False
