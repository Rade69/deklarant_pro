from core.draft.draft import InvoiceLine
from services.agent.validation.historical_tariff_search_service import (
    HistoricalTariffSearchService,
    TariffHistoryMatch,
)


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
