# gui/tabs/sifarnici_tab.py

from PySide6.QtWidgets import QWidget, QVBoxLayout
from typing import Optional, Callable

from core.draft import DeclarationDraft
from gui.tabs.sifarnici_view import SifarniciView


class SifarniciTab(QWidget):
    """Wrapper koji eksponuje SifarniciView prema MainWindow-u."""

    def __init__(
        self,
        draft: Optional[DeclarationDraft] = None,
        on_dirty: Optional[Callable] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.view = SifarniciView(draft=draft, on_dirty=on_dirty)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
