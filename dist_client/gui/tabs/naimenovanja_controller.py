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
        reload_header_fn: Optional[Callable[[], None]] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._get_draft = get_draft_fn
        self._service = service or NaimenovanjaService()
        self._tariff_service = tariff_service or TariffService()
        self._reload_header = reload_header_fn or (lambda: None)

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

        changed = self._service.clear_secondary_pe_documents(item) or changed

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
        result = self._service.build_tariff_lookup(code)
        draft = self._get_draft()
        idx = getattr(view, "current_item_index", 0)
        items = getattr(draft, "items", []) or []
        if items and idx < len(items):
            item = items[idx]
            old_code = getattr(item, "tariff_code", "") or ""
            item.tariff_code = result.tariff_code
            item.tariff_description1 = result.full_description
            item.tariff_description2 = result.short_description
            if (
                result.supplementary_unit_code
                and not getattr(item, "supplementary_unit_code", "")
            ):
                item.supplementary_unit_code = result.supplementary_unit_code
            self._service.sync_tariff_to_invoice_lines(
                old_code,
                getattr(item, "tariff_suffix", "") or "000",
                result.tariff_code,
                getattr(item, "tariff_suffix", "") or "000",
                item,
                draft,
            )
            self._service.add_tariff_documents(draft, result.tariff_code)
            self._notify_mutation(view, draft)
        view.show_tariff_lookup(result)

    def update_knowledge_base(self, view, tariff_code: str) -> None:
        draft = self._get_draft()
        items = getattr(draft, "items", []) or []
        index = getattr(view, "current_item_index", 0)
        if not items or index >= len(items):
            return
        item = items[index]
        lines = self._service.assigned_invoice_lines(draft, item)
        try:
            from services.tariff_facade import TariffFacade
            facade = TariffFacade.get_instance()
            updated = 0
            for line in lines:
                name = (getattr(line, "naziv_robe", "") or "").strip()
                if not name:
                    continue
                facade.sync_mapping(
                    naziv_robe=name,
                    product_code=getattr(line, "product_code", "") or "",
                    new_tariff=tariff_code,
                    zemlja_porijekla=getattr(line, "zemlja_porijekla", "") or "",
                    precision_1=getattr(item, "tariff_suffix", "") or "000",
                )
                updated += 1
            if not lines:
                name = (
                    getattr(item, "goods_description", "")
                    or getattr(item, "goods_trade_name", "")
                    or ""
                ).strip()
                if name:
                    facade.sync_mapping(
                        naziv_robe=name,
                        product_code="",
                        new_tariff=tariff_code,
                        zemlja_porijekla=(
                            getattr(item, "origin_country_code", "") or ""
                        ),
                        precision_1=(
                            getattr(item, "tariff_suffix", "") or "000"
                        ),
                    )
                    updated = 1
            view.show_knowledge_base_updated(updated, tariff_code)
        except Exception as exc:
            logger.exception("Greška pri ažuriranju baze znanja")
            view.show_error(f"Nije moguće ažurirati bazu znanja:\n{exc}")

    def accept_tariff_suggestion(self, view, result: dict) -> None:
        """Primijeni prihvaćeni tarifni prijedlog."""
        draft = self._get_draft()
        idx = getattr(view, "current_item_index", 0)
        items = getattr(draft, "items", []) or []
        if not items or idx >= len(items):
            return

        item = items[idx]
        code = self._service.normalize_field_value(
            "tariff_code", result.get("tarifni_broj", "")
        )
        if code:
            item.tariff_code = code
            self._notify_mutation(view, draft)
            view.render_current_item()
            try:
                from services.tariff_facade import TariffFacade
                TariffFacade.get_instance().increment_usage(
                    code, None, getattr(item, "goods_trade_name", "") or ""
                )
            except Exception:
                logger.warning("Nije ažuriran brojač korištenja tarife", exc_info=True)

    # ── Dokumenti (Faza 6) ────────────────────────────────────────

    def sync_pe_docs_to_header(self, view) -> None:
        """Sinhronizuj PE1/PE2/PE3 dokumente iz naimenovanja u zaglavlje."""
        draft = self._get_draft()
        index = getattr(view, "current_item_index", 0)
        value = view.current_pe_document()
        result = self._service.apply_pe_document(draft, index, value)
        self._notify_mutation(view, draft)
        view.show_document_merge(result)

    def compute_document_merge(self, items: list):
        draft = self._get_draft()
        value = getattr(items[0], "attached_document4", "") if items else ""
        return self._service.apply_pe_document(draft, 0, value)

    # ── XML / Prijedlozi (Faza 7) ──────────────────────────────────

    def import_xml(self, view, filepath: str) -> bool:
        """Uvezi naimenovanja iz XML fajla."""
        try:
            draft = self._get_draft()
            result = self._service.import_xml(draft, filepath)
            if not result.items_count:
                view.show_warning("\n".join(result.warnings))
                return False
            setattr(view, "current_item_index", 0)
            self._notify_mutation(view, draft)
            view.reload_data()
            self._reload_header()
            view.show_success(
                f"Uvezeno {result.items_count} naimenovanja iz XML-a.\n"
                "Kliknite 'Sačuvaj' da potvrdite promjene."
            )
            return True
        except Exception as exc:
            logger.exception("Greška pri uvozu XML naimenovanja")
            view.show_error(f"Greška pri uvozu: {exc}")
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
        is_valid, reason = self._tariff_service.validate_suggestion_input(name)
        if not is_valid:
            view.show_invalid_suggestion_input(reason, name)
            return []
        mappings = self._tariff_service.suggest_tariff(name, origin)
        return self._tariff_service.validate_mappings(mappings)
