"""
Testovi za ChatWorker._build_context() Zone A (=== STANJE DRAFTA ===) —
Faza 3, project_rooms/2026-07-25_agent-safe-input-schema-plan.md.

Zone A sad računa agregate preko AgentContextAdapter.build_draft_summary()
umjesto ručnih sum()/len() poziva — ovaj test provjerava da su brojevi
IDENTIČNI onome što je prije migracije proizvodio ručni izračun (isti
obrazac kao test_chat_worker_context_includes_naimenovanja_without_
invoice_lines u tests/test_tool_use_offline.py, koji je otkrio pravi
monkeypatch harness za _build_context()).
"""
from __future__ import annotations

from core.draft.draft import DeclarationDraft, InvoiceLine
from gui.tabs.agent.widgets.chat_worker import ChatWorker


def _line(tarifni_broj="", zemlja_porijekla="", povlastica="", has_origin_statement=False, eur1_number=""):
    return InvoiceLine(
        tarifni_broj=tarifni_broj,
        zemlja_porijekla=zemlja_porijekla,
        povlastica=povlastica,
        has_origin_statement=has_origin_statement,
        eur1_number=eur1_number,
        naziv_robe="ROBA",
    )


def _worker(draft, message="Pregledaj stanje"):
    worker = ChatWorker.__new__(ChatWorker)
    worker.draft = draft
    worker.message = message
    worker._determine_context_zones = lambda _: set()
    worker._build_session_zone = lambda _: []
    worker._fetch_pg_tariff_descriptions = lambda _: {}
    worker._is_regulatory_question = lambda _: False
    return worker


def test_zone_a_racuna_tacne_agregate():
    draft = DeclarationDraft()
    draft.invoice_lines = [
        _line(tarifni_broj="12345678", zemlja_porijekla="DE"),
        _line(tarifni_broj="", zemlja_porijekla="FR", povlastica="P", has_origin_statement=False, eur1_number=""),
        _line(tarifni_broj="87654321", zemlja_porijekla="", povlastica="P", has_origin_statement=True),
    ]
    worker = _worker(draft)

    context = worker._build_context()

    assert "Ukupno stavki: 3" in context
    assert "Bez tarifnog broja: 1" in context
    assert "Bez zemlje porijekla: 1" in context
    assert "Sa povlasticom: 2" in context
    assert "Čeka EUR1 broj: 1" in context
    assert "DE:1" in context
    assert "FR:1" in context
    assert "(nepoznato):1" in context


def test_zone_a_prazan_draft_vraca_poruku_bez_stavki():
    draft = DeclarationDraft()
    worker = _worker(draft)

    context = worker._build_context()

    assert "nema uvezenih stavki" in context
