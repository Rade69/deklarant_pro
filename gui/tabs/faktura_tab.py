# gui/tabs/faktura_tab.py

from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Signal
from typing import Optional, Callable

from core.draft import DeclarationDraft
from gui.tabs.faktura_view import FakturaView
from gui.tabs.faktura_controller import FakturaController


class FakturaTab(QWidget):
    """Wrapper koji eksponuje FakturaView prema MainWindow-u.

    Faza 1 (Codex plan §8): composition root.
    """

    data_changed = Signal()

    def __init__(
        self,
        draft: DeclarationDraft,
        on_dirty: Optional[Callable] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.view = FakturaView(draft=draft, on_dirty=on_dirty)
        self.view.data_changed.connect(self.data_changed)

        # Composition root (Faza 1)
        self.controller = FakturaController(
            get_draft_fn=lambda: self.view.draft,
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
