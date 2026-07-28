"""
FakturaController — prazna infrastruktura bez promjene ponašanja.

Faza 1 prema Codex planu §8: composition root.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

from PySide6.QtCore import QObject

from core.draft import DeclarationDraft
from services.faktura.naimenovanja_service import NaimenovanjaService

logger = logging.getLogger("deklarant_pro.faktura.controller")


class FakturaController(QObject):

    def __init__(
        self,
        get_draft_fn: Callable[[], DeclarationDraft],
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._get_draft = get_draft_fn

    @property
    def draft(self) -> DeclarationDraft:
        return self._get_draft()

    # ── Validacija i bojenje (Faza 3) ──────────────────────────

    def validate_and_color_rows(self, view, draft) -> ValidationPassResult:
        """Validiraj sve redove i vrati boje + tooltip.
        
        Koristi postojeći FakturaValidationService.
        """
        from services.faktura.validation_service import FakturaValidationService
        from services.faktura.models import ValidationPassResult
        
        svc = FakturaValidationService()
        lines = getattr(draft, "invoice_lines", []) or []
        color_map = {}
        errors = 0
        warnings = 0
        
        for idx, line in enumerate(lines):
            try:
                color, tooltip = svc.validate_and_get_color(line)
                color_map[idx] = (color, tooltip)
                if "#ff" in color.lower() or "#F9" in color.upper():  # crvena
                    errors += 1
                elif "#ff" in color.lower() or "#FF" in color.upper():  # žuta
                    warnings += 1
            except Exception:
                color_map[idx] = ("#ffffff", "")
        
        return ValidationPassResult(
            validated_count=len(lines),
            error_count=errors,
            warning_count=warnings,
            color_map=color_map,
        )
