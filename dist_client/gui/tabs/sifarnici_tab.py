# gui/tabs/sifarnici_tab.py
# Integrisani wrapper za SifarniciTab

from PySide6.QtWidgets import QWidget, QVBoxLayout
from typing import Optional, Callable

from core.draft import DeclarationDraft
from gui.tabs.sifarnici_view import SifarniciView


class SifarniciTab(QWidget):
    """Wrapper koji izlaže SifarniciView kroz stabilan interfejs (get_view/set_draft/refresh)."""

    def __init__(
        self,
        draft: Optional[DeclarationDraft] = None,
        on_dirty: Optional[Callable] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        # View je monolit koji sam upravlja UI-jem, business logikom i DB pristupom
        # (interno pravi svoj SifarniciService). SifarniciController je uklonjen 2026-08-04
        # kao mrtav kod — _connect_signals() je bio trajno isključen, nijedan View signal
        # nikad nije bio povezan sa njim. Vidi agent_reports/2026-08-04_sifarnici-audit.md
        self.view = SifarniciView(draft=draft, on_dirty=on_dirty)

        # Setup layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        
        logger.info("SifarniciTab uspešno inicijalizovan sa originalnim View-om")

    def get_view(self):
        """Vrati view komponentu (za backward compatibility)."""
        return self.view

    def set_draft(self, draft: DeclarationDraft):
        """Postavi draft za view."""
        self.view.draft = draft

    def refresh(self):
        """Osveži prikaz (originalni View radi sve sam)."""
        if self.view.current_category:
            # Originalni View ima svoju _load_category metodu
            self.view._load_category(self.view.current_category)


# Import logger-a
import logging
logger = logging.getLogger(__name__)
