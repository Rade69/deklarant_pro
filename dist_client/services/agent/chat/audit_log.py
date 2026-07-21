"""
Audit log — strukturisani zapis agent routing i tool-dispatch događaja.

Ne čuva sadržaj faktura, API ključeve ni deklaracijske podatke — samo meta
podatke (alat, efekat, status, trajanje, izvor, routing sloj, provider...).
Pad audita ne smije srušiti korisničku operaciju — record() nikad ne baca.

Vidi: docs/agent/AGENT_MODE_IMPROVEMENT_IMPLEMENTATION_PLAN.md §8.2
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import logging

logger = logging.getLogger("deklarant_pro.agent.audit")


@dataclass
class AuditEvent:
    routing_layer: str
    tool: str = ""
    effect: str = ""
    status: str = ""
    source: str = ""
    provider: str = ""
    duration_ms: float = 0.0
    fallback_reason: str = ""
    confirmation: str = ""
    pipeline_stage: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


def record(event: AuditEvent) -> None:
    try:
        logger.info(
            "routing=%s tool=%s effect=%s status=%s source=%s provider=%s "
            "duration_ms=%.1f fallback_reason=%s confirmation=%s pipeline_stage=%s extra=%s",
            event.routing_layer,
            event.tool,
            event.effect,
            event.status,
            event.source,
            event.provider,
            event.duration_ms,
            event.fallback_reason,
            event.confirmation,
            event.pipeline_stage,
            event.extra,
        )
    except Exception:
        pass
