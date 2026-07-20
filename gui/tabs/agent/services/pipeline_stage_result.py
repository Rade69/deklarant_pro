"""
PipelineStageResult — strukturisan ishod jedne faze automatskog pipeline-a.

Zaseban je od WorkflowState (gui/tabs/agent/workflow_state.py), koji prati
CJELOKUPNO stanje agent sesije (IDLE/ANALYZING/APPLYING/...). Ovaj model prati
ishod POJEDINAČNE faze unutar _puna_auto_pipeline() (mase, auto-popuna,
validacija, potvrda deklaranta, naimenovanja) — namjerno odvojen model, ne
duplira WorkflowState, samo hrani finalnu tranziciju u njega.

Vidi: docs/agent/AGENT_MODE_IMPROVEMENT_IMPLEMENTATION_PLAN.md §7
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PipelineStageStatus(str, Enum):
    SUCCESS = "success"
    WARNING = "warning"
    FAILED = "failed"
    WAITING_CONFIRMATION = "waiting_confirmation"
    CANCELLED = "cancelled"


@dataclass
class PipelineStageResult:
    """Ishod jedne faze pipeline-a."""
    stage: str
    status: PipelineStageStatus
    message: str = ""                          # Korisnička poruka (chat)
    reason: str = ""                            # Tehnički razlog za log
    can_continue: bool = True                   # Da li pipeline smije nastaviti
    stats: dict[str, Any] = field(default_factory=dict)  # Bez osjetljivog sadržaja


# Statusi koji uvijek prekidaju pipeline, bez obzira na can_continue vrijednost
# pojedinačnog rezultata — koriste se za agregaciju finalnog ishoda.
_BLOCKING = {PipelineStageStatus.FAILED, PipelineStageStatus.CANCELLED}


def overall_outcome(results: list[PipelineStageResult]) -> str:
    """
    Izračunaj finalni ishod (COMPLETED / PARTIAL / FAILED / CANCELLED) iz
    rezultata svih faza koje su se izvršile. Ne mijenja nijedan rezultat —
    samo agregira, redoslijed provjere odgovara ozbiljnosti (CANCELLED i
    FAILED su međusobno isključivi u praksi jer pipeline prekida odmah nakon
    prve blokirajuće faze, ali provjera je eksplicitna radi jasnoće).
    """
    if any(r.status == PipelineStageStatus.CANCELLED for r in results):
        return "CANCELLED"
    if any(r.status == PipelineStageStatus.FAILED for r in results):
        return "FAILED"
    if any(r.status == PipelineStageStatus.WARNING for r in results):
        return "PARTIAL"
    if results and all(r.status == PipelineStageStatus.SUCCESS for r in results):
        return "COMPLETED"
    return "FAILED"
