# gui/tabs/faktura_tab.py

from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Signal
from typing import Optional, Callable

from core.draft import DeclarationDraft
from gui.tabs.faktura_view import FakturaView


class FakturaTab(QWidget):
    """Wrapper koji eksponuje FakturaView prema MainWindow-u."""

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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
