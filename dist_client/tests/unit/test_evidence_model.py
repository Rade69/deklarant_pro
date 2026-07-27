from core.draft.draft import InvoiceLine
import pytest

from services.agent.validation.evidence_model import (
    DecisionConfidence,
    DecisionScoreCategory,
    DecisionSource,
    Evidence,
    badge_colors_for_score,
    build_evidence,
    evidence_badge_colors,
    evidence_score_category,
    evidence_from_preference,
    evidence_from_tariff_decision,
    score_band_for_confidence,
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
    assert evidence.score == 100
    assert evidence.score_category is DecisionScoreCategory.CONFIRMED
    assert evidence.auto_applicable is True


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
    assert evidence.score == 90
    assert evidence.score_category is DecisionScoreCategory.STRONG_HISTORY


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
    assert evidence.score == 75
    assert evidence.score_category is DecisionScoreCategory.NEEDS_REVIEW


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
    assert evidence.score == 0
    assert evidence.should_recommend is False


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
    assert evidence.score == 60
    assert evidence.score_category is DecisionScoreCategory.WEAK_INFORMATIONAL
    assert evidence.should_recommend is True


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
    assert evidence.score_category is DecisionScoreCategory.HIDDEN


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
    assert evidence.score == 100


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
    assert evidence.auto_applicable is True


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
    assert evidence.score_category is DecisionScoreCategory.CONFIRMED


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
    assert evidence.score == 60


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
    assert evidence.should_recommend is False


@pytest.mark.parametrize(
    ("score", "category"),
    [
        (100, DecisionScoreCategory.CONFIRMED),
        (95, DecisionScoreCategory.CONFIRMED),
        (94, DecisionScoreCategory.STRONG_HISTORY),
        (85, DecisionScoreCategory.STRONG_HISTORY),
        (84, DecisionScoreCategory.NEEDS_REVIEW),
        (70, DecisionScoreCategory.NEEDS_REVIEW),
        (69, DecisionScoreCategory.WEAK_INFORMATIONAL),
        (50, DecisionScoreCategory.WEAK_INFORMATIONAL),
        (49, DecisionScoreCategory.HIDDEN),
        (-10, DecisionScoreCategory.HIDDEN),
    ],
)
def test_evidence_score_category_thresholds(score, category):
    assert evidence_score_category(score) is category


def test_build_evidence_clamps_explicit_score():
    evidence = build_evidence(
        DecisionSource.SIMILARITY,
        DecisionConfidence.SUGGESTED_BY_SIMILARITY,
        score=160,
    )

    assert evidence.score == 100
    assert evidence.score_category is DecisionScoreCategory.CONFIRMED


def test_llm_source_cannot_create_confirmed_evidence():
    evidence = build_evidence(
        DecisionSource.LLM,
        DecisionConfidence.CONFIRMED_FROM_DOCUMENT,
        "LLM tvrdi da je potvrdjeno.",
    )

    assert evidence.source is DecisionSource.LLM
    assert evidence.confidence is DecisionConfidence.WEAK_GUESS
    assert evidence.requires_confirmation is True
    assert evidence.score == 60


def test_evidence_to_dict_is_structured_for_agent_ui():
    evidence = build_evidence(
        DecisionSource.EXPORTER_HISTORY,
        DecisionConfidence.CONFIRMED_FROM_SAME_EXPORTER_HISTORY,
        "Potvrdjeno iz istorije istog izvoznika.",
        {"supplier": "PIP FOOD GROUP DOO", "usage_count": 6},
    )

    payload = evidence.to_dict()

    assert payload["source"] == "exporter_history"
    assert payload["confidence"] == "confirmed_from_same_exporter_history"
    assert payload["score"] == 90
    assert payload["score_category"] == "strong_history"
    assert payload["should_recommend"] is True
    assert payload["auto_applicable"] is True


def test_evidence_model_covers_required_decision_sources():
    assert {
        DecisionSource.DOCUMENT.value,
        DecisionSource.EXPORTER_HISTORY.value,
        DecisionSource.TARIFF_DATABASE.value,
        DecisionSource.SIMILARITY.value,
        DecisionSource.PARSER.value,
        DecisionSource.USER.value,
        DecisionSource.LLM.value,
    } <= {source.value for source in DecisionSource}


def test_evidence_badge_colors_distinct_per_score_category():
    """Faza 5/6: 95% dokaz i 60% pretpostavka ne smiju imati isti badge stil."""
    seen = set()
    for category in DecisionScoreCategory:
        evidence = Evidence(
            source=DecisionSource.TARIFF_DATABASE,
            confidence=DecisionConfidence.UNKNOWN,
            score=0,
            score_category=category,
        )
        text_color, background_color = evidence_badge_colors(evidence)
        assert text_color.startswith("#")
        assert background_color.startswith("#")
        seen.add((text_color, background_color))

    assert len(seen) == len(list(DecisionScoreCategory))


def test_badge_colors_for_score_matches_evidence_badge_colors():
    """Faza 6: chat prijedlozi koriste isti badge stil kao TariffValidationDialog."""
    for score, confidence in [
        (95, DecisionConfidence.CONFIRMED_FROM_DOCUMENT),
        (90, DecisionConfidence.CONFIRMED_FROM_SAME_EXPORTER_HISTORY),
        (75, DecisionConfidence.SUGGESTED_BY_SIMILARITY),
        (60, DecisionConfidence.WEAK_GUESS),
        (0, DecisionConfidence.UNKNOWN),
    ]:
        evidence = Evidence(
            source=DecisionSource.TARIFF_DATABASE,
            confidence=confidence,
            score=score,
            score_category=evidence_score_category(score),
        )
        assert badge_colors_for_score(score) == evidence_badge_colors(evidence)

    # jak (90%) i slab (60%) prijedlog moraju biti vizuelno razliciti
    assert badge_colors_for_score(90) != badge_colors_for_score(60)


def test_score_band_for_confidence_ne_preklapa_kategorije():
    """
    Opsezi po kategoriji se ne smiju preklapati — inace bi isti broj mogao
    izgledati ispravno i za "jak" i za "slab" (korisnicka primjedba
    2026-07-21: rijec i procenat su djelovali kontradiktorno).
    """
    bands = [
        score_band_for_confidence(DecisionConfidence.UNKNOWN),
        score_band_for_confidence(DecisionConfidence.WEAK_GUESS),
        score_band_for_confidence(DecisionConfidence.SUGGESTED_BY_SIMILARITY),
        score_band_for_confidence(DecisionConfidence.CONFIRMED_FROM_SAME_EXPORTER_HISTORY),
        score_band_for_confidence(DecisionConfidence.CONFIRMED_FROM_DOCUMENT),
    ]
    for (_, prev_max), (next_min, _) in zip(bands, bands[1:]):
        assert next_min == prev_max + 1

    # Svaki bucket-default (_DEFAULT_SCORES) mora pasti unutar sopstvenog banda.
    for confidence, default_score in [
        (DecisionConfidence.CONFIRMED_FROM_DOCUMENT, 100),
        (DecisionConfidence.CONFIRMED_FROM_SAME_EXPORTER_HISTORY, 90),
        (DecisionConfidence.SUGGESTED_BY_SIMILARITY, 75),
        (DecisionConfidence.WEAK_GUESS, 60),
    ]:
        band_min, band_max = score_band_for_confidence(confidence)
        assert band_min <= default_score <= band_max
