# gui/tabs/naimenovanja_tab.py

from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Signal
from typing import Optional, Callable

from core.draft import DeclarationDraft
from gui.tabs.naimenovanja_view import NaimenovanjaView
from gui.tabs.naimenovanja_controller import NaimenovanjaController
from services.naimenovanja.naimenovanja_service import NaimenovanjaService


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
