"""
Evidence model — zajednicki vokabular izvora i pouzdanosti odluka agenta.

Definise DecisionSource (odakle podatak dolazi) i DecisionConfidence (koliko je
pouzdan), prema agent_tasks/2026-06-10_plan_unapredjenja_carinskog_agenta.md.
LLM nikad nije izvor dokaza — samo prezentacioni sloj.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DecisionSource(Enum):
    DOCUMENT = "document"
    EXPORTER_HISTORY = "exporter_history"
    TARIFF_DATABASE = "tariff_database"
    SIMILARITY = "similarity"
    USER = "user"
    LLM = "llm"


class DecisionConfidence(Enum):
    CONFIRMED_FROM_DOCUMENT = "confirmed_from_document"
    CONFIRMED_FROM_SAME_EXPORTER_HISTORY = "confirmed_from_same_exporter_history"
    SUGGESTED_BY_SIMILARITY = "suggested_by_similarity"
    WEAK_GUESS = "weak_guess"
    UNKNOWN = "unknown"


_CONFIRMED_STATUSES = frozenset({
    DecisionConfidence.CONFIRMED_FROM_DOCUMENT,
    DecisionConfidence.CONFIRMED_FROM_SAME_EXPORTER_HISTORY,
})


@dataclass(frozen=True)
class Evidence:
    source: DecisionSource
    confidence: DecisionConfidence
    reason: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    requires_confirmation: bool = False


def build_evidence(
    source: DecisionSource,
    confidence: DecisionConfidence,
    reason: str = "",
    data: dict[str, Any] | None = None,
    requires_confirmation: bool | None = None,
) -> Evidence:
    """Kreira Evidence; requires_confirmation se po defaultu izvodi iz confidence statusa."""
    if requires_confirmation is None:
        requires_confirmation = confidence not in _CONFIRMED_STATUSES
    return Evidence(
        source=source,
        confidence=confidence,
        reason=reason,
        data=data or {},
        requires_confirmation=requires_confirmation,
    )


def evidence_from_tariff_decision(
    decision_outcome: str,
    supplier_match: bool,
    usage_count: int,
    source: str,
) -> Evidence:
    """Mapira ishod decide_tariff_match() (show_strong/show_weak/suppress) na Evidence."""
    data = {"usage_count": usage_count, "source": source, "supplier_match": supplier_match}

    if decision_outcome == "show_strong":
        if supplier_match:
            return build_evidence(
                DecisionSource.EXPORTER_HISTORY,
                DecisionConfidence.CONFIRMED_FROM_SAME_EXPORTER_HISTORY,
                "Potvrdjeno iz istorije istog izvoznika.",
                data,
            )
        return build_evidence(
            DecisionSource.SIMILARITY,
            DecisionConfidence.SUGGESTED_BY_SIMILARITY,
            "Jak prijedlog bez potvrde istog izvoznika.",
            data,
        )

    if decision_outcome == "show_weak":
        src = DecisionSource.EXPORTER_HISTORY if supplier_match else DecisionSource.SIMILARITY
        return build_evidence(
            src,
            DecisionConfidence.WEAK_GUESS,
            "Slabiji prijedlog — potrebna potvrda korisnika.",
            data,
        )

    return build_evidence(
        DecisionSource.TARIFF_DATABASE,
        DecisionConfidence.UNKNOWN,
        "Prijedlog potisnut ili izvor nije prepoznat.",
        data,
    )
