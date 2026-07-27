"""
NaimenovanjaController — prazna infrastruktura bez promjene ponašanja.

Faza 1 prema Codex planu §8: composition root. Controller postoji ali
ne obrađuje signale dok se ne migriraju u vertikalnim rezovima (Faze 4-7).

Controller NE smije:
- koristiti findChild, widget_cache, setText, setGeometry
- sadržavati SQL
- keširati zasebnu draft referencu
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

from PySide6.QtCore import QObject

from core.draft import DeclarationDraft
from services.naimenovanja.naimenovanja_service import NaimenovanjaService
from services.naimenovanja.tariff_service import TariffService

logger = logging.getLogger("deklarant_pro.naimenovanja.controller")


class NaimenovanjaController(QObject):
    """Orchestration sloj između NaimenovanjaView i servisa.

    Prima get_draft_fn umjesto direktne draft reference —
    draft se uvijek čita iz View-a, ne kešira se u Controlleru.
    """

    def __init__(
        self,
        get_draft_fn: Callable[[], DeclarationDraft],
        service: Optional[NaimenovanjaService] = None,
        tariff_service: Optional[TariffService] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._get_draft = get_draft_fn
        self._service = service or NaimenovanjaService()
        self._tariff_service = tariff_service or TariffService()

    @property
    def draft(self) -> DeclarationDraft:
        """Trenutni draft — uvijek iz View-a, nikad keširan."""
        return self._get_draft()

    @property
    def service(self) -> NaimenovanjaService:
        return self._service

    @property
    def tariff_service(self) -> TariffService:
        return self._tariff_service
