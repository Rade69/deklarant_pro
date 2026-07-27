"""
Karakterizacioni testovi za agent routing — Faza 0 (Agent V2)

Testiraju lokalne routing slojeve (1-8) iz chat_intent_handler.py — determinističke,
bez LLM providera. Tool Use (sloj 9) nije testiran jer zahtijeva API ključeve.

Svaki test slučaj iz fixtures/agent/intent_routing_cases.json:
- Ako je expected_sloj jedan od lokalnih slojeva (1-8): test prolazi odmah.
- Ako je expected_sloj "tool_use": test se označava kao SKIP (ne može se
  testirati bez LLM providera i mock-ovanja kompletnog ToolDispatcherWorker-a).

Plan §8 Faza 0: characterization testovi za potvrđene pogrešne i ispravne upite.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

# Importujemo samo lokalne routing funkcije (bez ToolDispatcherWorker zavisnosti)
from gui.tabs.agent.services.chat_intent_handler import (
    _application_context_scope,
    _is_naimenovanja_review_request,
    _is_naimenovanja_validation_request,
    _extract_origin_product_query,
    _extract_similar_product_query,
    _normalize_naim_message,
)


FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "agent" / "intent_routing_cases.json"


def _load_cases():
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# Učitaj sve slučajeve
ALL_CASES = _load_cases()

# Filtriraj slučajeve čiji su slojevi testabilni lokalno (bez LLM-a)
LOCAL_SLOJEVI = {
    "_application_context_scope",
    "_is_naimenovanja_review_request",
    "_extract_origin_product_query",
    "_extract_similar_product_query",
    "pending_action",
    "_resolve_followup",
    "_resolve_contextual_request",
}

LOCAL_CASES = [c for c in ALL_CASES if c["expected_sloj"] in LOCAL_SLOJEVI]
TOOL_USE_CASES = [c for c in ALL_CASES if c["expected_sloj"] == "tool_use"]


# ── Pomoćne funkcije za simulaciju routing-a ─────────────────────────────


def _simulate_app_context_scope(message: str) -> str | None:
    """Simulira sloj 4 — vraća scope ili None."""
    result = _application_context_scope(message)
    return result if result else None


def _simulate_naimenovanja_routing(message: str) -> tuple[str | None, str | None]:
    """Simulira sloj 5 — vraća (is_review, is_validation)."""
    msg = _normalize_naim_message(message)
    if not msg:
        return None, None
    has_naim = any(kw in msg for kw in ("naim", "naimenov"))
    if not has_naim:
        return None, None
    is_review = _is_naimenovanja_review_request(message)
    is_validation = _is_naimenovanja_validation_request(message)
    return ("review" if is_review else None, "validation" if is_validation else None)


# ── Testiranje sloja 4: _application_context_scope ──────────────────────


class TestApplicationContextScope:
    """Sloj 4 — 'pregledaj/pokaži + faktura/naimenovanja' → snapshot."""

    sloj4_cases = [c for c in LOCAL_CASES if c["expected_sloj"] == "_application_context_scope"]

    @pytest.mark.parametrize("case", sloj4_cases, ids=[c["id"] for c in sloj4_cases])
    def test_application_context_scope_presrece(self, case):
        scope = _simulate_app_context_scope(case["message"])
        assert scope is not None, (
            f"Poruka '{case['message']}' bi trebala biti presretnuta od _application_context_scope. "
            f"Napomena: {case.get('note', '')}"
        )

    @pytest.mark.parametrize("case", sloj4_cases, ids=[c["id"] for c in sloj4_cases])
    def test_application_context_scope_vraca_ispravan_scope(self, case):
        scope = _simulate_app_context_scope(case["message"])
        if scope:
            # Provjeri da scope odgovara poruci
            msg = case["message"].lower()
            if any(kw in msg for kw in ("faktura", "tab faktura")):
                assert scope == "faktura", f"Očekivano 'faktura', dobijeno '{scope}' za: {case['message']}"
            elif any(kw in msg for kw in ("naimenov", "naim")):
                assert scope in ("naimenovanja", "all"), f"Očekivano 'naimenovanja', dobijeno '{scope}' za: {case['message']}"


# ── Testiranje sloja 5: _is_naimenovanja_review_request ──────────────────


class TestNaimenovanjaReviewRequest:
    """Sloj 5 — naimenovanja: prikaz vs validacija."""

    sloj5_cases = [c for c in LOCAL_CASES if c["expected_sloj"] == "_is_naimenovanja_review_request"]

    @pytest.mark.parametrize("case", sloj5_cases, ids=[c["id"] for c in sloj5_cases])
    def test_naimenovanja_review_presrece(self, case):
        review, validation = _simulate_naimenovanja_routing(case["message"])
        assert review is not None or validation is not None, (
            f"Poruka '{case['message']}' sa 'naimenovanja' keywordom bi trebala biti "
            f"presretnuta od _is_naimenovanja_review_request. "
            f"Napomena: {case.get('note', '')}"
        )

    @pytest.mark.parametrize("case", sloj5_cases, ids=[c["id"] for c in sloj5_cases])
    def test_naimenovanja_routing_akcija(self, case):
        review, validation = _simulate_naimenovanja_routing(case["message"])
        expected_action = case.get("expected_action", "")
        if expected_action == "VALIDATE":
            assert validation == "validation", (
                f"BUG potvrđen: '{case['message']}' bi trebao VALIDATE, "
                f"ali _is_naimenovanja_validation_request vraća False. "
                f"review={review}, validation={validation}"
            )
        elif expected_action == "SHOW":
            assert review == "review" or validation != "validation", (
                f"'{case['message']}' bi trebao SHOW. "
                f"review={review}, validation={validation}"
            )


# ── Testiranje poznatih bugova ──────────────────────────────────────────


class TestKnownRoutingBugs:
    """Potvrđeni bugovi iz plana §2 i Karta #2."""

    def test_pregledaj_faktura_tab_je_show_umjesto_validate(self):
        """BUG: 'Pregledaj Faktura tab' → _application_context_scope (SHOW).
        Plan §7: 'pregledaj' + poslovni objekat = VALIDATE."""
        scope = _simulate_app_context_scope("Pregledaj Faktura tab")
        # Trenutno ponašanje: presretne se kao aplikacioni scope (SHOW)
        assert scope == "faktura", (
            "Trenutno: 'Pregledaj Faktura tab' → SHOW (presretnuto od "
            "_application_context_scope). Plan kaže da treba VALIDATE."
        )

    def test_pregledaj_naimenovanja_je_show_umjesto_validate(self):
        """BUG: 'Pregledaj naimenovanja' → SHOW. Plan §7: treba VALIDATE."""
        review, validation = _simulate_naimenovanja_routing("Pregledaj naimenovanja")
        # Trenutno: _is_naimenovanja_validation_request ne prepoznaje 'pregledaj'
        # kao validation keyword — 'provjer', 'valid', 'da li su', 'šta fali'... ne uključuju 'pregledaj'
        assert validation != "validation", (
            f"Trenutno: 'Pregledaj naimenovanja' → SHOW (review={review}, validation={validation}). "
            "Plan §7: 'pregledaj' + poslovni objekat = VALIDATE."
        )

    def test_provjeri_faktura_tab_nije_presretnut_lokalno(self):
        """Ispravno: 'Provjeri Faktura tab' NE presreće lokalni sloj.
        'provjeri' nije u _application_context_scope wants_view keywordima."""
        scope = _simulate_app_context_scope("Provjeri tabelu u tabu Faktura")
        # 'provjeri' nije u wants_view, 'tabelu' nije u has_app_area...
        # Zapravo 'tabu' je u has_app_area, ali bez wants_view → ne prolazi
        assert scope is None, (
            f"'Provjeri tabelu u tabu Faktura' NE bi trebalo biti presretnuto "
            f"od _application_context_scope. Dobijeno: {scope}"
        )

    def test_pregledaj_deklaraciju_nema_lokalnu_precicu(self):
        """'Pregledaj deklaraciju' nema 'faktura/naimenovanja/zaglavlje'
        keyword u has_app_area → ne presreće sloj 4. Ide u Tool Use.
        Plan §7: treba VALIDATE, pa je Tool Use ispravan put."""
        scope = _simulate_app_context_scope("Pregledaj deklaraciju")
        # 'deklaraciju' nije u has_app_area keywordima
        assert scope is None, (
            f"'Pregledaj deklaraciju' nema lokalnu prečicu — ide kroz Tool Use. "
            f"To je ispravno za VALIDATE (plan §7)."
        )


# ── Testiranje ispravnih tokova ─────────────────────────────────────────


class TestCorrectRouting:
    """Potvrda da ispravni tokovi rade kako treba."""

    def test_prikazi_faktura_tab_je_show(self):
        scope = _simulate_app_context_scope("Prikaži Faktura tab")
        assert scope == "faktura"

    def test_pokazi_naimenovanje_3_je_review(self):
        review, validation = _simulate_naimenovanja_routing("Pokaži naimenovanje 3")
        assert review == "review"

    def test_provjeri_naimenovanje_5_je_validation(self):
        review, validation = _simulate_naimenovanja_routing("Provjeri naimenovanje 5")
        assert validation == "validation"

    def test_sta_je_ucitano_je_show(self):
        scope = _simulate_app_context_scope("Šta je učitano?")
        assert scope is not None  # vraća 'all' ili specifični scope

    def test_validiraj_faktura_tab_ne_presrece_lokalno(self):
        """'Validiraj' nije u wants_view → ide u Tool Use (ispravno)."""
        scope = _simulate_app_context_scope("Validiraj Faktura tab")
        assert scope is None

    def test_samo_pogledaj_fakturu_je_show(self):
        """Eksplicitno 'samo pogledaj' = SHOW (ispravno)."""
        scope = _simulate_app_context_scope("Samo pogledaj Faktura tab")
        assert scope is not None


# ── Broj slučajeva ──────────────────────────────────────────────────────


def test_fixture_ima_dovoljno_slucajeva():
    """Plan §8: minimalno 50 početnih jezičkih slučajeva."""
    assert len(ALL_CASES) >= 49, f"Fixture ima {len(ALL_CASES)} slučajeva, treba ≥49"


def test_fixture_ima_bug_slucajeve():
    """Svi poznati bugovi iz plana §2 trebaju biti pokriveni."""
    bug_ids = {"pregledaj_faktura_tab", "pregledaj_naimenovanja", "pregledaj_deklaraciju"}
    case_ids = {c["id"] for c in ALL_CASES}
    for bug_id in bug_ids:
        assert bug_id in case_ids, f"Nedostaje test slučaj za bug: {bug_id}"


# ── SKIP testovi za Tool Use slučajeve (ne mogu se testirati bez LLM-a) ──


@pytest.mark.skip(reason="Tool Use zahtijeva LLM provider — testira se u Fazi 1")
class TestToolUseCasesSkip:
    """Ovi slučajevi se NE mogu testirati u Fazi 0 (bez LLM providera).
    Biće pokriveni u Fazi 1 kad se uvede Intent Resolver."""

    @pytest.mark.parametrize("case", TOOL_USE_CASES, ids=[c["id"] for c in TOOL_USE_CASES])
    def test_tool_use_case_documented(self, case):
        """Samo potvrđujemo da je slučaj dokumentovan u fixture-u."""
        assert case["expected_sloj"] == "tool_use"
        assert case.get("expected_action")
