from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict


class TariffDecisionOutcome(Enum):
    SHOW_STRONG = "show_strong"
    SHOW_WEAK = "show_weak"
    SUPPRESS = "suppress"


@dataclass(frozen=True)
class TariffDecisionThresholds:
    min_usage_for_cross_chapter: int
    min_usage_for_out_of_profile_chapter: int
    min_usage_for_weak_source: int


@dataclass(frozen=True)
class TariffDecision:
    outcome: TariffDecisionOutcome
    reason: str = ""
    score: int = 0
    positive_reasons: tuple[str, ...] = ()
    negative_reasons: tuple[str, ...] = ()

    @property
    def should_show(self) -> bool:
        return self.outcome in {
            TariffDecisionOutcome.SHOW_STRONG,
            TariffDecisionOutcome.SHOW_WEAK,
        }


def is_actionable_tariff_match(
    match: Any,
    trenutni: str,
    invoice_profile: Dict | None,
    thresholds: TariffDecisionThresholds,
) -> bool:
    decision = decide_tariff_match(match, trenutni, invoice_profile, thresholds)
    if decision.reason:
        match.decision_reason = decision.reason
    return decision.should_show


def decide_tariff_match(
    match: Any,
    trenutni: str,
    invoice_profile: Dict | None,
    thresholds: TariffDecisionThresholds,
) -> TariffDecision:
    score = 0
    positive_reasons = []
    negative_reasons = []

    current = tariff_digits(trenutni)
    historical = tariff_digits(match.tarifni_broj_historijski)
    if not historical:
        return _decision(
            TariffDecisionOutcome.SUPPRESS,
            score,
            positive_reasons,
            ["Istorijski tarifni broj je prazan."],
        )
    if current and current == historical:
        return _decision(
            TariffDecisionOutcome.SUPPRESS,
            score,
            positive_reasons,
            ["Istorijski tarifni broj je isti kao trenutni."],
        )

    has_source = has_meaningful_source(match.source)
    if has_source:
        score += 20
        positive_reasons.append("Istorijski zapis ima smislen izvor.")
    else:
        score -= 10
        negative_reasons.append("Istorijski zapis nema smislen izvor.")

    if match.usage_count >= thresholds.min_usage_for_weak_source:
        score += min(match.usage_count, 10) * 3
        positive_reasons.append("Istorijski zapis ima dovoljno ponavljanja.")
    else:
        score -= 5
        negative_reasons.append("Istorijski zapis ima malo ponavljanja.")

    profile = invoice_profile or {}
    profile_chapters = profile.get("chapters", set())
    if not current:
        if match.usage_count >= thresholds.min_usage_for_weak_source or has_source:
            score += 35
            positive_reasons.append("Trenutna tarifa nije popunjena.")
            return _decision(
                TariffDecisionOutcome.SHOW_STRONG,
                score,
                positive_reasons,
                negative_reasons,
                "Nema trenutne tarife; istorijski zapis ima dovoljno izvora/ponavljanja.",
            )
        return _decision(
            TariffDecisionOutcome.SUPPRESS,
            score,
            positive_reasons,
            negative_reasons,
        )

    current_chapter = current[:2]
    historical_chapter = historical[:2]
    current_heading = current[:4]
    historical_heading = historical[:4]

    if (
        profile.get("item_count", 0) >= 5
        and current_chapter in profile_chapters
        and historical_chapter not in profile_chapters
        and current_chapter != historical_chapter
    ):
        if not (
            match.usage_count >= thresholds.min_usage_for_out_of_profile_chapter
            and has_source
            and match.confidence >= 0.68
        ):
            return _decision(
                TariffDecisionOutcome.SUPPRESS,
                score - 35,
                positive_reasons,
                negative_reasons + ["Prijedlog iskače van profila fakture bez dovoljno jakog dokaza."],
            )
        score += 15
        positive_reasons.append("Prijedlog van profila fakture ima jak istorijski dokaz.")

    if current_chapter != historical_chapter:
        score -= 25
        negative_reasons.append("Prijedlog mijenja tarifno poglavlje.")
        if (
            match.usage_count >= thresholds.min_usage_for_cross_chapter
            and (has_source or match.confidence >= 0.68)
        ):
            score += 45
            positive_reasons.append("Promjena poglavlja ima jači istorijski dokaz.")
            return _decision(
                TariffDecisionOutcome.SHOW_STRONG,
                score,
                positive_reasons,
                negative_reasons,
                "Promjena poglavlja dozvoljena samo zbog jačeg istorijskog dokaza.",
            )
        return _decision(
            TariffDecisionOutcome.SUPPRESS,
            score,
            positive_reasons,
            negative_reasons,
        )

    if current_heading != historical_heading:
        score += 15
        positive_reasons.append("Prijedlog ostaje u istom tarifnom poglavlju.")
        if match.usage_count >= thresholds.min_usage_for_weak_source or has_source:
            return _decision(
                TariffDecisionOutcome.SHOW_WEAK,
                score,
                positive_reasons,
                negative_reasons,
                "Isto poglavlje, drugi tarifni heading iz istorije.",
            )
        return _decision(
            TariffDecisionOutcome.SUPPRESS,
            score,
            positive_reasons,
            negative_reasons,
        )

    score += 30
    positive_reasons.append("Prijedlog ostaje u istoj tarifnoj glavi.")
    return _decision(
        TariffDecisionOutcome.SHOW_WEAK,
        score,
        positive_reasons,
        negative_reasons,
        "Ista tarifna glava; istorija ukazuje na precizniji broj.",
    )


def tariff_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def has_meaningful_source(value: str) -> bool:
    source = (value or "").strip()
    return bool(source and source not in {"-", "—", "+", "A", "HISTORIJA"})


def _decision(
    outcome: TariffDecisionOutcome,
    score: int,
    positive_reasons: list[str],
    negative_reasons: list[str],
    reason: str = "",
) -> TariffDecision:
    return TariffDecision(
        outcome=outcome,
        reason=reason,
        score=score,
        positive_reasons=tuple(positive_reasons),
        negative_reasons=tuple(negative_reasons),
    )
