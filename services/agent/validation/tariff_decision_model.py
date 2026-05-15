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
    current = tariff_digits(trenutni)
    historical = tariff_digits(match.tarifni_broj_historijski)
    if not historical:
        return TariffDecision(TariffDecisionOutcome.SUPPRESS)
    if current and current == historical:
        return TariffDecision(TariffDecisionOutcome.SUPPRESS)

    has_source = has_meaningful_source(match.source)
    profile = invoice_profile or {}
    profile_chapters = profile.get("chapters", set())
    if not current:
        if match.usage_count >= thresholds.min_usage_for_weak_source or has_source:
            return TariffDecision(
                TariffDecisionOutcome.SHOW_STRONG,
                "Nema trenutne tarife; istorijski zapis ima dovoljno izvora/ponavljanja.",
            )
        return TariffDecision(TariffDecisionOutcome.SUPPRESS)

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
            return TariffDecision(TariffDecisionOutcome.SUPPRESS)

    if current_chapter != historical_chapter:
        if (
            match.usage_count >= thresholds.min_usage_for_cross_chapter
            and (has_source or match.confidence >= 0.68)
        ):
            return TariffDecision(
                TariffDecisionOutcome.SHOW_STRONG,
                "Promjena poglavlja dozvoljena samo zbog jačeg istorijskog dokaza.",
            )
        return TariffDecision(TariffDecisionOutcome.SUPPRESS)

    if current_heading != historical_heading:
        if match.usage_count >= thresholds.min_usage_for_weak_source or has_source:
            return TariffDecision(
                TariffDecisionOutcome.SHOW_WEAK,
                "Isto poglavlje, drugi tarifni heading iz istorije.",
            )
        return TariffDecision(TariffDecisionOutcome.SUPPRESS)

    return TariffDecision(
        TariffDecisionOutcome.SHOW_WEAK,
        "Ista tarifna glava; istorija ukazuje na precizniji broj.",
    )


def tariff_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def has_meaningful_source(value: str) -> bool:
    source = (value or "").strip()
    return bool(source and source not in {"-", "—", "+", "A", "HISTORIJA"})
