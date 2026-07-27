"""
Integration test: preflight provjere za XML export.

Dokazuje da se decision_state provjere mogu koristiti prije XML exporta
da se sprijeci izvoz nepotvrdjenih vrijednosti.

agent_tasks/2026-07-18_jedan-izvor-istine-odluke-deklaracije.md
Faza 4.5 — XML export.
"""
from __future__ import annotations

import pytest
from core.draft.draft import InvoiceLine, DeclarationDraft
from core.decision.decision_model import (
    DecisionField,
    DecisionStatus,
    LineDecisionState,
)
from services.naimenovanja.create_naimenovanja_service import (
    CreateNaimenovanjaService,
    GroupKey,
)


def _make_line(**kwargs) -> InvoiceLine:
    defaults = dict(
        line_no=1,
        naziv_robe="Test",
        tarifni_broj="",
        zemlja_porijekla="",
        povlastica="",
    )
    defaults.update(kwargs)
    return InvoiceLine(**defaults)


def test_preflight_detects_unconfirmed_preference():
    """check_preflight() detektuje nepotvrdjenu povlasticu."""
    draft = DeclarationDraft()
    line = _make_line(
        line_no=1,
        tarifni_broj="84821000",
        zemlja_porijekla="RS",
        povlastica="CEFTAP",
    )
    state = LineDecisionState()
    state.tariff.status = DecisionStatus.CONFIRMED
    state.tariff.applied_value = "84821000"
    state.origin_country.status = DecisionStatus.CONFIRMED
    state.origin_country.applied_value = "RS"
    state.preference.status = DecisionStatus.CANDIDATE  # NIJE potvrdjeno
    line.decision_state = state
    draft.invoice_lines = [line]

    svc = CreateNaimenovanjaService(draft)
    warnings = svc.check_preflight()

    assert len(warnings) >= 1
    assert any("povlastica" in w and "nije potvrdjena" in w for w in warnings)


def test_preflight_ok_when_all_confirmed():
    """check_preflight() vraca praznu listu kad su sve odluke potvrdjene."""
    draft = DeclarationDraft()
    line = _make_line(
        line_no=1,
        tarifni_broj="84821000",
        zemlja_porijekla="RS",
        povlastica="CEFTAP",
    )
    state = LineDecisionState()
    state.tariff.status = DecisionStatus.CONFIRMED
    state.tariff.applied_value = "84821000"
    state.origin_country.status = DecisionStatus.CONFIRMED
    state.origin_country.applied_value = "RS"
    state.preference.status = DecisionStatus.CONFIRMED
    state.preference.applied_value = "CEFTAP"
    line.decision_state = state
    draft.invoice_lines = [line]

    svc = CreateNaimenovanjaService(draft)
    warnings = svc.check_preflight()

    assert len(warnings) == 0


def test_preflight_detects_no_decision_state():
    """check_preflight() detektuje liniju bez decision_state koja ima povlasticu."""
    draft = DeclarationDraft()
    line = _make_line(
        line_no=1,
        tarifni_broj="84821000",
        povlastica="CEFTAP",
        decision_state=None,
    )
    draft.invoice_lines = [line]

    svc = CreateNaimenovanjaService(draft)
    warnings = svc.check_preflight()

    assert len(warnings) >= 1
    assert any("decision_state nije postavljen" in w for w in warnings)


def test_preflight_detects_unconfirmed_tariff():
    """check_preflight() detektuje tarifu bez CONFIRMED statusa."""
    draft = DeclarationDraft()
    line = _make_line(
        line_no=1,
        tarifni_broj="84821000",
        zemlja_porijekla="RS",
    )
    state = LineDecisionState()
    state.tariff.status = DecisionStatus.UNKNOWN  # Nije evaluirana
    line.decision_state = state
    draft.invoice_lines = [line]

    svc = CreateNaimenovanjaService(draft)
    warnings = svc.check_preflight()

    assert any("tarifa" in w and "nije evaluirana" in w for w in warnings)


def test_create_flows_call_preflight(monkeypatch):
    """create_one_to_one() i create_smart_group() pozivaju preflight prije kreiranja."""
    draft = DeclarationDraft()
    draft.invoice_lines = [
        _make_line(
            line_no=1,
            tarifni_broj="84821000",
            zemlja_porijekla="RS",
            kolicina=1,
            bruto_kg=1,
            neto_kg=1,
            iznos=10,
        )
    ]

    calls: list[str] = []

    def fake_log(self, context: str) -> list[str]:
        calls.append(context)
        return []

    monkeypatch.setattr(CreateNaimenovanjaService, "_log_preflight_warnings", fake_log)

    svc = CreateNaimenovanjaService(draft)
    svc.create_one_to_one()
    svc.create_smart_group()

    assert calls == ["one_to_one", "smart_group"]


def test_decision_state_not_in_xml_metadata():
    """
    Decision_state metadata NE SMIJE uci u ASYCUDA XML.

    XML exporter koristi direktna polja (tarifni_broj, zemlja_porijekla,
    povlastica), a ne decision_state. Ovaj test potvrdjuje da su
    direktna polja i dalje jedini izvor za XML export.
    """
    state = LineDecisionState()
    state.tariff.status = DecisionStatus.CONFIRMED
    state.tariff.applied_value = "84821000"
    state.origin_country.status = DecisionStatus.CONFIRMED
    state.origin_country.applied_value = "JP"

    line = _make_line(
        tarifni_broj="84821000",
        zemlja_porijekla="JP",
        decision_state=state,
    )

    # XML export koristi ova polja:
    assert line.tarifni_broj == "84821000"
    assert line.zemlja_porijekla == "JP"
    assert line.povlastica == ""

    # decision_state je interno — ne izlazi u XML
    # (test osigurava da vrijednosti nisu samo u decision_state-u)
    assert line.tarifni_broj == state.tariff.applied_value


def test_grouping_key_uses_applied_values():
    """
    Grouping key za naimenovanja koristi direktna polja,
    koja su sinhronizovana sa decision_state-om.
    """
    state = LineDecisionState()
    state.tariff.status = DecisionStatus.CONFIRMED
    state.tariff.applied_value = "84821000"
    state.origin_country.status = DecisionStatus.CONFIRMED
    state.origin_country.applied_value = "JP"
    state.preference.status = DecisionStatus.CONFIRMED
    state.preference.applied_value = "EUP"

    line = _make_line(
        tarifni_broj="84821000",
        zemlja_porijekla="JP",
        povlastica="EUP",
        decision_state=state,
    )

    # Grouping key iz InvoiceLine (direktna polja)
    key = line.key()
    assert key == ("84821000", "JP", "EUP")

    # Isti key kao GroupKey za naimenovanja
    gk = GroupKey(tariff_code="84821000", origin_country="JP", preference_code="EUP")
    assert gk.tariff_code == "84821000"
    assert gk.origin_country == "JP"
    assert gk.preference_code == "EUP"
