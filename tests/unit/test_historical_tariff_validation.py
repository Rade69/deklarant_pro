import json
from pathlib import Path

import pytest

from core.draft.draft import InvoiceLine
from services.agent.validation.historical_tariff_search_service import (
    HistoricalTariffSearchService,
    TariffHistoryMatch,
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


def _invoice_line(data: dict) -> InvoiceLine:
    return InvoiceLine(
        line_no=data["line_no"],
        naziv_robe=data["naziv_robe"],
        tarifni_broj=data.get("tarifni_broj", ""),
    )


def _history_match(data: dict) -> TariffHistoryMatch:
    return _match(
        data["naziv_robe"],
        data["tarifni_broj"],
        usage=data["usage_count"],
        source=data["source"],
        confidence=data["confidence"],
    )


def _evaluate_case(case: dict) -> list[TariffHistoryMatch]:
    svc = HistoricalTariffSearchService()
    lines = [_invoice_line(line) for line in case["invoice_lines"]]
    history_matches = [_history_match(match) for match in case["history_matches"]]

    def fake_search(naziv, *_):
        return [
            match for match in history_matches
            if match.naziv_robe_original == naziv
        ]

    svc._search_one = fake_search

    return svc.validate_lines(lines)


def _metrics_for_cases(cases: list[dict]) -> dict:
    metrics = {
        "true_positive": 0,
        "true_negative": 0,
        "false_positive": 0,
        "false_negative": 0,
        "wrong_tariff": 0,
        "explanation_missing": 0,
    }

    for case in cases:
        matches = _evaluate_case(case)
        expected = case["expected"]
        expected_show = expected["action"] == "show"

        if expected_show:
            expected_tariff = expected["tarifni_broj"]
            if not matches:
                metrics["false_negative"] += 1
            elif matches[0].tarifni_broj_historijski == expected_tariff:
                metrics["true_positive"] += 1
            else:
                metrics["wrong_tariff"] += 1
        elif matches:
            metrics["false_positive"] += 1
        else:
            metrics["true_negative"] += 1

        metrics["explanation_missing"] += sum(
            1 for match in matches if not match.decision_reason
        )

    return metrics


@pytest.mark.parametrize("case", _load_cases(), ids=_case_ids())
def test_historical_validation_evaluation_cases(case):
    matches = _evaluate_case(case)
    expected = case["expected"]

    if expected["action"] == "suppress":
        assert matches == []
        return

    assert len(matches) == 1
    assert matches[0].tarifni_broj_historijski == expected["tarifni_broj"]
    assert expected["reason_contains"] in matches[0].decision_reason


def test_historical_validation_evaluation_metrics():
    metrics = _metrics_for_cases(_load_cases())

    assert metrics == {
        "true_positive": 5,
        "true_negative": 3,
        "false_positive": 0,
        "false_negative": 0,
        "wrong_tariff": 0,
        "explanation_missing": 0,
    }


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

    matches = svc.validate_lines([line])

    assert len(matches) == 1
    assert matches[0].tarifni_broj_historijski == "17049081"
    assert "Promjena poglavlja" in matches[0].decision_reason


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

    matches = svc.validate_lines(lines)

    assert len(matches) == 1
    assert matches[0].tarifni_broj_historijski == "17049081"
