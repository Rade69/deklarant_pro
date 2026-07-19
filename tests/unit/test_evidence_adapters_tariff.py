"""
Testovi za adapt_tariff_evidence (Faza 3 evidence adapter).

Pokriva regresiju: rucna ispravka tarife (desni klik -> correct_mapping)
odmah nakon ispravke ima usage_count=1 i ranije se nije nudila kao
kandidat na sljedecem uvozu iste robe (is_same_exporter je bio uvijek
False jer je poredio ime izvoznika sa nazivom PROIZVODA).

agent_reports/2026-07-19_evidence-adapter-exact-match-fix.md
"""
from __future__ import annotations

from unittest.mock import patch

from core.decision.decision_model import DecisionField
from core.decision.evidence import DecisionSource
from core.draft.draft import InvoiceLine
from services.decision.decision_policy import PolicyContext
from services.decision.evidence_adapters import adapt_tariff_evidence
from services.tariff.tariff_mapping_service import TariffMapping


def _make_line(**kwargs) -> InvoiceLine:
    defaults = dict(
        line_no=1,
        invoice_number="FA-TEST-001",
        naziv_robe="SUSSINA test proizvod",
        product_code="SUS-001",
        tarifni_broj="",
    )
    defaults.update(kwargs)
    return InvoiceLine(**defaults)


def _fake_mapping(**overrides) -> TariffMapping:
    defaults = dict(
        product_code="SUS-001",
        naziv_robe="SUSSINA test proizvod",
        tarifni_broj="39269097",
        precision_1="000",
        zemlja_porijekla="",
        povlastica="",
        usage_count=1,
        similarity=1.0,
    )
    defaults.update(overrides)
    return TariffMapping(**defaults)


def test_fresh_manual_correction_is_offered_as_candidate():
    """
    Regresija: odmah nakon correct_mapping() (usage_count=1), tacan
    product_code match mora biti ponudjen kao TARIFF kandidat, cak i
    bez podudaranja izvoznika i bez 3+ ponovne upotrebe.
    """
    line = _make_line()
    ctx = PolicyContext(normalized_exporter="NEKI DRUGI IZVOZNIK D.O.O.")

    with patch("services.tariff_mapping_service.TariffMappingService.find_mapping",
               return_value=_fake_mapping(usage_count=1, similarity=1.0)):
        candidates = adapt_tariff_evidence(line, ctx)

    db_candidates = [c for c in candidates if c.evidence.source == DecisionSource.TARIFF_DATABASE]
    assert len(db_candidates) == 1
    assert db_candidates[0].value == "39269097"
    assert db_candidates[0].evidence.score >= 80


def test_weak_fuzzy_single_use_is_not_offered():
    """
    Fuzzy (ne-tacan) match sa usage_count=1 i dalje ostaje ispod praga —
    ne smije se pojaviti kao kandidat dok ne dostigne usage_count>=3.
    """
    line = _make_line()
    ctx = PolicyContext(normalized_exporter="")

    with patch("services.tariff_mapping_service.TariffMappingService.find_mapping",
               return_value=_fake_mapping(usage_count=1, similarity=0.93)):
        candidates = adapt_tariff_evidence(line, ctx)

    db_candidates = [c for c in candidates if c.field == DecisionField.TARIFF
                     and c.evidence.source in (DecisionSource.TARIFF_DATABASE, DecisionSource.SIMILARITY)]
    assert db_candidates == []


def test_fuzzy_match_offered_after_three_uses():
    """Fuzzy match sa usage_count>=3 se i dalje nudi kao kandidat (postojece ponasanje)."""
    line = _make_line()
    ctx = PolicyContext(normalized_exporter="")

    with patch("services.tariff_mapping_service.TariffMappingService.find_mapping",
               return_value=_fake_mapping(usage_count=3, similarity=0.93)):
        candidates = adapt_tariff_evidence(line, ctx)

    db_candidates = [c for c in candidates if c.evidence.source == DecisionSource.SIMILARITY]
    assert len(db_candidates) == 1
