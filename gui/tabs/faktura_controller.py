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
