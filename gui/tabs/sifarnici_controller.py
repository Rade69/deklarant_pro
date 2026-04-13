# gui/tabs/sifarnici_controller.py

"""
Sifarnici Controller - Orchestration Layer (Original Design)

Koordinacija između View i Service layer-a.
Originalni dizajn sa categories_list umjesto tab_widget.

Odgovornosti:
- Event handling (category selection, CRUD, search)
- Orchestration (View ↔ Service communication)
- Error handling i poruke korisniku
- State management
"""

from typing import Optional, List, Dict, Any
from PySide6.QtCore import Qt
from gui.tabs.sifarnici_view import SifarniciView
from services.sifarnici_service import SifarniciService
from core.draft.draft import DeclarationDraft


class SifarniciController:
    """
    Controller layer za Sifarnici tab - Original Design!

    Odgovornosti:
    - Povezivanje View signala sa handler-ima
    - Orchestration CRUD operacija
    - Category selection
    - Error handling

    NEMA:
    - Direktne UI manipulacije
    - Business logike
    """

    # Mapiranje kategorija na tabele i service metode
    CATEGORY_CONFIG = {
        "Carinske tarife": {
            "columns": ["Tarifni kod", "Naziv robe", "Opis", "PDV", "Uvoz", "Akciza"],
            "table": "catalogs.tarifa_2026",
            "service_method": "load_trgovacki_nazivi_data",
            "add_method": "add_trgovacki_naziv",
            "delete_method": "delete_trgovacki_naziv",
            "validate_method": "validate_trgovacki_naziv_data",
        },
        "Pošiljaoci": {
            "columns": ["JIB", "Naziv", "Adresa", "Grad", "Zemlja", "Telefon", "Email"],
            "table": "catalogs.izvoznici",
            "service_method": "load_posiljaoci_data",
            "add_method": "add_posiljalac",
            "delete_method": "delete_posiljalac",
            "validate_method": "validate_posiljalac_data",
        },
        "Uvoznici": {
            "columns": ["JIB", "Naziv", "Adresa", "Grad", "Zemlja", "Telefon", "Email"],
            "table": "catalogs.uvoznici",
            "service_method": "load_uvoznici_data",
            "add_method": "add_uvoznik",
            "delete_method": "delete_uvoznik",
            "validate_method": "validate_uvoznik_data",
        },
        "Deklaranti": {
            "columns": ["JIB", "Naziv", "Adresa", "Grad", "Zemlja", "Telefon", "Email"],
            "table": "catalogs.deklaranti",
            "service_method": "load_deklaranti_data",
            "add_method": "add_deklarant",
            "delete_method": "delete_deklarant",
            "validate_method": "validate_deklarant_data",
        },
        "Carinarnice": {
            "columns": ["Šifra", "Naziv"],
            "table": "catalogs.carinske_ispostave",
            "service_method": "load_carinarnice_data",
            "add_method": "add_carinarnica",
            "delete_method": "delete_carinarnica",
            "validate_method": "validate_carinarnica_data",
            "hierarchical": True,
        },
        "Carinski postupci": {
            "columns": ["Šifra", "Naziv"],
            "table": "catalogs.carinski_postupci",
            "service_method": "load_carinski_postupci_data",
            "add_method": "add_carinski_postupak",
            "delete_method": "delete_carinski_postupak",
            "validate_method": "validate_carinski_postupak_data",
        },
        "Zemlje": {
            "columns": ["Šifra", "Naziv"],
            "table": "catalogs.drzave",
            "service_method": "load_zemlje_data",
            "add_method": "add_zemlja",
            "delete_method": "delete_zemlja",
            "validate_method": "validate_zemlja_data",
        },
    }

    def __init__(self, view: SifarniciView, service: SifarniciService):
        """
        Inicijalizacija Controller-a.

        Args:
            view: SifarniciView instanca
            service: SifarniciService instanca
        """
        self.view = view
        self.service = service
        self.draft: Optional[DeclarationDraft] = None

        # Current state
        self.current_category: Optional[str] = None
        self.current_data: List[Dict[str, Any]] = []
        self.is_editing: bool = False
        self.current_row_index: int = -1

        # Connect signals
        self._connect_signals()

    def _connect_signals(self):
        """Povezivanje View signala sa handler metodama."""
        # Category selection
        if self.view.categories_list:
            self.view.categories_list.currentRowChanged.connect(self._on_category_changed)

        # CRUD operations
        if self.view.btn_novi:
            self.view.btn_novi.clicked.connect(self._on_novi)
        if self.view.btn_uredi:
            self.view.btn_uredi.clicked.connect(self._on_uredi)
        if self.view.btn_obrisi:
            self.view.btn_obrisi.clicked.connect(self._on_obrisi)
        if self.view.btn_snimi:
            self.view.btn_snimi.clicked.connect(self._on_snimi)

        # Search
        if self.view.search_input:
            self.view.search_input.returnPressed.connect(self._apply_search)

        # Table selection
        if self.view.table:
            self.view.table.itemSelectionChanged.connect(self._on_row_selected)
            self.view.table.itemDoubleClicked.connect(self._on_table_double_clicked)

        # Data changes
        self.view.data_changed.connect(self._on_data_changed)

    # ============================================================
    # EVENT HANDLERS
    # ============================================================

    def _on_category_changed(self, row: int):
        """Category changed u sidebar-u."""
        if row < 0 or not self.view.categories_list:
            return

        item = self.view.categories_list.item(row)
        category = item.data(Qt.UserRole) if item else None
        
        if category:
            self._load_category(category)

    def _load_category(self, category: str):
        """Load category data."""
        try:
            self.current_category = category
            self.view.set_title(category)

            # Clear form
            self.view.clear_form()

            # Setup table columns based on category
            config = self.CATEGORY_CONFIG.get(category, {})
            columns = config.get("columns", [])
            
            if columns and self.view.table:
                self.view.table.setColumnCount(len(columns))
                self.view.table.setHorizontalHeaderLabels(columns)

            # Load data
            self._load_data()

            # Update status
            self._update_status()

            self.handle_success(f"Učitano {category}")

        except Exception as e:
            self.handle_error(e, f"load_category_{category}")

    def _load_data(self):
        """Load data for current category."""
        if not self.current_category:
            return

        try:
            config = self.CATEGORY_CONFIG.get(self.current_category, {})
            service_method_name = config.get("service_method", "")
            
            if not service_method_name:
                return

            # Get search query
            search_query = ""
            if self.view.search_input:
                search_query = self.view.search_input.text().strip()

            # Call appropriate service method
            service_method = getattr(self.service, service_method_name, None)
            if not service_method:
                self.handle_error(Exception(f"Service method {service_method_name} not found"), "load_data")
                return

            # Load data with optional search
            if search_query:
                data = service_method(search_query)
            else:
                data = service_method()
                
            self.current_data = data

            # Display in table
            self._display_data(data)

        except Exception as e:
            self.handle_error(e, "load_data")

    def _display_data(self, data: List[Dict[str, Any]]):
        """Display data in table."""
        if not data:
            self.view.set_data({"items": [], "columns": []})
            return

        # Get columns from first item
        columns = list(data[0].keys()) if data else []
        
        # Format data for view
        formatted_data = {
            "items": data,
            "columns": columns
        }
        
        # Use view's set_data method
        self.view.set_data(formatted_data)
        self._update_status()

    def _on_novi(self):
        """Novi record."""
        try:
            self.view.clear_form()
            self.view.set_readonly_mode(readonly=False)
            self.is_editing = False
            self.current_row_index = -1
            self.handle_success("Unesite podatke za novi zapis")
        except Exception as e:
            self.handle_error(e, "novi")

    def _on_uredi(self):
        """Uredi record."""
        try:
            row = self._get_selected_row()
            if row < 0:
                self.view.show_warning("Odaberite red za uređivanje")
                return

            self.current_row_index = row
            self._load_row_to_form(row)
            self.view.set_readonly_mode(readonly=False)
            self.is_editing = True
            self.handle_success(f"Uređivanje reda {row + 1}")
        except Exception as e:
            self.handle_error(e, "uredi")

    def _on_obrisi(self):
        """Obriši record."""
        from PySide6.QtWidgets import QMessageBox

        try:
            row = self._get_selected_row()
            if row < 0:
                self.view.show_warning("Odaberite red za brisanje")
                return

            if not self.current_category:
                self.view.show_warning("Odaberite kategoriju")
                return

            # Get the record to delete
            if row >= len(self.current_data):
                self.view.show_warning("Nevažeći red")
                return

            record = self.current_data[row]
            config = self.CATEGORY_CONFIG.get(self.current_category, {})
            
            # Get identifier (JIB for companies, sifra for others, tarifni_kod for trade names)
            identifier = None
            if "jib" in record:
                identifier = record["jib"]
            elif "sifra" in record:
                identifier = record["sifra"]
            elif "tarifni_kod" in record:
                identifier = record["tarifni_kod"]
            else:
                self.view.show_error("Nije moguće identifikovati zapis za brisanje")
                return

            # Confirm deletion
            reply = QMessageBox.question(
                self.view,
                "Potvrda brisanja",
                f"Da li ste sigurni da želite obrisati zapis '{identifier}'?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )

            if reply == QMessageBox.Yes:
                # Delete from database
                delete_method_name = config.get("delete_method", "")
                if not delete_method_name:
                    self.handle_error(Exception("Delete method not configured"), "obrisi")
                    return

                delete_method = getattr(self.service, delete_method_name, None)
                if not delete_method:
                    self.handle_error(Exception(f"Service method {delete_method_name} not found"), "obrisi")
                    return

                success = delete_method(identifier)
                if success:
                    self._load_data()  # Reload table
                    self.handle_success(f"Zapis '{identifier}' obrisan")
                else:
                    self.view.show_error("Greška pri brisanju zapisa")
                    
        except Exception as e:
            self.handle_error(e, "obrisi")

    def _on_snimi(self):
        """Snimi record."""
        try:
            if not self.current_category:
                self.view.show_warning("Odaberite kategoriju")
                return

            data = self.view.get_data()
            config = self.CATEGORY_CONFIG.get(self.current_category, {})
            
            # Validate data
            validate_method_name = config.get("validate_method", "")
            if validate_method_name:
                validate_method = getattr(self.service, validate_method_name, None)
                if validate_method:
                    errors = validate_method(data) if "data" in validate_method.__code__.co_varnames else validate_method(**data)
                    if errors:
                        self.view.show_warning("\n".join(errors))
                        return

            # Save to database
            add_method_name = config.get("add_method", "")
            if not add_method_name:
                self.handle_error(Exception("Add method not configured"), "snimi")
                return

            add_method = getattr(self.service, add_method_name, None)
            if not add_method:
                self.handle_error(Exception(f"Service method {add_method_name} not found"), "snimi")
                return

            success = add_method(data)
            if success:
                self.view.set_readonly_mode(readonly=True)
                self.is_editing = False
                self._load_data()  # Reload table
                self.handle_success("Podaci sačuvani")
            else:
                self.view.show_error("Greška pri čuvanju podataka")
                
        except Exception as e:
            self.handle_error(e, "snimi")

    def _on_row_selected(self):
        """Row selected in table."""
        row = self._get_selected_row()
        if row >= 0:
            if self.view.btn_uredi:
                self.view.btn_uredi.setEnabled(True)
            if self.view.btn_obrisi:
                self.view.btn_obrisi.setEnabled(True)

    def _on_table_double_clicked(self, row: int, column: int):
        """Table row double-clicked."""
        self.current_row_index = row
        self._on_uredi()

    def _apply_search(self):
        """Apply search filter."""
        if not self.view.search_input:
            return

        search_text = self.view.search_input.text().strip()
        
        if not search_text:
            # Reload without search
            self._load_data()
            return

        # Use service method with search
        self._load_data()  # This will use the search query from search_input

    def _on_data_changed(self):
        """Data changed."""
        pass

    # ============================================================
    # PUBLIC METHODS
    # ============================================================

    def load_data(self, draft: DeclarationDraft):
        """Load data from draft (not used for Sifarnici)."""
        self.draft = draft
        # Sifarnici loads from database, not draft
        if self.view.categories_list and self.view.categories_list.count() > 0:
            self.view.categories_list.setCurrentRow(0)

    def save_data(self) -> Optional[DeclarationDraft]:
        """Save data."""
        return self.draft

    def handle_error(self, error: Exception, context: str):
        """Handle error."""
        msg = f"Greška ({context}): {str(error)}"
        self.view.show_error(msg)

    def handle_success(self, msg: str):
        """Handle success."""
        pass  # Don't show success messages for every action

    # ============================================================
    # PRIVATE HELPERS
    # ============================================================

    def _get_selected_row(self) -> int:
        """Get selected row index."""
        if not self.view.table:
            return -1

        selected = self.view.table.selectedItems()
        return selected[0].row() if selected else -1

    def _load_row_to_form(self, row: int):
        """Load row data to form."""
        if not self.view.table or not self.current_category:
            return

        data = {}
        config = self.CATEGORY_CONFIG.get(self.current_category, {})
        columns = config.get("columns", [])

        for col, field_name in enumerate(columns):
            item = self.view.table.item(row, col)
            if item:
                data[field_name.lower()] = item.text()

        self.view.set_data(data)

    # Old CRUD methods removed - now handled by service layer

    def _update_status(self):
        """Update status bar."""
        if not self.view.table:
            return

        count = self.view.table.rowCount()
        self.view.update_totals(count, count)
        self.view.update_position(1 if count > 0 else 0, count)

    def _set_readonly_mode(self, readonly: bool):
        """Set readonly mode."""
        if self.view.btn_novi:
            self.view.btn_novi.setEnabled(readonly)
        if self.view.btn_uredi:
            self.view.btn_uredi.setEnabled(not readonly)
        if self.view.btn_obrisi:
            self.view.btn_obrisi.setEnabled(not readonly)
        if self.view.btn_snimi:
            self.view.btn_snimi.setEnabled(not readonly)
