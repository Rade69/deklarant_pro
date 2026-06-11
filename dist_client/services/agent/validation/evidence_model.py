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

from services.agent.validation.tariff_decision_model import has_meaningful_source


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

_TARIFF_CONFIDENCE_LABELS: dict[DecisionConfidence, str] = {
    DecisionConfidence.CONFIRMED_FROM_SAME_EXPORTER_HISTORY: "jak",
    DecisionConfidence.SUGGESTED_BY_SIMILARITY: "srednji",
    DecisionConfidence.WEAK_GUESS: "slab",
    DecisionConfidence.UNKNOWN: "nepoznat",
}


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

    if not has_meaningful_source(source):
        return build_evidence(
            DecisionSource.TARIFF_DATABASE,
            DecisionConfidence.UNKNOWN,
            "Istorijski zapis nema poznat izvor (izvoznik/XML) — prijedlog se ne moze potvrditi kao istorija.",
            data,
        )

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


def tariff_confidence_label(evidence: Evidence) -> str:
    """Mapira Evidence.confidence na jak/srednji/slab/nepoznat (Faza 3)."""
    return _TARIFF_CONFIDENCE_LABELS.get(evidence.confidence, "nepoznat")


def evidence_from_preference(item: Any) -> Evidence:
    """
    Izvedi Evidence za povlasticu (Rub.36) jedne stavke fakture (InvoiceLine).

    Povlastica smije biti potvrdjena SAMO dokazom — PE1 (EUR.1 broj), PE2 (izjava
    o porijeklu) ili PE3 (izjava ovlascenog izvoznika). Sama zemlja porijekla NIJE
    dokaz: ako je povlastica predlozena samo na osnovu zemlje, vraca se
    weak_guess/requires_confirmation=True (Faza 2, vidi
    agent_tasks/2026-06-10_plan_unapredjenja_carinskog_agenta.md).
    """
    eur1_number = (getattr(item, "eur1_number", "") or "").strip()
    has_statement = bool(getattr(item, "has_origin_statement", False))
    is_authorized_exporter = bool(getattr(item, "is_authorized_exporter", False))
    povlastica = (getattr(item, "povlastica", "") or "").strip()
    country = (getattr(item, "zemlja_porijekla", "") or "").strip()
    data = {"country": country, "povlastica": povlastica}

    if has_statement and is_authorized_exporter:
        return build_evidence(
            DecisionSource.DOCUMENT,
            DecisionConfidence.CONFIRMED_FROM_DOCUMENT,
            "Potvrdjeno izjavom ovlascenog izvoznika (PE3) na fakturi.",
            {**data, "doc_code": "PE3", "invoice_reference": eur1_number},
        )
    if has_statement:
        return build_evidence(
            DecisionSource.DOCUMENT,
            DecisionConfidence.CONFIRMED_FROM_DOCUMENT,
            "Potvrdjeno izjavom o porijeklu (PE2) na fakturi.",
            {**data, "doc_code": "PE2", "invoice_reference": eur1_number},
        )
    if eur1_number:
        return build_evidence(
            DecisionSource.DOCUMENT,
            DecisionConfidence.CONFIRMED_FROM_DOCUMENT,
            "Potvrdjeno EUR.1 obrascem (PE1).",
            {**data, "doc_code": "PE1", "eur1_number": eur1_number},
        )
    if povlastica:
        return build_evidence(
            DecisionSource.SIMILARITY,
            DecisionConfidence.WEAK_GUESS,
            "Povlastica izvedena samo iz zemlje porijekla, bez PE1/PE2/PE3 dokaza.",
            data,
        )
    return build_evidence(
        DecisionSource.TARIFF_DATABASE,
        DecisionConfidence.UNKNOWN,
        "Nema povlastice niti dokaza o porijeklu.",
        data,
    )
