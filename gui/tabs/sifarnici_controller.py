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

    # Mapiranje kategorija na tabele
    CATEGORY_CONFIG = {
        "Pošiljaoci": {
            "columns": ["JIB", "Naziv", "Adresa", "Grad", "Zemlja"],
            "table": "catalogs.izvoznici",
        },
        "Uvoznici": {
            "columns": ["JIB", "Naziv", "Adresa", "Grad", "Zemlja"],
            "table": "catalogs.uvoznici",
        },
        "Carinske tarife": {
            "columns": ["Tarifni kod", "Naziv robe"],
            "table": "catalogs.zvanicna_tarifa",
        },
        "Carinarnice": {
            "columns": ["Šifra", "Naziv"],
            "table": "catalogs.carinske_ispostave",
            "hierarchical": True,
        },
        "Carinski postupci": {
            "columns": ["Šifra", "Carinski postupci", "Vrsta", "Oznaka"],
            "table": "catalogs.carinski_postupci",
        },
        "Zemlje": {
            "columns": ["Šifra", "Naziv"],
            "table": "catalogs.zemlje",
        },
        "Deklaranti": {
            "columns": ["Kod", "Naziv", "Licenca", "Kontakt"],
            "table": "catalogs.deklaranti",
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
            table_name = config.get("table", "")
            
            if not table_name:
                return

            # Load from service
            data = self.service.load_category_data(table_name)
            self.current_data = data

            # Display in table
            self._display_data(data)

        except Exception as e:
            self.handle_error(e, "load_data")

    def _display_data(self, data: List[Dict[str, Any]]):
        """Display data in table."""
        if not self.view.table:
            return

        self.view.table.setRowCount(0)
        self.view.table.setRowCount(len(data))

        for row, item in enumerate(data):
            for col, (key, value) in enumerate(item.items()):
                table_item = QTableWidgetItem(str(value or ""))
                self.view.table.setItem(row, col, table_item)

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

            reply = QMessageBox.question(
                self.view,
                "Potvrda brisanja",
                f"Da li ste sigurni da želite obrisati red {row + 1}?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )

            if reply == QMessageBox.Yes:
                self._delete_row(row)
                self.handle_success(f"Red {row + 1} obrisan")
        except Exception as e:
            self.handle_error(e, "obrisi")

    def _on_snimi(self):
        """Snimi record."""
        try:
            data = self.view.get_data()
            
            if self.is_editing and self.current_row_index >= 0:
                # Update existing
                self._update_row(self.current_row_index, data)
            else:
                # Insert new
                self._insert_row(data)

            self.view.set_readonly_mode(readonly=True)
            self.is_editing = False
            self._load_data()  # Reload table
            self.handle_success("Podaci sačuvani")
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

        search_text = self.view.search_input.text()
        
        if not search_text:
            self._display_data(self.current_data)
            return

        # Filter data
        filtered = []
        for item in self.current_data:
            for value in item.values():
                if search_text.lower() in str(value).lower():
                    filtered.append(item)
                    break

        self._display_data(filtered)

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

    def _delete_row(self, row: int):
        """Delete row from data."""
        if 0 <= row < len(self.current_data):
            del self.current_data[row]
            self._display_data(self.current_data)

    def _update_row(self, row: int, data: Dict[str, Any]):
        """Update row with new data."""
        if 0 <= row < len(self.current_data):
            self.current_data[row].update(data)

    def _insert_row(self, data: Dict[str, Any]):
        """Insert new row."""
        self.current_data.append(data)

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
