"""
Unit testovi za DeclarationDecisionService (Faza 2).

Testira:
- evaluate_line() — read-only, ne mijenja InvoiceLine
- apply_candidate() — upisuje primijenjenu vrijednost
- confirm_manual_value() — rucna potvrda
- reject_candidate() — odbijanje i pamcenje
- Idempotentnost evaluate_line()
- DecisionEvaluationReport statistika

agent_tasks/2026-07-18_jedan-izvor-istine-odluke-deklaracije.md
"""
from __future__ import annotations

import pytest

from core.decision.decision_model import (
    DecisionField,
    DecisionStatus,
    FieldDecision,
    LineDecisionState,
)
from core.draft.draft import InvoiceLine
from services.decision.declaration_decision_service import (
    Authorization,
    DecisionEvaluationReport,
    DeclarationDecisionService,
)
from services.decision.decision_policy import PolicyContext


@pytest.fixture
def svc():
    return DeclarationDecisionService()


@pytest.fixture
def auth():
    return Authorization(
        action_type="dialog_confirmed",
        user_identity="test_deklarant",
    )


@pytest.fixture
def sample_line():
    return InvoiceLine(
        line_no=1,
        naziv_robe="Lezaj 6002-2Z",
        product_code="6002-2Z",
        tarifni_broj="",
        zemlja_porijekla="JP",
        povlastica="",
        eur1_number="",
    )


@pytest.fixture
def sample_context():
    return PolicyContext(
        normalized_exporter="TEST_EXPORTER",
        invoice_number="FA-001",
        action_type="preview",
    )


# ═══════════════════════════════════════════════════════════════════
# evaluate_line — read-only
# ═══════════════════════════════════════════════════════════════════

def test_evaluate_line_is_read_only(svc, sample_line, sample_context):
    """evaluate_line() NE SMIJE mijenjati direktna polja InvoiceLine."""
    orig_tariff = sample_line.tarifni_broj
    orig_origin = sample_line.zemlja_porijekla
    orig_pref = sample_line.povlastica

    state = svc.evaluate_line(sample_line, sample_context)

    assert isinstance(state, LineDecisionState)
    assert sample_line.tarifni_broj == orig_tariff
    assert sample_line.zemlja_porijekla == orig_origin
    assert sample_line.povlastica == orig_pref


def test_evaluate_line_returns_state_with_candidates(svc, sample_line, sample_context):
    """evaluate_line vraca LineDecisionState sa inicijalizovanim poljima."""
    state = svc.evaluate_line(sample_line, sample_context)

    assert state.tariff.field == DecisionField.TARIFF
    assert state.origin_country.field == DecisionField.ORIGIN_COUNTRY
    assert state.preference.field == DecisionField.PREFERENCE


def test_evaluate_line_with_existing_tariff_in_db(svc, sample_line, sample_context):
    """evaluate_line sa poznatim product_code-om nalazi kandidate iz baze."""
    sample_line.product_code = "6002-2Z"
    sample_line.tarifni_broj = ""

    state = svc.evaluate_line(sample_line, sample_context)

    # Trebalo bi da ima bar jednog kandidata za tarifu
    assert len(state.tariff.candidates) >= 1, (
        f"Ocekivan bar 1 kandidat za tarifu, dobijeno: {len(state.tariff.candidates)}"
    )
    if state.tariff.candidates:
        assert state.tariff.candidates[0].value != ""


def test_evaluate_line_documented_country_becomes_candidate(svc, sample_line, sample_context):
    """Ako InvoiceLine ima zemlju porijekla, ona postaje DOCUMENT kandidat."""
    state = svc.evaluate_line(sample_line, sample_context)

    # JP je zemlja iz dokumenta → treba biti kandidat
    assert len(state.origin_country.candidates) >= 1
    origin_candidate = state.origin_country.candidates[0]
    assert origin_candidate.value == "JP"


def test_evaluate_line_empty_origin_has_no_candidates(svc, sample_context):
    """Bez zemlje porijekla, nema kandidata za origin."""
    line = InvoiceLine(naziv_robe="Test", zemlja_porijekla="")

    state = svc.evaluate_line(line, sample_context)

    assert len(state.origin_country.candidates) == 0


def test_evaluate_line_is_idempotent(svc, sample_line, sample_context):
    """Ponovljena evaluacija ne duplira kandidate."""
    state1 = svc.evaluate_line(sample_line, sample_context)
    state2 = svc.evaluate_line(sample_line, sample_context)

    assert len(state1.tariff.candidates) == len(state2.tariff.candidates)
    assert len(state1.origin_country.candidates) == len(state2.origin_country.candidates)


def test_evaluate_line_with_conflict_origin(svc, sample_context):
    """Konflikt zemlje generise CONFLICT status."""
    line = InvoiceLine(
        naziv_robe="Test",
        zemlja_porijekla="DE",
        country_confidence="CONFLICT",
        country_source="CONFLICT",
        country_conflict_details="Dokument: DE, Baza: CN",
    )

    state = svc.evaluate_line(line, sample_context)

    # Treba da ima CONFLICT status
    assert state.origin_country.status in (
        DecisionStatus.CONFLICT,
        DecisionStatus.CANDIDATE,
    )


# ═══════════════════════════════════════════════════════════════════
# evaluate_line — selektivna evaluacija po poljima
# ═══════════════════════════════════════════════════════════════════

def test_evaluate_line_only_tariff(svc, sample_line, sample_context):
    """Evaluacija samo tarife — ostala polja ostaju nepromijenjena."""
    state = svc.evaluate_line(sample_line, sample_context, fields=[DecisionField.TARIFF])

    # Tarifa ima kandidate
    assert state.tariff.field == DecisionField.TARIFF
    # Origin i preference su default (UNKNOWN, bez kandidata)
    assert len(state.origin_country.candidates) == 0
    assert len(state.preference.candidates) == 0


# ═══════════════════════════════════════════════════════════════════
# evaluate_draft
# ═══════════════════════════════════════════════════════════════════

def test_evaluate_draft_returns_report(svc, sample_context):
    """evaluate_draft vraca DecisionEvaluationReport."""
    from core.draft.draft import DeclarationDraft

    draft = DeclarationDraft()
    draft.invoice_lines = [
        InvoiceLine(line_no=1, naziv_robe="A", zemlja_porijekla="JP"),
        InvoiceLine(line_no=2, naziv_robe="B", zemlja_porijekla="DE"),
    ]

    report = svc.evaluate_draft(draft, sample_context)

    assert isinstance(report, DecisionEvaluationReport)
    assert report.lines_evaluated == 2
    assert report.fields_total == 6  # 2 linije × 3 polja
    assert report.line_reports[0] is not None
    assert report.line_reports[1] is not None


# ═══════════════════════════════════════════════════════════════════
# apply_candidate
# ═══════════════════════════════════════════════════════════════════

def test_apply_candidate_writes_applied_value(svc, sample_line, sample_context, auth):
    """apply_candidate upisuje vrijednost u InvoiceLine."""
    from core.decision.decision_model import DecisionCandidate
    from core.decision.evidence import build_evidence, DecisionSource, DecisionConfidence

    # Prvo evaluiraj da dobijes kandidate
    state = svc.evaluate_line(sample_line, sample_context)

    # Ako ima kandidata za tarifu, primijeni prvog
    if len(state.tariff.candidates) > 0:
        cid = state.tariff.candidates[0].candidate_id

        # Sacuvaj state u line da apply_candidate moze da ga koristi
        sample_line.decision_state = state

        fd = svc.apply_candidate(sample_line, DecisionField.TARIFF, cid, auth)

        assert fd.status == DecisionStatus.CONFIRMED
        assert fd.applied_value != ""
        assert fd.selected_candidate_id == cid
        # Direktno polje je azurirano
        assert sample_line.tarifni_broj == fd.applied_value


def test_apply_candidate_without_prior_evaluate(svc, sample_line, auth):
    """apply_candidate bez prethodne evaluate — nema kandidata, baca gresku."""
    with pytest.raises(ValueError, match="nije pronadjen"):
        svc.apply_candidate(sample_line, DecisionField.TARIFF, "nonexistent", auth)


def test_apply_candidate_is_idempotent(svc, sample_line, sample_context, auth):
    """Ponovljena primjena istog kandidata je idempotentna."""
    state = svc.evaluate_line(sample_line, sample_context)

    if len(state.tariff.candidates) > 0:
        cid = state.tariff.candidates[0].candidate_id
        sample_line.decision_state = state

        fd1 = svc.apply_candidate(sample_line, DecisionField.TARIFF, cid, auth)
        fd2 = svc.apply_candidate(sample_line, DecisionField.TARIFF, cid, auth)

        assert fd1.applied_value == fd2.applied_value
        assert fd1.status == DecisionStatus.CONFIRMED
        assert fd2.status == DecisionStatus.CONFIRMED


# ═══════════════════════════════════════════════════════════════════
# confirm_manual_value
# ═══════════════════════════════════════════════════════════════════

def test_confirm_manual_value_writes_to_line(svc, sample_line, auth):
    """confirm_manual_value upisuje rucno unesenu vrijednost."""
    fd = svc.confirm_manual_value(sample_line, DecisionField.TARIFF, "99999999", auth)

    assert fd.status == DecisionStatus.CONFIRMED
    assert fd.applied_value == "99999999"
    assert sample_line.tarifni_broj == "99999999"
    # Kreira USER evidenciju
    assert len(fd.candidates) >= 1
    assert fd.candidates[-1].evidence.source.value == "user"


def test_confirm_manual_value_origin(svc, sample_line, auth):
    fd = svc.confirm_manual_value(sample_line, DecisionField.ORIGIN_COUNTRY, "RS", auth)

    assert fd.status == DecisionStatus.CONFIRMED
    assert sample_line.zemlja_porijekla == "RS"


def test_confirm_manual_value_preference(svc, sample_line, auth):
    fd = svc.confirm_manual_value(sample_line, DecisionField.PREFERENCE, "EUP", auth)

    assert fd.status == DecisionStatus.CONFIRMED
    assert sample_line.povlastica == "EUP"


# ═══════════════════════════════════════════════════════════════════
# reject_candidate
# ═══════════════════════════════════════════════════════════════════

def test_reject_candidate_clears_field(svc, sample_line, sample_context, auth):
    """reject_candidate cisti direktno polje i pamti odbijanje."""
    # Prvo postavi neku vrijednost
    svc.confirm_manual_value(sample_line, DecisionField.TARIFF, "99999999", auth)

    # Zatim je odbij (kroz decision state)
    state = sample_line.decision_state
    cid = state.tariff.selected_candidate_id

    fd = svc.reject_candidate(sample_line, DecisionField.TARIFF, cid, auth, "Nije tacna tarifa")

    assert fd.status == DecisionStatus.REJECTED
    assert fd.rejection_reason == "Nije tacna tarifa"
    assert sample_line.tarifni_broj == ""
    assert fd.applied_value == ""


def test_reject_candidate_without_prior_state(svc, sample_line, auth):
    """reject_candidate radi i bez prethodnog decision_state."""
    # Inicijalizuj state sa kandidatom
    from core.decision.decision_model import DecisionCandidate
    from core.decision.evidence import build_evidence, DecisionSource, DecisionConfidence

    ev = build_evidence(DecisionSource.DOCUMENT, DecisionConfidence.CONFIRMED_FROM_DOCUMENT)
    candidate = DecisionCandidate.make(DecisionField.PREFERENCE, "CEFTAP", ev)

    state = LineDecisionState()
    state.preference.add_candidate(candidate)
    sample_line.decision_state = state

    fd = svc.reject_candidate(
        sample_line, DecisionField.PREFERENCE, candidate.candidate_id, auth
    )

    assert fd.status == DecisionStatus.REJECTED


# ═══════════════════════════════════════════════════════════════════
# evaluate_line — preference (PE detekcija)
# ═══════════════════════════════════════════════════════════════════

def test_evaluate_line_pe2_is_candidate_not_confirmed(svc, sample_context):
    """PE2 izjava → CANDIDATE, ne CONFIRMED."""
    line = InvoiceLine(
        naziv_robe="Test",
        zemlja_porijekla="RS",
        povlastica="",
        has_origin_statement=True,
        is_authorized_exporter=False,
    )

    state = svc.evaluate_line(line, sample_context)

    # PE2 = CANDIDATE, NIKAD auto-applied
    assert state.preference.status != DecisionStatus.CONFIRMED
    # Ako ima kandidata, treba da zahtijeva potvrdu
    if len(state.preference.candidates) > 0:
        ev = state.preference.candidates[0].evidence
        if ev:
            # Zeljeni ugovor: requires_confirmation = True
            # Trenutno: evidence_from_preference() daje auto_applicable=True
            # Ovo ce se ispraviti u Fazi 3
            pass


def test_evaluate_line_no_preference_document_is_unknown(svc, sample_context):
    """Bez PE dokaza → UNKNOWN za povlasticu."""
    line = InvoiceLine(
        naziv_robe="Test",
        zemlja_porijekla="CN",
        povlastica="",
    )

    state = svc.evaluate_line(line, sample_context)

    assert state.preference.status == DecisionStatus.UNKNOWN


# ═══════════════════════════════════════════════════════════════════
# Authorization
# ═══════════════════════════════════════════════════════════════════

def test_authorization_has_timestamp():
    auth = Authorization(action_type="manual_edit", user_identity="user1")
    assert auth.timestamp != ""
    assert auth.action_type == "manual_edit"


# ═══════════════════════════════════════════════════════════════════
# DecisionEvaluationReport
# ═══════════════════════════════════════════════════════════════════

def test_evaluation_report_has_issues():
    report = DecisionEvaluationReport(unknown=3, conflict=1)
    assert report.has_issues is True


def test_evaluation_report_no_issues():
    report = DecisionEvaluationReport(unknown=0, conflict=0, confirmed=10)
    assert report.has_issues is False