"""
Deklarant Pro - Faktura Tab V2
Complete redesign based on HTML mockup with validation states
"""

import sys
import os
import re
import logging
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any
from datetime import datetime

# Logger setup
logger = logging.getLogger(__name__)

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QLabel,
    QFrame,
    QFileDialog,
    QMessageBox,
    QHeaderView,
    QAbstractItemView,
    QLineEdit,
    QProgressBar,
    QProgressDialog,
    QDialog,
)
from PySide6.QtCore import (
    Qt,
    Signal,
    QCoreApplication,
    QSignalBlocker,
    QSize,
    QTimer,
)
from PySide6.QtGui import QColor, QFont, QIcon

try:
    import qtawesome as qta

    QTAWESOME_AVAILABLE = True
    # Force output to stderr to ensure it's visible in GUI apps
    sys.stderr.write(f"✅ QtAwesome uspješno učitan (verzija: {qta.__version__})\n")
    sys.stderr.flush()
except ImportError as e:
    QTAWESOME_AVAILABLE = False
    sys.stderr.write(f"❌ QtAwesome import FAILED: {e}\n")
    sys.stderr.flush()

from gui.dialogs.eur1_quick_dialog import Eur1QuickDialog
from gui.dialogs.pe2_quick_dialog import PE2QuickDialog
from core.draft import DeclarationDraft, InvoiceLine, NaimenovanjeDraft
import uuid
from services.import_worker import ImportWorker
from services.validation_service import FakturaItemValidator, ValidationLevel
from services.declaration_assembly import DeclarationAssembly
from services.export_service import ExportService
from exporters.pdf_invoice_exporter import export_invoice_to_pdf
from exporters.pdf_faktura_pregled import export_faktura_pregled
from gui.delegates import ValidationDelegate
from gui.dialogs import AddItemDialog
from importers.import_result import ImportResult
from gui.tabs.base_view import BaseTabView
from gui.utils.safe_message_box import SafeMessageBox as QMessageBox
from gui.utils.safe_message_box import capture_window_geometry, restore_window_geometry_queued
from gui.utils.safe_message_box import exec_dialog_preserving_geometry, show_dialog_preserving_geometry
from services.faktura.weight_guards import (
    find_mass_total_mismatches,
    group_lines_by_invoice,
    is_suspicious_fallback,
    normalize_invoice_key,
    normalized_invoice_weights,
)
# Docs: docs/sections/window-geometry-modal-guard.md


class FakturaView(BaseTabView):
    """
    Faktura Tab V2 - Modern design with validation states.

    Features:
    - Import from PDF/Excel/XML
    - Add/Delete/Clear items
    - Validation with visual feedback (red/yellow/green)
    - Smart features (calculate masses, convert currency, auto-fill)
    - Real-time status bar with statistics
    - Create Naimenovanja integration
    """

    # data_changed naslijeđen iz BaseTabView

    # Signal za automatsku provjeru naimenovanja (sluša agent_tab controller)
    # Vidi: docs/decisions/002-tool-dispatcher-integration.md
    naimenovanja_created = Signal()

    # Regex za detekciju alfanumeričke šifre na početku naziva robe
    _RE_CODE_PREFIX = re.compile(r"^([A-Z0-9]{6,10})\s+(.+)$", re.IGNORECASE)

    # Cache za ikone i tamnjenje boja (dijele sve instance)
    _icon_cache: Dict[str, Any] = {}
    _darken_cache: Dict[str, str] = {}
    _CONFIDENCE_COLORS = {
        "HIGH": "#d4edda",
        "MEDIUM": "#fff3cd",
        "LOW": "#ffe5d0",
        "CONFLICT": "#f8d7da",
    }
    _CONFIDENCE_ICONS = {"HIGH": "✅", "MEDIUM": "📋", "LOW": "⚠️", "CONFLICT": "🚨"}

    def __init__(self, draft: DeclarationDraft, on_dirty: Optional[Callable] = None):
        super().__init__()
        self.draft = draft
        self.on_dirty = on_dirty
        self.import_worker: Optional[ImportWorker] = None
        self.validator = FakturaItemValidator()
        self.assembly = DeclarationAssembly()  # Assembly system
        self._agent_mode = False  # Agent mod: bez GUI dijaloga za povlastice

        # Initialize service layer
        from services.faktura.validation_cache import ValidationCache
        from services.faktura.weight_manager import WeightManager
        from services.faktura.auto_fill_service import AutoFillService
        from services.faktura.mass_calculator import MassCalculator
        from services.faktura.validation_service import ValidationService
        from services.faktura.error_handler import ErrorHandler
        from services.faktura.theme_manager import ThemeManager

        self.validation_cache = ValidationCache()
        self.weight_manager = WeightManager()
        self.auto_fill_service = AutoFillService()
        self.mass_calculator = MassCalculator()
        self.validation_service = ValidationService()
        self.error_handler = ErrorHandler(self)
        self.theme_manager = ThemeManager()

        # Track imported file counts
        self.imported_excel_count: int = 0
        self.imported_pdf_count: int = 0

        # Track last imported invoice name (for detecting pairs)
        self.last_invoice_name: Optional[str] = None

        # Track last import item count (for REPLACE logic)
        self.last_import_count: int = 0

        # Provjera konzistentnosti pošiljaoca/uvoznika između uvoza
        # Pamtimo ime iz prvog uvoza i poredimo pri svakom sljedećem
        self._expected_exporter: str = ""   # Pošiljalac iz prvog uvoza
        self._expected_importer: str = ""   # Uvoznik iz prvog uvoza

        # Debounce timer za validaciju i dirty signal nakon editovanja ćelije
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(200)  # 200ms
        self._debounce_timer.timeout.connect(self._flush_pending_validation)
        self._pending_validate_rows: set = set()

        # Set object name for styling
        self.setObjectName("FakturaTabV2")

        # Setup UI
        self._setup_ui()

        # Load data from draft
        self._load_data_from_draft()

        # Update status bar
        self._update_status_bar()

    def _setup_ui(self):
        """Setup the complete UI layout."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # Controls section
        controls_widget = self._create_controls_section()
        main_layout.addWidget(controls_widget)

        # Table section
        self.table = self._create_table()
        main_layout.addWidget(self.table, stretch=1)

        # Status bar section
        self.status_bar_widget = self._create_status_bar()
        main_layout.addWidget(self.status_bar_widget)

    def _create_controls_section(self) -> QWidget:
        """Create the controls section with header bar and colored buttons using GRID LAYOUT for perfect alignment."""
        from PySide6.QtWidgets import QGridLayout

        container = QWidget()
        container.setObjectName("controlsContainer")

        # Main GRID layout - header and toolbar share same columns!
        grid = QGridLayout(container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)
        grid.setColumnStretch(0, 1)  # Glavna lista
        grid.setColumnStretch(2, 3)  # Uvezi
        grid.setColumnStretch(4, 3)  # Uredi
        grid.setColumnStretch(6, 5)  # Izvezi
        grid.setColumnStretch(8, 3)  # Pametna pomoć

        # Create header and toolbar sections that share columns
        self._populate_grid_sections(grid)

        return container

    def _populate_grid_sections(self, grid):
        """Populate grid with header and toolbar sections sharing same columns for PERFECT alignment."""
        from PySide6.QtWidgets import QGridLayout

        # Sekcije: (naziv, pozadina, boja teksta) — unified_color_system v3.0 paleta
        sections = [
            ("Glavna lista", "#DAE8F2", "#2C5570"),  # plava familija
            ("Uvezi", "#EDE4F5", "#4A2E6B"),  # ljubičasta familija
            ("Uredi", "#F5EDD8", "#5C4A1E"),  # žuta familija
            ("Izvezi", "#D8F0EC", "#1E5A50"),  # teal familija
            ("Pametna pomoć", "#EDE4F5", "#4A2E6B"),  # ljubičasta (AI)
        ]

        col = 0
        for idx, (section_name, color, text_color) in enumerate(sections):
            # Create HEADER label for this section
            header_label = QPushButton(section_name)
            header_label.setEnabled(False)
            header_label.setFixedHeight(40)

            # Border radius for first/last
            if idx == 0:
                border_radius = "border-top-left-radius: 6px;"
            elif idx == len(sections) - 1:
                border_radius = "border-top-right-radius: 6px;"
            else:
                border_radius = ""

            header_label.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {color};
                    color: {text_color};
                    font-weight: bold;
                    font-size: 17px;
                    padding: 10px 6px;
                    border: none;
                    border-bottom: 2px solid {self._darken_color(color)};
                    {border_radius}
                }}
                QPushButton:disabled {{
                    background-color: {color};
                    color: {text_color};
                }}
            """
            )

            # Add header to row 0
            grid.addWidget(header_label, 0, col)

            # Create TOOLBAR section for this column
            toolbar_container = QWidget()
            toolbar_layout = QHBoxLayout(toolbar_container)
            toolbar_layout.setContentsMargins(8, 8, 8, 8)
            toolbar_layout.setSpacing(6)

            # Border radius for toolbar
            if idx == 0:
                t_border_radius = "border-bottom-left-radius: 6px;"
            elif idx == len(sections) - 1:
                t_border_radius = "border-bottom-right-radius: 6px;"
            else:
                t_border_radius = ""

            toolbar_container.setStyleSheet(
                f"""
                QWidget {{
                    {t_border_radius}
                }}
            """
            )

            # Populate toolbar content based on section
            self._populate_toolbar_section(toolbar_layout, idx)

            # Add toolbar to row 1
            grid.addWidget(toolbar_container, 1, col)

            # Add separator (spanning both rows)
            if idx < len(sections) - 1:
                col += 1
                sep = self._create_thick_separator()
                grid.addWidget(sep, 0, col, 2, 1)  # Span rows 0-1

            col += 1

    def _populate_toolbar_section(self, layout, section_idx):
        """Populate toolbar section content based on index."""
        if section_idx == 0:  # Glavna lista
            self.btn_load_master = self._create_button(
                "Učitaj glavnu listu",
                "Učitaj master listu proizvoda",
                object_name="btnUcitajListu",
                icon_name="fa5s.clipboard-list",
            )
            self.btn_load_master.clicked.connect(self._on_load_master_list)
            layout.addWidget(self.btn_load_master)

        elif section_idx == 1:  # Uvezi
            btn_pdf = self._create_button(
                "PDF",
                "Uvezi stavke iz PDF fakture",
                object_name="btnUveziPDF",
                compact=True,
                icon_name="fa5s.file-pdf",
            )
            btn_pdf.clicked.connect(self._on_import_pdf)
            layout.addWidget(btn_pdf)

            btn_excel = self._create_button(
                "Excel",
                "Uvezi stavke iz Excel fakture",
                object_name="btnUveziExcel",
                compact=True,
                icon_name="fa5s.file-excel",
            )
            btn_excel.clicked.connect(self._on_import_excel)
            layout.addWidget(btn_excel)

            btn_xml = self._create_button(
                "XML",
                "Uvezi stavke iz ASYCUDA XML-a",
                object_name="btnUveziXML",
                compact=True,
                icon_name="fa5s.file-alt",
            )
            btn_xml.clicked.connect(self._on_import_xml)
            layout.addWidget(btn_xml)

        elif section_idx == 2:  # Uredi
            self.btn_add = self._create_button(
                "Dodaj",
                "Dodaj novu stavku ručno",
                object_name="btnDodaj",
                icon_name="fa5s.plus",
            )
            self.btn_add.clicked.connect(self._on_add_item)
            layout.addWidget(self.btn_add)

            self.btn_delete = self._create_button(
                "Obriši",
                "Obriši odabranu stavku",
                object_name="btnObrisi",
                icon_name="fa5s.trash",
            )
            self.btn_delete.clicked.connect(self._on_delete_item)
            layout.addWidget(self.btn_delete)

            self.btn_clear = self._create_button(
                "Očisti sve",
                "Obriši sve stavke",
                object_name="btnOcistiSve",
                icon_name="fa5s.broom",
            )
            self.btn_clear.clicked.connect(self._on_clear_all)
            layout.addWidget(self.btn_clear)

        elif section_idx == 3:  # Izvezi
            self.btn_export_excel = self._create_button(
                "Excel",
                "Export u Excel (.xlsx)",
                object_name="btnExcel",
                compact=True,
                icon_name="fa5s.file-excel",
            )
            self.btn_export_excel.clicked.connect(self._on_export_excel)
            layout.addWidget(self.btn_export_excel)

            self.btn_export_pdf = self._create_button(
                "PDF",
                "Export u PDF — grupisanje po naimenovanjima",
                object_name="btnPDF",
                compact=True,
                icon_name="fa5s.file-pdf",
            )
            self.btn_export_pdf.clicked.connect(self._on_export_pdf)

            # docs/sections/export-pdf-excel.md — dugme Pregled faktura
            self.btn_pregled_faktura = self._create_button(
                "Pregled",
                "Pregled faktura — grupisanje po fakturi za carinika",
                object_name="btnPregledFaktura",
                compact=True,
                icon_name="fa5s.eye",
            )
            self.btn_pregled_faktura.clicked.connect(self._on_export_pregled_faktura)
            layout.addWidget(self.btn_export_pdf)

            self.btn_create_naimenovanja = self._create_button(
                "Kreiraj Naimenovanja",
                "Kreiraj naimenovanja iz faktura (grupisi po tarifi + zemlji + povlastici)",
                object_name="btnKreirajNaimenovanja",
                icon_name="fa5s.clipboard-list",
            )
            self.btn_create_naimenovanja.clicked.connect(self._on_create_naimenovanja)
            layout.addWidget(self.btn_create_naimenovanja)

            # Bruto/Neto weights
            weights_widget = QWidget()
            weights_layout = QVBoxLayout(weights_widget)
            weights_layout.setContentsMargins(4, 0, 4, 0)
            weights_layout.setSpacing(2)

            bruto_row = QHBoxLayout()
            bruto_row.setSpacing(4)
            bruto_label = QLabel("Bruto:")
            bruto_label.setFixedWidth(50)
            bruto_label.setStyleSheet(
                "color: #222; font-size: 14px; font-weight: bold;"
            )
            bruto_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            bruto_row.addWidget(bruto_label)
            self.input_bruto = QLineEdit()
            self.input_bruto.setFixedWidth(90)
            self.input_bruto.setToolTip("Ukupna bruto težina sa fakture (kg)")
            bruto_row.addWidget(self.input_bruto)
            weights_layout.addLayout(bruto_row)

            neto_row = QHBoxLayout()
            neto_row.setSpacing(4)
            neto_label = QLabel("Neto:")
            neto_label.setFixedWidth(50)
            neto_label.setStyleSheet("color: #222; font-size: 14px; font-weight: bold;")
            neto_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            neto_row.addWidget(neto_label)
            self.input_neto = QLineEdit()
            self.input_neto.setFixedWidth(90)
            self.input_neto.setToolTip("Ukupna neto težina sa fakture (kg)")
            neto_row.addWidget(self.input_neto)
            weights_layout.addLayout(neto_row)

            layout.addWidget(weights_widget)

            self.btn_validate = self._create_button(
                "Validacija",
                "Provaliziraj sve stavke",
                object_name="btnValidacija",
                icon_name="fa5s.check-circle",
            )
            self.btn_validate.clicked.connect(self._on_validate_all)
            layout.addWidget(self.btn_validate)

        elif section_idx == 4:  # Pametna pomoć
            self.btn_calc_masses = self._create_button(
                "Izračunaj mase",
                "Automatski izračunaj bruto/neto mase",
                object_name="btnIzracunajMase",
                icon_name="fa5s.balance-scale",
            )
            self.btn_calc_masses.clicked.connect(self._on_calculate_masses)
            layout.addWidget(self.btn_calc_masses)

            self.btn_auto_fill = self._create_button(
                "Auto-popuni",
                "Automatski popuni tarifne brojeve iz baze znanja",
                object_name="btnAutoPopuni",
                icon_name="fa5s.magic",
            )
            self.btn_auto_fill.clicked.connect(self._on_auto_fill)
            layout.addWidget(self.btn_auto_fill)

            self.btn_load_mappings = self._create_button(
                "Učitaj novi xml",
                "Učitaj novi XML fajl u bazu znanja",
                object_name="btnUcitajMappinge",
                icon_name="fa5s.database",
            )
            self.btn_load_mappings.clicked.connect(self._on_load_mappings_from_xml)
            layout.addWidget(self.btn_load_mappings)

    def _create_table(self) -> QTableWidget:
        """Create the main items table."""
        table = QTableWidget()
        table.setColumnCount(12)

        # Set headers
        headers = [
            "Red.br.",
            "Faktura",
            "Naimenovanja",
            "Naziv robe",
            "Tarifni broj",
            "Količina",
            "Iznos",
            "Bruto (kg)",
            "Neto (kg)",
            "Zemlja",
            "Povlastica",
            "Valuta",
        ]
        table.setHorizontalHeaderLabels(headers)

        # Set column widths - optimized for 1536px window (80% Full HD)
        header = table.horizontalHeader()
        table.setColumnWidth(0, 60)  # Red.br. (povećano)
        table.setColumnWidth(1, 250)  # Faktura (250px za najduže brojeve faktura)
        table.setColumnWidth(2, 125)  # Naimenovanja (125px za savršenu čitljivost)
        table.setColumnWidth(3, 430)  # Naziv robe (glavna kolona - povećano, takođe rastegljiva)
        table.setColumnWidth(4, 140)  # Tarifni broj (povećano - 10 cifara)
        table.setColumnWidth(5, 100)  # Količina
        table.setColumnWidth(6, 110)  # Cijena
        table.setColumnWidth(7, 120)  # Bruto (kg)
        table.setColumnWidth(8, 120)  # Neto (kg)
        table.setColumnWidth(9, 80)  # Zemlja
        table.setColumnWidth(10, 100)  # Povlastica
        table.setColumnWidth(11, 65)  # Valuta (3 slova: EUR/USD/BAM)

        # ZAKUCAJ širinu tabele - ne dozvoli automatsku optimizaciju
        header.setSectionResizeMode(QHeaderView.Fixed)
        # "Faktura" (kolona 1) - Interactive sa početnom širinom od 200px za duge brojeve
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        # "Naziv robe" (kolona 3) se rasteže da popuni ostatak prostora
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        # Omogući rastezanje zadnje sekcije
        header.setStretchLastSection(False)

        # Table settings
        table.setAlternatingRowColors(
            False
        )  # Isključeno - koristimo validacione boje umjesto
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        table.verticalHeader().setVisible(False)

        # Optimalna visina redova i font za čitljivost
        table.verticalHeader().setDefaultSectionSize(35)  # Visina reda
        table.setStyleSheet(
            """
            QTableWidget {
                font-size: 10pt;
                gridline-color: #ddd;
                border: 1px solid #ccc;
            }
            QTableWidget::item {
                padding: 6px 4px;
                border: none;
                color: #000000;
            }
            QTableWidget::item:selected {
                background-color: #0078d7;
                color: white;
            }
            QHeaderView::section {
                background-color: #f5f5f5;
                color: #000000;
                padding: 8px 6px;
                border: 1px solid #ddd;
                font-weight: bold;
                font-size: 11pt;
            }
        """
        )

        # Enable inline editing
        table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.EditKeyPressed
            | QAbstractItemView.AnyKeyPressed
        )
        table.setTabKeyNavigation(True)

        # Set custom delegate for validation colors
        validation_delegate = ValidationDelegate(table)
        table.setItemDelegate(validation_delegate)

        self._install_bottom_scroll_buffer(table)

        # Connect signals
        table.itemSelectionChanged.connect(self._on_selection_changed)
        table.itemChanged.connect(self._on_item_changed)

        return table

    def _install_bottom_scroll_buffer(self, table: QTableWidget):
        scrollbar = table.verticalScrollBar()

        def _extend_range(mn, mx):
            row_h = max(1, table.verticalHeader().defaultSectionSize())
            target = mx + row_h
            blocker = QSignalBlocker(scrollbar)
            scrollbar.setMaximum(target)
            del blocker

        scrollbar.rangeChanged.connect(_extend_range)

    def _create_status_bar(self) -> QWidget:
        """Create the status bar with statistics."""
        container = QWidget()
        container.setObjectName("statusBarContainer")
        container.setAttribute(Qt.WA_StyledBackground, True)
        container.setFixedHeight(42)
        container.setStyleSheet("""
            QWidget#statusBarContainer {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1E3A5F, stop:1 #162D4A);
                border-top: 2px solid #2D5A8E;
            }
            QWidget#statusBarContainer QLabel {
                font-size: 13px;
                font-weight: 600;
                color: #CBD8E8;
                background: transparent;
                padding: 0 2px;
            }
            QWidget#statusBarContainer QLabel#statusSeparator {
                color: #3A5F82;
                font-size: 15px;
                font-weight: 400;
                background: transparent;
                padding: 0;
            }
            QWidget#statusBarContainer QLabel[status="error"] {
                color: #FF6B6B;
            }
            QWidget#statusBarContainer QLabel[status="warning"] {
                color: #FFD93D;
            }
            QWidget#statusBarContainer QLabel[status="success"] {
                color: #6BCB77;
            }
        """)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        def _stat_lbl(text: str, name: str = "") -> QLabel:
            lbl = QLabel(text)
            lbl.setProperty("class", "statusLabel")
            if name:
                lbl.setObjectName(name)
            return lbl

        def _sep() -> QLabel:
            s = QLabel("|")
            s.setObjectName("statusSeparator")
            return s

        self.lbl_item_count    = _stat_lbl("📦 Stavki: 0")
        self.lbl_total_amount  = _stat_lbl("💰 Ukupno: 0.00 EUR")
        self.lbl_total_quantity = _stat_lbl("⬛ Komada: 0")
        self.lbl_bruto         = _stat_lbl("⚖  Bruto: 0.00 kg")
        self.lbl_neto          = _stat_lbl("◈  Neto: 0.00 kg")
        self.lbl_validation    = _stat_lbl("⚪ Neprovjereno")
        self.lbl_assembly      = _stat_lbl("📋 Assembly: N/A")

        for widget in [
            self.lbl_item_count,    _sep(),
            self.lbl_total_amount,  _sep(),
            self.lbl_total_quantity, _sep(),
            self.lbl_bruto,          _sep(),
            self.lbl_neto,           _sep(),
            self.lbl_validation,     _sep(),
            self.lbl_assembly,
        ]:
            layout.addWidget(widget)

        layout.addStretch()

        # Progress bar for imports (initially hidden)
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("importProgressBar")
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("Import: %p%")
        self.progress_bar.setFixedWidth(200)
        self.progress_bar.setVisible(False)  # Hidden by default
        layout.addWidget(self.progress_bar)

        return container

    def _create_button(
        self,
        text: str,
        tooltip: str,
        button_class: str = "",
        color: str = "",
        highlight: bool = False,
        compact: bool = False,
        icon_name: str = "",
        object_name: str = "",
    ) -> QPushButton:
        """Create a styled button with optional background color, highlight, compact mode, and icon."""
        btn_text = (" " + text) if icon_name else text
        btn = QPushButton(btn_text)
        btn.setToolTip(tooltip)

        # Add icon if QtAwesome is available and icon_name is provided
        if icon_name:
            if not QTAWESOME_AVAILABLE:
                logger.debug(
                    f"⚠️  QtAwesome NIJE DOSTUPAN - ikona '{icon_name}' za '{text}' se neće prikazati"
                )
            else:
                try:
                    if icon_name not in self._icon_cache:
                        qta_icon = qta.icon(icon_name, color="#FFFFFF")
                        pixmap = qta_icon.pixmap(QSize(16, 16))
                        self._icon_cache[icon_name] = QIcon(pixmap)
                    btn.setIcon(self._icon_cache[icon_name])
                    btn.setIconSize(QSize(16, 16))
                except Exception as e:
                    logger.warning(
                        f"❌ GREŠKA pri učitavanju ikone '{icon_name}' za dugme '{text}': {e}"
                    )

        if object_name:
            # Stilizacija dolazi iz button_styles.qss — samo postavi objectName
            btn.setObjectName(object_name)
        elif color:
            # Inline stil za sekcije koje ne koriste QSS paletu
            border_color = self._darken_color(color)
            border_width = "2px" if highlight else "1px"
            font_weight = "bold" if highlight else "normal"
            padding = "4px 8px" if compact else "6px 10px"

            btn.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {color};
                    color: #333;
                    border: {border_width} solid {border_color};
                    border-radius: 4px;
                    padding: {padding};
                    font-size: 13px;
                    font-weight: {font_weight};
                    text-align: center;
                }}
                QPushButton:hover {{
                    background-color: {border_color};
                    border: {border_width} solid {self._darken_color(border_color)};
                }}
                QPushButton:pressed {{
                    background-color: {self._darken_color(border_color)};
                }}
                QPushButton:disabled {{
                    background-color: #f0f0f0;
                    color: #999;
                    border: 1px solid #ddd;
                }}
            """
            )
        elif button_class:
            btn.setProperty("class", button_class)

        return btn

    def _darken_color(self, hex_color: str, factor: float = 0.85) -> str:
        """Darken a hex color by a factor (0.0 = black, 1.0 = same)."""
        cache_key = f"{hex_color}:{factor}"
        if cache_key in self._darken_cache:
            return self._darken_cache[cache_key]

        clean = hex_color.lstrip("#")
        r = int(int(clean[0:2], 16) * factor)
        g = int(int(clean[2:4], 16) * factor)
        b = int(int(clean[4:6], 16) * factor)
        result = f"#{r:02x}{g:02x}{b:02x}"
        self._darken_cache[cache_key] = result
        return result

    def _create_label(self, text: str) -> QLabel:
        """Create a control label."""
        lbl = QLabel(text)
        lbl.setProperty("class", "controlLabel")
        return lbl

    def _create_separator(self) -> QFrame:
        """Create a vertical separator line."""
        sep = QFrame()
        sep.setProperty("class", "separator")
        sep.setFrameShape(QFrame.VLine)
        return sep

    def _create_thick_separator(self) -> QFrame:
        """Create a thick vertical separator between sections."""
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFrameShadow(QFrame.Sunken)
        sep.setLineWidth(2)
        sep.setMidLineWidth(1)
        sep.setStyleSheet(
            """
            QFrame {
                color: #999;
                margin: 0px 8px;
            }
        """
        )
        return sep

    # ============================================================
    # Data Management
    # ============================================================

    def _load_data_from_draft(self):
        """Load invoice items from draft into table - OPTIMIZED bulk load."""
        self.table.blockSignals(True)
        self.table.setUpdatesEnabled(False)
        try:
            # FIX BUG: Clear validation cache at start to avoid stale data
            self.validation_cache.clear()

            item_count = len(self.draft.invoice_lines)

            # OPTIMIZATION: Use setRowCount instead of insertRow loop
            self.table.setRowCount(item_count)

            # PASS 1: Insert all items WITHOUT validation (fast)
            for idx, item in enumerate(self.draft.invoice_lines):
                self._add_item_to_table_fast(idx, item)

            # PASS 2: Validate all rows AFTER insertion (better UI responsiveness)
            for idx, item in enumerate(self.draft.invoice_lines):
                self._validate_and_color_row(idx, item)

            self._update_status_bar()
        finally:
            self.table.setUpdatesEnabled(True)
            self.table.viewport().update()
            self.table.blockSignals(False)

    def _populate_row_cells(self, row: int, row_number: int, item: InvoiceLine):
        """Popuni ćelije reda tabele iz InvoiceLine objekta (bez insertRow ili validacije)."""
        naziv_display = item.naziv_robe or ""
        if item.product_code and naziv_display.startswith(item.product_code):
            naziv_display = naziv_display[len(item.product_code):].strip()
        elif not item.product_code or not item.product_code.strip():
            match = self._RE_CODE_PREFIX.match(naziv_display)
            if match:
                naziv_display = match.group(2)

        naimenovanje_text = (
            str(item.assigned_naimenovanje_ordinal)
            if item.assigned_naimenovanje_ordinal > 0
            else ""
        )

        self._set_table_item(row, 0, str(row_number + 1), align=Qt.AlignCenter)
        self._set_table_item(row, 1, item.invoice_number or "", align=Qt.AlignCenter)
        self._set_table_item(row, 2, naimenovanje_text, align=Qt.AlignCenter)
        self._set_table_item(row, 3, naziv_display)
        self._set_table_item(row, 4, item.tarifni_broj or "", align=Qt.AlignCenter)
        self._set_table_item(row, 5, self._format_number(item.kolicina), align=Qt.AlignRight)
        self._set_table_item(row, 6, self._format_number(item.iznos), align=Qt.AlignRight)
        self._set_table_item(row, 7, self._format_number(item.bruto_kg), align=Qt.AlignRight)
        self._set_table_item(row, 8, self._format_number(item.neto_kg), align=Qt.AlignRight)
        self._set_table_item(row, 9, item.zemlja_porijekla or "", align=Qt.AlignCenter)
        self._set_table_item(row, 10, item.povlastica or "", align=Qt.AlignCenter)
        self._set_table_item(row, 11, item.valuta or "", align=Qt.AlignCenter)

    def _add_item_to_table_fast(self, row_number: int, item: InvoiceLine):
        """FAST bulk insert - no validation, no color (called from _load_data_from_draft)."""
        self._populate_row_cells(row_number, row_number, item)

    def _add_item_to_table(self, row_number: int, item: InvoiceLine):
        """Add a single item to the table (with validation for single adds)."""
        row = self.table.rowCount()
        self.table.insertRow(row)
        self._populate_row_cells(row, row_number, item)
        self._validate_and_color_row(row, item)

    def _set_table_item(
        self, row: int, col: int, value: str, align: Qt.AlignmentFlag = Qt.AlignLeft
    ):
        """Set a table cell value with alignment."""
        item = QTableWidgetItem(value)
        item.setTextAlignment(align | Qt.AlignVCenter)
        self.table.setItem(row, col, item)

    def _format_number(self, value: Optional[float]) -> str:
        """Format a number for display (European format: 10.258,23)."""
        if value is None or value == 0.0:
            return ""
        # Format with thousands separator and comma for decimals
        formatted = f"{value:,.2f}"
        # Convert to European format: . for thousands, , for decimals
        formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
        return formatted

    def _validate_and_color_row(self, row: int, item: InvoiceLine):
        """Validate item and apply background color to row."""
        # Validate item
        result = self.validator.validate(item)

        # ⭐ TARIFF SIMILARITY BOJENJE
        # Ako je tarifni broj nađen fuzzy match-om sa sličnošću < 0.92
        # oboj red žutom kao upozorenje da treba provjeriti
        tariff_sim = getattr(item, 'tariff_similarity', 0.0) or 0.0

        # Check if item is UNMATCHED (came from invoice but not found in master list)
        is_unmatched = (
            not item.tarifni_broj or len(item.tarifni_broj.strip()) == 0
        ) and (not item.zemlja_porijekla or len(item.zemlja_porijekla.strip()) == 0)

        # Determine color based on validation result
        # ⭐ PRVO provjeri tariff similarity (žuta za fuzzy match < 0.92)
        if item.tarifni_broj and 0.70 <= tariff_sim < 0.92:
            # ŽUTA boja - fuzzy match, preporučuje se provjera
            color_hex = "#fff9c4"  # Svijetlo žuta
            tooltip = f"⚠️ Tarifni broj: {item.tarifni_broj}\n" \
                      f"Pouzdanje: {tariff_sim:.0%}\n" \
                      f"Preporučuje se ručna provjera tarifnog broja"
        elif is_unmatched:
            # PLAVA boja za nepodudarajuće stavke (nisu pronađene u master listi)
            color_hex = "#cce5ff"  # Light blue for unmatched
            tooltip = "🔵 Nepodudarajuća stavka - nije pronađena u master listi. Popunite tarifni broj i zemlju porijekla."
        elif not item.tarifni_broj or len(item.tarifni_broj.strip()) == 0:
            # CRVENA boja samo ako NEMA tarifnog broja
            color_hex = "#ffcccc"  # Red for missing tariff
            tooltip = "❌ Greška: Nedostaje tarifni broj"
        elif result.has_blocking_errors():
            # CRVENA boja za druge kritične greške
            color_hex = "#ffcccc"  # Red for errors
            tooltip = "❌ Greška: " + "; ".join([e.message for e in result.errors])
        elif len(result.warnings) > 0:
            # ŽUTA boja za upozorenja
            color_hex = "#ffffcc"  # Yellow for warnings
            tooltip = "⚠️ Upozorenje: " + "; ".join([e.message for e in result.warnings])
        elif result.valid:
            # ZELENA boja za validne stavke
            color_hex = "#ccffcc"  # Green for valid
            tooltip = "✅ Validna stavka"
        else:
            # Bijela boja za neprovjerene
            color_hex = "#ffffff"  # White (not validated)
            tooltip = ""

        # Update cache
        self.validation_cache.set(row, result)

        # Apply color to all cells in row using custom delegate
        # Store color in ValidationColorRole so delegate can render it
        for col in range(self.table.columnCount()):
            cell_item = self.table.item(row, col)
            if cell_item:
                cell_item.setData(ValidationDelegate.ValidationColorRole, color_hex)
                if tooltip:
                    cell_item.setToolTip(tooltip)
        
        # DODATNO: Apply country confidence color to zemlja_porijekla column (col 8)
        self._apply_country_confidence_color(row, item)

    def _apply_country_confidence_color(self, row: int, item: InvoiceLine):
        """
        Apply color coding to zemlja_porijekla column based on country_confidence.
        
        Confidence levels:
        - HIGH (green): Data from PDF or matching PDF+DB
        - MEDIUM (yellow): Data from database only
        - LOW (orange): No data available
        - CONFLICT (red): PDF and DB have different values
        """
        if not item.country_confidence:
            return  # No confidence data
        
        color_hex = self._CONFIDENCE_COLORS.get(item.country_confidence, "#ffffff")
        icon = self._CONFIDENCE_ICONS.get(item.country_confidence, "")
        
        # Build tooltip
        tooltip_parts = []
        if item.country_confidence == "HIGH":
            if item.country_source in ("PDF", "EXCEL"):
                tooltip_parts.append("✅ Podatak o poreklu iz uvezenog dokumenta (visoka pouzdanost)")
            elif item.country_source == "PDF_IZJAVA":
                tooltip_parts.append("✅ Podatak o poreklu iz izjave u dokumentu (visoka pouzdanost)")
            elif item.country_source == "PDF_OZNAKA":
                tooltip_parts.append("✅ Podatak o poreklu iz uvezenog dokumenta; povlasticu provjerava deklarant")
            elif item.country_source == "MATCH":
                tooltip_parts.append("✅ PDF i baza se poklapaju (visoka pouzdanost)")
            else:
                tooltip_parts.append("✅ Visoka pouzdanost")
        elif item.country_confidence == "MEDIUM":
            tooltip_parts.append("📋 Podatak o poreklu iz baze znanja (srednja pouzdanost)")
        elif item.country_confidence == "LOW":
            tooltip_parts.append("⚠️ Nema podataka o poreklu (potreban manuelni unos)")
        elif item.country_confidence == "CONFLICT":
            tooltip_parts.append(f"🚨 Konflikt porekla: {item.country_conflict_details or 'PDF i baza imaju različite vrednosti'}")
            tooltip_parts.append("ℹ️ Korišćena je vrednost iz PDF-a")
        
        # Apply to zemlja_porijekla column (col 9) - pomjereno zbog dodate kolone Faktura
        cell_item = self.table.item(row, 9)
        if cell_item:
            cell_item.setData(ValidationDelegate.ValidationColorRole, color_hex)
            if item.zemlja_porijekla:
                # Čisti kod u UserRole (čita se pri sync), emoji samo u displayu
                cell_item.setData(Qt.UserRole, item.zemlja_porijekla)
                cell_item.setText(f"{icon} {item.zemlja_porijekla}" if icon else item.zemlja_porijekla)
            if tooltip_parts:
                existing_tooltip = cell_item.toolTip()
                if existing_tooltip:
                    cell_item.setToolTip(f"{existing_tooltip}\n\n{' '.join(tooltip_parts)}")
                else:
                    cell_item.setToolTip(" ".join(tooltip_parts))

    def _on_item_changed(self, item: QTableWidgetItem):
        """Handle when user edits a cell."""
        # Sync changed data back to draft
        row = item.row()
        col = item.column()

        if row >= len(self.draft.invoice_lines):
            return

        invoice_item = self.draft.invoice_lines[row]
        value = item.text().strip()

        # Update corresponding field based on column
        try:
            if col == 1:  # Faktura (nova kolona)
                invoice_item.invoice_number = value
            elif col == 3:  # Naziv robe (pomjereno za +1 zbog nove kolone)
                invoice_item.naziv_robe = value
            elif col == 4:  # Tarifni broj (pomjereno za +1)
                invoice_item.tarifni_broj = value
            elif col == 5:  # Količina (pomjereno za +1)
                invoice_item.kolicina = self._parse_number(value) if value else 0.0
            elif col == 6:  # IZNOS (ukupan iznos, NE cijena po komadu!) (pomjereno za +1)
                invoice_item.iznos = self._parse_number(value) if value else 0.0
                # VAŽNO: Ne mijenjamo cijena_jed - to je cijena po komadu koja dolazi iz fakture
            elif col == 7:  # Bruto kg (pomjereno za +1)
                invoice_item.bruto_kg = self._parse_number(value) if value else 0.0
            elif col == 8:  # Neto kg (pomjereno za +1)
                invoice_item.neto_kg = self._parse_number(value) if value else 0.0
            elif col == 9:  # Zemlja — čisti kod iz UserRole, ne tekst sa emojiem (pomjereno za +1)
                from PySide6.QtCore import Qt as _Qt
                user_val = item.data(_Qt.UserRole)
                invoice_item.zemlja_porijekla = str(user_val).strip() if user_val else value
            elif col == 10:  # Povlastica (pomjereno za +1)
                invoice_item.povlastica = value
            elif col == 11:  # Valuta (pomjereno za +1)
                invoice_item.valuta = value
        except Exception as e:
            # Log error but don't crash
            logger.error(f"Error updating item: {e}")

        # Debounce: odgodi validaciju i dirty signal za 200ms
        self._pending_validate_rows.add(row)
        self._debounce_timer.start()

    def _flush_pending_validation(self):
        """Poziva se nakon debounce timera - validuje redove i emituje dirty signal."""
        for row in sorted(self._pending_validate_rows):
            if row < len(self.draft.invoice_lines):
                self._validate_and_color_row(row, self.draft.invoice_lines[row])
        self._pending_validate_rows.clear()
        self._notify_data_changed()

    def _notify_data_changed(self):
        self.data_changed.emit()
        if self.on_dirty:
            self.on_dirty()

    def _parse_number(self, value_str: str) -> float:
        """Parse European format number (10.258,23) to float."""
        if not value_str:
            return 0.0
        # Convert European format to Python float
        # Remove thousands separator (.) and replace decimal comma with dot
        value_str = value_str.replace(".", "").replace(",", ".")
        try:
            return float(value_str)
        except ValueError:
            return 0.0

    def _parse_weight_input(self, text: str) -> float:
        """Parsira težinu iz input polja - podržava US (1,234.56) i EU (1.234,56) format."""
        if not text:
            return 0.0
        text = text.strip()
        if "," in text and "." in text:
            # Koji separator dolazi zadnji - to je decimalni
            if text.rindex(".") > text.rindex(","):
                # US format: 1,234.56 → ukloni zareze
                text = text.replace(",", "")
            else:
                # EU format: 1.234,56 → ukloni tačke, zamijeni zarez s tačkom
                text = text.replace(".", "").replace(",", ".")
        elif "," in text:
            # Samo zarez → EU decimalni separator
            text = text.replace(",", ".")
        try:
            return float(text)
        except ValueError:
            return 0.0

    def _update_weights_after_deletion(self, deleted_bruto: float, deleted_neto: float):
        """Ažurira input polja za bruto/neto nakon brisanja stavke (oduzima težine obrisane stavke)."""
        # Read current values
        current_bruto = self._parse_weight_input(self.input_bruto.text() or "0")
        current_neto = self._parse_weight_input(self.input_neto.text() or "0")
        
        # Subtract deleted item weights
        new_bruto = max(0.0, current_bruto - deleted_bruto)
        new_neto = max(0.0, current_neto - deleted_neto)
        
        # Update input fields with formatted values
        self.input_bruto.setText(f"{new_bruto:,.3f}")
        self.input_neto.setText(f"{new_neto:,.3f}")

    def _get_cell_value(self, row: int, col: int) -> str:
        """Safely get cell value from table (HELPER METHOD - reduces code duplication)."""
        cell_item = self.table.item(row, col)
        if not cell_item:
            return ""
        # Kolona 9 (zemlja_porijekla): čisti kod čuvan u UserRole da emoji ne uđe u podatak
        # Pomjereno za +1 zbog dodate kolone Faktura
        if col == 9:
            from PySide6.QtCore import Qt as _Qt
            user_val = cell_item.data(_Qt.UserRole)
            if user_val is not None:
                return str(user_val).strip()
        return cell_item.text().strip()

    def _sync_table_to_draft(self):
        """Sync all table data back to draft (OPTIMIZED with helper method)."""
        # This is now handled by _on_item_changed for each edit
        # But we can still implement full sync for safety
        for row in range(self.table.rowCount()):
            if row >= len(self.draft.invoice_lines):
                break

            invoice_item = self.draft.invoice_lines[row]

            # Read all cells and update invoice_item (using helper method)
            invoice_item.invoice_number = self._get_cell_value(row, 1)  # Nova kolona
            invoice_item.naziv_robe = self._get_cell_value(row, 3)      # Pomjereno za +1
            invoice_item.tarifni_broj = self._get_cell_value(row, 4)    # Pomjereno za +1
            invoice_item.kolicina = self._parse_number(self._get_cell_value(row, 5))  # Pomjereno za +1

            # VAŽNO: Kolona 6 je "Ukupan iznos", ne cijena_jed! (pomjereno za +1)
            # Direktno čuvaj iznos, pa izračunaj cijena_jed ako ima količine
            ukupan_iznos = self._parse_number(self._get_cell_value(row, 6))
            invoice_item.iznos = ukupan_iznos
            if invoice_item.kolicina and invoice_item.kolicina > 0:
                invoice_item.cijena_jed = ukupan_iznos / invoice_item.kolicina
            else:
                invoice_item.cijena_jed = 0.0

            invoice_item.bruto_kg = self._parse_number(self._get_cell_value(row, 7))  # Pomjereno za +1
            invoice_item.neto_kg = self._parse_number(self._get_cell_value(row, 8))   # Pomjereno za +1
            invoice_item.zemlja_porijekla = self._get_cell_value(row, 9)              # Pomjereno za +1
            invoice_item.povlastica = self._get_cell_value(row, 10)                   # Pomjereno za +1
            invoice_item.valuta = self._get_cell_value(row, 11)                       # Pomjereno za +1

    def _update_status_bar(self):
        """Update status bar with current statistics."""
        item_count = len(self.draft.invoice_lines)

        if item_count == 0:
            self.lbl_item_count.setText("📦 Stavki: 0")
            self.lbl_total_amount.setText("💰 Ukupno: 0.00 EUR")
            self.lbl_total_quantity.setText("📦 Komada: 0")
            self.lbl_bruto.setText("⚖️ Bruto: 0.00 kg")
            self.lbl_neto.setText("📊 Neto: 0.00 kg")
            self.lbl_validation.setText("⚪ Neprovjereno")
            self.status_bar_widget.setProperty("status", "")
            self.status_bar_widget.style().polish(self.status_bar_widget)
            return

        # Calculate totals in single pass (OPTIMIZED)
        total_amount = 0.0
        total_quantity = 0
        total_bruto_items = 0.0
        total_neto_items = 0.0
        currencies = set()
        first_currency = "EUR"

        for item in self.draft.invoice_lines:
            # Accumulate totals
            total_amount += item.iznos or 0.0
            total_quantity += item.kolicina or 0
            total_bruto_items += item.bruto_kg or 0.0
            total_neto_items += item.neto_kg or 0.0

            # Track currencies
            if item.valuta:
                currencies.add(item.valuta)
                if not first_currency or first_currency == "EUR":
                    first_currency = item.valuta

        # Read weights from input fields (which accumulate weights from PDFs)
        try:
            total_bruto = self._parse_weight_input(self.input_bruto.text() or "0")
            total_neto = self._parse_weight_input(self.input_neto.text() or "0")
        except (ValueError, TypeError):
            # Fallback: use calculated values from items
            total_bruto = total_bruto_items
            total_neto = total_neto_items

        # Determine currency display
        currency = first_currency
        if len(currencies) > 1:
            currency = f"{first_currency} (⚠️ Mixed: {', '.join(sorted(currencies))})"

        # Update labels with file count
        total_files = self.imported_excel_count + self.imported_pdf_count
        if total_files > 0:
            excel_pdf = (
                f"(Excel: {self.imported_excel_count}, PDF: {self.imported_pdf_count})"
                if self.imported_pdf_count > 0
                else f"(Excel: {self.imported_excel_count})"
            )
            files_info = f" | 📁 Fajlovi: {total_files} {excel_pdf}"
        else:
            files_info = ""

        self.lbl_item_count.setText(f"📦 Stavki: {item_count}{files_info}")
        self.lbl_total_amount.setText(
            f"💰 Ukupno: {float(total_amount):.2f} {currency}"
        )
        self.lbl_total_quantity.setText(f"📦 Komada: {total_quantity:,}")
        # Use _format_weight to show full precision with thousands separator
        self.lbl_bruto.setText(f"⚖️ Bruto: {self._format_weight(total_bruto)} kg")
        self.lbl_neto.setText(f"📊 Neto: {self._format_weight(total_neto)} kg")

        # Validation status - koristi cache umesto ponovne validacije
        error_count = self.validation_cache.get_error_count()
        warning_count = self.validation_cache.get_warning_count()
        valid_count = self.validation_cache.get_valid_count()

        # Validation status and color
        if error_count > 0:
            self.lbl_validation.setText(f"❌ {error_count} greška")
            self.status_bar_widget.setProperty("status", "error")
            self.lbl_validation.setProperty("status", "error")
        elif warning_count > 0:
            self.lbl_validation.setText(f"⚠️ {warning_count} upozorenja")
            self.status_bar_widget.setProperty("status", "warning")
            self.lbl_validation.setProperty("status", "warning")
        elif valid_count == item_count:
            self.lbl_validation.setText("✅ Sve validne")
            self.status_bar_widget.setProperty("status", "success")
            self.lbl_validation.setProperty("status", "success")
        else:
            self.lbl_validation.setText("⚪ Neprovjereno")
            self.status_bar_widget.setProperty("status", "")
            self.lbl_validation.setProperty("status", "")

        # Assembly completion status
        if self.assembly.master_list_loaded:
            status = self.assembly.get_completion_status()
            completion = status["completion_percentage"]
            invoices = status["imported_invoices_count"]

            if completion == 100.0:
                self.lbl_assembly.setText(f"✅ {completion:.0f}% ({invoices} faktura)")
                self.lbl_assembly.setProperty("status", "success")
            elif completion > 0:
                self.lbl_assembly.setText(f"⚠️ {completion:.0f}% ({invoices} faktura)")
                self.lbl_assembly.setProperty("status", "warning")
            else:
                self.lbl_assembly.setText(f"⏳ {completion:.0f}% ({invoices} faktura)")
                self.lbl_assembly.setProperty("status", "")
        else:
            self.lbl_assembly.setText("📋 Assembly: N/A")
            self.lbl_assembly.setProperty("status", "")

        # Refresh style
        self.status_bar_widget.style().polish(self.status_bar_widget)
        self.lbl_validation.style().polish(self.lbl_validation)
        self.lbl_assembly.style().polish(self.lbl_assembly)

    # ============================================================
    # Button Handlers
    # ============================================================

    def _on_import_files(self, title: str, file_filter: str):
        filepaths, _ = QFileDialog.getOpenFileNames(self, title, "", file_filter)
        if filepaths:
            if len(filepaths) == 1:
                self._start_import(filepaths[0])
            else:
                self._import_multiple_files(filepaths)

    def _on_import_pdf(self):
        self._on_import_files(
            "Odaberi PDF fakture (Ctrl/Shift za više fajlova)",
            "PDF Files (*.pdf);;All Files (*)",
        )

    def _on_import_excel(self):
        self._on_import_files(
            "Odaberi Excel fakture (Ctrl/Shift za više fajlova)",
            "Excel Files (*.xlsx *.xls);;All Files (*)",
        )

    def _on_import_xml(self):
        """Handle Import XML button click."""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Odaberi XML fakturu ili ASYCUDA XML", "", "XML Files (*.xml);;All Files (*)"
        )

        if filepath:
            try:
                # Univerzalni faktura XML parser (<Faktura>/<Stavke>) → preusmjeri na _start_import
                from importers.faktura_xml_parser import detect_faktura_xml
                if detect_faktura_xml(filepath):
                    self._start_import(filepath)
                    return

                from importers.xml_importer import XMLImporter

                # Parse XML (ASYCUDA format)
                importer = XMLImporter()
                result = importer.import_file(Path(filepath))

                items = result.get("items", [])

                if not items:
                    QMessageBox.warning(
                        self,
                        "XML Import",
                        "Nije pronađena nijedna stavka u XML fajlu.\n\nProvjerite da li je XML fajl ispravan ASYCUDA format.",
                    )
                    return

                # Confirm import
                reply = QMessageBox.question(
                    self,
                    "XML Import - Potvrda",
                    f"Pronađeno {len(items)} naimenovanja u XML fajlu.\n\nŽelite li da učitate ove stavke?\n\n(Postojeće stavke će biti zamijenjene)",
                    QMessageBox.Yes | QMessageBox.No,
                )

                if reply == QMessageBox.Yes:
                    # Clear existing items
                    self.draft.invoice_lines.clear()

                    # Add items from XML
                    self.draft.invoice_lines.extend(items)

                    # Update header data if available in XML
                    header_data = result.get("header", {})
                    if header_data:
                        # Update draft with header data
                        updated_count = 0
                        for key, value in header_data.items():
                            if hasattr(self.draft, key):
                                setattr(self.draft, key, value)
                                updated_count += 1

                    # Reload table
                    self._load_data_from_draft()

                    # Update status bar
                    self._update_status_bar()

                    # Mark draft as dirty to trigger updates in other tabs
                    if header_data:
                        self.draft.mark_dirty()

                    # Mark as dirty
                    self._notify_data_changed()

                    QMessageBox.information(
                        self,
                        "XML Import - Uspješno",
                        f"✅ Učitano {len(items)} naimenovanja iz ASYCUDA XML fajla!\n\nFajl: {Path(filepath).name}",
                    )

            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Greška pri XML importu",
                    f"Nije uspjelo učitavanje XML fajla:\n\n{str(e)}\n\nProvjerite da li je fajl ispravan ASYCUDA XML format.",
                )

    def _on_load_master_list(self):
        """Handle Load Master List button click."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Odaberi glavnu listu (Excel)",
            "",
            "Excel Files (*.xlsx *.xls);;All Files (*)",
        )

        if not filepath:
            return

        try:
            # Load master list into assembly
            count = self.assembly.load_master_list(filepath)

            # Resetuj stanje import servisa da spriječimo lažno kombinovanje
            # sa prethodno uvezenim fakturama (npr. CASE 3 invoice+packing list)
            from services.import_service import get_import_service

            get_import_service().clear_memory()

            # Clear existing draft items
            self.draft.invoice_lines.clear()

            # Load assembly items into draft
            draft = self.assembly.create_draft()
            self.draft.invoice_lines = draft.invoice_lines

            # Reload table
            self._load_data_from_draft()

            # Update status bar
            self._update_status_bar()

            # Show success message with status
            status = self.assembly.get_completion_status()
            QMessageBox.information(
                self,
                "Glavna lista učitana",
                f"Uspješno učitano {count} stavki iz master liste.\n\n"
                f"Status:\n"
                f"- Ukupno stavki: {status['total']}\n"
                f"- Kompletno: {status['complete']} ({status['completion_percentage']:.1f}%)\n"
                f"- Nedostaje cijena: {status['missing_price_count']}",
            )

            # Mark as dirty
            if self.on_dirty:
                self.on_dirty()

            self.data_changed.emit()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Greška pri učitavanju",
                f"Greška pri učitavanju master liste:\n{str(e)}",
            )

    def _start_import(self, filepath: str):
        """Start import worker thread."""
        # Check if import is already running
        if (
            hasattr(self, "import_worker")
            and self.import_worker
            and self.import_worker.isRunning()
        ):
            QMessageBox.warning(
                self,
                "Import u toku",
                "Trenutno je u toku drugi import.\nMolimo pričekajte da se završi.",
            )
            return

        # Disable buttons during import
        self._set_buttons_enabled(False)

        # Create and start worker
        self.import_worker = ImportWorker(filepath)
        self.import_worker.progress.connect(self._on_import_progress)
        self.import_worker.finished.connect(self._on_import_finished)
        self.import_worker.error.connect(self._on_import_error)
        self.import_worker.start()

    def _import_multiple_files(self, filepaths: list):
        """
        Import više fajlova odjednom i agregira sve stavke u jednu deklaraciju.

        Args:
            filepaths: Lista putanja do fajlova za uvoz
        """
        from services.import_service import ImportService

        # Kreiraj progress dialog
        progress = QProgressDialog(
            f"Uvoz {len(filepaths)} faktura...", "Otkaži", 0, len(filepaths), self
        )
        progress.setWindowTitle("Grupni uvoz")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)  # Prikaži odmah

        # Agregatori za rezultate
        all_items = []
        total_bruto_kg = 0.0
        total_neto_kg = 0.0
        successful_imports = 0
        failed_imports = []
        excel_count = 0
        pdf_count = 0
        any_authorized_exporter = False

        import_service = ImportService()

        # Uvezi svaki fajl
        for i, filepath in enumerate(filepaths):
            # Proveri da li je korisnik otkazao
            if progress.wasCanceled():
                break

            try:
                # Update progress
                progress.setLabelText(
                    f"Uvoz {i+1}/{len(filepaths)}: {Path(filepath).name}"
                )
                progress.setValue(i)

                # Import fajla
                result = import_service.import_file(filepath)

                # Ekstrakcija podataka
                if isinstance(result, ImportResult):
                    items = result.items
                    bruto_kg = result.bruto_kg or 0.0
                    neto_kg = result.neto_kg or 0.0
                    is_auth_file = getattr(result, 'is_authorized_exporter', False)
                    if is_auth_file:
                        any_authorized_exporter = True
                    # Postavi invoice_number na stavke — samo ako ga parser eksplicitno izvukao
                    explicit_inv = result.invoice_name or ""
                    if explicit_inv:
                        for item in items:
                            if not item.invoice_number:
                                item.invoice_number = explicit_inv
                    # EUR.1 / PE2 / PE3 dialog — zasebno za svaku fakturu (kao kod agenta)
                    if items:
                        has_origin_file = getattr(result, 'has_origin_statement', False)
                        if has_origin_file or self._should_show_eur1_dialog(items):
                            invoice_name_file = result.invoice_name or Path(filepath).stem
                            # Privremeno dodaj u draft — dijalog radi na draft.invoice_lines
                            self.draft.invoice_lines.extend(items)
                            from gui.tabs.agent.services.import_pipeline_service import _origin_dialog_type
                            dialog_tip = _origin_dialog_type(items, has_origin_file, is_auth_file)
                            if dialog_tip == 'pe3':
                                logger.info(f"📦 [{invoice_name_file}] → PE3 dialog")
                                self._show_pe2_dialog(invoice_name_file, doc_code='PE3')
                            elif dialog_tip == 'pe2':
                                logger.info(f"📦 [{invoice_name_file}] → PE2 dialog")
                                self._show_pe2_dialog(invoice_name_file, doc_code='PE2')
                            else:
                                val = sum(getattr(it, 'iznos', 0.0) for it in items)
                                logger.info(f"📦 [{invoice_name_file}] iznos={val:.2f}€ → EUR.1 dialog")
                                self._show_eur1_dialog()
                            # Ukloni privremene stavke — biće dodane na kraju iz all_items
                            del self.draft.invoice_lines[-len(items):]
                else:
                    # Backward compatibility
                    items = result
                    bruto_kg = 0.0
                    neto_kg = 0.0

                # Normalizuj tarifne brojeve na 8 cifara
                self._normalize_item_tariffs(items)
                # Rasporedi težinu fakture na stavke (ako parser nije dao per-line težine)
                self._distribute_invoice_weights(items, bruto_kg, neto_kg)
                # Zapamti per-invoice težinu za dugme 'Izračunaj mase'
                if bruto_kg > 0 or neto_kg > 0:
                    _inv_key = (
                        result.invoice_name
                        if isinstance(result, ImportResult) and result.invoice_name
                        else None
                    ) or Path(filepath).stem
                    self.draft.invoice_weights[normalize_invoice_key(_inv_key)] = (
                        bruto_kg,
                        neto_kg,
                    )

                # Agreguj rezultate
                all_items.extend(items)
                total_bruto_kg += bruto_kg
                total_neto_kg += neto_kg
                successful_imports += 1

                # Track file type
                if filepath.lower().endswith((".xlsx", ".xls")):
                    excel_count += 1
                elif filepath.lower().endswith(".pdf"):
                    pdf_count += 1

            except Exception as e:
                failed_imports.append((Path(filepath).name, str(e)))

        progress.setValue(len(filepaths))

        # Prikaži rezultate
        if all_items:
            # Reset assembly i postavi sve stavke kao master listu
            # Ovo osigurava da assembly sistem upravlja sa svim stavkama
            if not self.assembly.master_list_loaded:
                # Ako nema master liste, kreiraj je od svih stavki
                self.assembly.load_master_list_from_lines(
                    all_items, f"Grupni uvoz ({successful_imports} faktura)"
                )
                draft = self.assembly.create_draft()
                self.draft.invoice_lines = draft.invoice_lines
            else:
                # Ako postoji master lista, zamijeni postojeće stavke
                self.draft.invoice_lines.clear()
                self.draft.invoice_lines.extend(all_items)

            # Update display
            self._load_data_from_draft()

            # Update weights koristeći istu metodu kao pojedinačni uvoz
            # Prvo resetuj akumulirane težine
            self.weight_manager.accumulated_bruto_kg = 0.0
            self.weight_manager.accumulated_neto_kg = 0.0
            # Onda akumuliraj nove težine
            self._accumulate_weights(total_bruto_kg, total_neto_kg)

            # Update file counters for status bar
            self.imported_excel_count += excel_count
            self.imported_pdf_count += pdf_count

            # Update status bar
            self._update_status_bar()

            # Enable buttons
            self._set_buttons_enabled(True)

            # Prikaži statistiku
            message = f"📦 Grupni uvoz završen!\n\n"
            message += f"✅ Uspješno: {successful_imports}/{len(filepaths)} faktura\n"
            message += f"📋 Ukupno stavki: {len(all_items)}\n"
            message += f"⚖️  Ukupno bruto: {self._format_weight(total_bruto_kg)} kg\n"
            message += f"⚖️  Ukupno neto: {self._format_weight(total_neto_kg)} kg\n"

            if failed_imports:
                message += f"\n❌ Neuspješno: {len(failed_imports)} faktura\n"
                for filename, error in failed_imports[:3]:  # Prikaži prvih 3
                    message += f"   • {filename}: {error[:50]}...\n"

            QMessageBox.information(self, "Grupni uvoz", message)

            # Mark as changed
            self.data_changed.emit()
        else:
            QMessageBox.warning(
                self,
                "Grupni uvoz",
                "Nije uvezena nijedna stavka.\n\nProvjerite da li su fajlovi ispravni.",
            )

    def _on_import_progress(self, percentage: int):
        """Handle import progress update."""
        # Show progress bar if hidden
        if not self.progress_bar.isVisible():
            self.progress_bar.setVisible(True)

        # Update progress value
        self.progress_bar.setValue(percentage)

    def _cleanup_import_worker(self):
        """Clean up import worker to prevent memory leaks."""
        if self.import_worker:
            self.import_worker.deleteLater()
            self.import_worker = None

    def _extract_import_result_data(self, result):
        """Extract items and metadata from import result (HELPER METHOD)."""
        if isinstance(result, ImportResult):
            items = result.items
            bruto_kg = result.bruto_kg
            neto_kg = result.neto_kg
            invoice_name_from_result = result.invoice_name
            is_combined = result.is_combined
            import_type = getattr(result, "import_type", "invoice")
            has_origin_statement = getattr(result, "has_origin_statement", False)
            is_authorized_exporter = getattr(result, "is_authorized_exporter", False)
            exporter_name = getattr(result.exporter, "name", "") if result.exporter else ""
            importer_name = getattr(result.importer, "name", "") if result.importer else ""
        else:
            # Backward compatibility: result is just List[InvoiceLine]
            items = result
            bruto_kg = 0.0
            neto_kg = 0.0
            invoice_name_from_result = ""
            is_combined = False
            import_type = "invoice"
            has_origin_statement = False
            is_authorized_exporter = False
            exporter_name = ""
            importer_name = ""

        return (
            items,
            bruto_kg,
            neto_kg,
            invoice_name_from_result,
            is_combined,
            import_type,
            has_origin_statement,
            is_authorized_exporter,
            exporter_name,
            importer_name,
        )

    def _get_invoice_name(self, invoice_name_from_result: str) -> str:
        """Get invoice name from result or worker filepath (HELPER METHOD)."""
        invoice_name = getattr(self.import_worker, "filepath", "Unknown")
        invoice_name = Path(invoice_name).name if invoice_name else "Unknown"

        # Use invoice name from result if available
        if invoice_name_from_result:
            invoice_name = invoice_name_from_result

        return invoice_name

    def _track_file_type(self):
        """Track file type (Excel vs PDF) for statistics (HELPER METHOD)."""
        filepath = getattr(self.import_worker, "filepath", "")
        if filepath.lower().endswith((".xlsx", ".xls")):
            self.imported_excel_count += 1
        elif filepath.lower().endswith(".pdf"):
            self.imported_pdf_count += 1

    def _assign_invoice_name(self, items, invoice_name: str) -> None:
        for item in items:
            item.invoice_number = invoice_name

    def _normalize_item_tariffs(self, items) -> None:
        from importers.invoice_line_utils import normalize_tariff_number
        for item in items:
            code = item.tarifni_broj or ""
            if not code:
                continue
            normalized = normalize_tariff_number(code)
            # Excel gubi vodeće nule (npr. "03824999" → "3824999") — zfill vraća ih za 4-7 cifara
            if normalized and normalized.isdigit() and 4 <= len(normalized) < 8:
                normalized = normalized.zfill(8)
            item.tarifni_broj = normalized

    def _distribute_invoice_weights(self, items: list, bruto_kg: float, neto_kg: float) -> None:
        """Rasporedi ukupnu težinu fakture na stavke koje nemaju individualne težine.

        Delegira MassCalculator.calculate_masses — jedina centralna logika za raspodjelu.
        Raspodijela ide proporcionalno po kolicina; pokriva scenarije:
          - stavka bez obe težine → proporcionalno po kolicina
          - stavka sa bruto ali bez neto → izračunaj neto iz neto/bruto omjera
          - stavka sa neto ali bez bruto → izračunaj bruto iz bruto/neto omjera
        """
        if not items or (bruto_kg <= 0 and neto_kg <= 0):
            return
        from services.faktura.mass_calculator import MassCalculator
        MassCalculator.calculate_masses(items, bruto_kg, neto_kg)

    def _is_same_combined_invoice(self, invoice_name: str, is_combined: bool) -> bool:
        if not (self.last_invoice_name and invoice_name and is_combined):
            return False

        last_normalized = self.last_invoice_name.replace(" ", "").replace("-", "").lower()
        current_normalized = invoice_name.replace(" ", "").replace("-", "").lower()
        min_len = min(len(last_normalized), len(current_normalized))

        if min_len < 5:
            return False

        prefix_match = last_normalized[:min_len] == current_normalized[:min_len]
        substring_match = (
            last_normalized in current_normalized
            or current_normalized in last_normalized
        )
        return prefix_match or substring_match

    def _append_imported_files_message(self, message: str, min_files: int = 1) -> str:
        total_files = self.imported_excel_count + self.imported_pdf_count
        if total_files < min_files:
            return message

        message += f"📁 Uvezeni fajlovi:\n"
        if self.imported_excel_count > 0:
            message += f"- Excel: {self.imported_excel_count}\n"
        if self.imported_pdf_count > 0:
            message += f"- PDF: {self.imported_pdf_count}\n"
        if min_files > 1:
            message += f"- Ukupno: {total_files} fajlova\n\n"
        return message

    def _show_no_export_items(self, title: str) -> None:
        QMessageBox.information(
            self, title, "Nema stavki za export.\n\nPrvo učitajte fakturu."
        )

    @staticmethod
    def _normalize_partner(name: str) -> str:
        """Normalizuj naziv partnera za poređenje (mala slova, bez interpunkcije)."""
        name = name.lower().strip()
        name = re.sub(r"[.\-,;:'/\\()]", " ", name)
        name = re.sub(r"\b(doo|d\.o\.o|dd|a\.d|ad|llc|ltd|gmbh|srl)\b", "", name)
        return re.sub(r"\s+", " ", name).strip()

    def _check_partner_consistency(self, exporter_name: str, importer_name: str) -> bool:
        """
        Provjeri konzistentnost pošiljaoca/uvoznika sa prethodnim uvozom.

        Ako je ovo prvi uvoz koji nosi podatke o partneru — zapamti ih.
        Ako se razlikuju od zapamćenih za više od praga — upitaj korisnika.

        Vraća True ako treba nastaviti sa uvozom, False ako korisnik odbija.
        """
        def similar(a: str, b: str) -> bool:
            na, nb = self._normalize_partner(a), self._normalize_partner(b)
            if not na or not nb:
                return True  # Nema podataka — ne blokiraj
            # Token overlap: koliko zajedničkih tokena
            ta, tb = set(na.split()), set(nb.split())
            if not ta or not tb:
                return True
            overlap = len(ta & tb) / max(len(ta), len(tb))
            return overlap >= 0.6  # 60% zajedničkih tokena = isti partner

        # Ažuriraj expected ako je prazno (prvi uvoz)
        if exporter_name and not self._expected_exporter:
            self._expected_exporter = exporter_name
        if importer_name and not self._expected_importer:
            self._expected_importer = importer_name

        warnings = []

        if (exporter_name and self._expected_exporter
                and not similar(exporter_name, self._expected_exporter)):
            warnings.append(
                f"<b>Pošiljalac (izvoznik):</b><br>"
                f"&nbsp;&nbsp;Očekivano: <b>{self._expected_exporter}</b><br>"
                f"&nbsp;&nbsp;Uvezeno:&nbsp;&nbsp; <b>{exporter_name}</b>"
            )

        if (importer_name and self._expected_importer
                and not similar(importer_name, self._expected_importer)):
            warnings.append(
                f"<b>Uvoznik (primalac):</b><br>"
                f"&nbsp;&nbsp;Očekivano: <b>{self._expected_importer}</b><br>"
                f"&nbsp;&nbsp;Uvezeno:&nbsp;&nbsp; <b>{importer_name}</b>"
            )

        if not warnings:
            return True

        from gui.utils.safe_message_box import SafeMessageBox as QMessageBox
        msg = QMessageBox(self)
        msg.setWindowTitle("Upozorenje — Pogrešan partner?")
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(
            "<b>⚠️ Podaci o partnerima se razlikuju od prethodnog uvoza!</b><br><br>"
            + "<br><br>".join(warnings)
            + "<br><br>Da li želite nastaviti sa ovim uvozom?"
        )
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        msg.button(QMessageBox.StandardButton.Yes).setText("Nastavi svejedno")
        msg.button(QMessageBox.StandardButton.No).setText("Odustani od uvoza")

        if msg.exec() == QMessageBox.StandardButton.Yes:
            # Korisnik je svjestan — ažuriraj expected na nove
            if exporter_name:
                self._expected_exporter = exporter_name
            if importer_name:
                self._expected_importer = importer_name
            return True

        return False  # Odbijen uvoz

    def _reset_partner_expectations(self):
        """Resetuj zapamćene partnere (poziva se pri brisanju deklaracije)."""
        self._expected_exporter = ""
        self._expected_importer = ""

    def _format_weight(self, weight: float) -> str:
        """
        Format weight with thousands separator and without rounding.

        Examples:
            2.383 → "2.383"
            1234.56 → "1,234.56"
            1234567.891 → "1,234,567.891"
        """
        if weight == 0:
            return "0"

        # Convert to string to preserve all decimals
        weight_str = f"{weight:f}".rstrip("0").rstrip(".")

        # Split into integer and decimal parts
        if "." in weight_str:
            integer_part, decimal_part = weight_str.split(".")
        else:
            integer_part = weight_str
            decimal_part = ""

        # Add thousands separator to integer part
        integer_with_sep = f"{int(integer_part):,}"

        # Combine with decimal part
        if decimal_part:
            return f"{integer_with_sep}.{decimal_part}"
        else:
            return integer_with_sep

    def _accumulate_weights(
        self, bruto_kg: float, neto_kg: float, replace: bool = False
    ):
        """
        Accumulate weights from this import (HELPER METHOD).

        Args:
            bruto_kg: Bruto težina za dodati/zamijeniti
            neto_kg: Neto težina za dodati/zamijeniti
            replace: Ako je True, zamijeni postojeće težine (za kombinovanje parova).
                     Ako je False, saberi sa postojećim (default - normalno učitavanje).
        """
        if bruto_kg > 0 or neto_kg > 0:
            if replace:
                # Kombinovanje parova (Excel + PDF) - ZAMIJENI, ne sabirati!
                self.weight_manager.accumulated_bruto_kg = bruto_kg
                self.weight_manager.accumulated_neto_kg = neto_kg
            else:
                # Normalno učitavanje - saberi
                self.weight_manager.accumulated_bruto_kg += bruto_kg
                self.weight_manager.accumulated_neto_kg += neto_kg

            # Update input fields with accumulated weights
            # Format: hiljada separator + bez zaokruživanja (sve decimale sa fakture)
            self.input_bruto.setText(
                self._format_weight(self.weight_manager.accumulated_bruto_kg)
            )
            self.input_neto.setText(
                self._format_weight(self.weight_manager.accumulated_neto_kg)
            )

    def set_agent_mode(self, enabled: bool):
        """Postavi agent mod — nema blokirajućih GUI dijaloga za povlastice."""
        self._agent_mode = enabled

    def _suggest_preference_by_country(self, country_code: str, exporter_name: str = "") -> str:
        """
        Vrati povlasticu (Rub.36) na osnovu koda zemlje.
        
        Poboljšana verzija koja koristi istorijsko učenje ako je dostupno.
        
        Args:
            country_code: Kod zemlje (npr. 'RS', 'DE')
            exporter_name: Ime dobavljača (opcionalno)
        """
        # Prvo probaj istorijsko učenje ako imamo exportera
        if exporter_name and exporter_name.strip():
            try:
                # Koristi HistoricalLearningServiceSafe
                from services.agent.historical_learning_service_safe import enhance_preference_logic
                historical_pref = enhance_preference_logic(country_code, exporter_name)
                if historical_pref:
                    return historical_pref
            except Exception:
                # Silent fallback - nastavi sa hardcoded pravilima
                pass
        
        # FALLBACK: Hardcoded pravila (originalna logika)
        eu_countries = {
            'AT', 'BE', 'BG', 'CY', 'CZ', 'DE', 'DK', 'EE', 'ES', 'FI',
            'FR', 'GR', 'HR', 'HU', 'IE', 'IT', 'LT', 'LU', 'LV', 'MT',
            'NL', 'PL', 'PT', 'RO', 'SE', 'SI', 'SK',
        }
        cefta_countries = {'RS', 'BA', 'ME', 'MK', 'AL', 'XK', 'MD'}
        c = (country_code or '').upper()
        if c in eu_countries:
            return 'EUP'
        if c in cefta_countries:
            return 'CEFTAP'
        if c == 'TR':
            return 'TRP'
        if c == 'IR':
            return 'IRP'
        return ''

    def _auto_handle_povlastice_agent(self, items, has_origin_statement: bool) -> dict:
        """
        Agent mod: automatski postavi povlastice bez GUI dijaloga.

        PE2 slučaj (has_origin_statement=True):
          - Sve stavke sa has_origin_statement=True → povlastica po zemlji, dokument PE2.
        EUR1 slučaj (has_origin_statement=False):
          - Postavi povlasticu (EUP/CEFTAP/TRP) na osnovu zemlje.
          - eur1_number ostaje prazan — korisnik popunjava ručno.

        Returns:
            dict: {'pe2': int, 'eur1': int, 'eur1_pending': int}
        """
        updated_pe2 = 0
        updated_eur1 = 0
        eur1_pending = 0

        # Pokušaj da dobiješ exporter name iz fakture
        exporter_name = ""
        if hasattr(self.draft, 'exporter') and self.draft.exporter:
            exporter_name = self.draft.exporter
        elif self.draft.invoice_lines and hasattr(self.draft.invoice_lines[0], 'exporter'):
            exporter_name = self.draft.invoice_lines[0].exporter
        
        for item in self.draft.invoice_lines:
            item_has_statement = getattr(item, 'has_origin_statement', has_origin_statement)
            if item_has_statement:
                # PE2: izjava o porijeklu → samo postavi povlasticu po zemlji
                if not getattr(item, 'povlastica', None) and item.zemlja_porijekla:
                    item.povlastica = self._suggest_preference_by_country(item.zemlja_porijekla, exporter_name)
                updated_pe2 += 1
            elif item.zemlja_porijekla:
                # EUR1: nema izjave → postavi povlasticu, EUR1 broj fali
                pov = self._suggest_preference_by_country(item.zemlja_porijekla, exporter_name)
                if pov and not getattr(item, 'povlastica', None):
                    item.povlastica = pov
                    updated_eur1 += 1
                if pov and not getattr(item, 'eur1_number', None):
                    eur1_pending += 1

        logger.info(
            f"🤖 [agent] Auto-povlastice: PE2={updated_pe2}, EUR1={updated_eur1}, "
            f"EUR1_pending={eur1_pending}"
        )
        return {'pe2': updated_pe2, 'eur1': updated_eur1, 'eur1_pending': eur1_pending}

    def _should_show_eur1_dialog(self, items) -> bool:
        """
        Provjeri da li treba pokazati EUR.1 dialog.
        
        Uslovi:
        - PDF NEMA izjavu o poreklu (has_origin_statement = False)
        - Ima stavki sa zemljom porijekla
        """
        # Check if items have has_origin_statement = False
        if isinstance(items, ImportResult):
            items = items.items
        
        # ❌ NE otvaraj ako BILO KOJA stavka ima izjavu
        has_any_statement = any(
            hasattr(item, 'has_origin_statement') and item.has_origin_statement
            for item in items
        )
        
        if has_any_statement:
            return False  # Faktura ima izjavu → otvoriće se PE2 dialog
        
        # ✅ Otvaraj ako ima stavki bez izjave
        has_items_without_statement = any(
            hasattr(item, 'has_origin_statement') and 
            not item.has_origin_statement and 
            item.zemlja_porijekla
            for item in items
        )
        
        return has_items_without_statement
    
    def _should_show_pe2_dialog(self, items) -> bool:
        """
        Provjeri da li treba pokazati PE2 dialog.
        
        Uslovi:
        - PDF IMA izjavu o poreklu (has_origin_statement = True)
        """
        if isinstance(items, ImportResult):
            items = items.items
        
        # ✅ Otvaraj ako BILO KOJA stavka ima izjavu
        has_any_statement = any(
            hasattr(item, 'has_origin_statement') and item.has_origin_statement
            for item in items
        )
        
        return has_any_statement
    
    def _show_eur1_dialog(self):
        """Prikaži EUR.1 quick dialog (za fakture BEZ izjave)."""
        logger.debug(f"📋 [_show_eur1_dialog] Otvaranje EUR.1 dialoga...")
        dialog = Eur1QuickDialog(self.draft.invoice_lines, self)
        
        result = exec_dialog_preserving_geometry(dialog, self)
        logger.debug(f"📋 [_show_eur1_dialog] Dialog zatvoren, result={result}")
        
        # PySide6: exec() vraća int (1=Accepted, 0=Rejected)
        if result == 1:  # QDialog.Accepted
            logger.debug(f"📋 [_show_eur1_dialog] Korisnik kliknuo Primijeni")
            eur1_data = dialog.get_data()
            logger.debug(f"📋 [_show_eur1_dialog] eur1_data={eur1_data}")
            
            if eur1_data:
                # Primeni EUR.1 podatke (automatski postavlja PE1)
                updated_count = Eur1QuickDialog.apply_eur1_data(
                    self.draft.invoice_lines, eur1_data
                )
                
                # Validacija
                from services.preference_validator import PreferenceValidator
                validator = PreferenceValidator()
                
                # Pronađi stavke sa povlasticom a bez EUR.1
                missing_eur1 = validator.get_missing_eur1(self.draft.invoice_lines)
                
                if missing_eur1:
                    # Pitaj korisnika da li da automatski konvertuje u PE1
                    msg = QMessageBox()
                    msg.setIcon(QMessageBox.Warning)
                    msg.setWindowTitle("Validacija povlastica")
                    msg.setText(f"⚠️ {len(missing_eur1)} stavki ima povlasticu ali nema EUR.1 broj.")
                    msg.setInformativeText(
                        "Da li da automatski postavim PE1 (šifra za EUR.1 obrazac) "
                        "umesto trenutnih povlastica (CEFTAP/EUP/TRP)?"
                    )
                    msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                    msg.setDefaultButton(QMessageBox.Yes)
                    
                    if msg.exec() == QMessageBox.Yes:
                        # Automatska konverzija
                        fixed_count = validator.auto_fix_missing_eur1(self.draft.invoice_lines)
                        QMessageBox.information(
                            self,
                            "Konverzija izvršena",
                            f"✅ Konvertovano {fixed_count} stavki u PE1.\n\n"
                            f"Sada unesi EUR.1 brojeve za ove stavke."
                        )
                
                # Reload table to show changes
                self._load_data_from_draft()
                
                # Obavesti korisnika
                countries = ", ".join(eur1_data.keys())
                QMessageBox.information(
                    self,
                    "EUR.1 primenjen",
                    f"✅ Ažurirano {updated_count} stavki iz {len(eur1_data)} zemlje:\n"
                    f"   {countries}\n\n"
                    f"Za sve stavke je postavljena šifra PE1 (EUR.1 obrazac)."
                )
                
                # Mark dirty
                self._notify_data_changed()
    
    def _show_pe2_dialog(self, invoice_number: str = "", doc_code: str = "PE2"):
        """Prikaži PE2 ili PE3 quick dialog (za fakture SA izjavom)."""
        logger.debug(f"📋 [_show_pe2_dialog] Otvaranje {doc_code} dialoga...")
        dialog = PE2QuickDialog(self.draft.invoice_lines, self,
                                invoice_number=invoice_number, doc_code=doc_code)

        result = exec_dialog_preserving_geometry(dialog, self)
        logger.debug(f"📋 [_show_pe2_dialog] Dialog zatvoren, result={result}")

        if result == 1:
            pe2_data = dialog.get_data()
            logger.debug(f"📋 [_show_pe2_dialog] pe2_data={pe2_data}")

            if pe2_data:
                updated_count = PE2QuickDialog.apply_pe2_data(
                    self.draft.invoice_lines, pe2_data
                )

                self._load_data_from_draft()

                countries = ", ".join(pe2_data.keys())
                QMessageBox.information(
                    self,
                    f"{doc_code} primijenjen",
                    f"✅ Ažurirano {updated_count} stavki iz {len(pe2_data)} zemlje:\n"
                    f"   {countries}\n\n"
                    + ("Za sve stavke je postavljena šifra PE3 (ovlašteni izvoznik)."
                       if doc_code == 'PE3' else
                       "Za sve stavke je postavljena šifra PE2 (izjava o poreklu na fakturi).")
                )

                self._notify_data_changed()

    def _on_import_finished(self, result):
        """Handle successful import.

        Args:
            result: Either ImportResult (with metadata) or List[InvoiceLine]
        """
        try:
            # Hide progress bar
            self.progress_bar.setVisible(False)
            self.progress_bar.setValue(0)

            # Extract items and metadata from result (REFACTORED to use helper methods)
            (
                items,
                bruto_kg,
                neto_kg,
                invoice_name_from_result,
                is_combined,
                import_type,
                has_origin_statement,
                is_authorized_exporter,
                exporter_name,
                importer_name,
            ) = self._extract_import_result_data(result)

            # Get invoice name
            invoice_name = self._get_invoice_name(invoice_name_from_result)

            # Track file type
            self._track_file_type()

            # Provjeri konzistentnost pošiljaoca/uvoznika
            if not self._check_partner_consistency(exporter_name, importer_name):
                # Korisnik je odbio uvoz — očisti progress i izađi
                self.progress_bar.setVisible(False)
                return

            # VAŽNO: NE akumuliraj težine ovdje - preuranjeno!
            # Težine će biti akumulirane kasnije, nakon što se utvrdi da li je isti invoice

            # NOVI PRISTUP: NE koristiti Assembly sistem za obične importe!
            # Assembly se koristi SAMO kada korisnik eksplicitno učita Master Listu preko menija.
            # Za Blagić i druge kompletne fakture, direktno dodaj u draft i održi redoslijed.

            # Normalizuj tarifne brojeve na 8 cifara (Excel može izgubiti vodeće nule)
            self._normalize_item_tariffs(items)
            # Rasporedi težinu fakture na stavke (ako parser nije dao per-line težine)
            self._distribute_invoice_weights(items, bruto_kg, neto_kg)
            # Zapamti per-invoice težinu za dugme 'Izračunaj mase'
            if (bruto_kg > 0 or neto_kg > 0) and invoice_name:
                self.draft.invoice_weights[normalize_invoice_key(invoice_name)] = (
                    bruto_kg,
                    neto_kg,
                )

            # Check: Da li je Assembly sistem aktivan (korisnik učitao Master Listu)?
            using_assembly = self.assembly.master_list_loaded

            if using_assembly:
                # Assembly sistem je aktivan - matchuj sa master listom
                # (Ovo se dešava SAMO ako je korisnik eksplicitno učitao Master Listu preko menija)
                # Postavi invoice_number za svaku stavku
                self._assign_invoice_name(items, invoice_name)
                
                matched, unmatched, unmatched_names = self.assembly.add_invoice(
                    items, invoice_name
                )

                # Update draft from assembly
                draft = self.assembly.create_draft()
                self.draft.invoice_lines = draft.invoice_lines

                # Reload table
                self._load_data_from_draft()

                # Ažuriraj težine u toolbaru
                self._accumulate_weights(bruto_kg, neto_kg)

                # Enable buttons
                self._set_buttons_enabled(True)

                # Get completion status
                status = self.assembly.get_completion_status()

                # Build message with match statistics
                message = f"Faktura '{invoice_name}' dodana u assembly.\n\n"
                message += f"Match rezultati:\n"
                message += f"- Matched: {matched} stavki\n"
                message += f"- Unmatched: {unmatched} stavki\n\n"

                # Add weight information if available
                if bruto_kg > 0 or neto_kg > 0:
                    message += f"Težine sa fakture '{invoice_name}':\n"
                    message += f"- Bruto: {bruto_kg:.3f} kg\n"
                    message += f"- Neto: {neto_kg:.3f} kg\n\n"

                # Show actual draft weights (read from input fields - sada ispravno ažurirani)
                try:
                    current_bruto = self._parse_weight_input(
                        self.input_bruto.text() or "0"
                    )
                    current_neto = self._parse_weight_input(
                        self.input_neto.text() or "0"
                    )
                    message += f"Ukupno u draft-u (nakon matching-a):\n"
                    message += f"- Bruto: {current_bruto:.3f} kg\n"
                    message += f"- Neto: {current_neto:.3f} kg\n\n"
                except (ValueError, TypeError):
                    pass  # Skip if cannot parse

                # Obavijesti korisnika gdje će vidjeti unmatched stavke
                if unmatched > 0:
                    message += "⚠️ Nepodudarajuće stavke su dodane u tabelu i označene CRVENOM bojom.\n"
                    message += "Provjerite ih i ručno popunite nedostajuća polja (tarifni broj, zemlja).\n\n"

                message += f"Status:\n"
                message += f"- Ukupno stavki: {status['total']}\n"
                message += f"- Kompletno: {status['complete']} ({status['completion_percentage']:.1f}%)\n"
                message += f"- Uvezene fakture: {status['imported_invoices_count']}\n\n"

                message = self._append_imported_files_message(message)

                # Show message box (warning if unmatched, info otherwise)
                if unmatched > 0:
                    QMessageBox.warning(self, "Uvoz uspješan sa upozorenjima", message)
                else:
                    QMessageBox.information(self, "Uvoz uspješan", message)

            else:
                # OBIČNI IMPORT - direktno dodaj u draft BEZ Assembly matching-a
                # Ovo održava redoslijed iz fakture i omogućava učitavanje više različitih faktura
                previous_count = len(self.draft.invoice_lines)

                # Safety check: ensure items is a list
                if isinstance(items, ImportResult):
                    items = items.items

                # === JEDNOSTAVNA LOGIKA: Matching se dešava u import_service.py ===
                # GUI samo provjerava da li je is_combined=True i zamijenjuje posljednji import

                is_same_invoice = self._is_same_combined_invoice(
                    invoice_name, is_combined
                )

                if is_combined and previous_count > 0 and is_same_invoice:
                    # REPLACE posljednji import (isti par, već kombіnovano u import_service)
                    # Postavi invoice_number za nove stavke
                    self._assign_invoice_name(items, invoice_name)
                    
                    keep_count = previous_count - self.last_import_count
                    self.draft.invoice_lines = (
                        self.draft.invoice_lines[:keep_count] + items
                    )
                    logger.info(
                        f"🔗 Kombinovani import - zamijenjeno {self.last_import_count} stavki sa {len(items)} stavki"
                    )
                else:
                    # EXTEND - dodaj na kraj (novi import ili nekombіnovani)
                    # Postavi invoice_number za svaku stavku
                    self._assign_invoice_name(items, invoice_name)
                    
                    self.draft.invoice_lines.extend(items)
                    if is_combined:
                        logger.info(
                            f"🔗 Kombinovani import (drugi par) - dodato {len(items)} stavki"
                        )
                    else:
                        logger.info(f"📝 Obični import - dodato {len(items)} stavki")

                # AKUMULIRAJ težine - ALI SAMO ako NIJE isti invoice!
                # Ako je isti invoice (Excel matchuje PDF), težine su već dodane iz PDF-a
                if is_same_invoice:
                    logger.debug(f"\n⏭️ SKIP ACCUMULATE (isti invoice - već akumulirano iz PDF-a)")
                    logger.debug(f"   Invoice: '{invoice_name}'")
                    logger.debug(f" accumulated_bruto={self.weight_manager.accumulated_bruto_kg:.2f}, accumulated_neto={self.weight_manager.accumulated_neto_kg:.2f} (OSTAJE ISTO)")
                    logger.debug(f"=" * 80)
                else:
                    # Novi invoice - saberi težine
                    logger.debug(f"\n💰 ACCUMULATE WEIGHTS (novi invoice):")
                    logger.debug(f"   Invoice: '{invoice_name}'")
                    logger.debug(f" Import težine: bruto={bruto_kg:.2f}, neto={neto_kg:.2f}")
                    logger.debug(f" PRIJE: accumulated_bruto={self.weight_manager.accumulated_bruto_kg:.2f}, accumulated_neto={self.weight_manager.accumulated_neto_kg:.2f}")

                    self._accumulate_weights(
                        bruto_kg, neto_kg, replace=False
                    )  # Uvijek saberi, ne zamijeni!

                    logger.debug(f" POSLIJE: accumulated_bruto={self.weight_manager.accumulated_bruto_kg:.2f}, accumulated_neto={self.weight_manager.accumulated_neto_kg:.2f}")
                    logger.debug(f"=" * 80)

                # Zapamti za sljedeći import
                self.last_invoice_name = invoice_name
                self.last_import_count = len(items)

                total_count = len(self.draft.invoice_lines)

                # Reload table
                self._load_data_from_draft()

                # EUR.1 / PE2 DIALOG - Pitaj korisnika na osnovu toga da li faktura ima izjavu
                logger.info(f"🔍 [dialog check] has_origin_statement={has_origin_statement}, agent_mode={self._agent_mode}, items={len(items)}")
                if self._agent_mode:
                    # Agent mod: auto-postavi povlastice, ali EUR1 broj zahtijeva korisnika
                    logger.info(f"🤖 [dialog check] Agent mod — auto-handle povlastice")
                    result = self._auto_handle_povlastice_agent(items, has_origin_statement)
                    if result['pe2'] > 0:
                        logger.info(f"🤖 PE2 auto-postavljeno za {result['pe2']} stavki")
                    if result['eur1'] > 0:
                        logger.info(f"🤖 EUR1 povlastica auto-postavljena za {result['eur1']} stavki, {result['eur1_pending']} čeka EUR1 broj")
                    self._load_data_from_draft()
                    # Ako ima stavki koje čekaju EUR1 broj → prikaži dialog
                    if result.get('eur1_pending', 0) > 0 and self._should_show_eur1_dialog(items):
                        logger.info(f"🤖 → EUR1 pending={result['eur1_pending']}: otvaram EUR.1 dialog")
                        self._show_eur1_dialog()
                elif has_origin_statement:
                    from gui.tabs.agent.services.import_pipeline_service import _origin_dialog_type
                    dialog_tip = _origin_dialog_type(items, has_origin_statement, is_authorized_exporter)
                    if dialog_tip == 'pe3':
                        logger.info("🔍 [dialog check] → ovlašteni izvoznik → PE3 dialog")
                        self._show_pe2_dialog(invoice_name, doc_code='PE3')
                    elif dialog_tip == 'pe2':
                        logger.info(f"🔍 [dialog check] → PE2 dialog")
                        self._show_pe2_dialog(invoice_name, doc_code='PE2')
                    else:
                        val = sum(getattr(i, 'iznos', 0.0) for i in items)
                        logger.info(f"🔍 [dialog check] → iznos={val:.2f}€ > 6000 → EUR.1 dialog")
                        self._show_eur1_dialog()
                elif self._should_show_eur1_dialog(items):
                    # ❌ Faktura NEMA izjavu → EUR.1 dialog
                    logger.info(f"🔍 [dialog check] → otvaram EUR.1 dialog")
                    self._show_eur1_dialog()
                else:
                    logger.info(f"🔍 [dialog check] → nema dijaloga")

                # VAŽNO: Ažuriraj ukupne težine u toolbar input poljima
                # Ovo sabira sve bruto/neto iz invoice_lines i prikazuje u poljima
                self._update_weight_totals()

                # Enable buttons
                self._set_buttons_enabled(True)

                # Build success message
                message = (
                    f"Uspješno uvezeno {len(items)} stavki iz '{invoice_name}'.\n\n"
                )

                if previous_count > 0:
                    message += f"📊 Akumulirano:\n"
                    message += f"- Prethodno: {previous_count} stavki\n"
                    message += f"- Nova faktura: {len(items)} stavki\n"
                    message += f"- Ukupno: {total_count} stavki\n\n"

                # Add weight information if available
                if bruto_kg > 0 or neto_kg > 0:
                    message += f"Težine sa fakture '{invoice_name}':\n"
                    message += f"- Bruto: {bruto_kg:.3f} kg\n"
                    message += f"- Neto: {neto_kg:.3f} kg\n\n"
                    message += f"Akumulirano ukupno:\n"
                    message += (
                        f"- Bruto: {self.weight_manager.accumulated_bruto_kg:.3f} kg\n"
                    )
                    message += (
                        f"- Neto: {self.weight_manager.accumulated_neto_kg:.3f} kg\n\n"
                    )

                message = self._append_imported_files_message(message, min_files=2)

                # Dodaj info poruku o redoslijedu
                if is_combined:
                    message += f"🔗 Redoslijed stavki održan iz PDF fakture."
                elif import_type == "loren_excel":
                    message += f"⚠️  LOREN EXCEL: Iznosi (cijene) dolaze iz PDF-a!\n"
                    message += f"   Uvezite PDF fajl sa istim brojem fakture da biste dobili\n"
                    message += f"   ispravne iznose. Trenutno su svi iznosi = 0."
                else:
                    message += f"💡 Možete nastaviti sa uvozom dodatnih faktura.\n"
                    message += f"   Svaka faktura će biti dodana u draft održavajući svoj redoslijed."

                # Show success message
                QMessageBox.information(self, "Uvoz uspješan", message)

            # Update status bar
            self._update_status_bar()

            # Mark as dirty
            if self.on_dirty:
                self.on_dirty()

            self.data_changed.emit()
        finally:
            # Cleanup worker to prevent memory leak
            self._cleanup_import_worker()

    def _on_import_error(self, error_message: str):
        """Handle import error."""
        self.error_handler.handle_import_error(Exception(error_message))

        # Cleanup worker to prevent memory leak
        self._cleanup_import_worker()

    def _on_add_item(self):
        # Calculate next line number
        next_line_no = len(self.draft.invoice_lines) + 1

        # Open dialog
        dialog = AddItemDialog(self, next_line_no=next_line_no)

        if exec_dialog_preserving_geometry(dialog, self) == AddItemDialog.Accepted:
            new_item = dialog.get_item()

            if new_item:
                # Add to draft
                self.draft.invoice_lines.append(new_item)

                # Add to table
                row = self.table.rowCount()
                self.table.insertRow(row)
                self._add_item_to_table(row, new_item)

                # Update status bar
                self._update_status_bar()

                # Mark as dirty
                self._notify_data_changed()

    def _on_delete_item(self):
        """Handle Delete button click."""
        current_row = self.table.currentRow()

        if current_row < 0:
            QMessageBox.warning(
                self, "Nema odabrane stavke", "Molimo odaberite stavku za brisanje."
            )
            return

        reply = QMessageBox.question(
            self,
            "Potvrda brisanja",
            "Da li ste sigurni da želite obrisati odabranu stavku?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            # Get the item being deleted (for weight calculation)
            deleted_item = self.draft.invoice_lines[current_row]
            deleted_bruto = deleted_item.bruto_kg or 0.0
            deleted_neto = deleted_item.neto_kg or 0.0
            
            # Remove from draft
            del self.draft.invoice_lines[current_row]

            # Reload table
            self._load_data_from_draft()

            # Update weight inputs (subtract deleted item weights)
            self._update_weights_after_deletion(deleted_bruto, deleted_neto)

            # Update status bar
            self._update_status_bar()

            # Mark as dirty
            if self.on_dirty:
                self.on_dirty()

            self.data_changed.emit()

    def _on_clear_all(self):
        """Handle Clear All button click."""
        item_count = len(self.draft.invoice_lines)

        if item_count == 0:
            return

        reply = QMessageBox.question(
            self,
            "Potvrda brisanja",
            f"Da li ste sigurni da želite obrisati SVE stavke?\n\nUkupno stavki: {item_count}\n\nOva akcija se ne može poništiti!",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            # Clear all items
            self.draft.invoice_lines.clear()

            # Reset accumulated weights
            self.weight_manager.accumulated_bruto_kg = 0.0
            self.weight_manager.accumulated_neto_kg = 0.0
            self.input_bruto.clear()
            self.input_neto.clear()

            # Reset file counters
            self.imported_excel_count = 0
            self.imported_pdf_count = 0

            # Reset last invoice name
            self.last_invoice_name = None

            # Reset zapamćenih partnera
            self._reset_partner_expectations()

            # Clear assembly
            self.assembly = DeclarationAssembly()

            # Reload table
            self._load_data_from_draft()

            # Update status bar
            self._update_status_bar()

            # Mark as dirty
            if self.on_dirty:
                self.on_dirty()

            self.data_changed.emit()

    def _on_create_naimenovanja(self, auto=False):
        """Handle Create Naimenovanja button click.

        Args:
            auto: Ako True, preskoči sve dijaloge (za punu automatizaciju).
        """
        geometry_state = capture_window_geometry(self) if not auto else None
        from services.create_naimenovanja_service import CreateNaimenovanjaService

        try:
            logger.debug(f"\n{'='*80}")
            logger.debug(f"🔍 [_on_create_naimenovanja] START (auto={auto})")
            logger.debug(f"🔍 [_on_create_naimenovanja] Broj invoice_lines: {len(self.draft.invoice_lines)}")

            if not self.draft.invoice_lines:
                if not auto:
                    QMessageBox.warning(
                        self,
                        "Nema faktura",
                        "Molimo prvo uvezite fakture (PDF/Excel/XML) prije kreiranja naimenovanja.",
                    )
                return

            # Upozori ako ima stavki bez tarifnog broja (samo u interaktivnom modu)
            bez_tarife = [l for l in self.draft.invoice_lines if not getattr(l, 'tarifni_broj', None)]
            if bez_tarife and not auto:
                odgovor = QMessageBox.warning(
                    self,
                    "Upozorenje — nedostaje tarifni broj",
                    f"⚠️ {len(bez_tarife)} od {len(self.draft.invoice_lines)} stavki nema tarifni broj!\n\n"
                    f"Grupiranje naimensovnja neće biti tačno — stavke bez tarife bit će "
                    f"spojene u JEDNO naimensovnje bez obzira na vrstu robe.\n\n"
                    f"Preporučuje se prvo popuniti sve tarifne brojeve (dugme 'Auto-popuni tarifne'), "
                    f"pa tek onda kreirati naimensovnja.\n\n"
                    f"Nastavi svejedno?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if odgovor == QMessageBox.No:
                    return

            # Potvrda (samo u interaktivnom modu)
            if not auto:
                reply = QMessageBox.question(
                    self,
                    "Kreiraj Naimenovanja",
                    f"Kreirati naimenovanja iz {len(self.draft.invoice_lines)} stavki?\n\n"
                    f"Naimenovanja će biti grupisana po:\n"
                    f"  • Tarifa (33)\n"
                    f"  • Zemlja porijekla (34)\n"
                    f"  • Povlastica (36)\n\n"
                    f"Postojeća naimenovanja će biti obrisana!",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if reply == QMessageBox.No:
                    logger.debug(f"🔍 [_on_create_naimenovanja] Korisnik odustao")
                    return

            # Create service
            service = CreateNaimenovanjaService(self.draft)

            # Use SMART_GROUP strategy (recommended)
            logger.debug(f"🔍 [_on_create_naimenovanja] Pozivanje create_smart_group()...")
            count = service.create_smart_group()
            split_info = getattr(service, "last_split_info", None)
            logger.info(f"✅ [_on_create_naimenovanja] Kreirano {count} naimenovanja")

            # Show success message (samo u interaktivnom modu)
            if not auto:
                if split_info and split_info.overflow_count > 0:
                    QMessageBox.warning(
                        self,
                        "ASYCUDA limit — 99 naimenovanja",
                        f"ASYCUDA World u BiH podržava najviše 99 naimenovanja po deklaraciji.\n\n"
                        f"Ukupno je formirano {split_info.total_count} naimenovanja.\n"
                        f"Trenutna deklaracija je ograničena na prvih {split_info.current_count}.\n"
                        f"Preostalih {split_info.overflow_count} naimenovanja je pripremljeno za sljedeću deklaraciju.\n\n"
                        f"Završite i izvezite ovu deklaraciju, pa će aplikacija ponuditi nastavak sa ostatkom.",
                    )
                else:
                    QMessageBox.information(
                        self,
                        "Uspjeh!",
                        f"✅ Kreirano {count} naimenovanja iz {len(self.draft.invoice_lines)} stavki!\n\n"
                        f"Naimenovanja su grupisana po tarifi, zemlji porijekla i povlastici.\n\n"
                        f"Možete ih pregledati i editovati u tabu 'Naimenovanja'.",
                    )

            # Mark as dirty
            if self.on_dirty:
                self.on_dirty()

            self.data_changed.emit()

            # Sinhronizuj PE1/PE2/PE3 iz attached_document4 u header_attached_documents
            # Vidi docs/sections/pe-rub44-4.md
            self._sync_pe_docs_to_header()
            self._sync_inspection_docs_to_header()

            # Auto-učenje: sačuvaj mappinge u bazu znanja — docs/architecture/TARIFF_FACADE_REFACTORING.md
            try:
                from services.tariff_facade import TariffFacade
                TariffFacade.get_instance().learn_from_draft(self.draft.invoice_lines)
            except Exception as e:
                logger.warning("Auto-učenje tarifa nije uspjelo: %s", e)

            # Reload table to show assigned naimenovanje numbers in column
            logger.debug(f"🔍 [_on_create_naimenovanja] Pozivanje _load_data_from_draft()...")
            self._set_weight_inputs_from_draft()
            self._load_data_from_draft()
            logger.info(f"✅ [_on_create_naimenovanja] Faktura tab ažuriran")

            # Notify Naimenovanja Tab to reload data
            # Ovo takođe ažurira Zaglavlje tab (rubrika 6 - broj paketa)
            logger.debug(f"🔍 [_on_create_naimenovanja] Pozivanje _reload_naimenovanja_tab()...")
            self._reload_naimenovanja_tab()
            logger.info(f"✅ [_on_create_naimenovanja] Naimenovanja i Zaglavlje tab ažurirani")

            # Automatska provjera popunjenosti naimenovanja u agent panelu
            # Emituje signal — agent_tab controller ga sluša i poziva
            # auto_provjeri_naimenovanja() sa kratkim rezimeom.
            # Vidi: docs/decisions/002-tool-dispatcher-integration.md
            try:
                self.naimenovanja_created.emit()
            except Exception as e:
                logger.warning(f"⚠️ [_on_create_naimenovanja] Signal naimenovanja_created nije uspio: {e}")

            # Clear import service memory (za auto-kombinovanje Loren parova)
            # Ovo osigurava da sljedeći import počinje sa čistom memorijom
            try:
                from services.import_service import get_import_service

                service = get_import_service()
                service.clear_memory()
            except Exception as e:
                pass  # Ne blokiraj ako clear_memory ne uspije

        except Exception as e:
            QMessageBox.critical(
                self, "Greška", f"Greška prilikom kreiranja naimenovanja:\n\n{str(e)}"
            )
        finally:
            restore_window_geometry_queued(geometry_state)

    def _set_weight_inputs_from_draft(self):
        total_bruto = sum(getattr(line, "bruto_kg", 0.0) or 0.0 for line in self.draft.invoice_lines)
        total_neto = sum(getattr(line, "neto_kg", 0.0) or 0.0 for line in self.draft.invoice_lines)
        self.weight_manager.accumulated_bruto_kg = total_bruto
        self.weight_manager.accumulated_neto_kg = total_neto
        self.input_bruto.setText(self._format_weight(total_bruto) if total_bruto > 0 else "")
        self.input_neto.setText(self._format_weight(total_neto) if total_neto > 0 else "")

    def _reload_naimenovanja_tab(self):
        """Helper method to reload Naimenovanja Tab after creating items.
        
        Also updates Zaglavlje tab (rubrika 6 - broj paketa) by:
        1. Calling _sync_header_packages() to update draft.uk_paketa
        2. Calling load_from_draft() on zaglavlje_tab to refresh UI
        """
        try:
            # Find parent window (MainWindow)
            main_window = self.window()
            
            # 🔍 Debug: log main_window discovery
            logger.debug(f"\n🔍 [_reload_naimenovanja_tab] main_window: {main_window}")

            # Find Naimenovanja Tab by attribute name
            if hasattr(main_window, "naimenovanje_tab"):
                logger.debug(f"🔍 [_reload_naimenovanja_tab] Found naimenovanje_tab, calling reload_data()")
                main_window.naimenovanje_tab.reload_data()
                
                # 🔍 Debug: log reload success
                logger.info(f"✅ [_reload_naimenovanja_tab] Naimenovanja tab reloaded successfully")
                
                # 📦 Sync header packages (updates draft.uk_paketa from naimenovanja items)
                logger.debug(f"🔍 [_reload_naimenovanja_tab] Calling _sync_header_packages()...")
                if hasattr(main_window.naimenovanje_tab, "_sync_header_packages"):
                    main_window.naimenovanje_tab._sync_header_packages()
                    logger.info(f"✅ [_reload_naimenovanja_tab] _sync_header_packages() called - draft.uk_paketa = '{self.draft.uk_paketa}'")
                else:
                    logger.warning(f"⚠️ [_reload_naimenovanja_tab] _sync_header_packages() method not found!")
                
                # 🔄 Update Zaglavlje tab (rubrika 6 - broj paketa)
                logger.debug(f"🔍 [_reload_naimenovanja_tab] Updating Zaglavlje tab...")
                if hasattr(main_window, "zaglavlje_tab"):
                    main_window.zaglavlje_tab.load_from_draft(self.draft)
                    logger.info(f"✅ [_reload_naimenovanja_tab] Zaglavlje tab updated from draft")
                else:
                    logger.warning(f"⚠️ [_reload_naimenovanja_tab] zaglavlje_tab not found!")
            else:
                logger.warning(f"⚠️ [_reload_naimenovanja_tab] naimenovanje_tab not found!")
        except Exception as e:
            logger.error(f"❌ [_reload_naimenovanja_tab] Error: {e}")
            pass

    def _on_validate_all(self, auto=False):
        """Handle Validate button click."""
        if not self.draft.invoice_lines:
            if not auto:
                QMessageBox.information(self, "Nema stavki", "Nema stavki za validaciju.")
            return

        try:
            # Sync table data to draft first (in case user edited cells)
            self._sync_table_to_draft()

            # Revalidate all rows
            for row in range(self.table.rowCount()):
                item = self.draft.invoice_lines[row]
                self._validate_and_color_row(row, item)

            # Force table repaint to show updated colors
            self.table.viewport().update()

            # Update status bar
            self._update_status_bar()

            # Count results iz cache-a (već ažuriran u prethodnoj petlji)
            error_count = self.validation_cache.get_error_count()
            warning_count = self.validation_cache.get_warning_count()
            valid_count = self.validation_cache.get_valid_count()

            # Show summary
            message = "╔══════════════════════════════════════╗\n"
            message += "║      REZULTAT VALIDACIJE             ║\n"
            message += "╠══════════════════════════════════════╣\n"
            message += f"║  Ukupno stavki: {len(self.draft.invoice_lines):>4}                ║\n"
            message += f"║  ✅ Validne:     {valid_count:>4}                ║\n"
            message += f"║  ❌ Nevažeće:    {error_count:>4}                ║\n"
            message += "╠══════════════════════════════════════╣\n"
            message += f"║  🔴 Greške:      {error_count:>4}                ║\n"
            message += f"║  🟡 Upozorenja:  {warning_count:>4}                ║\n"
            message += "╚══════════════════════════════════════╝\n"

            if not auto:
                if error_count > 0:
                    message += "\n⚠️  NAPOMENA:\nProvjerite crveno označene stavke!"
                    QMessageBox.warning(self, "Validacija", message)
                elif warning_count > 0:
                    message += "\n💡 SAVJET:\nProvjerite žuto označene stavke."
                    QMessageBox.information(self, "Validacija", message)
                else:
                    message += "\n🎉 SVE STAVKE SU VALIDNE!"
                    QMessageBox.information(self, "Validacija", message)

            # Istorijska validacija tarifnih brojeva (iz XML deklaracija)
            self._run_historical_tariff_validation(modal=auto)

        except Exception as e:
            self.error_handler.handle_validation_error(e)

    def _run_historical_tariff_validation(self, modal=False):
        """Pokreni istorijsku validaciju tarifa i prikaži dialog ako ima prijedloga."""
        try:
            from services.agent.validation.historical_tariff_search_service import (
                HistoricalTariffSearchService,
            )
            from gui.tabs.agent.widgets.tariff_validation_dialog import TariffValidationDialog

            izvoznik = getattr(self.draft, 'izvoznik_naziv', '') or ''
            primalac = getattr(self.draft, 'primalac_naziv', '') or ''

            svc = HistoricalTariffSearchService()
            matches = svc.validate_lines(
                self.draft.invoice_lines,
                izvoznik_naziv=izvoznik,
                uvoznik_naziv=primalac,
            )

            if not matches:
                return  # Nema prijedloga — tiho

            dlg = TariffValidationDialog(matches, parent=self.window())

            def _on_accepted(changes: list):
                self.table.blockSignals(True)
                try:
                    for idx, tarif in changes:
                        if 0 <= idx < len(self.draft.invoice_lines):
                            self.draft.invoice_lines[idx].tarifni_broj = tarif
                            self._set_table_item(idx, 4, tarif, align=Qt.AlignCenter)
                            self._validate_and_color_row(idx, self.draft.invoice_lines[idx])
                finally:
                    self.table.blockSignals(False)
                self.table.viewport().update()
                self._update_status_bar()

            dlg.tariffs_accepted.connect(_on_accepted)
            if modal:
                exec_dialog_preserving_geometry(dlg, self)
            else:
                show_dialog_preserving_geometry(dlg, self)

        except Exception as e:
            logger.warning("Istorijska validacija greška: %s", e)

    def _update_weight_totals(self):
        """
        Ažuriraj toolbar input polja sa akumuliranim težinama.

        VAŽNO: Koristi accumulated_bruto_kg i accumulated_neto_kg koje postavi
        _accumulate_weights() iz ImportResult-a, NE sabira iz stavki!

        Stavke mogu imati neto=0 (Excel nema neto po stavkama), ali ImportResult
        ima ukupan neto koji je već akumuliran u accumulated_neto_kg.
        """
        # Koristi akumulirane težine iz ImportResult-a (3 decimale za preciznost)
        bruto_text = (
            f"{self.weight_manager.accumulated_bruto_kg:,.3f}"
            if self.weight_manager.accumulated_bruto_kg > 0
            else ""
        )
        neto_text = (
            f"{self.weight_manager.accumulated_neto_kg:,.3f}"
            if self.weight_manager.accumulated_neto_kg > 0
            else ""
        )

        self.input_bruto.setText(bruto_text)
        self.input_neto.setText(neto_text)

    def _on_calculate_masses(self, auto=False):
        """Handle Calculate Masses button click - proporcionalno raspodjeli težine."""
        logger.debug("\n" + "=" * 80)
        logger.debug("⚖️  IZRAČUNAJ MASE - START")
        logger.debug("=" * 80)

        # Get total bruto and neto from input fields
        try:
            bruto_total_text = self.input_bruto.text().strip()
            neto_total_text = self.input_neto.text().strip()

            logger.debug(f"📊 Toolbar polja:")
            logger.debug(f"   Bruto: '{bruto_total_text}'")
            logger.debug(f"   Neto: '{neto_total_text}'")

            if not bruto_total_text and not neto_total_text:
                logger.error("   ❌ OBA polja prazna - prikazujem warning")
                if not auto:
                    QMessageBox.warning(
                        self,
                        "Nedostaju težine",
                        "Unesite ukupnu bruto i/ili neto težinu sa fakture.",
                    )
                return

            # Remove thousands separators (comma) before parsing
            # Format is: 1,234.567 (comma = thousands, dot = decimal)
            bruto_total = (
                float(bruto_total_text.replace(",", "")) if bruto_total_text else 0.0
            )
            neto_total = (
                float(neto_total_text.replace(",", "")) if neto_total_text else 0.0
            )

            logger.debug(f"\n📐 Parsirano:")
            logger.debug(f"   bruto_total = {bruto_total:.2f} kg")
            logger.debug(f"   neto_total = {neto_total:.2f} kg")

            if bruto_total <= 0 and neto_total <= 0:
                if not auto:
                    QMessageBox.warning(
                        self, "Neispravne težine", "Težine moraju biti veće od nule."
                    )
                return

        except ValueError as e:
            logger.error(f"❌ ValueError: {e}")
            if not auto:
                QMessageBox.critical(
                    self,
                    "Greška",
                    "Neispravna vrijednost težine. Koristite brojeve (npr. 1234.56).",
                )
            return

        logger.debug(f"\n🔍 Ukupno stavki u draft-u: {len(self.draft.invoice_lines)}")

        from services.faktura.mass_calculator import MassCalculator

        invoice_groups, no_invoice_lines, invoice_labels = group_lines_by_invoice(
            self.draft.invoice_lines
        )
        invoice_weights = normalized_invoice_weights(self.draft.invoice_weights)

        total_updated = 0
        total_skipped = 0
        no_weight_invoices = []
        fallback_skipped = 0

        # Per-invoice raspodjela težine
        for inv_key, lines in invoice_groups.items():
            if inv_key in invoice_weights:
                inv_bruto, inv_neto = invoice_weights[inv_key]
                stats = MassCalculator.calculate_masses(lines, inv_bruto, inv_neto)
                total_updated += stats["updated"]
                total_skipped += stats["skipped"]
                label = invoice_labels.get(inv_key, inv_key)
                logger.debug(
                    f"   ⚖️ [{label}]: {stats['updated']} ažurirano, "
                    f"{stats['skipped']} preskočeno "
                    f"({inv_bruto:.3f}/{inv_neto:.3f} kg)"
                )
            else:
                no_weight_invoices.append(inv_key)
                total_skipped += len(lines)
                label = invoice_labels.get(inv_key, inv_key)
                logger.debug(f"   ⚠️ [{label}]: nema sačuvane težine — preskočeno")

        # Fallback: stavke bez invoice_number → koristi toolbar total
        if no_invoice_lines:
            proceed_with_fallback = True
            if is_suspicious_fallback(invoice_groups, no_invoice_lines):
                proceed_with_fallback = False
                if not auto:
                    response = QMessageBox.question(
                        self,
                        "Stavke bez broja fakture",
                        f"Pronađeno je {len(no_invoice_lines)} stavki bez broja "
                        "fakture u deklaraciji koja ima više faktura.\n\n"
                        "Ako nastavite, za te stavke će se koristiti ukupna težina iz toolbar-a.\n\n"
                        "Nastaviti obračun za stavke bez broja fakture?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No,
                    )
                    proceed_with_fallback = response == QMessageBox.Yes

            if proceed_with_fallback:
                stats = MassCalculator.calculate_masses(
                    no_invoice_lines,
                    bruto_total,
                    neto_total,
                )
                total_updated += stats["updated"]
                total_skipped += stats["skipped"]
                logger.debug(
                    f"   ⚖️ [bez fakture]: {stats['updated']} ažurirano "
                    "koristeći toolbar total"
                )
            else:
                fallback_skipped = len(no_invoice_lines)
                total_skipped += fallback_skipped
                logger.debug(
                    f"   ⚠️ [bez fakture]: {fallback_skipped} preskočeno "
                    "zbog sumnjivog fallback-a"
                )

        updated_count = total_updated
        skipped_count = total_skipped
        mass_mismatches = find_mass_total_mismatches(
            invoice_groups,
            invoice_weights,
            invoice_labels,
        )

        if updated_count == 0:
            if fallback_skipped:
                if not auto:
                    QMessageBox.warning(
                        self,
                        "Stavke bez broja fakture",
                        f"Preskočeno je {fallback_skipped} stavki bez broja fakture.\n\n"
                        "Dodijelite broj fakture tim stavkama ili ih obračunajte ručno.",
                    )
                return
            if no_weight_invoices and not no_invoice_lines:
                # Sve fakture nemaju sačuvane težine (stari draft ili ručni unos)
                logger.debug("   ❌ Nema sačuvanih težina ni za jednu fakturu")
                if not auto:
                    names = "\n".join(
                        f"  - {invoice_labels.get(inv, inv)}" for inv in no_weight_invoices
                    )
                    QMessageBox.warning(
                        self,
                        "Nema sačuvanih težina",
                        f"Nijedna faktura nema sačuvanu težinu. Uvezite fakture ponovo ili ručno unesite težine.\n\nFakture:\n{names}",
                    )
                return
            if mass_mismatches:
                if not auto:
                    details = "\n".join(
                        f"  - {m['invoice']} {m['field']}: "
                        f"stavke {m['actual']:.3f} kg, "
                        f"faktura {m['expected']:.3f} kg"
                        for m in mass_mismatches[:5]
                    )
                    QMessageBox.warning(
                        self,
                        "Neslaganje težina",
                        f"Zbir težina stavki se ne slaže sa težinom fakture.\n\n{details}",
                    )
                return
            logger.debug("   ❌ Nema stavki za update - sve imaju obe težine")
            if not auto:
                QMessageBox.information(
                    self,
                    "Sve težine popunjene",
                    "Sve stavke već imaju upisane obe težine (bruto i neto). Nema šta da se računa.",
                )
            return

        logger.info(f"\n✅ ZAVRŠENO: ažurirano {updated_count}, preskočeno {skipped_count}")
        logger.debug("=" * 80 + "\n")

        # Reload table
        self._load_data_from_draft()

        # Show success message
        message = f"Težine raspoređene na {updated_count} stavki.\n\n"
        if skipped_count > 0:
            message += f"⚠️ Preskočeno {skipped_count} stavki koje već imaju obe težine.\n"
        if fallback_skipped:
            message += (
                f"\n⚠️ Preskočeno {fallback_skipped} stavki bez broja fakture "
                "zbog sumnjivog fallback-a.\n"
            )
        if no_weight_invoices:
            message += f"\n⚠️ Fakture bez sačuvanih težina (preskočene):\n"
            for inv in no_weight_invoices:
                message += f"  - {invoice_labels.get(inv, inv)}\n"
            message += "\nZa ove fakture uvezite ih ponovo ili ručno unesite težine."
        if mass_mismatches:
            message += "\n⚠️ Neslaganje zbira težina:\n"
            for mismatch in mass_mismatches[:5]:
                message += (
                    f"  - {mismatch['invoice']} {mismatch['field']}: "
                    f"stavke {mismatch['actual']:.3f} kg, "
                    f"faktura {mismatch['expected']:.3f} kg\n"
                )

        if not auto:
            QMessageBox.information(self, "Težine raspoređene", message)

        # Mark as dirty
        if self.on_dirty:
            self.on_dirty()

        self.data_changed.emit()

    def _on_auto_fill(self, auto=False):
        """
        Auto-popuni tarifne brojeve iz baze znanja.

        Args:
            auto: Ako True, preskoči dijaloge i preskači ako su sve tarife popunjene.
        """
        if not self.draft.invoice_lines:
            if not auto:
                QMessageBox.information(
                    self,
                    "Auto-popuni",
                    "Nema stavki za popunjavanje.\n\nPrvo učitajte fakturu.",
            )
            return

        # U auto modu preskači ako su sve tarife već popunjene
        if auto:
            bez_tarife = [l for l in self.draft.invoice_lines if not getattr(l, 'tarifni_broj', None)]
            if not bez_tarife:
                logger.info("✅ [Auto-popuni] Sve stavke imaju tarifni broj — preskačem")
                return

        # Prvo popuni osnovna polja (valuta, jm, iznos)
        basic_filled_count = self.auto_fill_service.fill_basic_fields(
            self.draft.invoice_lines
        )

        # Auto-popuni tarifne iz baze znanja — docs/architecture/TARIFF_FACADE_REFACTORING.md
        try:
            from services.tariff_facade import TariffFacade

            if not auto:
                progress = QProgressDialog(
                    "Auto-popunjavanje tarifnih brojeva...",
                    "Otkaži",
                    0,
                    len(self.draft.invoice_lines),
                    self,
                )
                progress.setWindowTitle("Auto-popuni tarifne")
                progress.setWindowModality(Qt.WindowModal)
                progress.setMinimumDuration(500)
                progress.setValue(0)
                QCoreApplication.processEvents()
            else:
                progress = None

            facade = TariffFacade.get_instance()

            # Skupi skipped stavke (već imaju tarifni broj)
            skipped_details = [
                (
                    line.line_no,
                    line.product_code or line.naziv_robe[:30],
                    line.tarifni_broj,
                )
                for line in self.draft.invoice_lines
                if line.tarifni_broj
            ]

            supplier_name = ""
            if self.draft.invoice_lines:
                supplier_name = self.draft.invoice_lines[0].exporter.name or ""

            result = facade.auto_populate_tariffs(
                self.draft.invoice_lines,
                min_similarity=0.70,
                overwrite_existing=False,
                supplier=supplier_name,
            )

            # Dodaj skipped info u result
            result.skipped_items = len(skipped_details)
            result.skipped_details = skipped_details

            if progress is not None:
                progress.setValue(len(self.draft.invoice_lines))

            # Reload table to show changes
            self._load_data_from_draft()

            # Update status bar
            self._update_status_bar()

            # Mark as dirty
            if result.matched_items > 0 or basic_filled_count > 0:
                self.data_changed.emit()
                if self.on_dirty:
                    self.on_dirty()

            # Show detailed result dialog (samo u interaktivnom modu)
            if not auto:
                self._show_tariff_mapping_result(result, basic_filled_count)

        except Exception as e:
            self.error_handler.handle_auto_fill_error(e)

    def _show_tariff_mapping_result(self, result, basic_filled_count: int):
        """
        Prikaži rezultate auto-popunjavanja u dialogu.

        Args:
            result: MappingResult objekat
            basic_filled_count: Broj stavki sa popunjenim osnovnim poljima
        """
        # Kreiraj poruku sa rezultatima
        message = "🎯 Auto-popunjavanje završeno!\n\n"

        # Osnovna polja
        if basic_filled_count > 0:
            message += (
                f"✅ Osnovna polja (valuta, jm, iznos): {basic_filled_count} stavki\n\n"
            )

        # Tarifni brojevi
        message += f"📋 Tarifni brojevi:\n"
        message += f"  ✅ Novo popunjeno: {result.matched_items} stavki\n"

        if result.skipped_items > 0:
            message += (
                f"  ⏭️  Preskočeno (već imaju tarif): {result.skipped_items} stavki\n"
            )

        if result.unmatched_items > 0:
            message += f"  ⚠️  Nije pronađeno: {result.unmatched_items} stavki\n\n"

            # Prikaži prvih 5 nepronađenih stavki
            message += "Nepronađene stavke (treba ručno popuniti):\n"
            for i, (line_no, product_code, naziv) in enumerate(
                result.unmatched_details[:5], 1
            ):
                display_text = product_code if product_code else naziv
                message += f"  {i}. Stavka #{line_no}: {display_text[:40]}\n"

            if len(result.unmatched_details) > 5:
                message += f"  ... i još {len(result.unmatched_details) - 5} stavki\n"
        else:
            message += "\n✅ Svi tarifni brojevi uspješno popunjeni!"

        # Prikaži detalje preskočenih stavki ako ih ima
        if result.skipped_items > 0 and result.skipped_details:
            message += f"\n\n⏭️  Preskočene stavke (već popunjene):\n"
            for i, (line_no, product_info, tarif) in enumerate(
                result.skipped_details[:5], 1
            ):
                message += f"  {i}. Stavka #{line_no}: {product_info[:35]} → {tarif}\n"

            if len(result.skipped_details) > 5:
                message += f"  ... i još {len(result.skipped_details) - 5} stavki\n"

        # Savjet
        if result.unmatched_items > 0:
            message += "\n💡 Savjet: Nakon što ručno popunite tarifne brojeve,\n"
            message += "   sistem će ih zapamtiti za buduće uvoza."

        QMessageBox.information(self, "Auto-popuni - Rezultati", message)

    def _on_selection_changed(self):
        """Handle table selection change."""
        current = self.table.currentRow()
        has_selection = current >= 0
        self.btn_delete.setEnabled(has_selection)

        if current >= 0 and current == self.table.rowCount() - 1:
            self.table.scrollToBottom()

    def _on_export_excel(self):
        # docs/sections/export-pdf-excel.md — Excel izvoz, grupisanje po naimenovanjima
        """Export fakturnih stavki u Excel."""
        if not self.draft.invoice_lines:
            self._show_no_export_items("Export u Excel")
            return

        # File dialog
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Sačuvaj kao Excel",
            f"Faktura_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            "Excel Files (*.xlsx)",
        )

        if filepath:
            success = ExportService.export_to_excel(self.draft.invoice_lines, filepath, self.draft)

            if success:
                QMessageBox.information(
                    self,
                    "Export uspješan",
                    f"✅ Faktura exportovana u Excel!\n\nFajl: {Path(filepath).name}\nStavki: {len(self.draft.invoice_lines)}",
                )
            else:
                QMessageBox.critical(
                    self,
                    "Greška",
                    "Export u Excel nije uspio.\n\nProvjerite konzolu za detalje.",
                )

    def _on_export_pdf(self):
        """Export fakturnih stavki u PDF sa grupisanjem po naimenovanjima."""
        if not self.draft.invoice_lines:
            self._show_no_export_items("Export u PDF")
            return

        # Provjeri da li su naimenovanja kreirana
        if not self.draft.items:
            reply = QMessageBox.question(
                self,
                "Naimenovanja nisu kreirana",
                "PDF export grupiše stavke po naimenovanjima.\n\n"
                "Naimenovanja još nisu kreirana. Da li želite da ih kreirate prvo?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )

            if reply == QMessageBox.Yes:
                # Pozovi kreiranje naimenovanja
                self._on_create_naimenovanja()
                return
            else:
                return

        # File dialog
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Sačuvaj kao PDF",
            f"Faktura_Naimenovanja_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            "PDF Files (*.pdf)",
        )

        if filepath:
            # Koristi novi PDF exporter sa grupisanjem po naimenovanjima
            success = export_invoice_to_pdf(self.draft, filepath)

            if success:
                # Prebrojati naimenovanja i ukupno stavki
                num_naimenovanja = len(self.draft.items)
                num_stavki = len(self.draft.invoice_lines)

                QMessageBox.information(
                    self,
                    "Export uspješan",
                    f"✅ Faktura exportovana u PDF!\n\n"
                    f"Fajl: {Path(filepath).name}\n"
                    f"Naimenovanja: {num_naimenovanja}\n"
                    f"Ukupno stavki: {num_stavki}",
                )
            else:
                QMessageBox.critical(
                    self,
                    "Greška",
                    "Export u PDF nije uspio.\n\nProvjerite console za detalje greške.",
                )

    def _on_export_pregled_faktura(self):
        """Export pregled faktura u PDF — grupisanje po fakturi za carinika."""
        if not self.draft.invoice_lines:
            self._show_no_export_items("Pregled faktura")
            return

        if not self.draft.items:
            QMessageBox.warning(
                self,
                "Naimenovanja nisu kreirana",
                "PDF pregled zahtijeva kreirana naimenovanja.\n\n"
                "Prvo kreirajte naimenovanja pa pokušajte ponovo.",
            )
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Sačuvaj pregled faktura kao PDF",
            f"Pregled_Faktura_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            "PDF Files (*.pdf)",
        )

        if filepath:
            success = export_faktura_pregled(self.draft, filepath)

            if success:
                # Izbroj koliko faktura ima
                broj_faktura = len(set(
                    l.invoice_number for l in self.draft.invoice_lines if l.invoice_number
                ))
                QMessageBox.information(
                    self,
                    "Export uspješan",
                    f"✅ Pregled faktura exportovan u PDF!\n\n"
                    f"Fajl: {Path(filepath).name}\n"
                    f"Faktura: {broj_faktura}\n"
                    f"Stavki: {len(self.draft.invoice_lines)}",
                )
            else:
                QMessageBox.critical(
                    self,
                    "Greška",
                    "Export pregleda faktura nije uspio.\n\nProvjerite console za detalje greške.",
                )

    def _on_load_mappings_from_xml(self):
        """
        Učitaj novi XML fajl u bazu znanja.

        Omogućava selektivno učitavanje mappinga (naziv_robe → tarifni_broj)
        iz starih deklaracija sa sličnom robom.
        """
        # Otvori file dialog za multi-select XML fajlova
        filepaths, _ = QFileDialog.getOpenFileNames(
            self, "Odaberi ASYCUDA XML fajlove", "", "XML Files (*.xml);;All Files (*)"
        )

        if not filepaths:
            return

        try:
            # Uvoz XML mappinga — docs/architecture/TARIFF_FACADE_REFACTORING.md
            from services.tariff_facade import TariffFacade

            progress = QProgressDialog(
                f"Učitavanje mappinga iz {len(filepaths)} XML fajlova...",
                "Otkaži",
                0,
                len(filepaths),
                self,
            )
            progress.setWindowTitle("Učitaj novi XML")
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(0)

            # Importuj mappinge
            stats = TariffFacade.get_instance().import_from_xml_files(filepaths)

            progress.setValue(len(filepaths))

            # Prikaži rezultat
            message = f"📚 Učitavanje mappinga završeno!\n\n"
            message += f"📁 Obrađeno fajlova: {stats['total_files']}\n"
            message += f"📋 Pronađeno stavki: {stats['total_items']}\n"
            message += f"✅ Uvezeno mappinga: {stats['imported']}\n"
            message += f"⏭️  Preskočeno (duplikati/loši): {stats['skipped']}\n\n"

            if stats["imported"] > 0:
                message += "Sada možete koristiti '🎯 Auto-popuni tarifne' dugme\n"
                message += "za automatsko popunjavanje tarifnih brojeva."
                QMessageBox.information(self, "Učitavanje uspješno", message)
            else:
                message += "⚠️  Nijedan novi mapping nije uvezen.\n"
                message += "Mogući razlozi:\n"
                message += "- Svi mappinzi već postoje u bazi\n"
                message += "- XML fajlovi ne sadrže validne podatke"
                QMessageBox.warning(self, "Učitavanje završeno", message)

        except Exception as e:
            logger.exception("❌ Greška pri učitavanju mappinga")

            QMessageBox.critical(
                self,
                "Greška",
                f"❌ Greška pri učitavanju mappinga iz XML fajlova:\n\n{str(e)}\n\nProvjerite konzolu za detalje.",
            )

    def _set_buttons_enabled(self, enabled: bool):
        """Enable/disable all buttons (used during import)."""
        self.btn_add.setEnabled(enabled)
        self.btn_delete.setEnabled(enabled)
        self.btn_clear.setEnabled(enabled)
        self.btn_validate.setEnabled(enabled)
        self.btn_calc_masses.setEnabled(enabled)
        self.btn_auto_fill.setEnabled(enabled)
        self.btn_load_mappings.setEnabled(enabled)
        self.btn_create_naimenovanja.setEnabled(enabled)
        self.btn_export_excel.setEnabled(enabled)
        self.btn_export_pdf.setEnabled(enabled)

    # ============================================================
    # BaseTabView interface
    # ============================================================

    def get_data(self) -> Dict[str, Any]:
        """Vraća podatke iz view-a (BaseTabView interface)."""
        return {}

    def set_data(self, data: Dict[str, Any]) -> None:
        """Postavlja podatke u view (BaseTabView interface)."""
        pass

    def _sync_pe_docs_to_header(self) -> None:
        """Sinhronizuj PE1/PE2/PE3 iz attached_document4 u header_attached_documents.

        Ovo je ista logika kao u naimenovanja_view.py._sync_pe_docs_to_header,
        samo pozvana nakon kreiranja naimenovanja.
        """
        header_docs = getattr(self.draft, "header_attached_documents", None)
        if header_docs is None:
            return

        # 1. Sakupi sve jedinstvene (sifra, broj) parove iz svih naimenovanja
        pe_entries: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for item in self.draft.items:
            doc4 = (getattr(item, 'attached_document4', '') or '').strip()
            if not doc4:
                continue
            parts = doc4.split(' ', 1)
            sifra = parts[0].strip()
            broj = parts[1].strip() if len(parts) > 1 else ''
            if sifra in ("PE1", "PE2", "PE3"):
                key = (sifra, broj)
                if key not in seen:
                    seen.add(key)
                    pe_entries.append(key)

        # 2. Ukloni postojeće PE1/PE2/PE3 unose iz header_attached_documents
        header_docs[:] = [d for d in header_docs if d.code not in ("PE1", "PE2", "PE3")]

        # 3. Dodaj nove unose
        if pe_entries:
            from core.draft.draft import AttachedDocument
            naziv_map = {
                "PE1": "EUR.1 obrazac",
                "PE2": "Izjava na fakturi",
                "PE3": "Izjava ovlaštenog izvoznika",
            }
            for sifra, broj in pe_entries:
                naziv = naziv_map.get(sifra, f"Dokument {sifra}")
                header_docs.append(AttachedDocument(
                    code=sifra,
                    name=naziv,
                    number=broj,
                    from_rule=sifra == "PE1",
                ))

            # Obavijesti da su se podaci promijenili
            if self.on_dirty:
                self.on_dirty()

    def _sync_inspection_docs_to_header(self) -> None:
        header_docs = getattr(self.draft, "header_attached_documents", None)
        if header_docs is None:
            return

        try:
            from services.tariff_controls_service import get_tariff_controls_service
            svc = get_tariff_controls_service()
        except Exception:
            return

        seen_codes = {getattr(d, "code", "") for d in header_docs}
        added = 0

        for item in getattr(self.draft, "items", []) or []:
            tariff_code = (getattr(item, "tariff_code", "") or "").strip()
            if not tariff_code:
                continue
            try:
                docs = svc.get_required_docs(tariff_code)
            except Exception:
                continue
            for doc in docs:
                code = (doc.get("code") or "").strip()
                if not code or code in seen_codes:
                    continue
                from core.draft.draft import AttachedDocument
                header_docs.append(AttachedDocument(
                    code=code,
                    name=doc.get("name", ""),
                    number="",
                    from_rule=False,
                ))
                seen_codes.add(code)
                added += 1

        if added > 0 and self.on_dirty:
            self.on_dirty()

    def clear_form(self) -> None:
        """Čisti formu (BaseTabView interface) - uklanja sve stavke iz tabele."""
        if hasattr(self, 'table') and self.table is not None:
            self.table.setRowCount(0)
