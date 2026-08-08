import logging
logger = logging.getLogger(__name__)
"""
Database-integrated widgets for Deklarant Pro GUI.

Provides autocomplete and database lookup functionality for:
- Tariff codes (zvanicna_tarifa)
- Goods names (znanje_tarifa)
- Package codes (pakovanja)
- Partners (partneri)
"""

from typing import List, Optional, Callable
from PySide6.QtWidgets import (
    QLineEdit, QComboBox, QCompleter, QDialog, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QAbstractItemView, QHeaderView
)
from PySide6.QtCore import Qt, Signal, QStringListModel, QTimer
from PySide6.QtGui import QStandardItemModel, QStandardItem

# Import database functions
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from database import db


class TariffCodeEdit(QLineEdit):
    """
    QLineEdit sa autocomplete za tarifne brojeve.

    Features:
    - Real-time autocomplete iz zvanicna_tarifa
    - Automatsko popunjavanje opisa
    - Debounced database lookup
    """

    description_loaded = Signal(str)  # Emituje opis kada se pronađe tarifa

    def __init__(self, parent=None, description_callback: Optional[Callable[[str], None]] = None):
        super().__init__(parent)
        self.description_callback = description_callback
        self.cache = {}  # Cache za tariff descriptions

        # Setup debounced lookup timer
        self.lookup_timer = QTimer()
        self.lookup_timer.setSingleShot(True)
        self.lookup_timer.timeout.connect(self._perform_lookup)

        # Connect text changed signal
        self.textChanged.connect(self._on_text_changed)

        # Setup completer (lazy load)
        self.completer_model = None
        self._completer_loaded = False

    def _on_text_changed(self, text: str):
        """Handle text changes with debouncing."""
        # Cancel previous timer
        self.lookup_timer.stop()

        if len(text.strip()) >= 4:  # Minimum 4 characters
            # Start new timer (400ms delay)
            self.lookup_timer.property("pending_code", text.strip())
            self.lookup_timer.start(400)

    def _perform_lookup(self):
        """Perform tariff code lookup."""
        code = self.lookup_timer.property("pending_code")
        if not code:
            return

        # Check cache first
        if code in self.cache:
            desc = self.cache[code]
            self._emit_description(desc)
            return

        # Database lookup
        try:
            result = db.get_tarifa_opis(code)
            if result:
                desc = result['opis']
                self.cache[code] = desc
                self._emit_description(desc)
        except Exception as e:
            logger.warning(f"  ⚠️  Tariff lookup error: {e}")

    def _emit_description(self, description: str):
        """Emit description signal and call callback."""
        self.description_loaded.emit(description)
        if self.description_callback:
            self.description_callback(description)

    def load_completer(self):
        """Lazy load completer with tariff codes."""
        if self._completer_loaded:
            return

        try:
            # Load top tariff codes for autocomplete
            results = db.search_tarife_by_text("", limit=1000)  # Top 1000
            codes = [r['tarifni_kod'] for r in results]

            # Setup completer
            completer = QCompleter(codes, self)
            completer.setCaseSensitivity(Qt.CaseInsensitive)
            completer.setFilterMode(Qt.MatchContains)
            self.setCompleter(completer)

            self._completer_loaded = True
            logger.info(f"  ✅ Tariff completer loaded with {len(codes)} codes")
        except Exception as e:
            logger.warning(f"  ⚠️  Error loading tariff completer: {e}")


class PackageCodeComboBox(QComboBox):
    """
    QComboBox sa šiframa pakovanja iz baze.

    Features:
    - Učitava sve šifre pakovanja iz catalogs.pakovanja
    - Format: "SIFRA - Opis"
    - Autocomplete search
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)

        # Make searchable
        self.setMaxVisibleItems(15)

        # Load package codes
        self._load_packages()

    def _load_packages(self):
        """Load package codes from database."""
        try:
            results = db.get_all_pakovanja(limit=500)

            # Add empty option
            self.addItem("-- Izaberi --", "")

            # Add packages
            for row in results:
                sifra = row['sifra']
                opis = row['opis']
                self.addItem(f"{sifra} - {opis}", sifra)

            logger.info(f"  ✅ Loaded {len(results)} package codes")
        except Exception as e:
            logger.warning(f"  ⚠️  Error loading package codes: {e}")

    def get_selected_code(self) -> str:
        """Get currently selected package code."""
        return self.currentData() or ""

    def set_code(self, code: str):
        """Set package code by value."""
        index = self.findData(code)
        if index >= 0:
            self.setCurrentIndex(index)


class GoodsNameEdit(QLineEdit):
    """
    QLineEdit sa autocomplete za nazive robe.

    Features:
    - Real-time autocomplete iz znanje_tarifa
    - Automatsko popunjavanje tarifnog broja
    """

    tariff_code_suggested = Signal(str)  # Emituje tarifni broj kada se odabere naziv

    def __init__(self, parent=None, tariff_callback: Optional[Callable[[str], None]] = None):
        super().__init__(parent)
        self.tariff_callback = tariff_callback

        # Setup completer
        self.completer_model = QStringListModel()
        completer = QCompleter(self.completer_model, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.activated.connect(self._on_completion_activated)
        self.setCompleter(completer)

        # Search timer (debounced)
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._perform_search)

        self.textChanged.connect(self._on_text_changed)

    def _on_text_changed(self, text: str):
        """Handle text changes with debounced search."""
        self.search_timer.stop()

        if len(text.strip()) >= 3:  # Minimum 3 characters
            self.search_timer.property("pending_query", text.strip())
            self.search_timer.start(300)

    def _perform_search(self):
        """Perform goods name search."""
        query = self.search_timer.property("pending_query")
        if not query:
            return

        try:
            results = db.search_nazivi_robe(query, limit=20)
            suggestions = [r['naziv_robe'] for r in results]
            self.completer_model.setStringList(suggestions)
        except Exception as e:
            logger.warning(f"  ⚠️  Goods name search error: {e}")

    def _on_completion_activated(self, text: str):
        """Handle completion selection - lookup tariff code."""
        try:
            results = db.search_nazivi_robe(text, limit=1)
            if results and len(results) > 0:
                tariff_code = results[0]['tarifni_kod']
                self.tariff_code_suggested.emit(tariff_code)
                if self.tariff_callback:
                    self.tariff_callback(tariff_code)
        except Exception as e:
            logger.warning(f"  ⚠️  Tariff lookup error: {e}")


class PartnerSearchDialog(QDialog):
    """
    Dialog za pretragu partnera iz baze.

    Features:
    - Search po nazivu ili JIB-u
    - Table sa rezultatima
    - Double-click ili Enter za selekciju
    - Mogućnost ograničavanja na tip partnera (izvoznik, uvoznik, svi)
    """

    partner_selected = Signal(dict)  # Emituje selektovanog partnera

    def __init__(self, parent=None, partner_type="all"):
        """
        Inicijalizacija dijaloga.

        Args:
            parent: Roditeljski widget
            partner_type: "all", "exporter", "consignee" - ograničava pretragu na tip partnera
        """
        super().__init__(parent)
        self.partner_type = partner_type
        titles = {
            "exporter": "Pretraga izvoznika",
            "consignee": "Pretraga uvoznika",
            "all": "Pretraga partnera",
        }
        self.setWindowTitle(titles.get(partner_type, titles["all"]))
        self.setMinimumSize(960, 560)
        self.resize(1100, 650)
        self.selected_partner = None

        self._setup_ui()
        self._load_all_partners()

    def _setup_ui(self):
        """Setup dialog UI."""
        layout = QVBoxLayout(self)

        # Search bar
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Pretraga:"))

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Unesite naziv ili JIB...")
        self.search_edit.textChanged.connect(self._on_search)
        search_layout.addWidget(self.search_edit)

        layout.addLayout(search_layout)

        # Results table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["JIB", "Naziv", "Adresa", "Grad", "Poštanski broj", "Država"])
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.setColumnWidth(3, 150)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.doubleClicked.connect(self._on_select)

        layout.addWidget(self.table)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        select_btn = QPushButton("Odaberi")
        select_btn.clicked.connect(self._on_select)
        button_layout.addWidget(select_btn)

        cancel_btn = QPushButton("Otkaži")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

    def _load_all_partners(self):
        """Load all partners initially."""
        self._perform_search("")

    def _on_search(self, query: str):
        """Handle search input."""
        self._perform_search(query)

    def _perform_search(self, query: str):
        """Execute partner search."""
        try:
            if query.strip():
                # Pretraga na osnovu tipa partnera
                if self.partner_type == "exporter":
                    results = db.search_izvoznike(query, limit=100)
                elif self.partner_type == "consignee":
                    results = db.search_uvoznike(query, limit=100)
                else:  # all
                    results = db.search_partnere(query, limit=100)
            else:
                # Load all if no query
                if self.partner_type == "exporter":
                    results = db.search_izvoznike("", limit=1000)
                elif self.partner_type == "consignee":
                    results = db.search_uvoznike("", limit=1000)
                else:  # all
                    results = db.search_partnere("", limit=1000)

            self._populate_table(results)
        except Exception as e:
            logger.warning(f"  ⚠️  Partner search error: {e}")
            import traceback
            traceback.print_exc()

    def _populate_table(self, results: List[dict]):
        """Populate table with results."""
        self.table.setRowCount(0)

        # Ažuriraj broj kolona i zaglavlja ako imamo više informacija
        if len(results) > 0 and 'grad' in results[0]:
            # Imamo dodatne kolone za adresu
            self.table.setColumnCount(6)
            self.table.setHorizontalHeaderLabels(["JIB", "Naziv", "Adresa", "Grad", "Poštanski broj", "Država"])
            for row_data in results:
                row = self.table.rowCount()
                self.table.insertRow(row)

                self.table.setItem(row, 0, QTableWidgetItem(row_data.get('jib', '')))
                self.table.setItem(row, 1, QTableWidgetItem(row_data.get('naziv', '')))
                self.table.setItem(row, 2, QTableWidgetItem(row_data.get('adresa', '')))
                self.table.setItem(row, 3, QTableWidgetItem(row_data.get('grad', '')))
                self.table.setItem(row, 4, QTableWidgetItem(row_data.get('postanski_broj', '')))
                self.table.setItem(row, 5, QTableWidgetItem(row_data.get('drzava', '')))

        else:
            # Standardna verzija sa tri kolone
            self.table.setColumnCount(3)
            self.table.setHorizontalHeaderLabels(["JIB", "Naziv", "Adresa"])
            for row_data in results:
                row = self.table.rowCount()
                self.table.insertRow(row)

                self.table.setItem(row, 0, QTableWidgetItem(row_data.get('jib', '')))
                self.table.setItem(row, 1, QTableWidgetItem(row_data.get('naziv', '')))
                self.table.setItem(row, 2, QTableWidgetItem(row_data.get('adresa', '')))

        self.table.setColumnHidden(0, self.partner_type == "exporter")
        for row in range(self.table.rowCount()):
            for column in range(self.table.columnCount()):
                item = self.table.item(row, column)
                if item and item.text():
                    item.setToolTip(item.text())

    def _on_select(self):
        """Handle partner selection."""
        current_row = self.table.currentRow()
        if current_row < 0:
            return

        # Safely get item text, checking if item exists
        def get_item_text(row, col):
            item = self.table.item(row, col)
            return item.text() if item else ''

        # Get column count to handle both 3-column and 6-column layouts
        col_count = self.table.columnCount()

        self.selected_partner = {
            'jib': get_item_text(current_row, 0),
            'naziv': get_item_text(current_row, 1),
            'adresa': get_item_text(current_row, 2),
            'grad': get_item_text(current_row, 3) if col_count > 3 else '',
            'postanski_broj': get_item_text(current_row, 4) if col_count > 4 else '',
            'drzava': get_item_text(current_row, 5) if col_count > 5 else ''
        }

        self.partner_selected.emit(self.selected_partner)
        self.accept()

    def get_selected_partner(self) -> Optional[dict]:
        """Get selected partner data."""
        return self.selected_partner
