# gui/tabs/zaglavlje_tab_refactored.py

"""
Refaktorisani ZaglavljeTab wrapper koji koristi refaktorisane Service i Controller klase.
Zadržava backward compatibility sa starim API-jem.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Signal
from typing import Optional, Callable

from core.draft.draft import DeclarationDraft
from gui.tabs.zaglavlje_view import ZaglavljeView
from gui.tabs.zaglavlje_controller import ZaglavljeController
from services.zaglavlje_service import ZaglavljeService


class ZaglavljeTabRefactored(QWidget):
    """
    Refaktorisani ZaglavljeTab koji koristi refaktorisane Service i Controller.
    
    Zadržava backward compatibility sa starim API-jem:
    - draft parametar
    - on_dirty callback
    - load_from_draft() i save_to_draft() metode
    - data_changed signal
    """
    
    # Signal koji MainWindow očekuje
    data_changed = Signal()
    
    def __init__(
        self, 
        draft: Optional[DeclarationDraft] = None,
        on_dirty: Optional[Callable] = None,
        parent: Optional[QWidget] = None
    ):
        """
        Inicijalizacija ZaglavljeTab widgeta.
        
        Args:
            draft: Početni draft (opciono)
            on_dirty: Callback funkcija koja se poziva kada se podaci promijene
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Sačuvaj stari API parametre za backward compatibility
        self.draft = draft if draft else DeclarationDraft()
        self.on_dirty = on_dirty
        
        # Inicijalizuj 3-layer arhitekturu
        self._init_layers()
        
        # Setup UI
        self._setup_ui()
        
        # Poveži signale
        self._connect_signals()
        
        # Učitaj draft ako je dostupan
        if self.draft:
            self.load_from_draft(self.draft)
    
    def _init_layers(self):
        """Inicijalizuj sve layer-e 3-layer arhitekture."""
        # 1. Service layer (business logic)
        self.service = ZaglavljeService()

        # 2. View layer (UI)
        self.view = ZaglavljeView()

        # 3. Controller layer (orchestration)
        self.controller = ZaglavljeController(
            view=self.view,
            service=self.service,
            save_draft_fn=self._save_draft_callback,
            get_draft_fn=self._get_draft_callback
        )

    def _setup_ui(self):
        """Setup layouta — view zauzima cijeli prostor."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.view)
    
    def _connect_signals(self):
        """Poveži signale između layer-a."""
        # Kada se podaci promijene u view-u, emituj data_changed signal
        self.view.data_changed.connect(self._on_data_changed)
        
        # Kada controller prijavi grešku, prikaži je
        # (Controller već prikazuje greške kroz view)
        pass
    
    def _on_data_changed(self):
        """Poziva se kada se podaci promijene u view-u."""
        # Emituj signal koji MainWindow očekuje
        self.data_changed.emit()
        
        # Pozovi on_dirty callback ako postoji
        if self.on_dirty and callable(self.on_dirty):
            self.on_dirty()
    
    def _save_draft_callback(self, draft: DeclarationDraft) -> None:
        """
        Callback koji controller poziva kada treba sačuvati draft.
        Ovo je potrebno jer controller ne bi trebao direktno mijenjati
        draft property.
        """
        self.draft = draft
    
    def _get_draft_callback(self) -> DeclarationDraft:
        """
        Callback koji controller poziva kada treba dobiti trenutni draft.
        """
        return self.draft if self.draft else DeclarationDraft()
    
    # Public API koje MainWindow očekuje (backward compatibility)
    
    def load_from_draft(self, draft: DeclarationDraft):
        """Učitaj podatke iz draft-a u view."""
        self.draft = draft
        data = self.service.load_from_draft(draft)
        self.view.set_data(data)

    def save_to_draft(self) -> DeclarationDraft:
        """Sačuvaj podatke iz view-a u draft."""
        data = self.view.get_data()
        self.draft = self.service.save_to_draft(self.draft, data)
        return self.draft

    def clear_form(self):
        """Očisti formu."""
        self.view.clear_data()
    
    # Signal handlers
    
    def _on_data_changed_in_view(self):
        """Poziva se kada se podaci promijene u view-u."""
        self.data_changed.emit()
        if self.on_dirty and callable(self.on_dirty):
            self.on_dirty()
    
    def _on_save_requested(self):
        """Poziva se kada korisnik klikne Save u view-u."""
        if self.controller:
            saved_draft = self.controller.save_data()
            if saved_draft:
                self.draft = saved_draft
    
    def _on_validation_error(self, errors: list):
        """Prikazuje greške validacije."""
        # Controller će već prikazati greške kroz view
        pass
    
    def _on_save_success(self, message: str):
        """Prikazuje poruku o uspješnom čuvanju."""
        # Controller će prikazati poruku kroz view
        pass
    
    def _on_error(self, error: Exception, context: str = ""):
        """Rukovanje greškama."""
        # Controller će prikazati grešku kroz view
        pass
    
    # Property za backward compatibility
    @property
    def is_dirty(self) -> bool:
        """
        Vraća True ako postoje nesačuvane promjene.
        Ovo je deo starog API-ja.
        """
        # Ovdje bi trebalo implementirati logiku za provjeru
        # da li postoje nesačuvane promjene
        return False  # Za sada uvijek vraća False
    
    def is_valid(self) -> bool:
        """
        Provjeri da li su svi podaci ispravni.
        Dio starog API-ja.
        """
        if self.controller:
            return self.controller.is_valid()
        return True
    
    def get_validation_errors(self) -> list:
        """
        Vrati listu grešaka u validaciji.
        Dio starog API-ja.
        """
        if self.controller:
            return self.controller.get_validation_errors()
        return []
    
    def refresh(self):
        """
        Osvježi prikaz podataka.
        Dio starog API-ja.
        """
        if self.draft and self.controller:
            self.controller.load_data(self.draft)
    
    def reset(self):
        """
        Resetuj formu na početno stanje.
        Dio starog API-ja.
        """
        if self.controller:
            self.controller.clear_form()
        if self.draft:
            self.draft = DeclarationDraft()
    
    # Convenience metode za testiranje
    
    def get_controller(self):
        """Vrati controller za testiranje."""
        return self.controller
    
    def get_view(self):
        """Vrati view za testiranje."""
        return self.view
    
    def get_service(self):
        """Vrati service za testiranje."""
        return self.service