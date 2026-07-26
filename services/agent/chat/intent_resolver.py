"""
Intent Resolver — jedinstvena tačka za klasifikaciju korisničke poruke.

Plan §12: jedan resolver određuje action/target/scope prije dispatchera.
Koristi lokalna pravila (intent_rules.py) za visoko pouzdane obrasce,
i LLM Tool Use za složene slučajeve.

Ne zavisi od Qt widgeta. Komunicira sa chat_intent_handler preko
Audit i ToolDispatcherWorker signala.
"""

from __future__ import annotations

import logging

from services.agent.chat.intent_model import (
    AgentIntent,
    IntentAction,
    IntentSource,
    IntentTarget,
)
from services.agent.chat.intent_rules import apply_rules

logger = logging.getLogger("deklarant_pro.agent.intent_resolver")


def resolve(message: str) -> AgentIntent:
    """Klasifikuj poruku u AgentIntent.

    Flow:
      1. Lokalna pravila (intent_rules) — za nedvosmislene obrasce
      2. Ako pravila ne mogu → OTHER (prepušta se Tool Use u _handle_message)

    Napomena: LLM Tool Use se pokreće u chat_intent_handler._handle_message,
    ne u resolveru. Resolver samo vraća intent — dispatcher odlučuje
    da li da pozove LLM ili ne.
    """
    # Prvo probaj lokalna pravila
    intent = apply_rules(message)
    if intent is not None:
        logger.debug(
            "Intent resolved locally: %s/%s (%.0f%%)",
            intent.action.value, intent.target.value, intent.confidence * 100,
        )
        return intent

    # Pravila nisu uspjela — prepusti Tool Use
    logger.debug("Intent unresolved by local rules — delegating to Tool Use")
    return AgentIntent(
        action=IntentAction.OTHER,
        source=IntentSource.LLM,
        confidence=0.0,
    )
