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

    def _notify_mutation(self, view, draft) -> None:
        draft.mark_dirty()
        if getattr(view, "on_dirty", None):
            view.on_dirty()
        if hasattr(view, "data_changed"):
            view.data_changed.emit()

    def save_current_item(self, view, notify: bool = True) -> bool:
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

        form_data = view.read_current_form()
        changed = self._service.apply_form_to_item(form_data, item)

        from gui.tabs.naimenovanja_view import _clear_secondary_pe_documents
        changed = _clear_secondary_pe_documents(item) or changed

        new_tariff = getattr(item, "tariff_code", "") or ""
        new_suffix = getattr(item, "tariff_suffix", "") or "000"
        if new_tariff and (new_tariff != old_tariff or new_suffix != old_suffix):
            changed = bool(self._service.sync_tariff_to_invoice_lines(
                old_tariff, old_suffix, new_tariff, new_suffix, item, draft,
            )) or changed

        if changed and notify:
            self._notify_mutation(view, draft)
        return changed

    # ── Navigation ─────────────────────────────────────────────────

    def navigate_to(self, view, index: int) -> None:
        """Navigiraj na item — snimi trenutni prije navigacije."""
        self.save_current_item(view)
        draft = self._get_draft()
        items = getattr(draft, "items", []) or []
        if not items or index < 0 or index >= len(items):
            return
        setattr(view, "current_item_index", index)
        view.render_current_item()

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
        for ordinal, item in enumerate(items, 1):
            item.ordinal_no = ordinal
        new_idx = min(index, len(items) - 1) if items else 0
        setattr(view, "current_item_index", new_idx)
        self._notify_mutation(view, draft)
        view.render_current_item()

    def add_item(self, view) -> None:
        self.save_current_item(view, notify=False)
        draft = self._get_draft()
        item = draft.add_item()
        item.ordinal_no = len(draft.items)
        setattr(view, "current_item_index", len(draft.items) - 1)
        self._notify_mutation(view, draft)
        view.render_current_item()
        view.focus_tariff_field()

    # ── Tarifni tok (Faza 5) ──────────────────────────────────────

    def on_tariff_changed(self, view, code: str) -> None:
        """Handler za promjenu tarifnog broja u View-u.

        Flow: Controller debounce → TariffService lookup →
        Service dokumenti → Controller primjena → View render.
        KB učenje samo nakon eksplicitne potvrde.
        """
        if not code or not code.strip():
            return
        code = code.strip()

        # 1. Tarifni lookup (full + short opisi)
        full, short = self._tariff_service.load_tariff_descriptions(code)
        warnings = []

        if not full and not short:
            warnings.append(f"Tarifni broj '{code}' nije pronađen u zvaničnoj tarifi")

        # 2. Dopunska JM
        supp_code = self._service.resolve_supplementary_unit(code)

        # 3. Dokumenti po tarifi
        try:
            from services.tariff_controls_service import check_tariff_controls, get_required_docs
            controls = check_tariff_controls(code)
            docs = get_required_docs(code) if controls else []
        except Exception:
            docs = []

        # 4. Primijeni na draft
        draft = self._get_draft()
        idx = getattr(view, "current_item_index", 0)
        items = getattr(draft, "items", []) or []
        if items and idx < len(items):
            item = items[idx]
            item.tariff_code = code
            if full:
                item.tariff_description1 = full
            if short:
                item.tariff_description2 = short
            if supp_code and not getattr(item, "supplementary_unit_code", ""):
                item.supplementary_unit_code = supp_code
            draft.mark_dirty()

        # 5. View render (ako postoji render metoda)
        if hasattr(view, "_populate_tariff_description"):
            view._populate_tariff_description(full or "", short or "")
        if warnings and hasattr(view, "_check_and_show_tariff_warning"):
            view._check_and_show_tariff_warning(code)

    def accept_tariff_suggestion(self, view, result: dict) -> None:
        """Primijeni prihvaćeni tarifni prijedlog."""
        draft = self._get_draft()
        idx = getattr(view, "current_item_index", 0)
        items = getattr(draft, "items", []) or []
        if not items or idx >= len(items):
            return

        item = items[idx]
        code = result.get("tarifni_broj", "")
        if code:
            item.tariff_code = code
            item.preference_code = result.get("povlastica", "")
            item.origin_country_code = result.get("zemlja_porijekla", "")
            draft.mark_dirty()
            if hasattr(view, "_load_current_item"):
                view._load_current_item()

    # ── Dokumenti (Faza 6) ────────────────────────────────────────

    def sync_pe_docs_to_header(self, view) -> None:
        """Sinhronizuj PE1/PE2/PE3 dokumente iz naimenovanja u zaglavlje."""
        draft = self._get_draft()
        pe_codes = {"PE1", "PE2", "PE3"}
        items = getattr(draft, "items", []) or []
        header_docs = getattr(draft, "header_attached_documents", None) or []
        from core.draft import AttachedDocument
        for field_name in ("attached_document4", "attached_document5", "attached_document1", "attached_document2", "attached_document3"):
            for item in items:
                doc_text = getattr(item, field_name, "") or ""
                code = doc_text.strip().split(" ", 1)[0].upper() if doc_text.strip() else ""
                if code in pe_codes:
                    if not any(d.code == code for d in header_docs):
                        header_docs.append(AttachedDocument(code=code, name=code, number=doc_text.strip().split(" ", 1)[1] if " " in doc_text else ""))
        draft.header_attached_documents = header_docs
        draft.mark_dirty()

    def compute_document_merge(self, items: list) -> dict:
        """Deduplikovani dokumenti za sva naimenovanja."""
        result: dict = {}
        pe_codes = {"PE1", "PE2", "PE3"}
        for item in items:
            for field_name in ("attached_document4", "attached_document5", "attached_document1", "attached_document2", "attached_document3"):
                doc_text = getattr(item, field_name, "") or ""
                if not doc_text.strip():
                    continue
                code = doc_text.strip().split(" ", 1)[0].upper()
                number = doc_text.strip().split(" ", 1)[1] if " " in doc_text else ""
                if code not in result:
                    result[code] = number
        return result

    # ── XML / Prijedlozi (Faza 7) ──────────────────────────────────

    def import_xml(self, view, filepath: str) -> bool:
        """Uvezi naimenovanja iz XML fajla."""
        try:
            from services.zaglavlje_service import ZaglavljeService
            svc = ZaglavljeService()
            items = svc.parse_naimenovanja_from_xml(filepath)
            if not items:
                return False

            draft = self._get_draft()
            draft.items = items
            draft.mark_dirty()
            return True
        except Exception:
            return False

    def prepare_tariff_suggestions(self, view) -> list:
        """Pripremi kandidate za tarifni prijedlog (ne prikazuje dijalog)."""
        draft = self._get_draft()
        idx = getattr(view, "current_item_index", 0)
        items = getattr(draft, "items", []) or []
        if not items or idx >= len(items):
            return []
        item = items[idx]
        name = getattr(item, "goods_trade_name", "") or getattr(item, "goods_description", "")
        origin = getattr(item, "origin_country_code", "")
        if not name or not name.strip():
            return []
        return self._tariff_service.suggest_tariff(name, origin)
