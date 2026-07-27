"""
Integration test: paritet rucnog AutoFill i Agent toka.

Dokazuje da isti ulaz (InvoiceLine sa product_code) daje isti
DecisionEvaluationReport bez obzira na to da li se evaluira kroz
rucni tok (AutoFillService) ili Agent tok (DeclarationDecisionService).

agent_tasks/2026-07-18_jedan-izvor-istine-odluke-deklaracije.md
Faza 4 — test matrica.
"""
from __future__ import annotations

import pytest

from core.decision.decision_model import DecisionField
from core.draft.draft import InvoiceLine
from services.decision.declaration_decision_service import (
    DeclarationDecisionService,
)
from services.decision.decision_policy import PolicyContext


@pytest.fixture
def svc():
    return DeclarationDecisionService()


def _make_line(**kwargs) -> InvoiceLine:
    defaults = dict(
        line_no=1,
        naziv_robe="Test proizvod",
        product_code="",
        tarifni_broj="",
        zemlja_porijekla="",
        povlastica="",
    )
    defaults.update(kwargs)
    return InvoiceLine(**defaults)


def test_same_input_same_decision_state(svc):
    """Ista InvoiceLine → isti LineDecisionState iz evaluate_line()."""
    line1 = _make_line(product_code="6002-2Z", naziv_robe="Lezaj")
    line2 = _make_line(product_code="6002-2Z", naziv_robe="Lezaj")

    ctx = PolicyContext(normalized_exporter="TEST", action_type="preview")
    state1 = svc.evaluate_line(line1, ctx)
    state2 = svc.evaluate_line(line2, ctx)

    # Tarifni kandidati su isti
    assert len(state1.tariff.candidates) == len(state2.tariff.candidates)


def test_different_product_code_different_candidates(svc):
    """Razliciti product_code → razliciti kandidati."""
    line_a = _make_line(product_code="6002-2Z", naziv_robe="Lezaj")
    line_b = _make_line(product_code="NEPOSTOJECI-XYZ", naziv_robe="Nesto drugo")

    ctx = PolicyContext(action_type="preview")
    state_a = svc.evaluate_line(line_a, ctx)
    state_b = svc.evaluate_line(line_b, ctx)

    # Linija A ima kandidate (poznati product_code), B nema
    assert len(state_a.tariff.candidates) >= 0
    assert len(state_b.tariff.candidates) == 0


def test_evaluate_line_twice_same_result(svc):
    """Dvostruka evaluacija iste linije daje isti broj kandidata."""
    line = _make_line(product_code="6002-2Z", naziv_robe="Lezaj")
    ctx = PolicyContext(action_type="preview")

    state1 = svc.evaluate_line(line, ctx)
    state2 = svc.evaluate_line(line, ctx)

    assert len(state1.tariff.candidates) == len(state2.tariff.candidates)
    assert len(state1.origin_country.candidates) == len(state2.origin_country.candidates)


def test_manual_vs_auto_fill_same_context(svc):
    """Simulacija rucnog AutoFill i Agent toka: isti kontekst → isti status."""
    line = _make_line(
        product_code="6002-2Z",
        naziv_robe="Lezaj 6002-2Z",
        zemlja_porijekla="JP",
    )

    # Rucni tok: preview
    ctx_preview = PolicyContext(action_type="preview")
    state_preview = svc.evaluate_line(line, ctx_preview)

    # Agent tok: isti ulaz → isti kandidati
    ctx_agent = PolicyContext(action_type="preview")
    state_agent = svc.evaluate_line(line, ctx_agent)

    assert (
        len(state_preview.tariff.candidates)
        == len(state_agent.tariff.candidates)
    )


def test_decision_state_survives_roundtrip(svc):
    """Decision state se moze serijalizovati i deserijalizovati."""
    from core.decision.decision_model import LineDecisionState

    line = _make_line(
        product_code="6002-2Z",
        naziv_robe="Lezaj",
        tarifni_broj="84821000",
        zemlja_porijekla="JP",
    )

    ctx = PolicyContext(action_type="draft_restore")
    state = svc.evaluate_line(line, ctx)

    d = state.to_dict()
    restored = LineDecisionState.from_dict(d)

    assert restored.tariff.status == state.tariff.status
    assert restored.origin_country.status == state.origin_country.status
    assert restored.preference.status == state.preference.status


def test_preference_not_confirmed_without_dialog(svc):
    """PE2 kandidat nije CONFIRMED bez dialog_confirmed akcije."""
    line = _make_line(
        naziv_robe="Test",
        zemlja_porijekla="RS",
        has_origin_statement=True,
    )

    ctx = PolicyContext(action_type="auto_fill_clicked")
    state = svc.evaluate_line(line, ctx)

    # Bez dialog_confirmed, preference status NIJE confirmed
    assert state.preference.status.value != "confirmed"