"""
Evidence model — zajednicki neutralni vokabular izvora i pouzdanosti odluka.

Premjesten iz services/agent/validation/evidence_model.py u core/decision/
da bi core sloj mogao da ga koristi bez zavisnosti od services.agent.

Stari modul (services/agent/validation/evidence_model.py) postaje
compatibility re-export i postepeno ce se gasiti kako se pozivaoci migriraju.
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
    PARSER = "parser"
    USER = "user"
    LLM = "llm"


class DecisionConfidence(Enum):
    CONFIRMED_FROM_DOCUMENT = "confirmed_from_document"
    CONFIRMED_FROM_SAME_EXPORTER_HISTORY = "confirmed_from_same_exporter_history"
    SUGGESTED_BY_SIMILARITY = "suggested_by_similarity"
    WEAK_GUESS = "weak_guess"
    UNKNOWN = "unknown"


class DecisionScoreCategory(Enum):
    CONFIRMED = "confirmed"
    STRONG_HISTORY = "strong_history"
    NEEDS_REVIEW = "needs_review"
    WEAK_INFORMATIONAL = "weak_informational"
    HIDDEN = "hidden"


_CONFIRMED_STATUSES = frozenset({
    DecisionConfidence.CONFIRMED_FROM_DOCUMENT,
    DecisionConfidence.CONFIRMED_FROM_SAME_EXPORTER_HISTORY,
})

_DEFAULT_SCORES: dict[DecisionConfidence, int] = {
    DecisionConfidence.CONFIRMED_FROM_DOCUMENT: 100,
    DecisionConfidence.CONFIRMED_FROM_SAME_EXPORTER_HISTORY: 90,
    DecisionConfidence.SUGGESTED_BY_SIMILARITY: 75,
    DecisionConfidence.WEAK_GUESS: 60,
    DecisionConfidence.UNKNOWN: 0,
}

_TARIFF_CONFIDENCE_LABELS: dict[DecisionConfidence, str] = {
    DecisionConfidence.CONFIRMED_FROM_DOCUMENT: "potvrdjen dokumentom",
    DecisionConfidence.CONFIRMED_FROM_SAME_EXPORTER_HISTORY: "jak",
    DecisionConfidence.SUGGESTED_BY_SIMILARITY: "srednji",
    DecisionConfidence.WEAK_GUESS: "slab",
    DecisionConfidence.UNKNOWN: "nepoznat",
}

_SCORE_CATEGORY_BADGE_COLORS: dict[DecisionScoreCategory, tuple[str, str]] = {
    DecisionScoreCategory.CONFIRMED: ("#065f46", "#d1fae5"),
    DecisionScoreCategory.STRONG_HISTORY: ("#1e3a5f", "#dbeafe"),
    DecisionScoreCategory.NEEDS_REVIEW: ("#92400e", "#fef3c7"),
    DecisionScoreCategory.WEAK_INFORMATIONAL: ("#6b7280", "#f3f4f6"),
    DecisionScoreCategory.HIDDEN: ("#b91c1c", "#fee2e2"),
}


@dataclass(frozen=True)
class Evidence:
    source: DecisionSource
    confidence: DecisionConfidence
    reason: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    requires_confirmation: bool = False
    score: int = 0
    score_category: DecisionScoreCategory = DecisionScoreCategory.HIDDEN

    @property
    def should_recommend(self) -> bool:
        return self.score >= 50 and self.confidence is not DecisionConfidence.UNKNOWN

    @property
    def auto_applicable(self) -> bool:
        return not self.requires_confirmation and self.score >= 85

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.value,
            "confidence": self.confidence.value,
            "reason": self.reason,
            "data": self.data,
            "requires_confirmation": self.requires_confirmation,
            "score": self.score,
            "score_category": self.score_category.value,
            "should_recommend": self.should_recommend,
            "auto_applicable": self.auto_applicable,
        }


def build_evidence(
    source: DecisionSource,
    confidence: DecisionConfidence,
    reason: str = "",
    data: dict[str, Any] | None = None,
    requires_confirmation: bool | None = None,
    score: int | None = None,
) -> Evidence:
    if source is DecisionSource.LLM and confidence in _CONFIRMED_STATUSES:
        confidence = DecisionConfidence.WEAK_GUESS
        reason = reason or "LLM odgovor nije dokaz; potrebna je potvrda iz dokumenta ili baze."
    if requires_confirmation is None:
        requires_confirmation = confidence not in _CONFIRMED_STATUSES
    resolved_score = _normalize_score(score if score is not None else _DEFAULT_SCORES[confidence])
    return Evidence(
        source=source,
        confidence=confidence,
        reason=reason,
        data=data or {},
        requires_confirmation=requires_confirmation,
        score=resolved_score,
        score_category=evidence_score_category(resolved_score),
    )


def evidence_from_tariff_decision(
    decision_outcome: str,
    supplier_match: bool,
    usage_count: int,
    source: str,
) -> Evidence:
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
    return _TARIFF_CONFIDENCE_LABELS.get(evidence.confidence, "nepoznat")


def evidence_badge_colors(evidence: Evidence) -> tuple[str, str]:
    return _SCORE_CATEGORY_BADGE_COLORS.get(
        evidence.score_category, _SCORE_CATEGORY_BADGE_COLORS[DecisionScoreCategory.HIDDEN]
    )


def badge_colors_for_score(score: int) -> tuple[str, str]:
    return _SCORE_CATEGORY_BADGE_COLORS.get(
        evidence_score_category(score), _SCORE_CATEGORY_BADGE_COLORS[DecisionScoreCategory.HIDDEN]
    )


def evidence_score_category(score: int) -> DecisionScoreCategory:
    score = _normalize_score(score)
    if score >= 95:
        return DecisionScoreCategory.CONFIRMED
    if score >= 85:
        return DecisionScoreCategory.STRONG_HISTORY
    if score >= 70:
        return DecisionScoreCategory.NEEDS_REVIEW
    if score >= 50:
        return DecisionScoreCategory.WEAK_INFORMATIONAL
    return DecisionScoreCategory.HIDDEN


def _normalize_score(score: int) -> int:
    return max(0, min(100, int(score)))


def evidence_from_preference(item: Any) -> Evidence:
    """
    Izvedi Evidence za povlasticu (Rub.36) jedne stavke fakture (InvoiceLine).

    Povlastica smije biti potvrdjena SAMO dokazom — PE1 (EUR.1 broj), PE2 (izjava
    o porijeklu) ili PE3 (izjava ovlascenog izvoznika). Sama zemlja porijekla NIJE
    dokaz: ako je povlastica predlozena samo na osnovu zemlje, vraca se
    weak_guess/requires_confirmation=True.
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
