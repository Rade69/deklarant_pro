from core.draft.draft import InvoiceLine
import pytest

from services.agent.validation.evidence_model import (
    DecisionConfidence,
    DecisionSource,
    Evidence,
    build_evidence,
    evidence_from_preference,
    evidence_from_tariff_decision,
    tariff_confidence_label,
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
        source="MEDICO PHARM SERVIS",
    )

    assert evidence.source is DecisionSource.SIMILARITY
    assert evidence.confidence is DecisionConfidence.SUGGESTED_BY_SIMILARITY
    assert evidence.requires_confirmation is True


@pytest.mark.parametrize("source", ["", "HISTORIJA", "+", "A"])
def test_unknown_source_placeholders_are_unknown(source):
    evidence = evidence_from_tariff_decision(
        decision_outcome="show_strong",
        supplier_match=False,
        usage_count=8,
        source=source,
    )

    assert evidence.confidence is DecisionConfidence.UNKNOWN
    assert evidence.source is DecisionSource.TARIFF_DATABASE
    assert evidence.requires_confirmation is True


@pytest.mark.parametrize(
    ("confidence", "label"),
    [
        (DecisionConfidence.CONFIRMED_FROM_SAME_EXPORTER_HISTORY, "jak"),
        (DecisionConfidence.SUGGESTED_BY_SIMILARITY, "srednji"),
        (DecisionConfidence.WEAK_GUESS, "slab"),
        (DecisionConfidence.UNKNOWN, "nepoznat"),
    ],
)
def test_tariff_confidence_label(confidence, label):
    evidence = build_evidence(DecisionSource.TARIFF_DATABASE, confidence)

    assert tariff_confidence_label(evidence) == label


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


def test_evidence_from_preference_pe1_eur1_confirmed():
    item = InvoiceLine(
        zemlja_porijekla="DE",
        povlastica="EUP",
        eur1_number="A-123456",
        has_origin_statement=False,
    )

    evidence = evidence_from_preference(item)

    assert evidence.source is DecisionSource.DOCUMENT
    assert evidence.confidence is DecisionConfidence.CONFIRMED_FROM_DOCUMENT
    assert evidence.requires_confirmation is False
    assert evidence.data["doc_code"] == "PE1"


def test_evidence_from_preference_pe2_origin_statement():
    item = InvoiceLine(
        zemlja_porijekla="RS",
        povlastica="CEFTAP",
        has_origin_statement=True,
        is_authorized_exporter=False,
    )

    evidence = evidence_from_preference(item)

    assert evidence.source is DecisionSource.DOCUMENT
    assert evidence.confidence is DecisionConfidence.CONFIRMED_FROM_DOCUMENT
    assert evidence.requires_confirmation is False
    assert evidence.data["doc_code"] == "PE2"


def test_evidence_from_preference_pe3_authorized_exporter():
    item = InvoiceLine(
        zemlja_porijekla="TR",
        povlastica="TRP",
        has_origin_statement=True,
        is_authorized_exporter=True,
    )

    evidence = evidence_from_preference(item)

    assert evidence.source is DecisionSource.DOCUMENT
    assert evidence.confidence is DecisionConfidence.CONFIRMED_FROM_DOCUMENT
    assert evidence.requires_confirmation is False
    assert evidence.data["doc_code"] == "PE3"


def test_evidence_from_preference_eu_bez_dokumenta_je_weak_guess():
    """Povlastica izvedena samo iz zemlje (EU), bez PE1/PE2/PE3 — slab dokaz."""
    item = InvoiceLine(
        zemlja_porijekla="DE",
        povlastica="EUP",
        eur1_number="",
        has_origin_statement=False,
        is_authorized_exporter=False,
    )

    evidence = evidence_from_preference(item)

    assert evidence.source is DecisionSource.SIMILARITY
    assert evidence.confidence is DecisionConfidence.WEAK_GUESS
    assert evidence.requires_confirmation is True


def test_evidence_from_preference_cn_bez_povlastice_je_unknown():
    """Kina nema povlasticu niti PE dokaz — unknown, ali nema šta da se potvrdi."""
    item = InvoiceLine(
        zemlja_porijekla="CN",
        povlastica="",
        eur1_number="",
        has_origin_statement=False,
        is_authorized_exporter=False,
    )

    evidence = evidence_from_preference(item)

    assert evidence.source is DecisionSource.TARIFF_DATABASE
    assert evidence.confidence is DecisionConfidence.UNKNOWN
    assert evidence.requires_confirmation is True
    assert item.povlastica == ""
