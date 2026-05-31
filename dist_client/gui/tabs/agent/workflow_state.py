# gui/tabs/agent/workflow_state.py
"""
WorkflowStateManager — state machine za Agent tab workflow.

Stanja: IDLE → DOCUMENT_UPLOADED → ANALYZING → PROPOSAL_READY →
        WAITING_USER_CONFIRMATION → APPLYING → COMPLETED
                                              ↘ FAILED → IDLE
"""

import logging
from enum import Enum
from typing import Callable, Optional, Set

logger = logging.getLogger("deklarant_pro.workflow_state")


class WorkflowState(Enum):
    IDLE                      = "idle"
    DOCUMENT_UPLOADED         = "document_uploaded"
    ANALYZING                 = "analyzing"
    PROPOSAL_READY            = "proposal_ready"
    WAITING_USER_CONFIRMATION = "waiting_confirmation"
    APPLYING                  = "applying"
    COMPLETED                 = "completed"
    FAILED                    = "failed"


# Dozvoljene tranzicije — šta smije slijediti iza kojeg stanja
_TRANSITIONS: dict[WorkflowState, Set[WorkflowState]] = {
    WorkflowState.IDLE: {
        WorkflowState.DOCUMENT_UPLOADED,
    },
    WorkflowState.DOCUMENT_UPLOADED: {
        WorkflowState.ANALYZING,
        WorkflowState.IDLE,
    },
    WorkflowState.ANALYZING: {
        WorkflowState.PROPOSAL_READY,
        WorkflowState.COMPLETED,
        WorkflowState.FAILED,
        WorkflowState.IDLE,
        WorkflowState.ANALYZING,   # restart dok je u toku
    },
    WorkflowState.PROPOSAL_READY: {
        WorkflowState.WAITING_USER_CONFIRMATION,
        WorkflowState.COMPLETED,
        WorkflowState.IDLE,
    },
    WorkflowState.WAITING_USER_CONFIRMATION: {
        WorkflowState.APPLYING,
        WorkflowState.IDLE,
    },
    WorkflowState.APPLYING: {
        WorkflowState.COMPLETED,
        WorkflowState.FAILED,
    },
    WorkflowState.COMPLETED: {
        WorkflowState.IDLE,
        WorkflowState.DOCUMENT_UPLOADED,
        WorkflowState.ANALYZING,
    },
    WorkflowState.FAILED: {
        WorkflowState.IDLE,
        WorkflowState.DOCUMENT_UPLOADED,
        WorkflowState.ANALYZING,
    },
}

_STATE_LABELS: dict[WorkflowState, str] = {
    WorkflowState.IDLE:                      "Spreman",
    WorkflowState.DOCUMENT_UPLOADED:         "Dokument učitan",
    WorkflowState.ANALYZING:                 "Analiza u toku...",
    WorkflowState.PROPOSAL_READY:            "Prijedlog spreman",
    WorkflowState.WAITING_USER_CONFIRMATION: "Čeka potvrdu",
    WorkflowState.APPLYING:                  "Primjenjujem...",
    WorkflowState.COMPLETED:                 "Završeno",
    WorkflowState.FAILED:                    "Greška",
}


class WorkflowStateManager:
    """
    Jednostavan state machine. Prati trenutno stanje workflowa i
    poziva callback svaki put kad se stanje promijeni.
    """

    def __init__(self):
        self._state: WorkflowState = WorkflowState.IDLE
        self.on_state_changed: Optional[Callable[[WorkflowState], None]] = None

    @property
    def state(self) -> WorkflowState:
        return self._state

    @property
    def label(self) -> str:
        return _STATE_LABELS.get(self._state, self._state.value)

    def transition(self, new_state: WorkflowState) -> bool:
        """
        Pokušaj tranziciju. Vraća True ako je uspjela, False ako nije dozvoljena.
        """
        allowed = _TRANSITIONS.get(self._state, set())
        if new_state not in allowed:
            logger.warning("Nedozvoljena tranzicija: %s → %s", self._state.value, new_state.value)
            return False
        self._state = new_state
        if self.on_state_changed:
            self.on_state_changed(new_state)
        return True

    def force(self, new_state: WorkflowState):
        """Force tranzicija bez provjere (koristi samo za reset/restore)."""
        self._state = new_state
        if self.on_state_changed:
            self.on_state_changed(new_state)

    def reset(self):
        self.force(WorkflowState.IDLE)

    def is_busy(self) -> bool:
        return self._state in {WorkflowState.ANALYZING, WorkflowState.APPLYING}
