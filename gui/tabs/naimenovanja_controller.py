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

    # ── Save Current Item ──────────────────────────────────────────

    def save_current_item(self, view) -> bool:
        """Snimi trenutne vrijednosti iz View forme u draft item.

        Flow: View.read_current_form → Service.apply_form_to_item
        → sync_tariff → mark_dirty.

        Returns True ako je nešto snimljeno.
        """
        draft = self._get_draft()
        if getattr(view, "is_loading", False):
            return False
        items = getattr(draft, "items", []) or []
        if not items:
            return False
        idx = getattr(view, "current_item_index", 0)
        if idx >= len(items):
            return False

        item = items[idx]
        old_tariff = getattr(item, "tariff_code", "") or ""
        old_suffix = getattr(item, "tariff_suffix", "") or "000"

        # Čitaj formu i primijeni na item
        from gui.tabs.naimenovanja_view_phase4 import read_current_form
        form_data = read_current_form(view)
        self._service.apply_form_to_item(form_data, item)

        # PE dokumenti
        from gui.tabs.naimenovanja_view import _clear_secondary_pe_documents
        _clear_secondary_pe_documents(item)

        draft.mark_dirty()

        # Sinhronizuj tarifu
        new_tariff = getattr(item, "tariff_code", "") or ""
        new_suffix = getattr(item, "tariff_suffix", "") or "000"
        if new_tariff and (new_tariff != old_tariff or new_suffix != old_suffix):
            self._service.sync_tariff_to_invoice_lines(
                old_tariff, old_suffix, new_tariff, new_suffix, item, draft,
            )

        return True

    # ── Navigation ─────────────────────────────────────────────────

    def navigate_to(self, view, index: int) -> None:
        """Navigiraj na item — snimi trenutni prije navigacije."""
        self.save_current_item(view)
        draft = self._get_draft()
        items = getattr(draft, "items", []) or []
        if not items or index < 0 or index >= len(items):
            return
        setattr(view, "current_item_index", index)
        if hasattr(view, "_load_current_item"):
            view._load_current_item()
        if hasattr(view, "_update_status_bar"):
            view._update_status_bar()

    def next_item(self, view) -> None:
        draft = self._get_draft()
        idx = getattr(view, "current_item_index", 0)
        if idx < len(getattr(draft, "items", [])) - 1:
            self.navigate_to(view, idx + 1)

    def prev_item(self, view) -> None:
        idx = getattr(view, "current_item_index", 0)
        if idx > 0:
            self.navigate_to(view, idx - 1)

    def delete_item(self, view, index: int) -> None:
        draft = self._get_draft()
        items = getattr(draft, "items", []) or []
        if not items or index < 0 or index >= len(items):
            return
        del items[index]
        draft.mark_dirty()
        new_idx = min(index, len(items) - 1) if items else 0
        self.navigate_to(view, new_idx)
