"""
Unit testovi za kanonski model odluke deklaracije (Faza 1).

Testira:
- DecisionCandidate — deterministicki candidate_id
- FieldDecision — statusni prelazi, add_candidate, serijalizacija
- LineDecisionState — get(), all_confirmed, serijalizacija
- InvoiceLine.from_any() — backward compat sa starim i novim draftovima
- InvoiceLine.decision_state — None default za stare draftove

agent_tasks/2026-07-18_jedan-izvor-istine-odluke-deklaracije.md
"""
from __future__ import annotations

import json
import pytest

from core.decision.decision_model import (
    DecisionCandidate,
    DecisionField,
    DecisionStatus,
    FieldDecision,
    LineDecisionState,
)
from core.decision.evidence import (
    DecisionConfidence,
    DecisionSource,
    Evidence,
    build_evidence,
)
from core.draft.draft import InvoiceLine


# ═══════════════════════════════════════════════════════════════════
# DecisionCandidate
# ═══════════════════════════════════════════════════════════════════

def test_candidate_id_is_deterministic():
    """Isti field + value + source = isti candidate_id."""
    ev = build_evidence(DecisionSource.DOCUMENT, DecisionConfidence.CONFIRMED_FROM_DOCUMENT)

    c1 = DecisionCandidate.make(DecisionField.TARIFF, "84821000", ev)
    c2 = DecisionCandidate.make(DecisionField.TARIFF, "84821000", ev)

    assert c1.candidate_id == c2.candidate_id
    assert len(c1.candidate_id) == 12


def test_candidate_id_differs_by_field():
    """Razlicit DecisionField = razlicit candidate_id."""
    ev = build_evidence(DecisionSource.DOCUMENT, DecisionConfidence.CONFIRMED_FROM_DOCUMENT)

    c_tariff = DecisionCandidate.make(DecisionField.TARIFF, "84821000", ev)
    c_origin = DecisionCandidate.make(DecisionField.ORIGIN_COUNTRY, "84821000", ev)

    assert c_tariff.candidate_id != c_origin.candidate_id


def test_candidate_id_differs_by_value():
    """Razlicita vrijednost = razlicit candidate_id."""
    ev = build_evidence(DecisionSource.DOCUMENT, DecisionConfidence.CONFIRMED_FROM_DOCUMENT)

    c1 = DecisionCandidate.make(DecisionField.TARIFF, "84821000", ev)
    c2 = DecisionCandidate.make(DecisionField.TARIFF, "82054000", ev)

    assert c1.candidate_id != c2.candidate_id


def test_candidate_is_frozen():
    """DecisionCandidate je frozen — ne moze se mijenjati nakon kreiranja."""
    c = DecisionCandidate.make(DecisionField.TARIFF, "84821000")
    with pytest.raises(Exception):
        c.value = "99999999"


# ═══════════════════════════════════════════════════════════════════
# FieldDecision
# ═══════════════════════════════════════════════════════════════════

def test_field_decision_default_is_unknown():
    fd = FieldDecision(field=DecisionField.TARIFF)
    assert fd.status == DecisionStatus.UNKNOWN
    assert fd.applied_value == ""
    assert fd.candidates == []
    assert fd.is_pending is True
    assert fd.is_confirmed is False


def test_add_candidate_transitions_to_candidate():
    fd = FieldDecision(field=DecisionField.TARIFF)
    c = DecisionCandidate.make(DecisionField.TARIFF, "84821000")

    fd.add_candidate(c)

    assert fd.status == DecisionStatus.CANDIDATE
    assert len(fd.candidates) == 1
    assert fd.candidates[0].candidate_id == c.candidate_id


def test_add_duplicate_candidate_is_idempotent():
    fd = FieldDecision(field=DecisionField.TARIFF)
    c = DecisionCandidate.make(DecisionField.TARIFF, "84821000")

    fd.add_candidate(c)
    fd.add_candidate(c)  # duplicate

    assert len(fd.candidates) == 1


def test_add_candidate_does_not_override_confirmed():
    fd = FieldDecision(
        field=DecisionField.TARIFF,
        status=DecisionStatus.CONFIRMED,
        applied_value="84821000",
    )
    c = DecisionCandidate.make(DecisionField.TARIFF, "82054000")

    fd.add_candidate(c)

    # Status ostaje CONFIRMED
    assert fd.status == DecisionStatus.CONFIRMED
    # Ali kandidat se dodaje
    assert len(fd.candidates) == 1


def test_field_decision_status_properties():
    # CONFIRMED
    fd = FieldDecision(field=DecisionField.TARIFF, status=DecisionStatus.CONFIRMED)
    assert fd.is_confirmed is True
    assert fd.is_pending is False
    assert fd.has_conflict is False
    assert fd.is_rejected is False

    # REJECTED
    fd.status = DecisionStatus.REJECTED
    assert fd.is_rejected is True
    assert fd.is_confirmed is False

    # CONFLICT
    fd.status = DecisionStatus.CONFLICT
    assert fd.has_conflict is True


# ═══════════════════════════════════════════════════════════════════
# FieldDecision serializacija (roundtrip)
# ═══════════════════════════════════════════════════════════════════

def test_field_decision_to_dict_and_back():
    ev = build_evidence(
        DecisionSource.EXPORTER_HISTORY,
        DecisionConfidence.CONFIRMED_FROM_SAME_EXPORTER_HISTORY,
        "Iz istorije.",
        {"usage_count": 10},
    )
    fd = FieldDecision(
        field=DecisionField.TARIFF,
        status=DecisionStatus.CONFIRMED,
        applied_value="84821000",
        selected_candidate_id="abc123",
        confirmed_by="deklarant",
        confirmed_at="2026-07-18T10:00:00",
    )
    fd.add_candidate(DecisionCandidate.make(DecisionField.TARIFF, "84821000", ev))

    d = fd.to_dict()
    restored = FieldDecision.from_dict(d)

    assert restored.field == DecisionField.TARIFF
    assert restored.status == DecisionStatus.CONFIRMED
    assert restored.applied_value == "84821000"
    assert restored.selected_candidate_id == "abc123"
    assert restored.confirmed_by == "deklarant"
    assert len(restored.candidates) == 1
    assert restored.candidates[0].value == "84821000"
    assert restored.candidates[0].evidence is not None
    assert restored.candidates[0].evidence.source == DecisionSource.EXPORTER_HISTORY


def test_field_decision_from_empty_dict():
    fd = FieldDecision.from_dict({})
    assert fd.field == DecisionField.TARIFF
    assert fd.status == DecisionStatus.UNKNOWN


# ═══════════════════════════════════════════════════════════════════
# LineDecisionState
# ═══════════════════════════════════════════════════════════════════

def test_line_decision_state_default():
    lds = LineDecisionState()

    assert lds.tariff.field == DecisionField.TARIFF
    assert lds.origin_country.field == DecisionField.ORIGIN_COUNTRY
    assert lds.preference.field == DecisionField.PREFERENCE
    assert lds.tariff.status == DecisionStatus.UNKNOWN
    assert lds.origin_country.status == DecisionStatus.UNKNOWN
    assert lds.preference.status == DecisionStatus.UNKNOWN


def test_line_decision_state_get():
    lds = LineDecisionState()
    lds.tariff.status = DecisionStatus.CONFIRMED

    assert lds.get(DecisionField.TARIFF).is_confirmed is True
    assert lds.get(DecisionField.ORIGIN_COUNTRY).is_confirmed is False
    assert lds.get(DecisionField.PREFERENCE).is_confirmed is False


def test_line_decision_state_all_confirmed():
    lds = LineDecisionState()
    assert lds.all_confirmed is False

    lds.tariff.status = DecisionStatus.CONFIRMED
    lds.origin_country.status = DecisionStatus.CONFIRMED
    assert lds.all_confirmed is True  # preference UNKNOWN je prihvatljivo


def test_line_decision_state_to_dict_and_back():
    lds = LineDecisionState()
    lds.tariff.status = DecisionStatus.CONFIRMED
    lds.tariff.applied_value = "84821000"
    lds.origin_country.status = DecisionStatus.CANDIDATE

    d = lds.to_dict()
    restored = LineDecisionState.from_dict(d)

    assert restored.tariff.status == DecisionStatus.CONFIRMED
    assert restored.tariff.applied_value == "84821000"
    assert restored.origin_country.status == DecisionStatus.CANDIDATE
    assert restored.preference.status == DecisionStatus.UNKNOWN


def test_line_decision_state_from_none():
    lds = LineDecisionState.from_dict(None)
    assert lds.tariff.status == DecisionStatus.UNKNOWN
    assert lds.origin_country.status == DecisionStatus.UNKNOWN


# ═══════════════════════════════════════════════════════════════════
# InvoiceLine — backward compatibility
# ═══════════════════════════════════════════════════════════════════

def test_invoice_line_default_decision_state_is_none():
    """Novi InvoiceLine bez decision_state — default je None (backward compat)."""
    line = InvoiceLine(naziv_robe="Test")
    assert line.decision_state is None


def test_invoice_line_from_any_old_dict_no_decision_state():
    """Stari dict bez decision_state — ucitava se bez greske, decision_state=None."""
    old_dict = {
        "naziv_robe": "Test proizvod",
        "tarifni_broj": "84713000",
        "zemlja_porijekla": "CN",
        "povlastica": "",
    }
    line = InvoiceLine.from_any(old_dict)

    assert line.naziv_robe == "Test proizvod"
    assert line.tarifni_broj == "84713000"
    assert line.zemlja_porijekla == "CN"
    assert line.decision_state is None  # Backward compat


def test_invoice_line_from_any_with_decision_state():
    """Novi dict sa decision_state — ucitava se ispravno."""
    lds = LineDecisionState()
    lds.tariff.status = DecisionStatus.CONFIRMED
    lds.tariff.applied_value = "84821000"

    new_dict = {
        "naziv_robe": "Lezaj",
        "tarifni_broj": "84821000",
        "decision_state": lds.to_dict(),
    }
    line = InvoiceLine.from_any(new_dict)

    assert line.decision_state is not None
    assert line.decision_state.tariff.status == DecisionStatus.CONFIRMED
    assert line.decision_state.tariff.applied_value == "84821000"


def test_invoice_line_from_any_with_invalid_decision_state():
    """Nepotpun decision_state dict — fallback na default LineDecisionState."""
    bad_dict = {
        "naziv_robe": "Test",
        "decision_state": {"invalid": "data"},
    }
    line = InvoiceLine.from_any(bad_dict)

    assert line.naziv_robe == "Test"
    # Nepotpun dict se tretira kao default (UNKNOWN) stanje
    assert line.decision_state is not None
    assert line.decision_state.tariff.status == DecisionStatus.UNKNOWN


def test_invoice_line_from_any_already_line_with_state():
    """InvoiceLine objekat sa decision_state prolazi kroz from_any nepromenjen."""
    lds = LineDecisionState()
    lds.tariff.status = DecisionStatus.CANDIDATE

    line = InvoiceLine(naziv_robe="Test", decision_state=lds)
    result = InvoiceLine.from_any(line)

    assert result is line  # Isti objekat
    assert result.decision_state is lds
    assert result.decision_state.tariff.status == DecisionStatus.CANDIDATE


def test_invoice_line_direct_polja_i_dalje_rade():
    """Direktna polja (tarifni_broj, zemlja_porijekla, povlastica)
    i dalje postoje i rade zbog backward compatibility."""
    line = InvoiceLine(
        naziv_robe="Test",
        tarifni_broj="84713000",
        zemlja_porijekla="CN",
        povlastica="",
        eur1_number="EUR1-001",
    )

    assert line.tarifni_broj == "84713000"
    assert line.zemlja_porijekla == "CN"
    assert line.povlastica == ""
    assert line.eur1_number == "EUR1-001"
    assert line.decision_state is None


def test_invoice_line_with_decision_state_and_direct_polja():
    """InvoiceLine moze imati i decision_state i direktna polja istovremeno.
    Direktna polja su primijenjena vrijednost (kompatibilnost sa XML-om)."""
    lds = LineDecisionState()
    lds.tariff.status = DecisionStatus.CONFIRMED
    lds.tariff.applied_value = "84821000"

    line = InvoiceLine(
        naziv_robe="Lezaj",
        tarifni_broj="84821000",
        decision_state=lds,
    )

    assert line.tarifni_broj == "84821000"
    assert line.decision_state.tariff.applied_value == "84821000"


def test_line_decision_state_json_roundtrip():
    """LineDecisionState moze da se serijalizuje kroz JSON (draft save/load)."""
    lds = LineDecisionState()
    lds.tariff.status = DecisionStatus.CONFIRMED
    lds.tariff.applied_value = "84821000"
    lds.origin_country.status = DecisionStatus.CANDIDATE
    c = DecisionCandidate.make(
        DecisionField.TARIFF, "84821000",
        build_evidence(DecisionSource.EXPORTER_HISTORY, DecisionConfidence.CONFIRMED_FROM_SAME_EXPORTER_HISTORY)
    )
    lds.tariff.add_candidate(c)

    d = lds.to_dict()
    json_str = json.dumps(d)
    restored_dict = json.loads(json_str)
    restored = LineDecisionState.from_dict(restored_dict)

    assert restored.tariff.status == DecisionStatus.CONFIRMED
    assert restored.tariff.applied_value == "84821000"
    assert restored.origin_country.status == DecisionStatus.CANDIDATE
    assert len(restored.tariff.candidates) == 1
    assert restored.tariff.candidates[0].value == "84821000"


# ═══════════════════════════════════════════════════════════════════
# DecisionField enum
# ═══════════════════════════════════════════════════════════════════

def test_decision_field_covers_tariff_origin_preference():
    assert DecisionField.TARIFF.value == "tariff"
    assert DecisionField.ORIGIN_COUNTRY.value == "origin_country"
    assert DecisionField.PREFERENCE.value == "preference"
    assert len(DecisionField) == 3


# ═══════════════════════════════════════════════════════════════════
# DecisionStatus enum
# ═══════════════════════════════════════════════════════════════════

def test_decision_status_covers_all_states():
    assert DecisionStatus.UNKNOWN.value == "unknown"
    assert DecisionStatus.CANDIDATE.value == "candidate"
    assert DecisionStatus.CONFIRMED.value == "confirmed"
    assert DecisionStatus.REJECTED.value == "rejected"
    assert DecisionStatus.CONFLICT.value == "conflict"
    assert len(DecisionStatus) == 5