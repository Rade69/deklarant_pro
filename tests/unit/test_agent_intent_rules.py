"""
Testovi za intent_rules — lokalna pravila klasifikacije (Faza 1).

Koristi isti fixture kao Faza 0, ali testira NOVA pravila (IntentAction/IntentTarget).
Ovo su karakterizacioni testovi za Fazu 1 — dokumentuju kako pravila TRENUTNO rade.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.agent.chat.intent_model import IntentAction, IntentTarget
from services.agent.chat.intent_rules import (
    apply_rules,
    classify_action,
    classify_target,
    extract_ordinal,
)

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "agent" / "intent_routing_cases.json"


def _load_cases():
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Unit testovi za helper funkcije ──────────────────────────────────────


class TestClassifyAction:
    def test_show(self):
        action, conf = classify_action("Prikaži Faktura tab")
        assert action == IntentAction.SHOW
        assert conf > 0.8

    def test_validate(self):
        action, conf = classify_action("Provjeri Faktura tab")
        assert action == IntentAction.VALIDATE
        assert conf > 0.7

    def test_pregledaj_je_validate(self):
        """Plan §9.1: 'pregledaj' + poslovni objekat = VALIDATE."""
        action, conf = classify_action("Pregledaj Faktura tab")
        assert action == IntentAction.VALIDATE

    def test_negacija_obara_na_show(self):
        """'samo prikaži' negira VALIDATE."""
        action, conf = classify_action("Samo pogledaj Faktura tab")
        assert action == IntentAction.SHOW

    def test_analyze(self):
        action, conf = classify_action("Analiziraj tarife")
        assert action == IntentAction.ANALYZE

    def test_propose(self):
        action, conf = classify_action("Predloži tarife")
        assert action == IntentAction.PROPOSE

    def test_mutate(self):
        action, conf = classify_action("Ispravi tarifni broj")
        assert action == IntentAction.REQUEST_CHANGE

    def test_workflow(self):
        action, conf = classify_action("Pripremi deklaraciju")
        assert action == IntentAction.RUN_WORKFLOW

    def test_export(self):
        action, conf = classify_action("Izvezi XML")
        assert action == IntentAction.EXPORT

    def test_confirm(self):
        action, conf = classify_action("Da")
        assert action == IntentAction.CONFIRM

    def test_cancel(self):
        action, conf = classify_action("Ne")
        assert action == IntentAction.CANCEL


class TestClassifyTarget:
    def test_faktura(self):
        target, conf = classify_target("Provjeri Faktura tab")
        assert target == IntentTarget.INVOICE

    def test_naimenovanja(self):
        target, conf = classify_target("Prikaži naimenovanja")
        assert target == IntentTarget.ITEMS

    def test_tarife(self):
        target, conf = classify_target("Provjeri tarife")
        assert target == IntentTarget.TARIFFS

    def test_zaglavlje(self):
        target, conf = classify_target("Provjeri zaglavlje")
        assert target == IntentTarget.HEADER

    def test_xml(self):
        target, conf = classify_target("Izvezi XML")
        assert target == IntentTarget.XML


class TestExtractOrdinal:
    def test_stavka(self):
        assert extract_ordinal("Prikaži stavku 22") == 22

    def test_naimenovanje(self):
        assert extract_ordinal("Provjeri naimenovanje 5") == 5

    def test_nema_ordinal(self):
        assert extract_ordinal("Provjeri sve") is None


class TestApplyRules:
    def test_show_faktura(self):
        intent = apply_rules("Prikaži Faktura tab")
        assert intent is not None
        assert intent.action == IntentAction.SHOW
        assert intent.target == IntentTarget.INVOICE

    def test_validate_faktura(self):
        intent = apply_rules("Provjeri Faktura tab")
        assert intent is not None
        assert intent.action == IntentAction.VALIDATE
        assert intent.target == IntentTarget.INVOICE

    def test_pregledaj_faktura_validate(self):
        """BUG iz Faze 0: 'pregledaj' + faktura treba VALIDATE."""
        intent = apply_rules("Pregledaj Faktura tab")
        assert intent is not None
        assert intent.action == IntentAction.VALIDATE, (
            f"BUG: 'Pregledaj Faktura tab' treba VALIDATE, "
            f"dobijeno {intent.action}"
        )

    def test_pregledaj_naimenovanja_validate(self):
        intent = apply_rules("Pregledaj naimenovanja")
        assert intent is not None
        assert intent.action == IntentAction.VALIDATE

    def test_show_naimenovanja(self):
        intent = apply_rules("Prikaži naimenovanja")
        assert intent is not None
        assert intent.action == IntentAction.SHOW
        assert intent.target == IntentTarget.ITEMS

    def test_specific_row(self):
        intent = apply_rules("Provjeri naimenovanje 5")
        assert intent is not None
        assert intent.action == IntentAction.VALIDATE
        assert intent.target == IntentTarget.SPECIFIC_ROW
        assert intent.ordinals == (5,)

    def test_unknown_goes_to_none(self):
        # Bez prepoznatljivih keyworda — pravila ne mogu klasifikovati
        intent = apply_rules("Bla bla nešto nepoznato")
        # Treba da vrati None (prepušta LLM-u)
        # ili OTHER sa niskom confidence
        if intent is not None:
            assert intent.action == IntentAction.OTHER
            assert intent.confidence < 0.75 or intent.source == "llm"
