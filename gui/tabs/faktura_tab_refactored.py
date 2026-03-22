# gui/tabs/faktura_tab_refactored.py

"""
Refaktorisani FakturaTab wrapper koji koristi refaktorisane Service i Controller klase.
Zadržava backward compatibility sa starim API-jem.

Napomena: FakturaView trenutno ne nasljeđuje BaseTabView pa controller
skeleton postoji ali signali nisu spojeni. Spajanje će uslijediti kada
se View refaktoriše da koristi BaseTabView.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Signal
from typing import Optional, Callable

from core.draft.draft import DeclarationDraft
from gui.tabs.faktura_view import FakturaView
from gui.tabs.faktura_controller_refactored import FakturaController
from services.faktura_service_refactored import FakturaService


class FakturaTabRefactored(QWidget):
    """
    Refaktorisani FakturaTab koji koristi refaktorisane Service i Controller.

    Zadržava backward compatibility sa starim API-jem:
    - draft parametar
    - on_dirty callback
    - data_changed signal
    """

    data_changed = Signal()

    def __init__(
        self,
        draft: Optional[DeclarationDraft] = None,
        on_dirty: Optional[Callable] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        self.draft = draft if draft else DeclarationDraft()
        self.on_dirty = on_dirty

        # 1. Service layer (refaktorisani)
        self.service = FakturaService()

        # 2. View layer (original, nepromijenjen)
        self.view = FakturaView(draft=self.draft, on_dirty=on_dirty)

        # 3. Controller layer (skeleton - signali prazni dok View ne dobije BaseTabView)
        self.controller = FakturaController(view=self.view, service=self.service)

        # Proslijedi data_changed signal iz view-a
        self.view.data_changed.connect(self._on_data_changed)

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.view)
        self.setLayout(layout)

    def _on_data_changed(self):
        """Proslijedi data_changed signal i pozovi on_dirty callback."""
        self.data_changed.emit()
        if self.on_dirty and callable(self.on_dirty):
            self.on_dirty()

    # Convenience metode za testiranje
    def get_controller(self):
        return self.controller

    def get_view(self):
        return self.view

    def get_service(self):
        return self.service
