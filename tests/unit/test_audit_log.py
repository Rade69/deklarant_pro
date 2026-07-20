"""Testovi za services/agent/chat/audit_log.py (Faza D, §8.2)."""
from __future__ import annotations

import logging

from services.agent.chat.audit_log import AuditEvent, record


def test_record_ne_baca_ni_uz_neispravan_logger(monkeypatch, caplog):
    def _boom(*args, **kwargs):
        raise RuntimeError("logger je pukao")

    monkeypatch.setattr("services.agent.chat.audit_log.logger.info", _boom)

    record(AuditEvent(routing_layer="tool_use", tool="provjeri_tarife"))  # ne smije baciti


def test_record_upisuje_sva_polja(caplog):
    caplog.set_level(logging.INFO, logger="deklarant_pro.agent.audit")

    record(AuditEvent(
        routing_layer="tool_use",
        tool="upisi_u_kolonu",
        effect="mutate",
        status="dispatched",
        source="_execute_tool",
        provider="groq",
        duration_ms=12.5,
        fallback_reason="",
        confirmation="confirmed",
        pipeline_stage="",
    ))

    assert len(caplog.records) == 1
    msg = caplog.records[0].getMessage()
    assert "routing=tool_use" in msg
    assert "tool=upisi_u_kolonu" in msg
    assert "effect=mutate" in msg
    assert "provider=groq" in msg
    assert "confirmation=confirmed" in msg


def test_record_default_polja_su_prazna():
    event = AuditEvent(routing_layer="local")

    assert event.tool == ""
    assert event.effect == ""
    assert event.status == ""
    assert event.provider == ""
    assert event.duration_ms == 0.0
    assert event.extra == {}
