# gui/tabs/sifarnici_tab.py
# Integrisani wrapper za SifarniciTab sa MVC patternom

from PySide6.QtWidgets import QWidget, QVBoxLayout
from typing import Optional, Callable

from core.draft import DeclarationDraft
from gui.tabs.sifarnici_view import SifarniciView
from gui.tabs.sifarnici_controller import SifarniciController
from services.sifarnici_service import SifarniciService


class SifarniciTab(QWidget):
    """Integrisani wrapper koji povezuje View, Controller i Service prema MVC patternu."""

    def __init__(
        self,
        draft: Optional[DeclarationDraft] = None,
        on_dirty: Optional[Callable] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        
        # Kreiraj view (originalni monolit koji radi sve sam)
        self.view = SifarniciView(draft=draft, on_dirty=on_dirty)
        
        # Controller i Service postoje ali originalni View ih ne koristi
        # Zadržavamo ih za backward compatibility
        self.service = SifarniciService()
        self.controller = SifarniciController(self.view, self.service)
        
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
