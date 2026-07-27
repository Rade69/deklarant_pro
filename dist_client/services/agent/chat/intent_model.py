"""
AgentIntent model — jedinstveni ugovor za klasifikaciju korisničke namjere.

Plan §7.1: AgentIntent, IntentAction, IntentTarget.
Koristi se u Intent Resolveru (Faza 1) da zamijeni raspršenu keyword/routing
logiku u chat_intent_handler.py i tool_dispatcher.py.

Nezavisan od Qt i LLM providera — može se koristiti i u testovima.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class IntentAction(str, Enum):
    """Šta korisnik želi da uradi."""
    SHOW = "show"           # prikaz (snapshot)
    VALIDATE = "validate"   # stručna provjera
    ANALYZE = "analyze"     # dublje poređenje sa istorijom
    PROPOSE = "propose"     # prijedlog bez automatskog upisa
    REQUEST_CHANGE = "request_change"  # mutacija (zahtijeva ToolPolicy kapiju)
    RUN_WORKFLOW = "run_workflow"     # višekoračni plan
    EXPORT = "export"       # XML izvoz
    CANCEL = "cancel"       # otkazivanje pending akcije
    CONFIRM = "confirm"     # potvrda pending akcije
    OTHER = "other"         # neklasifikovano (ide u ChatWorker)


class IntentTarget(str, Enum):
    """Šta je predmet korisničkog zahtjeva."""
    APPLICATION = "application"
    INVOICE = "invoice"
    TARIFFS = "tariffs"
    ORIGIN = "origin"
    ITEMS = "items"
    HEADER = "header"
    DECLARATION = "declaration"
    XML = "xml"
    SPECIFIC_ROW = "specific_row"


class IntentSource(str, Enum):
    """Odakle je došla odluka o intentu."""
    LOCAL = "local"     # keyword/kontekstualno pravilo (pouzdano)
    LLM = "llm"         # Tool Use / LLM provider
    CONTEXT = "context" # follow-up / pending action


@dataclass(frozen=True)
class AgentIntent:
    """Rezultat klasifikacije korisničke poruke.

    Sve što routing treba da zna o poruci prije nego što se
    pozove dispatcher ili ChatWorker.
    """
    action: IntentAction
    target: IntentTarget = IntentTarget.APPLICATION
    scope: str = "all"           # "all", "selection", ordinal string
    ordinals: tuple[int, ...] = ()
    depth: str = "summary"       # "summary", "full", "row"
    goal: str = ""               # opis cilja (za workflow)
    confidence: float = 1.0      # 0.0 - 1.0
    source: IntentSource = IntentSource.LOCAL
    requires_clarification: bool = False
    clarification_reason: str = ""

    @property
    def is_mutation(self) -> bool:
        """Da li intent zahtijeva mutaciju drafta (ToolPolicy kapija)."""
        return self.action == IntentAction.REQUEST_CHANGE

    @property
    def is_read_only(self) -> bool:
        """Da li intent samo čita/prikazuje (bez izmjene)."""
        return self.action in (
            IntentAction.SHOW,
            IntentAction.VALIDATE,
            IntentAction.ANALYZE,
        )
