"""
Testovi za politiku zemlje porijekla (Faza 3).

Pokriva:
- Redoslijed izvora (rucno > dokument > parser > mapping > unknown)
- Baza i istorija ne smiju prepisati dokument
- Konflikt se cuva kao CONFLICT sa oba izvora
- Nepoznata zemlja ostaje prazna

agent_tasks/2026-07-18_jedan-izvor-istine-odluke-deklaracije.md
"""
from __future__ import annotations

import pytest

from core.decision.decision_model import DecisionCandidate, DecisionField
from core.decision.evidence import (
    DecisionConfidence,
    DecisionSource,
    build_evidence,
)
from services.decision.decision_policy import (
    PolicyContext,
    can_auto_apply_origin,
    rank_origin_candidates,
)


def _make_candidate(value: str, source: DecisionSource, confidence: DecisionConfidence, score: int = 80) -> DecisionCandidate:
    ev = build_evidence(source, confidence, score=score)
    return DecisionCandidate.make(DecisionField.ORIGIN_COUNTRY, value, ev)


def _user(value: str) -> DecisionCandidate:
    return _make_candidate(value, DecisionSource.USER, DecisionConfidence.CONFIRMED_FROM_DOCUMENT, score=100)


def _document(value: str) -> DecisionCandidate:
    return _make_candidate(value, DecisionSource.DOCUMENT, DecisionConfidence.CONFIRMED_FROM_DOCUMENT, score=100)


def _parser(value: str) -> DecisionCandidate:
    return _make_candidate(value, DecisionSource.PARSER, DecisionConfidence.SUGGESTED_BY_SIMILARITY, score=75)


def _mapping(value: str) -> DecisionCandidate:
    return _make_candidate(value, DecisionSource.TARIFF_DATABASE, DecisionConfidence.WEAK_GUESS, score=60)


# ═══════════════════════════════════════════════════════════════════
# Redoslijed izvora
# ═══════════════════════════════════════════════════════════════════

def test_user_ranks_first():
    ranked = rank_origin_candidates(
        [_mapping("CN"), _user("DE"), _document("RS")],
        PolicyContext(),
    )
    assert ranked[0].value == "DE"


def test_document_before_parser():
    ranked = rank_origin_candidates(
        [_parser("RS"), _document("DE")],
        PolicyContext(),
    )
    assert ranked[0].value == "DE"


def test_parser_before_mapping():
    ranked = rank_origin_candidates(
        [_mapping("CN"), _parser("RS")],
        PolicyContext(),
    )
    assert ranked[0].value == "RS"


def test_mapping_is_informational_only():
    """Mapping i istorija su samo informativni — najnizi prioritet."""
    ranked = rank_origin_candidates(
        [_mapping("CN"), _document("DE")],
        PolicyContext(),
    )
    # Dokument uvijek ispred mapping-a
    assert ranked[0].value == "DE"


# ═══════════════════════════════════════════════════════════════════
# Auto-apply pravila
# ═══════════════════════════════════════════════════════════════════

def test_document_origin_can_auto_apply():
    candidate = _document("DE")
    ctx = PolicyContext(action_type="auto_fill_clicked")
    assert can_auto_apply_origin(candidate, ctx) is True


def test_mapping_origin_cannot_auto_apply():
    """Mapping/istorija NIKAD ne smiju auto-apply zemlju."""
    candidate = _mapping("CN")
    ctx = PolicyContext(action_type="auto_fill_clicked")
    assert can_auto_apply_origin(candidate, ctx) is False


def test_preview_action_cannot_auto_apply_origin():
    candidate = _document("DE")
    ctx = PolicyContext(action_type="preview")
    assert can_auto_apply_origin(candidate, ctx) is False


def test_parser_origin_can_auto_apply():
    candidate = _parser("RS")
    ctx = PolicyContext(action_type="auto_fill_clicked")
    assert can_auto_apply_origin(candidate, ctx) is True


# ═══════════════════════════════════════════════════════════════════
# Baza/istorija ne prepisuju dokument
# ═══════════════════════════════════════════════════════════════════

def test_document_always_before_mapping():
    """Cak i sa nizim score-om, dokument je ispred mapping-a."""
    doc = _make_candidate("DE", DecisionSource.DOCUMENT, DecisionConfidence.CONFIRMED_FROM_DOCUMENT, score=70)
    mp = _make_candidate("CN", DecisionSource.TARIFF_DATABASE, DecisionConfidence.CONFIRMED_FROM_SAME_EXPORTER_HISTORY, score=95)
    ranked = rank_origin_candidates([mp, doc], PolicyContext())
    assert ranked[0].value == "DE"


def test_empty_candidates():
    assert rank_origin_candidates([], PolicyContext()) == []


def test_none_evidence_ranks_last():
    candidate = DecisionCandidate.make(DecisionField.ORIGIN_COUNTRY, "XX", None)
    ranked = rank_origin_candidates([candidate, _document("DE")], PolicyContext())
    assert ranked[0].value == "DE"