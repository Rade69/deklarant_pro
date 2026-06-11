import json
from pathlib import Path

import pytest

from core.draft.draft import InvoiceLine
from scripts.agent_tariff_eval_report import (
    evaluate_case,
    metrics_for_cases,
)
from services.agent.validation.historical_tariff_search_service import (
    HistoricalTariffSearchService,
    TariffHistoryMatch,
)
from services.agent.validation.evidence_model import (
    DecisionConfidence,
    DecisionSource,
)
from services.agent.validation.tariff_decision_model import (
    TariffDecisionOutcome,
    TariffDecisionThresholds,
    decide_tariff_match,
)


CASES_PATH = Path(__file__).parents[1] / "fixtures" / "agent" / "tariff_validation_cases.json"


def _match(original: str, historical_tariff: str, usage: int, source: str, confidence: float):
    return TariffHistoryMatch(
        line_index=-1,
        naziv_robe_original=original,
        naziv_robe_historijski=original,
        tarifni_broj_historijski=historical_tariff,
        tarifni_broj_trenutni="",
        supplier_match=False,
        usage_count=usage,
        source=source,
        confidence=confidence,
    )


def _case_ids():
    with CASES_PATH.open(encoding="utf-8") as fh:
        return [case["name"] for case in json.load(fh)]


def _load_cases():
    with CASES_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _thresholds() -> TariffDecisionThresholds:
    return TariffDecisionThresholds(
        min_usage_for_cross_chapter=5,
        min_usage_for_out_of_profile_chapter=10,
        min_usage_for_weak_source=2,
    )


@pytest.mark.parametrize("case", _load_cases(), ids=_case_ids())
def test_historical_validation_evaluation_cases(case):
    matches = evaluate_case(case)
    expected = case["expected"]

    if expected["action"] == "suppress":
        assert matches == []
        return

    assert len(matches) == 1
    assert matches[0].tarifni_broj_historijski == expected["tarifni_broj"]
    assert expected["reason_contains"] in matches[0].decision_reason


def test_historical_validation_evaluation_metrics():
    metrics = metrics_for_cases(_load_cases())

    assert metrics == {
        "true_positive": 10,
        "true_negative": 7,
        "false_positive": 0,
        "false_negative": 0,
        "wrong_tariff": 0,
        "explanation_missing": 0,
    }


def test_tariff_decision_model_returns_explicit_show_strong():
    match = _match(
        "DIXI dekstroza 7vit bomb a40",
        "17049081",
        usage=10,
        source="MEDIKO",
        confidence=0.68,
    )

    decision = decide_tariff_match(match, "21069092", {}, _thresholds())

    assert decision.outcome is TariffDecisionOutcome.SHOW_STRONG
    assert "Promjena poglavlja" in decision.reason
    assert decision.score > 0
    assert decision.positive_reasons
    assert decision.negative_reasons


def test_tariff_decision_model_returns_explicit_show_weak():
    match = _match(
        "OHP SILICON CEPOVI TUBA A2",
        "39269097",
        usage=3,
        source="MEDIKO",
        confidence=0.66,
    )

    decision = decide_tariff_match(match, "3926909710", {}, _thresholds())

    assert decision.outcome is TariffDecisionOutcome.SHOW_WEAK
    assert "Ista tarifna glava" in decision.reason
    assert decision.score > 0
    assert "Prijedlog ostaje u istoj tarifnoj glavi." in decision.positive_reasons


def test_tariff_decision_model_returns_explicit_suppress():
    match = _match(
        "BORT 112900 B.R.Z.palac lev XL",
        "11010015",
        usage=1,
        source="",
        confidence=0.60,
    )

    decision = decide_tariff_match(match, "63079099", {}, _thresholds())

    assert decision.outcome is TariffDecisionOutcome.SUPPRESS
    assert decision.reason == ""
    assert decision.score <= 0
    assert decision.negative_reasons


def test_tariff_decision_model_score_explains_missing_current_tariff():
    match = _match(
        "CICASTIM GEL15 ML. (5+1)PROMO",
        "33049900",
        usage=1,
        source="MEDIKO",
        confidence=0.60,
    )

    decision = decide_tariff_match(match, "", {}, _thresholds())

    assert decision.outcome is TariffDecisionOutcome.SHOW_STRONG
    assert decision.score > 0
    assert "Trenutna tarifa nije popunjena." in decision.positive_reasons


def test_historical_validation_filters_single_weak_cross_chapter_match(monkeypatch):
    svc = HistoricalTariffSearchService()
    line = InvoiceLine(
        line_no=58,
        naziv_robe="BORT 112900 B.R.Z.palac lev XL",
        tarifni_broj="63079099",
    )

    monkeypatch.setattr(
        svc,
        "_search_one",
        lambda *_: [
            _match(
                "BORT 112900 B.R.Z.palac lev XL",
                "11010015",
                usage=1,
                source="",
                confidence=0.60,
            )
        ],
    )

    assert svc.validate_lines([line]) == []


def test_historical_validation_allows_strong_cross_chapter_match(monkeypatch):
    svc = HistoricalTariffSearchService()
    line = InvoiceLine(
        line_no=52,
        naziv_robe="DIXI dekstroza 7vit bomb a40",
        tarifni_broj="21069092",
    )

    monkeypatch.setattr(
        svc,
        "_search_one",
        lambda *_: [
            _match(
                "DIXI dekstroza 7vit bomb a40",
                "17049081",
                usage=10,
                source="MEDIKO",
                confidence=0.68,
            )
        ],
    )
    monkeypatch.setattr(svc, "_feedback_action", lambda m: "")

    matches = svc.validate_lines([line])

    assert len(matches) == 1
    assert matches[0].tarifni_broj_historijski == "17049081"
    assert "Promjena poglavlja" in matches[0].decision_reason


def test_historical_validation_marks_placeholder_source_as_unknown(monkeypatch):
    svc = HistoricalTariffSearchService()
    line = InvoiceLine(
        line_no=52,
        naziv_robe="DIXI dekstroza 7vit bomb a40",
        tarifni_broj="21069092",
    )

    monkeypatch.setattr(
        svc,
        "_search_one",
        lambda *_: [
            _match(
                "DIXI dekstroza 7vit bomb a40",
                "17049081",
                usage=10,
                source="HISTORIJA",
                confidence=0.68,
            )
        ],
    )
    monkeypatch.setattr(svc, "_feedback_action", lambda m: "")

    matches = svc.validate_lines([line])

    assert len(matches) == 1
    assert matches[0].evidence is not None
    assert matches[0].evidence.confidence is DecisionConfidence.UNKNOWN
    assert matches[0].evidence.source is DecisionSource.TARIFF_DATABASE


def test_historical_validation_uses_invoice_profile_for_cross_chapter_noise(monkeypatch):
    svc = HistoricalTariffSearchService()
    lines = [
        InvoiceLine(line_no=1, naziv_robe="GW krema", tarifni_broj="33049900"),
        InvoiceLine(line_no=2, naziv_robe="GW puder", tarifni_broj="33049900"),
        InvoiceLine(line_no=3, naziv_robe="VITIX gel", tarifni_broj="33049900"),
        InvoiceLine(line_no=4, naziv_robe="OHP cepovi", tarifni_broj="39269097"),
        InvoiceLine(line_no=5, naziv_robe="BORT 112900 B.R.Z.palac lev XL", tarifni_broj="63079099"),
    ]

    def fake_search(naziv, *_):
        if naziv.startswith("BORT"):
            return [
                _match(
                    "BORT 112900 B.R.Z.palac lev XL",
                    "11010015",
                    usage=5,
                    source="MEDIKO",
                    confidence=0.68,
                )
            ]
        return []

    monkeypatch.setattr(svc, "_search_one", fake_search)

    assert svc.validate_lines(lines) == []


def test_historical_validation_allows_out_of_profile_with_very_strong_evidence(monkeypatch):
    svc = HistoricalTariffSearchService()
    lines = [
        InvoiceLine(line_no=1, naziv_robe="GW krema", tarifni_broj="33049900"),
        InvoiceLine(line_no=2, naziv_robe="GW puder", tarifni_broj="33049900"),
        InvoiceLine(line_no=3, naziv_robe="VITIX gel", tarifni_broj="33049900"),
        InvoiceLine(line_no=4, naziv_robe="OHP cepovi", tarifni_broj="39269097"),
        InvoiceLine(line_no=5, naziv_robe="DIXI dekstroza 7vit bomb a40", tarifni_broj="21069092"),
    ]

    def fake_search(naziv, *_):
        if naziv.startswith("DIXI"):
            return [
                _match(
                    "DIXI dekstroza 7vit bomb a40",
                    "17049081",
                    usage=12,
                    source="MEDIKO",
                    confidence=0.70,
                )
            ]
        return []

    monkeypatch.setattr(svc, "_search_one", fake_search)
    monkeypatch.setattr(svc, "_feedback_action", lambda m: "")

    matches = svc.validate_lines(lines)

    assert len(matches) == 1
    assert matches[0].tarifni_broj_historijski == "17049081"


def test_historical_validation_auto_applies_previously_accepted_feedback(monkeypatch):
    svc = HistoricalTariffSearchService()
    line = InvoiceLine(
        line_no=1,
        naziv_robe="SUSSINA 650 tbl.",
        tarifni_broj="38249993",
    )

    monkeypatch.setattr(
        svc,
        "_search_one",
        lambda *_: [
            _match(
                "SUSSINA 650 tbl.",
                "21069098",
                usage=25,
                source="MED",
                confidence=0.72,
            )
        ],
    )
    monkeypatch.setattr(
        "services.agent.validation.tariff_feedback_service.get_tariff_validation_feedback_summary",
        lambda *_: {"accept": 1, "reject": 0},
    )

    matches = svc.validate_lines([line])

    assert matches == []
    assert line.tarifni_broj == "21069098"
    assert svc.last_auto_applied == [(0, "21069098")]


def test_historical_validation_suppresses_previously_rejected_feedback(monkeypatch):
    svc = HistoricalTariffSearchService()
    line = InvoiceLine(
        line_no=1,
        naziv_robe="OHP SILICON CEPOVI ZA USI a6",
        tarifni_broj="3926909710",
    )

    monkeypatch.setattr(
        svc,
        "_search_one",
        lambda *_: [
            _match(
                "OHP SILICON CEPOVI ZA USI a6",
                "39269097",
                usage=16,
                source="",
                confidence=0.65,
            )
        ],
    )
    monkeypatch.setattr(
        "services.agent.validation.tariff_feedback_service.get_tariff_validation_feedback_summary",
        lambda *_: {"accept": 0, "reject": 1},
    )

    matches = svc.validate_lines([line])

    assert matches == []
    assert line.tarifni_broj == "3926909710"
    assert svc.last_auto_applied == []


def test_historical_validation_drops_tariff_missing_from_official_tariff(monkeypatch):
    svc = HistoricalTariffSearchService()

    monkeypatch.setattr(svc, "_tariff_exists", lambda code: code != "40199090")

    rows = [
        {
            "commodity_code": "40199090",
            "naziv_robe": "GW GEL STITNIK CUKLJEVA MALI PRST",
            "supplier": "MEDIKO",
            "usage_count": 10,
            "source": "xml",
        },
        {
            "commodity_code": "40149000",
            "naziv_robe": "GW STITNIK MALI PRST",
            "supplier": "MEDIKO",
            "usage_count": 8,
            "source": "xml",
        },
    ]

    matches = svc._to_matches(rows, "GW GEL STITNIK CUKLJEVA MALI PRST")

    assert [match.tarifni_broj_historijski for match in matches] == ["40149000"]
