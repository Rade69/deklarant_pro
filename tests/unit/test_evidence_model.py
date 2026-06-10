from services.agent.validation.evidence_model import (
    DecisionConfidence,
    DecisionSource,
    Evidence,
    build_evidence,
    evidence_from_tariff_decision,
)


def test_confirmed_from_document_does_not_require_confirmation():
    evidence = build_evidence(
        DecisionSource.DOCUMENT,
        DecisionConfidence.CONFIRMED_FROM_DOCUMENT,
        "Potvrdjeno iz EUR.1 dokumenta.",
    )

    assert isinstance(evidence, Evidence)
    assert evidence.source is DecisionSource.DOCUMENT
    assert evidence.confidence is DecisionConfidence.CONFIRMED_FROM_DOCUMENT
    assert evidence.requires_confirmation is False


def test_confirmed_from_same_exporter_history():
    evidence = evidence_from_tariff_decision(
        decision_outcome="show_strong",
        supplier_match=True,
        usage_count=12,
        source="MEDICO PHARM SERVIS",
    )

    assert evidence.source is DecisionSource.EXPORTER_HISTORY
    assert evidence.confidence is DecisionConfidence.CONFIRMED_FROM_SAME_EXPORTER_HISTORY
    assert evidence.requires_confirmation is False
    assert evidence.data["supplier_match"] is True


def test_suggested_by_similarity():
    evidence = evidence_from_tariff_decision(
        decision_outcome="show_strong",
        supplier_match=False,
        usage_count=8,
        source="HISTORIJA",
    )

    assert evidence.source is DecisionSource.SIMILARITY
    assert evidence.confidence is DecisionConfidence.SUGGESTED_BY_SIMILARITY
    assert evidence.requires_confirmation is True


def test_weak_guess():
    evidence = evidence_from_tariff_decision(
        decision_outcome="show_weak",
        supplier_match=True,
        usage_count=2,
        source="MEDICO PHARM SERVIS",
    )

    assert evidence.confidence is DecisionConfidence.WEAK_GUESS
    assert evidence.source is DecisionSource.EXPORTER_HISTORY
    assert evidence.requires_confirmation is True


def test_unknown_for_suppressed_decision():
    evidence = evidence_from_tariff_decision(
        decision_outcome="suppress",
        supplier_match=False,
        usage_count=0,
        source="",
    )

    assert evidence.confidence is DecisionConfidence.UNKNOWN
    assert evidence.source is DecisionSource.TARIFF_DATABASE
    assert evidence.requires_confirmation is True
