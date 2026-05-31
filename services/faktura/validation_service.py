"""
Validation Service - Validacija stavki
"""

from typing import List, Tuple, Dict, Any, Optional
from core.draft import InvoiceLine
from services.validation_service import FakturaItemValidator, ValidationResult


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
        result = self.validator.validate(item)

        # Check if item is UNMATCHED
        is_unmatched = (
            not item.tarifni_broj or len(item.tarifni_broj.strip()) == 0
        ) and (not item.zemlja_porijekla or len(item.zemlja_porijekla.strip()) == 0)

        # Determine color based on validation result
        if is_unmatched:
            color_hex = "#cce5ff"  # Light blue for unmatched
            tooltip = "🔵 Nepodudarajuća stavka - nije pronađena u master listi. Popunite tarifni broj i zemlju porijekla."
        elif not item.tarifni_broj or len(item.tarifni_broj.strip()) == 0:
            color_hex = "#ffcccc"  # Red for missing tariff
            tooltip = "❌ Greška: Nedostaje tarifni broj"
        elif result.has_blocking_errors():
            color_hex = "#ffcccc"  # Red for errors
            tooltip = "❌ Greška: " + "; ".join([e.message for e in (result.errors or [])])
        elif len(result.warnings or []) > 0:
            color_hex = "#ffffcc"  # Yellow for warnings
            tooltip = "⚠️ Upozorenje: " + "; ".join([e.message for e in (result.warnings or [])])
        elif result.valid:
            color_hex = "#ccffcc"  # Green for valid
            tooltip = "✅ Validna stavka"
        else:
            color_hex = "#ffffff"  # White (not validated)
            tooltip = ""

        return color_hex, tooltip

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
