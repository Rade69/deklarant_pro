"""
Integration test: prenos decision_state u naimenovanja.

Dokazuje da se samo CONFIRMED vrijednosti iz decision_state prenose
u NaimenovanjeDraft, a CANDIDATE/UNKNOWN ostaju neprimijenjeni.

agent_tasks/2026-07-18_jedan-izvor-istine-odluke-deklaracije.md
"""
from __future__ import annotations

import pytest

from core.decision.decision_model import (
    DecisionField,
    DecisionStatus,
    LineDecisionState,
)
from core.draft.draft import InvoiceLine, NaimenovanjeDraft


def _make_line(**kwargs) -> InvoiceLine:
    defaults = dict(
        line_no=1,
        naziv_robe="Test",
        product_code="",
        tarifni_broj="",
        zemlja_porijekla="",
        povlastica="",
    )
    defaults.update(kwargs)
    return InvoiceLine(**defaults)


def test_confirmed_values_ready_for_naimenovanja():
    """CONFIRMED tarifa, zemlja i povlastica su spremne za naimenovanje."""
    state = LineDecisionState()
    state.tariff.status = DecisionStatus.CONFIRMED
    state.tariff.applied_value = "84821000"
    state.origin_country.status = DecisionStatus.CONFIRMED
    state.origin_country.applied_value = "JP"
    state.preference.status = DecisionStatus.CONFIRMED
    state.preference.applied_value = "EUP"

    line = _make_line(
        tarifni_broj="84821000",
        zemlja_porijekla="JP",
        povlastica="EUP",
    )
    line.decision_state = state

    assert line.tarifni_broj == "84821000"
    assert line.zemlja_porijekla == "JP"
    assert line.povlastica == "EUP"
    assert line.decision_state.tariff.is_confirmed
    assert line.decision_state.origin_country.is_confirmed
    assert line.decision_state.preference.is_confirmed


def test_candidate_values_not_ready_for_naimenovanja():
    """CANDIDATE povlastica NIJE spremna za naimenovanje."""
    state = LineDecisionState()
    state.tariff.status = DecisionStatus.CONFIRMED
    state.tariff.applied_value = "84821000"
    state.origin_country.status = DecisionStatus.CONFIRMED
    state.origin_country.applied_value = "DE"
    state.preference.status = DecisionStatus.CANDIDATE  # NIJE potvrdjeno!

    line = _make_line(tarifni_broj="84821000", zemlja_porijekla="DE")
    line.decision_state = state

    # Tarifa i zemlja su OK
    assert line.decision_state.tariff.is_confirmed
    assert line.decision_state.origin_country.is_confirmed
    # Povlastica NIJE potvrdjena
    assert not line.decision_state.preference.is_confirmed
    assert line.decision_state.preference.status == DecisionStatus.CANDIDATE


def test_rejected_preference_clears_value():
    """REJECTED povlastica — applied_value je prazan."""
    state = LineDecisionState()
    state.preference.status = DecisionStatus.REJECTED
    state.preference.applied_value = ""
    state.preference.rejection_reason = "Nema PE dokaza"

    line = _make_line(povlastica="")
    line.decision_state = state

    assert line.decision_state.preference.is_rejected
    assert line.decision_state.preference.applied_value == ""


def test_all_confirmed_flag():
    """LineDecisionState.all_confirmed — tarifa + zemlja potvrdjene, povlastica opciona."""
    state = LineDecisionState()
    assert not state.all_confirmed

    state.tariff.status = DecisionStatus.CONFIRMED
    state.origin_country.status = DecisionStatus.CONFIRMED
    # preference UNKNOWN ili REJECTED je prihvatljivo
    assert state.all_confirmed


def test_unknown_tariff_blocks_all_confirmed():
    """UNKNOWN tarifa — all_confirmed je False."""
    state = LineDecisionState()
    state.origin_country.status = DecisionStatus.CONFIRMED
    assert not state.all_confirmed


def test_key_generation_from_applied_values():
    """Grouping key se generise iz primijenjenih vrijednosti (direktnih polja)."""
    line = _make_line(
        tarifni_broj="84821000",
        zemlja_porijekla="JP",
        povlastica="",
    )
    state = LineDecisionState()
    state.tariff.status = DecisionStatus.CONFIRMED
    state.tariff.applied_value = "84821000"
    line.decision_state = state

    assert line.key() == ("84821000", "JP", "")