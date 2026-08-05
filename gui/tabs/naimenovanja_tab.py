# gui/tabs/naimenovanja_tab.py

import logging
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Signal
from typing import Optional, Callable

from core.draft import DeclarationDraft
from gui.tabs.naimenovanja_view import NaimenovanjaView
from gui.tabs.naimenovanja_controller import NaimenovanjaController
from services.naimenovanja.naimenovanja_service import NaimenovanjaService


logger = logging.getLogger("deklarant_pro.naimenovanja")

class NaimenovanjaTab(QWidget):
    """Wrapper koji eksponuje NaimenovanjaView prema MainWindow-u.

    Faza 1 (Codex plan §8): composition root — kreira Controller
    sa get_draft_fn i injektovanim Service-om.
    """

    data_changed = Signal()

    def __init__(
        self,
        draft: Optional[DeclarationDraft] = None,
        on_dirty: Optional[Callable] = None,
        parent: Optional[QWidget] = None,
        service: Optional[NaimenovanjaService] = None,
    ):
        super().__init__(parent)
        self.view = NaimenovanjaView(draft=draft, on_dirty=on_dirty)
        self.view.data_changed.connect(self.data_changed)

        # Composition root: Controller sa get_draft_fn i injektovanim Service-om
        self._service = service or NaimenovanjaService()
        self.controller = NaimenovanjaController(
            get_draft_fn=lambda: self.view.draft,
            service=self._service,
            reload_header_fn=self._reload_header,
            save_header_fn=self._save_header,
            replace_draft_fn=self._replace_draft,
            parent=self,
        )
        self.view.save_current_requested.connect(
            lambda: self.controller.save_current_item(self.view)
        )
        self.view.navigate_requested.connect(
            lambda index: self.controller.navigate_to(self.view, index)
        )
        self.view.add_requested.connect(
            lambda: self.controller.add_item(self.view)
        )
        self.view.delete_requested.connect(
            lambda index: self.controller.delete_item(self.view, index)
        )
        self.view.tariff_lookup_requested.connect(
            lambda code: self.controller.on_tariff_changed(self.view, code)
        )
        self.view.knowledge_base_update_requested.connect(
            lambda code: self.controller.update_knowledge_base(self.view, code)
        )
        self.view.pe_documents_changed.connect(
            lambda: self.controller.sync_pe_docs_to_header(self.view)
        )
        self.view.import_xml_requested.connect(
            lambda path: self.controller.import_xml(self.view, path)
        )
        self.view.save_declaration_requested.connect(
            lambda path: self.controller.save_declaration(self.view, path)
        )
        self.view.open_declaration_requested.connect(
            lambda path: self.controller.load_declaration(self.view, path)
        )
        self.view.suggest_tariff_requested.connect(self._prepare_tariff_suggestions)
        self.view.tariff_suggestion_accepted.connect(
            lambda result: self.controller.accept_tariff_suggestion(
                self.view, result
            )
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)

        # FORCE: osiguraj da se view expanduje
        from PySide6.QtWidgets import QSizePolicy
        self.view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def reload_data(self):
        """Delegira reload_data() prema NaimenovanjaView."""
        self.view.reload_data()

    def _sync_header_packages(self):
        """Delegira _sync_header_packages() prema NaimenovanjaView."""
        self.view._sync_header_packages()

    def _prepare_tariff_suggestions(self):
        logger.warning("🔍 TAB: signal primljen")
        logger.warning("🔍 TAB: controller=%s view=%s", type(self.controller).__name__, type(self.view).__name__)
        logger.warning("🔍 TAB: pozivam controller.prepare_tariff_suggestions...")
        mappings = self.controller.prepare_tariff_suggestions(self.view)
        logger.warning("🔍 TAB: controller vratio %s mappings", len(mappings) if mappings else 0)
        if not mappings:
            logger.warning("🔍 TAB: nema mappings, izlazim")
            return
        item = self.view.draft.items[self.view.current_item_index]
        self.view._show_tariff_suggestion_dialog(mappings, item)

    def _reload_header(self):
        main_window = self.window()
        tab = getattr(main_window, "zaglavlje_tab", None)
        if tab and hasattr(tab, "reload_data"):
            tab.reload_data()

    def _save_header(self):
        main_window = self.window()
        tab = getattr(main_window, "zaglavlje_tab", None)
        if tab and hasattr(tab, "save_to_draft"):
            tab.save_to_draft()

    def _replace_draft(self, loaded):
        main_window = self.window()
        main_window._replace_draft_contents(loaded)
        main_window._reload_all_tabs_from_draft()
