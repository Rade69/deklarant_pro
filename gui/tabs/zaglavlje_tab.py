# gui/tabs/zaglavlje_tab.py

"""
ZaglavljeTab - Wrapper around 3-layer architecture.

Ovaj fajl služi kao adapter između starog API-ja (koji MainWindow očekuje)
i novih layer-a (ZaglavljeView, ZaglavljeController, ZaglavljeService).

Backward compatible - MainWindow ne mora mijenjati ni liniju koda!
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Signal
from typing import Optional, Callable

from core.draft.draft import DeclarationDraft
from gui.tabs.zaglavlje_view import ZaglavljeView
from gui.tabs.zaglavlje_controller import ZaglavljeController
from services.zaglavlje_service import ZaglavljeService


class ZaglavljeTab(QWidget):
    """
    Wrapper koji integriše 3-layer arhitekturu.
    
    Zadržava stari API (draft, on_dirty) ali interno koristi
    nove layer-e (View/Controller/Service).
    
    Primjer korišćenja (isti kao prije):
        tab = ZaglavljeTab(draft=draft, on_dirty=self._on_dirty)
        tab.load_from_draft(draft)
        tab.save_to_draft()
    """
    
    # ============================================================
    # SIGNALS (MainWindow očekuje ove signale)
    # ============================================================
    
    data_changed = Signal()
    """Signal koji se emituje kada se podaci promijene."""
    
    # ============================================================
    # INIT (stari API - backward compatible)
    # ============================================================
    
    def __init__(
        self, 
        draft: Optional[DeclarationDraft] = None,
        on_dirty: Optional[Callable] = None,
        parent: Optional[QWidget] = None
    ):
        """
        Inicijalizacija taba - stari API.
        
        Args:
            draft: DeclarationDraft objekat
            on_dirty: Callback za dirty flag
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Zadrži reference na stari API
        self.draft = draft if draft else DeclarationDraft()
        self.on_dirty = on_dirty
        
        # Kreiraj nove layer-e
        self._setup_layers()
        
        # Setup UI layout
        self._setup_ui()
        
        # Povezivanje signala
        self._connect_signals()
        
        # Load initial data from draft ako postoji
        if self.draft:
            self.load_from_draft(self.draft)
    
    # ============================================================
    # LAYER SETUP
    # ============================================================
    
    def _setup_layers(self):
        """
        Kreiraj View/Controller/Service layer-e.
        
        Order matters:
        1. Service (business logic) - nema zavisnosti
        2. View (UI) - nema zavisnosti
        3. Controller (orchestration) - zavisi od View i Service
        """
        # Service layer (business logic)
        self.service = ZaglavljeService()
        
        # View layer (UI)
        self.view = ZaglavljeView()
        
        # Controller layer (orchestration) — prosljeđujemo draft callback-e
        self.controller = ZaglavljeController(
            self.view,
            self.service,
            save_draft_fn=self.save_to_draft,
            get_draft_fn=self.get_draft,
        )
    
    def _setup_ui(self):
        """Setup glavnog layout-a."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
    
    def _connect_signals(self):
        """
        Povezivanje signala između layer-a i wrapper-a.
        
        View data changes -> emit data_changed (MainWindow očekuje ovo)
        View data changes -> pozovi on_dirty callback
        """
        # View data changes -> emit data_changed (MainWindow očekuje ovo)
        self.view.data_changed.connect(self._on_data_changed)
        
        # View data changes -> pozovi on_dirty callback
        self.view.data_changed.connect(self._on_dirty_triggered)
    
    def _on_data_changed(self):
        """Handle data change event - emit signal koji MainWindow očekuje."""
        self.data_changed.emit()
    
    def _on_dirty_triggered(self):
        """Pozovi on_dirty callback ako postoji."""
        if self.on_dirty:
            self.on_dirty()
    
    # ============================================================
    # PUBLIC API - Metode koje MainWindow/FakturaTab pozivaju
    # ============================================================
    
    def load_from_draft(self, draft: DeclarationDraft):
        """
        Učitaj podatke iz Draft-a.
        
        Ovo je glavna metoda koju MainWindow i FakturaTab pozivaju!
        
        Workflow:
        1. Sačuvaj draft referencu
        2. Service konvertuje Draft → View data dict
        3. View popuni UI widgete podacima
        
        Args:
            draft: DeclarationDraft objekat
        """
        self.draft = draft
        
        # Delegiraj Service layer-u da konvertuje Draft → View data
        data = self.service.load_from_draft(draft)
        
        # Delegiraj View layer-u da popuni UI
        self.view.set_data(data)
    
    def save_to_draft(self) -> DeclarationDraft:
        """
        Sačuvaj podatke u Draft.
        
        Workflow:
        1. View ekstraktuje podatke iz UI widgeta
        2. Service konvertuje View data → Draft fields
        3. Return ažurirani Draft
        
        Returns:
            Ažurirani DeclarationDraft objekat
        """
        # Uzmi podatke iz View
        data = self.view.get_data()
        
        # Delegiraj Service layer-u da konvertuje View data → Draft
        self.draft = self.service.save_to_draft(self.draft, data)
        
        return self.draft
    
    def get_draft(self) -> DeclarationDraft:
        """
        Vrati trenutni Draft objekat.
        
        Returns:
            DeclarationDraft objekat
        """
        return self.draft
    
    def clear_form(self):
        """
        Očisti formu.
        
        Delegiraj View layer-u da očisti sve widgete.
        """
        self.view.clear_form()
    
    # ============================================================
    # HELPER METHODS (za kompatibilnost)
    # ============================================================
    
    def update(self):
        """
        Force update UI-a.
        
        MainWindow možda poziva ovo poslije load_from_draft.
        """
        self.view.update()
    
    def show(self):
        """
        Prikaži tab.
        
        Override za dodavanje custom logike pri pokazivanju.
        """
        super().show()
    
    def hide(self):
        """
        Sakrij tab.
        
        Override za dodavanje custom logike pri sakrivanju.
        """
        super().hide()
