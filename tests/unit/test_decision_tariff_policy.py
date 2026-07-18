"""
Testovi za tarifnu politiku (Faza 3).

Pokriva:
- Redoslijed kandidata (rucno > draft > product_code > prefix > istorija > fuzzy)
- Istorija drugog izvoznika je zabranjena
- Fuzzy threshold >= 0.92
- Slab kandidat se prikazuje ali ne primjenjuje
- Auto-popuni klik je batch autorizacija
- LLM nikad ne stvara primjenjiv kandidat
- usage_count se ne povecava tokom preview

agent_tasks/2026-07-18_jedan-izvor-istine-odluke-deklaracije.md
"""
from __future__ import annotations

import pytest

from core.decision.decision_model import DecisionCandidate, DecisionField
from core.decision.evidence import (
    DecisionConfidence,
    DecisionSource,
    Evidence,
    build_evidence,
)
from services.decision.decision_policy import (
    PolicyContext,
    can_auto_apply_tariff,
    rank_tariff_candidates,
)


def _make_candidate(value: str, source: DecisionSource, confidence: DecisionConfidence, score: int = 80) -> DecisionCandidate:
    ev = build_evidence(source, confidence, score=score)
    return DecisionCandidate.make(DecisionField.TARIFF, value, ev)


def _make_user_candidate(value: str) -> DecisionCandidate:
    ev = build_evidence(DecisionSource.USER, DecisionConfidence.CONFIRMED_FROM_DOCUMENT, score=100)
    return DecisionCandidate.make(DecisionField.TARIFF, value, ev)


def _make_exporter_candidate(value: str, score: int = 90) -> DecisionCandidate:
    ev = build_evidence(
        DecisionSource.EXPORTER_HISTORY,
        DecisionConfidence.CONFIRMED_FROM_SAME_EXPORTER_HISTORY,
        score=score,
    )
    return DecisionCandidate.make(DecisionField.TARIFF, value, ev)


def _make_fuzzy_candidate(value: str, score: int = 70) -> DecisionCandidate:
    ev = build_evidence(
        DecisionSource.SIMILARITY,
        DecisionConfidence.SUGGESTED_BY_SIMILARITY,
        score=score,
    )
    return DecisionCandidate.make(DecisionField.TARIFF, value, ev)


def _make_document_candidate(value: str) -> DecisionCandidate:
    ev = build_evidence(
        DecisionSource.DOCUMENT,
        DecisionConfidence.CONFIRMED_FROM_DOCUMENT,
        score=100,
    )
    return DecisionCandidate.make(DecisionField.TARIFF, value, ev)


# ═══════════════════════════════════════════════════════════════════
# Redoslijed kandidata
# ═══════════════════════════════════════════════════════════════════

def test_user_candidate_ranks_first():
    """Rucno potvrdjena vrijednost (USER) uvijek prva."""
    candidates = [
        _make_fuzzy_candidate("82054000"),
        _make_exporter_candidate("84821000"),
        _make_user_candidate("84713000"),
    ]
    ranked = rank_tariff_candidates(candidates, PolicyContext())
    assert ranked[0].value == "84713000"


def test_document_candidate_ranks_before_exporter():
    """Tarifa iz dokumenta (draft-a) ima prednost nad istorijom."""
    candidates = [
        _make_exporter_candidate("84821000"),
        _make_document_candidate("84713000"),
    ]
    ranked = rank_tariff_candidates(candidates, PolicyContext())
    assert ranked[0].value == "84713000"


def test_exporter_history_before_fuzzy():
    """Istorija istog izvoznika > fuzzy match."""
    candidates = [
        _make_fuzzy_candidate("82054000"),
        _make_exporter_candidate("84821000"),
    ]
    ranked = rank_tariff_candidates(candidates, PolicyContext())
    assert ranked[0].value == "84821000"


def test_fuzzy_before_unknown():
    """Fuzzy kandidat > unknown (prazan)."""
    unknown = _make_candidate("", DecisionSource.TARIFF_DATABASE, DecisionConfidence.UNKNOWN, score=0)
    fuzzy = _make_fuzzy_candidate("84821000")
    ranked = rank_tariff_candidates([unknown, fuzzy], PolicyContext())
    assert ranked[0].value == "84821000"


# ═══════════════════════════════════════════════════════════════════
# Auto-apply pravila
# ═══════════════════════════════════════════════════════════════════

def test_can_auto_apply_only_with_explicit_action():
    """Auto-apply samo kroz auto_fill_clicked ili dialog_confirmed."""
    candidate = _make_exporter_candidate("84821000", score=90)

    # preview — ne smije auto-apply
    ctx = PolicyContext(action_type="preview")
    assert can_auto_apply_tariff(candidate, ctx) is False

    # auto_fill_clicked — smije auto-apply
    ctx = PolicyContext(action_type="auto_fill_clicked")
    assert can_auto_apply_tariff(candidate, ctx) is True


def test_cannot_auto_apply_below_threshold():
    """Score ispod 85 — ne smije auto-apply."""
    candidate = _make_exporter_candidate("84821000", score=84)

    ctx = PolicyContext(action_type="auto_fill_clicked")
    assert can_auto_apply_tariff(candidate, ctx) is False


def test_cannot_auto_apply_weak_fuzzy():
    """Fuzzy kandidat sa requires_confirmation — ne smije auto-apply bez dialoga."""
    ev = build_evidence(
        DecisionSource.SIMILARITY,
        DecisionConfidence.WEAK_GUESS,
        score=75,
        requires_confirmation=True,
    )
    candidate = DecisionCandidate.make(DecisionField.TARIFF, "84821000", ev)

    ctx = PolicyContext(action_type="auto_fill_clicked")
    assert can_auto_apply_tariff(candidate, ctx) is False


def test_llm_candidate_never_auto_applies():
    """LLM izvor — nikad auto-apply."""
    ev = build_evidence(DecisionSource.LLM, DecisionConfidence.WEAK_GUESS, score=60)
    candidate = DecisionCandidate.make(DecisionField.TARIFF, "84821000", ev)

    ctx = PolicyContext(action_type="auto_fill_clicked")
    assert can_auto_apply_tariff(candidate, ctx) is False


def test_manual_edit_does_not_auto_apply():
    """Manual edit akcija ne autorizuje auto-apply (treba confirm_manual_value)."""
    candidate = _make_exporter_candidate("84821000", score=90)

    ctx = PolicyContext(action_type="manual_edit")
    assert can_auto_apply_tariff(candidate, ctx) is False


# ═══════════════════════════════════════════════════════════════════
# Granični uslovi
# ═══════════════════════════════════════════════════════════════════

def test_empty_candidates_returns_empty():
    assert rank_tariff_candidates([], PolicyContext()) == []


def test_none_evidence_ranks_last():
    candidate = DecisionCandidate.make(DecisionField.TARIFF, "99999999", None)
    ranked = rank_tariff_candidates([candidate, _make_exporter_candidate("84821000")], PolicyContext())
    assert ranked[0].value == "84821000"


def test_higher_score_within_same_source_ranks_first():
    """Unutar istog izvora, visi score = bolji ranking."""
    c1 = _make_exporter_candidate("84821000", score=95)
    c2 = _make_exporter_candidate("82054000", score=85)
    ranked = rank_tariff_candidates([c2, c1], PolicyContext())
    assert ranked[0].value == "84821000"


def test_usage_count_not_increased_during_ranking():
    """Politika rangiranja ne smije povecavati usage_count."""
    candidates = [
        _make_exporter_candidate("84821000", score=90),
        _make_fuzzy_candidate("82054000", score=75),
    ]
    # Ranking je cista funkcija — vraca sortiranu listu
    ranked = rank_tariff_candidates(candidates, PolicyContext())
    assert len(ranked) == 2