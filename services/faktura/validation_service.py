"""
Validation Service - Validacija stavki
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any, Optional
from core.draft import InvoiceLine
from services.validation.validation_service import FakturaItemValidator, ValidationResult


@dataclass
class RowValidationStyle:
    result: ValidationResult
    row_color: str = "#ffffff"
    row_tooltip: str = ""
    cell_overrides: dict[int, tuple[str, str]] = field(default_factory=dict)


class ValidationService:
    """Validacija i bojenje redova"""

    def __init__(self):
        self.validator = FakturaItemValidator()

    def validate_and_get_color(self, item: InvoiceLine) -> Tuple[str, str]:
        """
        Validira stavku i vraća boju i tooltip.

        Args:
            item: InvoiceLine stavka

        Returns:
            Tuple: (color_hex, tooltip)
        """
        style = self.validate_and_get_style(item)
        return style.row_color, style.row_tooltip

    def validate_and_get_style(self, item: InvoiceLine) -> RowValidationStyle:
        result = self.validator.validate(item)
        tariff_sim = getattr(item, "tariff_similarity", 0.0) or 0.0

        # Check if item is UNMATCHED
        is_unmatched = (
            not item.tarifni_broj or len(item.tarifni_broj.strip()) == 0
        ) and (not item.zemlja_porijekla or len(item.zemlja_porijekla.strip()) == 0)

        # Determine color based on validation result
        cell_overrides: dict[int, tuple[str, str]] = {}
        if item.tarifni_broj and 0.70 <= tariff_sim < 0.92:
            color_hex = "#FFF4D6"
            tooltip = (
                f"⚠️ Tarifni broj: {item.tarifni_broj}\n"
                f"Pouzdanje: {tariff_sim:.0%}\n"
                f"Preporučuje se ručna provjera tarifnog broja"
            )
            cell_overrides[4] = (color_hex, tooltip)
            color_hex = "#ffffff"
            tooltip = ""
        elif is_unmatched:
            color_hex = "#E6F0F8"
            tooltip = "🔵 Nepodudarajuća stavka - nije pronađena u master listi. Popunite tarifni broj i zemlju porijekla."
            cell_overrides[4] = (color_hex, "❌ Nedostaje tarifni broj")
            cell_overrides[9] = (color_hex, "❌ Nedostaje zemlja porijekla")
            color_hex = "#ffffff"
            tooltip = ""
        elif not item.tarifni_broj or len(item.tarifni_broj.strip()) == 0:
            color_hex = "#F9E4E3"
            tooltip = "❌ Greška: Nedostaje tarifni broj"
            cell_overrides[4] = (color_hex, tooltip)
            color_hex = "#ffffff"
            tooltip = ""
        elif not item.zemlja_porijekla or len(item.zemlja_porijekla.strip()) == 0:
            color_hex = "#F9E4E3"
            tooltip = "❌ Greška: Nedostaje zemlja porijekla"
            cell_overrides[9] = (color_hex, tooltip)
            color_hex = "#ffffff"
            tooltip = ""
        elif result.has_blocking_errors():
            color_hex = "#F9E4E3"
            tooltip = "❌ Greška: " + "; ".join([e.message for e in (result.errors or [])])
        elif len(result.warnings or []) > 0:
            color_hex = "#FFF4D6"
            tooltip = "⚠️ Upozorenje: " + "; ".join([e.message for e in (result.warnings or [])])
        elif result.valid:
            color_hex = "#EAF4EE"
            tooltip = "✅ Validna stavka"
        else:
            color_hex = "#ffffff"  # White (not validated)
            tooltip = ""

        return RowValidationStyle(result, color_hex, tooltip, cell_overrides)

    def validate_all(self, items: List[InvoiceLine]) -> Dict[str, int]:
        """
        Validira sve stavke i vraća statistiku.

        Args:
            items: Lista InvoiceLine stavki

        Returns:
            Dict sa statistikom:
            {
                "error_count": int,
                "warning_count": int,
                "valid_count": int,
                "total_count": int
            }
        """
        error_count = 0
        warning_count = 0
        valid_count = 0

        for item in items:
            result = self.validator.validate(item)
            if result.has_blocking_errors():
                error_count += 1
            elif len(result.warnings or []) > 0:
                warning_count += 1
            elif result.valid:
                valid_count += 1

        return {
            "error_count": error_count,
            "warning_count": warning_count,
            "valid_count": valid_count,
            "total_count": len(items),
        }
