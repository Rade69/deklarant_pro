"""
Faza 7: regresioni dataset za odluke carinskog agenta.

Pokriva 7 scenarija iz agent_tasks/2026-06-10_plan_unapredjenja_carinskog_agenta.md
(PE2, EUR.1, bez dokaza porijekla, CN bez povlastice, dva izvoznika/isti proizvod,
Blagic/Loren vise faktura, slab istorijski prijedlog) preko cistih funkcija
evidence_model-a - bez LLM-a, bez API kljuca, bez pristupa bazi ili fajlovima.
"""
import json
from pathlib import Path

import pytest

from core.draft.draft import InvoiceLine
from services.agent.validation.evidence_model import (
    evidence_from_preference,
    evidence_from_tariff_decision,
)


CASES_PATH = Path(__file__).parents[1] / "fixtures" / "agent" / "agent_decision_regression_cases.json"


def _load_cases() -> list[dict]:
    with CASES_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _case_ids() -> list[str]:
    return [case["name"] for case in _load_cases()]


def _evidence_for(case: dict):
    if case["kind"] == "preference":
        item = InvoiceLine(**case["invoice_line"])
        return evidence_from_preference(item)
    return evidence_from_tariff_decision(**case["tariff_decision"])


@pytest.mark.parametrize("case", _load_cases(), ids=_case_ids())
def test_agent_decision_regression_cases(case):
    evidence = _evidence_for(case)
    expected = case["expected"]

    assert evidence.source.value == expected["source"]
    assert evidence.confidence.value == expected["confidence"]
    assert evidence.score == expected["score"]
    assert evidence.score_category.value == expected["score_category"]
    assert evidence.requires_confirmation == expected["requires_confirmation"]
    assert evidence.should_recommend == expected["should_recommend"]
    assert evidence.auto_applicable == expected["auto_applicable"]

    doc_code = expected.get("doc_code")
    if doc_code is not None:
        assert evidence.data.get("doc_code") == doc_code


def test_two_exporters_same_product_dont_share_tariff_evidence():
    """Faza 3 acceptance: isti proizvod kod dva izvoznika ne vraca tudju potvrdu."""
    cases = {case["name"]: case for case in _load_cases()}

    izvoznik_a = _evidence_for(cases["izvoznik_a_potvrdjena_istorija_tarife"])
    izvoznik_b = _evidence_for(cases["izvoznik_b_bez_sopstvene_istorije"])

    assert izvoznik_a.confidence != izvoznik_b.confidence
    assert izvoznik_a.auto_applicable is True
    assert izvoznik_b.auto_applicable is False


def test_multi_invoice_draft_lines_have_independent_evidence():
    """Blagic/Loren: stavke iz razlicitih faktura u istoj deklaraciji imaju nezavisne dokaze."""
    cases = {case["name"]: case for case in _load_cases()}

    faktura_46 = _evidence_for(cases["blagic_faktura_46_pe2_potvrdjeno"])
    faktura_703 = _evidence_for(cases["blagic_faktura_703_bez_izjave"])

    assert faktura_46.score == 100
    assert faktura_703.score == 0


def test_weak_history_proposal_is_never_auto_applicable():
    """Faza 3 pravilo: slabi prijedlozi ne smiju biti automatski primijenjeni."""
    cases = {case["name"]: case for case in _load_cases()}

    slab_prijedlog = _evidence_for(cases["istorija_slab_prijedlog_zahtjeva_potvrdu"])

    assert slab_prijedlog.should_recommend is True
    assert slab_prijedlog.auto_applicable is False
    assert slab_prijedlog.requires_confirmation is True
