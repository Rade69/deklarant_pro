"""
Integration test: decision_state draft save/load roundtrip.

Dokazuje da se decision_state ispravno serijalizuje i deserijalizuje
kroz InvoiceLine.from_any() — simulira Deklarant Pro draft save/load.

agent_tasks/2026-07-18_jedan-izvor-istine-odluke-deklaracije.md
"""
from __future__ import annotations

import json
import pytest

from core.decision.decision_model import (
    DecisionField,
    DecisionStatus,
    LineDecisionState,
)
from core.draft.draft import InvoiceLine


def test_empty_decision_state_roundtrip():
    """InvoiceLine bez decision_state → from_any → None."""
    line = InvoiceLine(naziv_robe="Test", tarifni_broj="12345678")
    d = {
        "naziv_robe": line.naziv_robe,
        "tarifni_broj": line.tarifni_broj,
        "decision_state": None,
    }
    restored = InvoiceLine.from_any(d)
    assert restored.decision_state is None
    assert restored.tarifni_broj == "12345678"


def test_confirmed_tariff_state_roundtrip():
    """Potvrdjena tarifa u decision_state prezivi roundtrip."""
    state = LineDecisionState()
    state.tariff.status = DecisionStatus.CONFIRMED
    state.tariff.applied_value = "84821000"
    state.origin_country.status = DecisionStatus.CANDIDATE

    line = InvoiceLine(
        naziv_robe="Lezaj",
        tarifni_broj="84821000",
        decision_state=state,
    )

    d = {
        "naziv_robe": line.naziv_robe,
        "tarifni_broj": line.tarifni_broj,
        "decision_state": state.to_dict(),
    }
    restored = InvoiceLine.from_any(d)

    assert restored.decision_state is not None
    assert restored.decision_state.tariff.status == DecisionStatus.CONFIRMED
    assert restored.decision_state.tariff.applied_value == "84821000"
    assert restored.decision_state.origin_country.status == DecisionStatus.CANDIDATE


def test_decision_state_json_roundtrip():
    """Decision state prezivi JSON serijalizaciju (simulira draft file)."""
    state = LineDecisionState()
    state.tariff.status = DecisionStatus.CONFIRMED
    state.tariff.applied_value = "84821000"
    state.origin_country.status = DecisionStatus.CANDIDATE
    state.preference.status = DecisionStatus.REJECTED
    state.preference.rejection_reason = "Nema dokaza"

    json_str = json.dumps(state.to_dict())
    restored_dict = json.loads(json_str)
    restored = LineDecisionState.from_dict(restored_dict)

    assert restored.tariff.status == DecisionStatus.CONFIRMED
    assert restored.tariff.applied_value == "84821000"
    assert restored.origin_country.status == DecisionStatus.CANDIDATE
    assert restored.preference.status == DecisionStatus.REJECTED
    assert restored.preference.rejection_reason == "Nema dokaza"


def test_decision_state_not_in_legacy_dict():
    """Stari dict bez decision_state — from_any() ne baca gresku."""
    old_dict = {
        "naziv_robe": "Stara roba",
        "tarifni_broj": "99999999",
        "zemlja_porijekla": "CN",
    }
    line = InvoiceLine.from_any(old_dict)

    assert line.naziv_robe == "Stara roba"
    assert line.tarifni_broj == "99999999"
    assert line.decision_state is None


def test_multiple_lines_roundtrip():
    """Vise linija sa razlicitim decision_state-ovima."""
    lines_data = []

    for i, (tariff, origin, pref) in enumerate([
        ("84821000", "JP", ""),
        ("82054000", "CN", ""),
        ("84713000", "DE", "EUP"),
    ]):
        state = LineDecisionState()
        if tariff:
            state.tariff.status = DecisionStatus.CONFIRMED
            state.tariff.applied_value = tariff
        if origin:
            state.origin_country.status = DecisionStatus.CONFIRMED
            state.origin_country.applied_value = origin
        if pref:
            state.preference.status = DecisionStatus.CONFIRMED
            state.preference.applied_value = pref

        line = InvoiceLine(
            line_no=i+1,
            naziv_robe=f"Proizvod {i+1}",
            tarifni_broj=tariff,
            zemlja_porijekla=origin,
            povlastica=pref,
            decision_state=state,
        )

        d = {
            "line_no": line.line_no,
            "naziv_robe": line.naziv_robe,
            "tarifni_broj": line.tarifni_broj,
            "zemlja_porijekla": line.zemlja_porijekla,
            "povlastica": line.povlastica,
            "decision_state": state.to_dict(),
        }
        lines_data.append(d)

    restored = [InvoiceLine.from_any(d) for d in lines_data]

    assert len(restored) == 3
    assert restored[0].decision_state.tariff.applied_value == "84821000"
    assert restored[1].decision_state.tariff.applied_value == "82054000"
    assert restored[2].decision_state.preference.applied_value == "EUP"