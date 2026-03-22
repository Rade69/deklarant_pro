# gui/tabs/sifarnici_tab_refactored.py

"""
Refaktorisani SifarniciTab wrapper koji koristi refaktorisane Service i Controller klase.
Zadržava backward compatibility sa starim API-jem.

Napomena: SifarniciView trenutno ne nasljeđuje BaseTabView pa controller
skeleton postoji ali signali nisu spojeni. Spajanje će uslijediti kada
se View refaktoriše da koristi BaseTabView.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout
from typing import Optional, Callable

from core.draft.draft import DeclarationDraft
from gui.tabs.sifarnici_view import SifarniciView
from gui.tabs.sifarnici_controller_refactored import SifarniciController
from services.sifarnici_service_refactored import SifarniciService


class SifarniciTabRefactored(QWidget):
    """
    Refaktorisani SifarniciTab koji koristi refaktorisane Service i Controller.

    Zadržava backward compatibility sa starim API-jem:
    - draft parametar
    - on_dirty callback
    """

    def __init__(
        self,
        draft: Optional[DeclarationDraft] = None,
        on_dirty: Optional[Callable] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        self.draft = draft if draft else DeclarationDraft()
        self.on_dirty = on_dirty

        # 1. Service layer (sa cachingom)
        self.service = SifarniciService()

        # 2. View layer (original, nepromijenjen)
        self.view = SifarniciView(draft=self.draft, on_dirty=on_dirty)

        # 3. Controller layer (skeleton - signali prazni dok View ne dobije BaseTabView)
        self.controller = SifarniciController(view=self.view, service=self.service)

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.view)
        self.setLayout(layout)

    # Convenience metode za testiranje
    def get_controller(self):
        return self.controller

    def get_view(self):
        return self.view

    def get_service(self):
        return self.service
