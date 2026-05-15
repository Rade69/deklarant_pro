from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class TariffDecisionThresholds:
    min_usage_for_cross_chapter: int
    min_usage_for_out_of_profile_chapter: int
    min_usage_for_weak_source: int


def is_actionable_tariff_match(
    match: Any,
    trenutni: str,
    invoice_profile: Dict | None,
    thresholds: TariffDecisionThresholds,
) -> bool:
    current = tariff_digits(trenutni)
    historical = tariff_digits(match.tarifni_broj_historijski)
    if not historical:
        return False
    if current and current == historical:
        return False

    has_source = has_meaningful_source(match.source)
    profile = invoice_profile or {}
    profile_chapters = profile.get("chapters", set())
    if not current:
        if match.usage_count >= thresholds.min_usage_for_weak_source or has_source:
            match.decision_reason = "Nema trenutne tarife; istorijski zapis ima dovoljno izvora/ponavljanja."
            return True
        return False

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
            return False

    if current_chapter != historical_chapter:
        if (
            match.usage_count >= thresholds.min_usage_for_cross_chapter
            and (has_source or match.confidence >= 0.68)
        ):
            match.decision_reason = (
                "Promjena poglavlja dozvoljena samo zbog jačeg istorijskog dokaza."
            )
            return True
        return False

    if current_heading != historical_heading:
        if match.usage_count >= thresholds.min_usage_for_weak_source or has_source:
            match.decision_reason = "Isto poglavlje, drugi tarifni heading iz istorije."
            return True
        return False

    match.decision_reason = "Ista tarifna glava; istorija ukazuje na precizniji broj."
    return True


def tariff_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def has_meaningful_source(value: str) -> bool:
    source = (value or "").strip()
    return bool(source and source not in {"-", "—", "+", "A", "HISTORIJA"})
