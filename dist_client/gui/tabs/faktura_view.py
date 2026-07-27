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
from services.security.safe_xml import safe_parse

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
    QTextEdit,
    QDialogButtonBox,
    QSizePolicy,
    QInputDialog,
    QMenu,
)
from PySide6.QtCore import (
    Qt,
    Signal,
    QCoreApplication,
    QSignalBlocker,
    QSize,
    QTimer,
    QItemSelection,
    QItemSelectionModel,
)
from PySide6.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter, QShortcut, QKeySequence

try:
    import qtawesome as qta

    QTAWESOME_AVAILABLE = True
    logging.getLogger(__name__).info("✅ QtAwesome učitan (verzija: %s)", qta.__version__)
except ImportError as e:
    QTAWESOME_AVAILABLE = False
    logging.getLogger(__name__).warning("❌ QtAwesome import FAILED: %s", e)

from gui.dialogs.eur1_quick_dialog import Eur1QuickDialog
from gui.dialogs.pe2_quick_dialog import PE2QuickDialog
from core.draft import DeclarationDraft, InvoiceLine, NaimenovanjeDraft
import uuid
from services.import_worker import ImportWorker
from services.historical_validation_worker import HistoricalValidationWorker
from services.validation.validation_service import FakturaItemValidator, ValidationLevel
from services.naimenovanja.declaration_assembly import DeclarationAssembly
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
from services.agent.validation.evidence_model import evidence_from_preference

_PE_DOC_CODES = {"PE1", "PE2", "PE3"}


class _InvoiceTableWidget(QTableWidget):
    def paintEvent(self, event):
        super().paintEvent(event)
        if self.rowCount() != 0:
            return

        painter = QPainter(self.viewport())
        painter.setPen(QColor("#667d8f"))
        font = painter.font()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            self.viewport().rect(),
            Qt.AlignCenter,
            "Nema učitanih stavki\nUčitajte glavnu listu ili fakturu za početak rada.",
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            modifiers = event.modifiers()
            if modifiers & (Qt.ShiftModifier | Qt.ControlModifier):
                row = self.rowAt(event.position().toPoint().y())
                if row >= 0:
                    self._select_row_with_modifier(row, modifiers)
                    event.accept()
                    return
        super().mousePressEvent(event)

    def _select_row_with_modifier(self, row: int, modifiers: Qt.KeyboardModifiers) -> None:
        selection_model = self.selectionModel()
        if selection_model is None:
            return

        model = self.model()
        current_index = model.index(row, 0)

        if modifiers & Qt.ShiftModifier:
            anchor = self.currentRow()
            if anchor < 0:
                anchor = row
            start, end = sorted((anchor, row))
            selection = QItemSelection(
                model.index(start, 0),
                model.index(end, self.columnCount() - 1),
            )
            selection_model.select(
                selection,
                QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows,
            )
            selection_model.setCurrentIndex(current_index, QItemSelectionModel.NoUpdate)
            return

        row_selection = QItemSelection(
            model.index(row, 0),
            model.index(row, self.columnCount() - 1),
        )
        command = (
            QItemSelectionModel.Deselect
            if selection_model.isRowSelected(row, current_index.parent())
            else QItemSelectionModel.Select
        )
        selection_model.select(row_selection, command | QItemSelectionModel.Rows)
        selection_model.setCurrentIndex(current_index, QItemSelectionModel.NoUpdate)


def _normalize_pe_document_text(value: str) -> str:
    text = re.sub(r"\s+", " ", (value or "").strip())
    parts = text.split(" ", 1)
    code = parts[0].upper() if parts else ""
    if code not in _PE_DOC_CODES:
        return text
    rest = parts[1].strip() if len(parts) > 1 else ""
    while rest.upper().startswith(f"{code} "):
        rest = rest[len(code):].strip()
    if rest.upper() == code:
        rest = ""
    return f"{code} {rest}".strip()


def _pe_doc_code(value: str) -> str:
    code = (value or "").strip().split(" ", 1)[0].upper()
    return code if code in _PE_DOC_CODES else ""


def _clear_secondary_pe_documents(item) -> bool:
    doc4 = _normalize_pe_document_text(getattr(item, "attached_document4", "") or "")
    if doc4 != (getattr(item, "attached_document4", "") or "").strip():
        item.attached_document4 = doc4
    if not _pe_doc_code(doc4):
        return False

    changed = False
    for field_name in (
        "attached_document1",
        "attached_document2",
        "attached_document3",
        "attached_document5",
    ):
        if _pe_doc_code(getattr(item, field_name, "") or ""):
            setattr(item, field_name, "")
            changed = True
    return changed


# Docs: docs/sections/window-geometry-modal-guard.md


def _manual_invoice_record_sort_key(record: dict) -> tuple:
    from gui.tabs.agent.widgets.processing_worker import ProcessingWorker

    invoice_name = record.get("invoice_name") or record.get("filepath") or ""
    filepath = record.get("filepath") or ""
    return (
        ProcessingWorker._natural_invoice_parts(invoice_name or filepath),
        ProcessingWorker._normalized_invoice_token(invoice_name or filepath),
        Path(filepath).name.lower(),
    )


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
    # Neutralna nijansa (sivo-plava) za zemlje koje su pouzdano prepoznate, ali
    # NEMAJU mogućnost povlastice (npr. Kina) — namjerno različita od zelene
    # ("HIGH" pouzdanost), da se vizuelno ne miješa sa zemljama kod kojih
    # povlastica jeste moguća/potvrđena. Vidi agent_reports/2026-06-07_*.
    _NEUTRAL_COUNTRY_COLOR = "#dfe4ea"

    def __init__(self, draft: DeclarationDraft, on_dirty: Optional[Callable] = None):
        super().__init__()
        self.draft = draft
        self.on_dirty = on_dirty
        self.import_worker: Optional[ImportWorker] = None
        self.historical_validation_worker: Optional[HistoricalValidationWorker] = None
        self._historical_validation_token = 0
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

        # Multi-draft navigator state (podjela po zemljama porijekla)
        self._multi_drafts: List[DeclarationDraft] = []
        self._multi_draft_navigator: Optional["MultiDraftNavigator"] = None  # noqa: F821

        # Track imported file counts
        self.imported_excel_count: int = 0
        self.imported_pdf_count: int = 0

        # Track last imported invoice name (for detecting pairs)
        self.last_invoice_name: Optional[str] = None

        # Track last import item count (for REPLACE logic)
        self.last_import_count: int = 0
        self._analysis_summary_auto: bool = False

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
        self._pending_learn_rows: set = set()   # redovi gdje je tarifni_broj ručno izmijenjen

        # Undo/redo stekovi — max 30 snapshotova
        self._undo_stack: list = []
        self._redo_stack: list = []

        self._learn_notify_timer = QTimer(self)
        self._learn_notify_timer.setSingleShot(True)
        self._learn_notify_timer.setInterval(3000)
        self._learn_notify_timer.timeout.connect(self._restore_validation_label)

        # Set object name for styling
        self.setObjectName("FakturaTabV2")

        # Setup UI
        self._setup_ui()
        self._setup_keyboard_shortcuts()

        # Undo/redo shortcuts
        QShortcut(QKeySequence("Ctrl+Z"), self).activated.connect(self._undo)
        QShortcut(QKeySequence("Ctrl+Y"), self).activated.connect(self._redo)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self).activated.connect(self._redo)

        # Load data from draft
        self._load_data_from_draft()

        # Update status bar
        self._update_status_bar()

    def _setup_keyboard_shortcuts(self) -> None:
        self._navigation_shortcuts = []
        bindings = (
            ("Ctrl+N", self._on_add_item),
            ("Alt+Left", lambda: self._navigate_invoice_row(-1)),
            ("Alt+A", lambda: self._navigate_invoice_row(-1)),
            ("Alt+Right", lambda: self._navigate_invoice_row(1)),
            ("Alt+D", lambda: self._navigate_invoice_row(1)),
        )
        for sequence, handler in bindings:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(handler)
            self._navigation_shortcuts.append(shortcut)
        self.btn_add.setToolTip("Dodaj novu stavku ručno — Ctrl+N")

    def _navigate_invoice_row(self, step: int) -> None:
        total = self.table.rowCount()
        if total == 0:
            return
        current = self.table.currentRow()
        target = 0 if current < 0 else max(0, min(total - 1, current + step))
        self.table.selectRow(target)
        cell = self.table.item(target, 0)
        if cell:
            self.table.scrollToItem(cell)

    def _setup_ui(self):
        """Setup the complete UI layout."""
        main_layout = QVBoxLayout(self)
        self._main_layout = main_layout
        main_layout.setContentsMargins(12, 4, 12, 12)
        main_layout.setSpacing(12)

        # Controls section
        controls_widget = self._create_controls_section()
        main_layout.addWidget(controls_widget)

        # Multi-draft navigator (skriven dok nema podjele)
        from gui.widgets.multi_draft_navigator import MultiDraftNavigator
        self._multi_draft_navigator = MultiDraftNavigator(self)
        self._multi_draft_navigator.draft_changed.connect(self._switch_to_draft)
        main_layout.addWidget(self._multi_draft_navigator)

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
        self._controls_grid = grid
        grid.setColumnStretch(0, 2)  # Glavna lista
        grid.setColumnStretch(2, 3)  # Uvezi
        grid.setColumnStretch(4, 3)  # Uredi
        grid.setColumnStretch(6, 5)  # Izvezi
        grid.setColumnStretch(8, 4)  # Pametna pomoć

        self._toolbar_headers = []
        self._toolbar_layouts = []

        # Create header and toolbar sections that share columns
        self._populate_grid_sections(grid)

        container.setStyleSheet(
            """
            QWidget#controlsContainer QPushButton#btnUcitajListu,
            QWidget#controlsContainer QPushButton#btnUveziPDF,
            QWidget#controlsContainer QPushButton#btnUveziExcel,
            QWidget#controlsContainer QPushButton#btnUveziXML,
            QWidget#controlsContainer QPushButton#btnDodaj,
            QWidget#controlsContainer QPushButton#btnExcel,
            QWidget#controlsContainer QPushButton#btnPDF,
            QWidget#controlsContainer QPushButton#btnPregledFaktura,
            QWidget#controlsContainer QPushButton#btnPrethodnaDekl {
                background-color: #52697A;
                color: #FFFFFF;
                border: none;
            }
            QWidget#controlsContainer QPushButton#btnUcitajListu:hover,
            QWidget#controlsContainer QPushButton#btnUveziPDF:hover,
            QWidget#controlsContainer QPushButton#btnUveziExcel:hover,
            QWidget#controlsContainer QPushButton#btnUveziXML:hover,
            QWidget#controlsContainer QPushButton#btnDodaj:hover,
            QWidget#controlsContainer QPushButton#btnExcel:hover,
            QWidget#controlsContainer QPushButton#btnPDF:hover,
            QWidget#controlsContainer QPushButton#btnPregledFaktura:hover,
            QWidget#controlsContainer QPushButton#btnPrethodnaDekl:hover {
                background-color: #607B8E;
            }
            QWidget#controlsContainer QPushButton#btnUcitajListu:pressed,
            QWidget#controlsContainer QPushButton#btnUveziPDF:pressed,
            QWidget#controlsContainer QPushButton#btnUveziExcel:pressed,
            QWidget#controlsContainer QPushButton#btnUveziXML:pressed,
            QWidget#controlsContainer QPushButton#btnDodaj:pressed,
            QWidget#controlsContainer QPushButton#btnExcel:pressed,
            QWidget#controlsContainer QPushButton#btnPDF:pressed,
            QWidget#controlsContainer QPushButton#btnPregledFaktura:pressed,
            QWidget#controlsContainer QPushButton#btnPrethodnaDekl:pressed {
                background-color: #405563;
            }
            QWidget#controlsContainer QPushButton#btnKreirajNaimenovanja {
                background-color: #2F6F9F;
                color: #FFFFFF;
                border: none;
            }
            QWidget#controlsContainer QPushButton#btnKreirajNaimenovanja:hover {
                background-color: #245F88;
            }
            QWidget#controlsContainer QPushButton#btnKreirajNaimenovanja:pressed {
                background-color: #1E4B6A;
            }
            QWidget#controlsContainer QWidget#massControlsPanel {
                background-color: #E8F2ED;
                border: 1px solid #7FA895;
                border-radius: 6px;
            }
            QWidget#controlsContainer QWidget#massControlsPanel QLabel#massLabel {
                color: #244B3C;
                font-size: 14px;
                font-weight: 700;
            }
            QWidget#controlsContainer QWidget#massControlsPanel QLineEdit#massInput {
                background-color: #FFFFFF;
                color: #18382C;
                border: 1px solid #8EAA9C;
                border-radius: 4px;
                padding: 3px 6px;
                font-size: 13px;
                font-weight: 700;
            }
            QWidget#controlsContainer QWidget#massControlsPanel QLineEdit#massInput:focus {
                border: 2px solid #2F7D5A;
                background-color: #F8FFFB;
            }
            QWidget#controlsContainer QPushButton#btnValidacija {
                background-color: #2F7D5A;
                color: #FFFFFF;
                border: 1px solid #245F45;
            }
            QWidget#controlsContainer QPushButton#btnValidacija:hover {
                background-color: #3B906B;
            }
            QWidget#controlsContainer QPushButton#btnValidacija:pressed {
                background-color: #256347;
            }
            QWidget#controlsContainer QPushButton#btnIzracunajMase,
            QWidget#controlsContainer QPushButton#btnAutoPopuni {
                background-color: #6A55A3;
                color: #FFFFFF;
                border: none;
            }
            QWidget#controlsContainer QPushButton#btnIzracunajMase:hover,
            QWidget#controlsContainer QPushButton#btnAutoPopuni:hover {
                background-color: #59458D;
            }
            QWidget#controlsContainer QPushButton#btnIzracunajMase:pressed,
            QWidget#controlsContainer QPushButton#btnAutoPopuni:pressed {
                background-color: #493875;
            }
            QWidget#controlsContainer QPushButton#btnObrisi,
            QWidget#controlsContainer QPushButton#btnOcistiSve {
                background-color: #A6403D;
                color: #FFFFFF;
                border: none;
            }
            QWidget#controlsContainer QPushButton#btnObrisi:hover,
            QWidget#controlsContainer QPushButton#btnOcistiSve:hover {
                background-color: #B9514D;
            }
            QWidget#controlsContainer QPushButton#btnObrisi:pressed,
            QWidget#controlsContainer QPushButton#btnOcistiSve:pressed {
                background-color: #85322F;
            }
            QWidget#controlsContainer QPushButton:hover {
                border: 1px solid rgba(255, 255, 255, 90);
            }
            QWidget#controlsContainer QPushButton:pressed {
                border: 1px solid rgba(0, 0, 0, 80);
            }
            QWidget#controlsContainer QPushButton:disabled {
                background-color: #D5DCE3;
                color: #7D8994;
                border: none;
            }
            """
        )

        return container

    def _populate_grid_sections(self, grid):
        """Populate grid with header and toolbar sections sharing same columns for PERFECT alignment."""
        from PySide6.QtWidgets import QGridLayout

        # Sekcije: (naziv, pozadina, boja teksta) — umjereno naglašena toolbar paleta
        sections = [
            ("Glavna lista", "#D8E7F0", "#214F6B"),
            ("Uvezi", "#E0E6EC", "#2D3F4D"),
            ("Uredi", "#ECE6D7", "#59481F"),
            ("Izvezi", "#D9E9E4", "#245E50"),
            ("Pametna pomoć", "#E5DDF0", "#563A82"),
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
                    border-bottom: 2px solid #7893A6;
                    {border_radius}
                }}
                QPushButton:disabled {{
                    background-color: {color};
                    color: {text_color};
                }}
            """
            )
            header_label.setProperty("headerColor", color)
            header_label.setProperty("headerTextColor", text_color)
            header_label.setProperty("headerRadius", border_radius)
            self._toolbar_headers.append(header_label)

            # Add header to row 0
            grid.addWidget(header_label, 0, col)

            # Create TOOLBAR section for this column
            toolbar_container = QWidget()
            toolbar_container.setObjectName("toolbarSection")
            toolbar_layout = QHBoxLayout(toolbar_container)
            toolbar_layout.setContentsMargins(8, 8, 8, 8)
            toolbar_layout.setSpacing(6)
            toolbar_layout.setAlignment(Qt.AlignVCenter)
            self._toolbar_layouts.append(toolbar_layout)

            # Border radius for toolbar
            if idx == 0:
                t_border_radius = "border-bottom-left-radius: 6px;"
            elif idx == len(sections) - 1:
                t_border_radius = "border-bottom-right-radius: 6px;"
            else:
                t_border_radius = ""

            toolbar_container.setStyleSheet(
                f"""
                QWidget#toolbarSection {{
                    background-color: #F8FAFC;
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
            layout.addSpacing(8)
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
                "Izaberi vrstu PDF izvještaja",
                object_name="btnPDF",
                compact=True,
                icon_name="fa5s.file-pdf",
            )
            self.pdf_export_menu = QMenu(self.btn_export_pdf)
            self.action_export_naimenovanja_pdf = self.pdf_export_menu.addAction(
                "Spisak naimenovanja"
            )
            self.action_export_naimenovanja_pdf.triggered.connect(self._on_export_pdf)
            self.action_export_pregled_faktura = self.pdf_export_menu.addAction(
                "Pregled po fakturama"
            )
            self.action_export_pregled_faktura.triggered.connect(
                self._on_export_pregled_faktura
            )
            self.btn_export_pdf.setMenu(self.pdf_export_menu)
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
            weights_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
            weights_layout = QVBoxLayout(weights_widget)
            weights_layout.setContentsMargins(4, 0, 4, 0)
            weights_layout.setSpacing(2)

            bruto_row = QHBoxLayout()
            bruto_row.setSpacing(4)
            bruto_label = QLabel("Bruto:")
            bruto_label.setObjectName("massLabel")
            bruto_label.setFixedWidth(50)
            bruto_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            bruto_row.addWidget(bruto_label)
            self.input_bruto = QLineEdit()
            self.input_bruto.setObjectName("massInput")
            self.input_bruto.setFixedWidth(90)
            self.input_bruto.setFixedHeight(26)
            self.input_bruto.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.input_bruto.setToolTip("Ukupna bruto težina sa fakture (kg)")
            bruto_row.addWidget(self.input_bruto)
            weights_layout.addLayout(bruto_row)

            neto_row = QHBoxLayout()
            neto_row.setSpacing(4)
            neto_label = QLabel("Neto:")
            neto_label.setObjectName("massLabel")
            neto_label.setFixedWidth(50)
            neto_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            neto_row.addWidget(neto_label)
            self.input_neto = QLineEdit()
            self.input_neto.setObjectName("massInput")
            self.input_neto.setFixedWidth(90)
            self.input_neto.setFixedHeight(26)
            self.input_neto.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.input_neto.setToolTip("Ukupna neto težina sa fakture (kg)")
            neto_row.addWidget(self.input_neto)
            weights_layout.addLayout(neto_row)

            self._weight_labels = (bruto_label, neto_label)
            self._weight_rows = (bruto_row, neto_row)
            self._weights_layout = weights_layout
            self._weights_widget = weights_widget

            self.btn_validate = self._create_button(
                "Provjeri",
                "Provaliziraj sve stavke",
                object_name="btnValidacija",
                icon_name="fa5s.check-circle",
            )
            self.btn_validate.clicked.connect(self._on_validate_all)

            mass_controls_panel = QWidget()
            mass_controls_panel.setObjectName("massControlsPanel")
            mass_controls_layout = QHBoxLayout(mass_controls_panel)
            mass_controls_layout.setContentsMargins(2, 3, 2, 3)
            mass_controls_layout.setSpacing(8)
            mass_controls_layout.addWidget(weights_widget)
            mass_controls_layout.addWidget(self.btn_validate)
            layout.addWidget(mass_controls_panel)

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
                "Prethodna deklaracija",
                "Učitaj zaglavlje iz prethodne deklaracije istog izvoznika",
                object_name="btnPrethodnaDekl",
                icon_name="fa5s.history",
            )
            self.btn_load_mappings.clicked.connect(self._on_load_previous_declaration)
            layout.addWidget(self.btn_load_mappings)

    def apply_display_profile(self, profile_name: str) -> None:
        compact = profile_name == "compact"
        margins = (1, 4, 1, 4) if compact else (6, 5, 6, 5)
        spacing = 2 if compact else 5

        main_layout = getattr(self, "_main_layout", None)
        if main_layout is not None:
            main_layout.setContentsMargins(*(2, 6, 2, 6) if compact else (12, 12, 12, 12))
            main_layout.setSpacing(6 if compact else 12)

        grid = getattr(self, "_controls_grid", None)
        if grid is not None:
            stretches = (2, 3, 3, 5, 4) if compact else (1, 3, 3, 5, 3)
            for column, stretch in zip((0, 2, 4, 6, 8), stretches):
                grid.setColumnStretch(column, stretch)

        for toolbar_layout in getattr(self, "_toolbar_layouts", []):
            toolbar_layout.setContentsMargins(*margins)
            toolbar_layout.setSpacing(spacing)

        for button in self.findChildren(QPushButton):
            standard_text = button.property("standardText")
            if not standard_text:
                continue
            prefix = "" if compact or button.icon().isNull() else " "
            button.setText(prefix + standard_text)
            button.setIconSize(QSize(12, 12) if compact else QSize(16, 16))
            button.setFixedHeight(32 if compact else 36)

        weight_font_size = 15 if compact else 14
        input_width = 62 if compact else 90
        weight_labels = getattr(self, "_weight_labels", ())
        for label in weight_labels:
            font = label.font()
            font.setPixelSize(weight_font_size)
            font.setWeight(QFont.Weight.Bold)
            label.setFont(font)
            label.setStyleSheet("")
            label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        if weight_labels:
            label_width = max(
                QFontMetrics(label.font()).horizontalAdvance(label.text())
                for label in weight_labels
            ) + 6
            for label in weight_labels:
                label.setFixedWidth(label_width)
        weights_layout = getattr(self, "_weights_layout", None)
        if weights_layout is not None:
            weights_layout.setContentsMargins(*(0, 0, 0, 0) if compact else (4, 0, 4, 0))
        for row in getattr(self, "_weight_rows", ()):
            row.setSpacing(2 if compact else 4)
        for field in (getattr(self, "input_bruto", None), getattr(self, "input_neto", None)):
            if field is not None:
                field.setFixedWidth(input_width)

        weights_widget = getattr(self, "_weights_widget", None)
        if weights_widget is not None:
            weights_widget.setFixedWidth(weights_widget.sizeHint().width())

        header_font_size = 15 if compact else 17
        for header in getattr(self, "_toolbar_headers", []):
            color = header.property("headerColor")
            text_color = header.property("headerTextColor")
            border_radius = header.property("headerRadius") or ""
            header.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {color};
                    color: {text_color};
                    font-weight: bold;
                    font-size: {header_font_size}px;
                    padding: 8px 4px;
                    border: none;
                    border-bottom: 2px solid #7893A6;
                    {border_radius}
                }}
                QPushButton:disabled {{
                    background-color: {color};
                    color: {text_color};
                }}
                """
            )

    def _create_table(self) -> QTableWidget:
        """Create the main items table."""
        table = _InvoiceTableWidget()
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
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        table.setMouseTracking(True)
        table.verticalHeader().setVisible(False)

        # Optimalna visina redova i font za čitljivost
        table.verticalHeader().setDefaultSectionSize(35)  # Visina reda
        table.setStyleSheet(
            """
            QTableWidget {
                font-size: 10pt;
                background-color: #ffffff;
                alternate-background-color: #eef4f7;
                gridline-color: #c9d5de;
                border: 1px solid #aebfcb;
            }
            QTableWidget::item {
                padding: 6px 4px;
                border: none;
                color: #17212b;
            }
            QTableWidget::item:selected {
                background-color: #2c668f;
                color: white;
            }
            QTableWidget::item:hover:!selected {
                background-color: #dfeaf1;
            }
            QHeaderView::section {
                background-color: #c8d7e2;
                color: #172b39;
                padding: 8px 6px;
                border: none;
                border-right: 1px solid #aebfcb;
                border-bottom: 2px solid #557d9a;
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

        # Right-click context menu
        table.setContextMenuPolicy(Qt.CustomContextMenu)
        table.customContextMenuRequested.connect(self._on_table_context_menu)

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
                color: #E2EAF3;
                background: transparent;
                padding: 0 2px;
            }
            QWidget#statusBarContainer QLabel#primaryMetric {
                color: #FFFFFF;
                font-weight: 700;
            }
            QWidget#statusBarContainer QLabel#weightMetric {
                color: #D7E8F5;
                font-weight: 700;
            }
            QWidget#statusBarContainer QLabel#secondaryMetric {
                color: #91A7BD;
                font-weight: 500;
            }
            QWidget#statusBarContainer QLabel#analysisSummary {
                color: #75E098;
                font-weight: 600;
            }
            QWidget#statusBarContainer QLabel#statusSeparator {
                color: #6684A1;
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
            QWidget#statusBarContainer QLabel#validationStatus {
                border: 1px solid #6684A1;
                border-radius: 9px;
                padding: 3px 8px;
            }
            QWidget#statusBarContainer QLabel#validationStatus[status=""] {
                color: #F1F5F9;
                background-color: #304D6B;
            }
            QWidget#statusBarContainer QLabel#validationStatus[status="error"] {
                color: #FFD9D9;
                background-color: #7A3038;
                border-color: #B7555F;
            }
            QWidget#statusBarContainer QLabel#validationStatus[status="warning"] {
                color: #FFF2C2;
                background-color: #735B20;
                border-color: #A98731;
            }
            QWidget#statusBarContainer QLabel#validationStatus[status="success"] {
                color: #DDF8E3;
                background-color: #2C6848;
                border-color: #4A946B;
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
            s = QLabel("•")
            s.setObjectName("statusSeparator")
            return s

        self.lbl_item_count    = _stat_lbl("📦 Stavki: 0", "primaryMetric")
        self.lbl_total_amount  = _stat_lbl("💰 Ukupno: 0.00 EUR", "primaryMetric")
        self.lbl_total_quantity = _stat_lbl("⬛ Komada: 0")
        self.lbl_bruto         = _stat_lbl("⚖  Bruto: 0.00 kg", "weightMetric")
        self.lbl_neto          = _stat_lbl("◈  Neto: 0.00 kg", "weightMetric")
        self.lbl_validation    = _stat_lbl("⚪ Neprovjereno", "validationStatus")
        self.lbl_validation.setProperty("status", "")
        self.lbl_assembly      = _stat_lbl("📋 Assembly: N/A", "secondaryMetric")
        self.lbl_analysis      = _stat_lbl("", "analysisSummary")
        self._sep_analysis     = _sep()
        self.lbl_analysis.setVisible(False)
        self._sep_analysis.setVisible(False)

        for widget in [
            self.lbl_item_count,
            self.lbl_total_amount,
            self.lbl_total_quantity, _sep(),
            self.lbl_bruto,
            self.lbl_neto, _sep(),
            self.lbl_validation,
            self.lbl_assembly,
        ]:
            layout.addWidget(widget)

        layout.addStretch()
        layout.addWidget(self._sep_analysis)
        layout.addWidget(self.lbl_analysis)

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
        btn.setProperty("standardText", text)

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
                color: #D1D9E0;
                margin: 0px 8px;
            }
        """
        )
        return sep

    # ============================================================
    # Data Management
    # ============================================================

    _validation_generation: int = 0  # inkrementiše se pri svakom _load_data_from_draft
    _VALIDATION_CHUNK = 40           # redova po frame-u (veći chunk = manje timer overhead-a)

    def _load_data_from_draft(self):
        """Load invoice items from draft into table - OPTIMIZED bulk load."""
        # Otkaži sve prethodno zakazane validacione lance
        self._validation_generation += 1
        my_gen = self._validation_generation

        self.table.blockSignals(True)
        self.table.setUpdatesEnabled(False)
        try:
            self.validation_cache.clear()
            item_count = len(self.draft.invoice_lines)
            self.table.setRowCount(item_count)

            # PASS 1: Popuni ćelije BEZ validacije — odmah vidljivo
            for idx, item in enumerate(self.draft.invoice_lines):
                self._add_item_to_table_fast(idx, item)

            self._update_status_bar()
        finally:
            self.table.setUpdatesEnabled(True)
            self.table.viewport().update()
            self.table.blockSignals(False)

        # PASS 2: Validacija u chunkovima samo za male tabele ili sinhrono
        item_count = len(self.draft.invoice_lines)
        if item_count <= self._VALIDATION_CHUNK:
            # Malo redova — validiraj odmah, nema potrebe za timer overhead-om
            self.table.blockSignals(True)
            try:
                for idx, item in enumerate(self.draft.invoice_lines):
                    self._validate_and_color_row(idx, item)
            finally:
                self.table.blockSignals(False)
        else:
            # Veliki batch — chunkovano kroz QTimer, ali samo najnovija generacija
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._validation_pass_chunk(0, my_gen))

    def _validation_pass_chunk(self, start: int, generation: int) -> None:
        """Validira chunk redova. Otkazuje se ako je pokrenuta nova generacija."""
        if generation != self._validation_generation:
            return  # Noviji _load_data_from_draft je pokrenut — odustaj
        lines = self.draft.invoice_lines
        if start >= len(lines):
            return
        end = min(start + self._VALIDATION_CHUNK, len(lines))
        self.table.blockSignals(True)
        try:
            for idx in range(start, end):
                self._validate_and_color_row(idx, lines[idx])
        finally:
            self.table.blockSignals(False)
        if end < len(lines):
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._validation_pass_chunk(end, generation))

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
        self.table.blockSignals(True)
        try:
            self._populate_row_cells(row, row_number, item)
            self._validate_and_color_row(row, item)
        finally:
            self.table.blockSignals(False)

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
        cell_overrides = {}
        if item.tarifni_broj and 0.70 <= tariff_sim < 0.92:
            # ŽUTA boja - fuzzy match, preporučuje se provjera
            color_hex = "#FFF4D6"  # Svijetlo žuta
            tooltip = f"⚠️ Tarifni broj: {item.tarifni_broj}\n" \
                      f"Pouzdanje: {tariff_sim:.0%}\n" \
                      f"Preporučuje se ručna provjera tarifnog broja"
            cell_overrides[4] = (color_hex, tooltip)
            color_hex = "#ffffff"
            tooltip = ""
        elif is_unmatched:
            # PLAVA boja za nepodudarajuće stavke (nisu pronađene u master listi)
            color_hex = "#E6F0F8"  # Light blue for unmatched
            tooltip = "🔵 Nepodudarajuća stavka - nije pronađena u master listi. Popunite tarifni broj i zemlju porijekla."
            cell_overrides[4] = (color_hex, "❌ Nedostaje tarifni broj")
            cell_overrides[9] = (color_hex, "❌ Nedostaje zemlja porijekla")
            color_hex = "#ffffff"
            tooltip = ""
        elif not item.tarifni_broj or len(item.tarifni_broj.strip()) == 0:
            # CRVENA boja samo ako NEMA tarifnog broja
            color_hex = "#F9E4E3"  # Red for missing tariff
            tooltip = "❌ Greška: Nedostaje tarifni broj"
            cell_overrides[4] = (color_hex, tooltip)
            color_hex = "#ffffff"
            tooltip = ""
        elif not item.zemlja_porijekla or len(item.zemlja_porijekla.strip()) == 0:
            # CRVENA boja ako NEMA zemlje porijekla
            color_hex = "#F9E4E3"
            tooltip = "❌ Greška: Nedostaje zemlja porijekla"
            cell_overrides[9] = (color_hex, tooltip)
            color_hex = "#ffffff"
            tooltip = ""
        elif result.has_blocking_errors():
            # CRVENA boja za druge kritične greške
            color_hex = "#F9E4E3"  # Red for errors
            tooltip = "❌ Greška: " + "; ".join([e.message for e in result.errors])
        elif len(result.warnings) > 0:
            # ŽUTA boja za upozorenja
            color_hex = "#FFF4D6"  # Yellow for warnings
            tooltip = "⚠️ Upozorenje: " + "; ".join([e.message for e in result.warnings])
        elif result.valid:
            # ZELENA boja za validne stavke
            color_hex = "#EAF4EE"  # Green for valid
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
                cell_item.setToolTip(tooltip)

        # DODATNO: Apply country confidence color to zemlja_porijekla column (col 8)
        self._apply_country_confidence_color(row, item)

        # I posebno za kolonu Povlastica — "zemlja potvrđena" NE znači
        # "povlastica potvrđena" (vidi _apply_preference_confidence_color)
        self._apply_preference_confidence_color(row, item)

        for col, (cell_color, cell_tooltip) in cell_overrides.items():
            cell_item = self.table.item(row, col)
            if cell_item:
                cell_item.setData(
                    ValidationDelegate.ValidationColorRole, cell_color
                )
                cell_item.setToolTip(cell_tooltip)

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

        # Boja/znak na zemlji prati ISKLJUČIVO da li je povlastica EKSPLICITNO
        # potvrđena za ovu konkretnu stavku (povlastica + prateći dokument:
        # PE-šifra/EUR.1 broj/izjava o porijeklu) — bez obzira na pouzdanost
        # podatka o zemlji, podobnost zemlje ili bilo koju drugu izvedenu/
        # predviđenu vrijednost. Korisnik je eksplicitno tražio da aplikacija
        # ne nagađa: sve što NEMA eksplicitnu potvrdu dobija istu neutralnu
        # boju pozadine, bez ikonice. Znak (✅) i zelena boja se prikazuju
        # ISKLJUČIVO kada je povlastica stvarno potvrđena.
        preference = (getattr(item, "povlastica", "") or "").strip()
        evidence = evidence_from_preference(item)
        has_preferential_doc = bool(preference and not evidence.requires_confirmation)
        if has_preferential_doc:
            color_hex = self._CONFIDENCE_COLORS.get(item.country_confidence, "#ffffff")
            icon = "✅"
        else:
            color_hex = self._NEUTRAL_COUNTRY_COLOR
            icon = ""
        neutral_country = not has_preferential_doc

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
            elif item.country_source == "EUR1_POTVRDA":
                tooltip_parts.append("✅ Porijeklo potvrđeno EUR.1 sertifikatom (visoka pouzdanost)")
            else:
                tooltip_parts.append("✅ Visoka pouzdanost")
        elif item.country_confidence == "MEDIUM":
            tooltip_parts.append("📋 Podatak o poreklu iz baze znanja (srednja pouzdanost)")
        elif item.country_confidence == "LOW":
            tooltip_parts.append("⚠️ Nema podataka o poreklu (potreban manuelni unos)")
        elif item.country_confidence == "CONFLICT":
            tooltip_parts.append(f"🚨 Konflikt porekla: {item.country_conflict_details or 'PDF i baza imaju različite vrednosti'}")
            tooltip_parts.append("ℹ️ Korišćena je vrednost iz PDF-a")
        if neutral_country:
            tooltip_parts.append(
                "ℹ️ Povlastica za ovu stavku nije eksplicitno potvrđena."
            )

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

    def _apply_preference_confidence_color(self, row: int, item: InvoiceLine):
        """
        Vizuelno označi pouzdanost POVLASTICE (kolona 10), odvojeno od
        pouzdanosti zemlje porijekla (kolona 9).

        Razlog: korisnici su se zbunjivali kad vide ✅ zelenu "CN" oznaku za
        zemlju i pomisle da je time potvrđena i povlastica — a sistem je
        (namjerno, vidi merge_country_origin) NIKAD ne postavlja automatski
        kad dokument nema izjavu o porijeklu (PDF_OZNAKA). Ova oznaka to čini
        vidljivim direktno na ćeliji Povlastica, bez potrebe za hover-om nad
        susjednom ćelijom Zemlja.

        - ⚠️ žuto: povlastica namjerno NIJE postavljena — treba ručna provjera
        - ✅ zeleno: povlastica izvedena iz potvrđenog porijekla (izjava/MATCH)
        """
        cell_item = self.table.item(row, 10)
        if not cell_item:
            return

        source = getattr(item, 'country_source', None)
        evidence = evidence_from_preference(item)
        has_pref = bool(item.povlastica)
        # Zemlja koja fundamentalno nema mogućnost povlastice (npr. Kina) ne
        # treba upozorenje "provjerite ručno" — to samo zbunjuje korisnika jer
        # za tu zemlju povlastica nikad neće postojati. Upozorenje ima smisla
        # SAMO za zemlje koje su uopšte podobne za neku povlasticu (EU/CEFTA/TR/IR).
        country_code = (getattr(item, 'zemlja_porijekla', '') or '').strip()
        eligible_for_pref = bool(self._suggest_preference_by_country(country_code))

        if source == "PDF_OZNAKA" and not has_pref and eligible_for_pref:
            cell_item.setData(ValidationDelegate.ValidationColorRole, "#fff3cd")
            cell_item.setToolTip(
                "⚠️ Povlastica NIJE automatski postavljena — dokument sadrži "
                "samo oznaku zemlje porijekla, bez izjave o porijeklu.\n"
                "Provjerite ručno da li roba ima pravo na povlasticu i unesite je."
            )
        elif has_pref and not evidence.requires_confirmation:
            cell_item.setData(ValidationDelegate.ValidationColorRole, "#d4edda")
            cell_item.setToolTip(
                "✅ Povlastica je potvrđena PE1/PE2/PE3 dokazom.\n"
                "Provjerite da li odgovara podacima na fakturi."
            )

    def _on_item_changed(self, item: QTableWidgetItem):
        """Handle when user edits a cell."""
        # Sync changed data back to draft
        row = item.row()
        col = item.column()

        if row >= len(self.draft.invoice_lines):
            return

        # Snapshot PRIJE sync-a — draft još ima staru vrijednost u ovoj tački
        self._push_undo_snapshot()

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
                if value:
                    self._pending_learn_rows.add(row)
            elif col == 5:  # Količina (pomjereno za +1)
                invoice_item.kolicina = self._parse_number(value) if value else 0.0
            elif col == 6:  # IZNOS (ukupan iznos, NE cijena po komadu!) (pomjereno za +1)
                invoice_item.iznos = self._parse_number(value) if value else 0.0
                # VAŽNO: Ne mijenjamo cijena_jed - to je cijena po komadu koja dolazi iz fakture
            elif col == 7:  # Bruto kg (pomjereno za +1)
                invoice_item.bruto_kg = self._parse_number(value) if value else 0.0
            elif col == 8:  # Neto kg (pomjereno za +1)
                invoice_item.neto_kg = self._parse_number(value) if value else 0.0
            elif col == 9:  # Zemlja porijekla (pomjereno za +1)
                # VAŽNO: NE čitati Qt.UserRole — ono čuva PRETHODNU vrijednost
                # koju je upisala _apply_country_confidence_color (auto-bojenje
                # pri validaciji), pa bi se korisnikova ručna izmjena teksta
                # odbacila i vraćala na staru vrijednost (korisnik vidi da
                # "ne može da promijeni" zemlju). Umjesto toga, očisti samo
                # eventualni ikonica-prefiks (✅/📋/⚠️/🚨) iz upisanog teksta.
                cleaned = value
                for _icon in self._CONFIDENCE_ICONS.values():
                    if cleaned.startswith(_icon):
                        cleaned = cleaned[len(_icon):].strip()
                        break
                invoice_item.zemlja_porijekla = cleaned
            elif col == 10:  # Povlastica (pomjereno za +1)
                invoice_item.povlastica = value
            elif col == 11:  # Valuta (pomjereno za +1)
                invoice_item.valuta = value
        except Exception as e:
            # Log error but don't crash
            logger.error(f"Error updating item: {e}")

        # Debounce: odgodi validaciju i dirty signal za 200ms
        self._pending_validate_rows.add(row)

        # Sinhronizuj decision_state nakon rucne izmjene kljucnih polja
        if col in (4, 9, 10):  # tarifni_broj, zemlja_porijekla, povlastica
            try:
                from services.decision.integration import sync_decision_state_after_manual_edit
                from core.decision.decision_model import DecisionField
                field_map = {4: DecisionField.TARIFF, 9: DecisionField.ORIGIN_COUNTRY, 10: DecisionField.PREFERENCE}
                sync_decision_state_after_manual_edit(
                    invoice_item, field_map[col], value
                )
            except Exception:
                logger.warning("Decision sync manual edit nije uspio", exc_info=True)

        self._debounce_timer.start()

    def _flush_pending_validation(self):
        """Poziva se nakon debounce timera - validuje redove i emituje dirty signal."""
        # Blokiramo signale tokom vizualnog bojenja da setData/setText ne okida
        # itemChanged ponovo → beskonačna petlja debounce timera
        self.table.blockSignals(True)
        try:
            for row in sorted(self._pending_validate_rows):
                if row < len(self.draft.invoice_lines):
                    self._validate_and_color_row(row, self.draft.invoice_lines[row])
        finally:
            self.table.blockSignals(False)
        self._pending_validate_rows.clear()
        self._update_status_bar()
        if self._pending_learn_rows:
            self._auto_learn_edits()
        self._notify_data_changed()

    def _notify_data_changed(self):
        self.data_changed.emit()
        if self.on_dirty:
            self.on_dirty()

    # ------------------------------------------------------------------
    # Undo / Redo
    # ------------------------------------------------------------------

    def _push_undo_snapshot(self):
        import copy
        snapshot = copy.deepcopy(self.draft.invoice_lines)
        self._undo_stack.append(snapshot)
        if len(self._undo_stack) > 30:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def _undo(self):
        if not self._undo_stack:
            self.lbl_validation.setText("⚠️ Nema više koraka za poništavanje")
            return
        import copy
        self._redo_stack.append(copy.deepcopy(self.draft.invoice_lines))
        self.draft.invoice_lines = self._undo_stack.pop()
        self._load_data_from_draft()
        self._update_status_bar()
        self._notify_data_changed()
        count = len(self._undo_stack)
        self.lbl_validation.setText(f"↩ Poništeno — još {count} koraka u historiji")

    def _redo(self):
        if not self._redo_stack:
            self.lbl_validation.setText("⚠️ Nema više koraka za ponavljanje")
            return
        import copy
        self._undo_stack.append(copy.deepcopy(self.draft.invoice_lines))
        self.draft.invoice_lines = self._redo_stack.pop()
        self._load_data_from_draft()
        self._update_status_bar()
        self._notify_data_changed()
        self.lbl_validation.setText("↪ Ponovljeno")

    # ------------------------------------------------------------------
    # Context menu i bulk izmjena tarifnih brojeva
    # ------------------------------------------------------------------

    def _on_table_context_menu(self, pos):
        selected = self.table.selectionModel().selectedRows()
        rows = sorted({idx.row() for idx in selected if 0 <= idx.row() < len(self.draft.invoice_lines)})
        if not rows:
            return

        menu = QMenu(self)
        n = len(rows)
        label = f"Promijeni tarifni broj za {n} odabran{'u stavku' if n == 1 else 'e stavke' if n < 5 else 'ih stavki'}"
        act_tariff = menu.addAction(label)
        menu.addSeparator()

        current_tariffs = sorted({self.draft.invoice_lines[r].tarifni_broj or "" for r in rows})
        current_display = ", ".join(t for t in current_tariffs if t) or "(prazno)"
        menu.addAction(f"Trenutni tarif: {current_display}").setEnabled(False)

        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen == act_tariff:
            self._on_bulk_change_tariff(rows)

    def _on_bulk_change_tariff(self, rows: list):
        current_tariffs = sorted({self.draft.invoice_lines[r].tarifni_broj or "" for r in rows})
        current_display = ", ".join(t for t in current_tariffs if t) or "(prazno)"
        n = len(rows)

        new_tariff, ok = QInputDialog.getText(
            self,
            "Promijeni tarifni broj",
            f"Odabrano stavki: {n}\nTrenutni tarif: {current_display}\n\nNovi tarifni broj (8 cifara):",
            text=current_tariffs[0] if len(current_tariffs) == 1 else "",
        )
        if not ok:
            return
        new_tariff = new_tariff.strip()
        if not new_tariff:
            return

        self._push_undo_snapshot()
        self.table.blockSignals(True)
        try:
            for row in rows:
                line = self.draft.invoice_lines[row]
                old_tariff = line.tarifni_broj or ""
                line.tarifni_broj = new_tariff
                self._set_table_item(row, 4, new_tariff, align=Qt.AlignCenter)
                self._validate_and_color_row(row, line)
                if old_tariff != new_tariff:
                    self._correct_tariff_in_db(line, old_tariff, new_tariff)
        finally:
            self.table.blockSignals(False)

        self.table.viewport().update()
        self._update_status_bar()
        self._notify_data_changed()
        self.lbl_validation.setText(f"✅ Tarifni broj {new_tariff} upisan u {n} stavki")

    def _correct_tariff_in_db(self, line, old_tariff: str, new_tariff: str):
        try:
            from services.tariff.tariff_mapping_service import TariffMappingService
            svc = TariffMappingService()
            correct_fn = getattr(svc, 'correct_mapping', None)
            if correct_fn:
                correct_fn(
                    product_code=getattr(line, 'product_code', '') or '',
                    naziv_robe=line.naziv_robe or '',
                    old_commodity=old_tariff,
                    new_commodity=new_tariff,
                    zemlja_porijekla=getattr(line, 'zemlja_porijekla', '') or '',
                )
            else:
                # Fallback za .pyd verziju bez correct_mapping
                svc.save_mapping(
                    getattr(line, 'product_code', '') or '',
                    line.naziv_robe or '',
                    new_tariff,
                    getattr(line, 'zemlja_porijekla', '') or '',
                )
        except Exception as exc:
            logger.warning("_correct_tariff_in_db: %s", exc)

    def _auto_learn_edits(self):
        """Automatski snimi ručno izmijenjene tarifne brojeve u bazu znanja."""
        rows = set(self._pending_learn_rows)
        self._pending_learn_rows.clear()
        learned = []
        try:
            from services.tariff.tariff_mapping_service import TariffMappingService
            svc = TariffMappingService()
            for row in rows:
                if row >= len(self.draft.invoice_lines):
                    continue
                line = self.draft.invoice_lines[row]
                tarifa = (getattr(line, 'tarifni_broj', '') or '').strip()
                naziv = (getattr(line, 'naziv_robe', '') or '').strip()
                if not tarifa or not naziv:
                    continue
                product_code = (getattr(line, 'product_code', '') or '').strip()
                zemlja = (getattr(line, 'zemlja_porijekla', '') or '').strip()
                ok = svc.save_mapping(product_code, naziv, tarifa, zemlja)
                if ok:
                    kratko = naziv[:30] + ('…' if len(naziv) > 30 else '')
                    learned.append(f"{kratko} → {tarifa}")
        except Exception as exc:
            logger.warning("auto_learn_edits greška: %s", exc)

        if learned:
            msg = "💾 Naučeno: " + " | ".join(learned[:2])
            if len(learned) > 2:
                msg += f" (+{len(learned)-2})"
            self.lbl_validation.setText(msg)
            self.lbl_validation.setProperty("status", "success")
            self.lbl_validation.style().unpolish(self.lbl_validation)
            self.lbl_validation.style().polish(self.lbl_validation)
            self._learn_notify_timer.start()

    def _restore_validation_label(self):
        """Vrati lbl_validation na normalan prikaz validacije."""
        self._update_status_bar()

    def set_analysis_summary(self, text: str, level: str = "warning") -> None:
        """
        Prikaži sažetak analize uvoza u status baru (diskretno, bez ometanja).
        level: 'warning' | 'success' | ''
        Poziva se iz AgentController-a nakon uvoza.
        """
        self._analysis_summary_auto = bool(text)
        self._set_analysis_summary_text(text, level)

    def _set_analysis_summary_text(self, text: str, level: str = "warning") -> None:
        if not text:
            self.lbl_analysis.setVisible(False)
            self._sep_analysis.setVisible(False)
            return
        self.lbl_analysis.setText(text)
        self.lbl_analysis.setProperty("status", level)
        self.lbl_analysis.style().unpolish(self.lbl_analysis)
        self.lbl_analysis.style().polish(self.lbl_analysis)
        self.lbl_analysis.setVisible(True)
        self._sep_analysis.setVisible(True)

    def _build_analysis_summary_from_draft(self) -> tuple[str, str]:
        rows = []
        if hasattr(self, "table") and self.table is not None and self.table.rowCount() > 0:
            for row in range(self.table.rowCount()):
                country_item = self.table.item(row, 9)
                country_text = country_item.text().strip() if country_item else ""
                rows.append({
                    "tarifni_broj": self._get_cell_value(row, 4),
                    "zemlja_porijekla": country_text,
                    "povlastica": self._get_cell_value(row, 10),
                    "has_origin_statement": (
                        row < len(self.draft.invoice_lines)
                        and bool(getattr(self.draft.invoice_lines[row], "has_origin_statement", False))
                    ),
                    "eur1_number": (
                        getattr(self.draft.invoice_lines[row], "eur1_number", "")
                        if row < len(self.draft.invoice_lines)
                        else ""
                    ),
                })
        else:
            rows = [
                {
                    "tarifni_broj": getattr(line, "tarifni_broj", "") or "",
                    "zemlja_porijekla": getattr(line, "zemlja_porijekla", "") or "",
                    "povlastica": getattr(line, "povlastica", "") or "",
                    "has_origin_statement": getattr(line, "has_origin_statement", False),
                    "eur1_number": getattr(line, "eur1_number", "") or "",
                }
                for line in self.draft.invoice_lines
            ]

        if not rows:
            return "", ""

        bez_tarife = [
            row for row in rows
            if not (row["tarifni_broj"] or "").strip()
        ]
        bez_zemlje = [
            row for row in rows
            if not (row["zemlja_porijekla"] or "").strip()
        ]
        sa_povlasticom = [
            row for row in rows
            if (row["povlastica"] or "").strip()
        ]
        bez_eur1 = [
            row for row in sa_povlasticom
            if not row["has_origin_statement"]
            and not (row["eur1_number"] or "").strip()
        ]

        countries: dict[str, int] = {}
        for row in rows:
            raw_country = (row["zemlja_porijekla"] or "").strip().upper()
            match = re.search(r"\b[A-Z]{2}\b", raw_country)
            country = match.group(0) if match else raw_country
            country = country or "(nepoznato)"
            countries[country] = countries.get(country, 0) + 1

        problemi = []
        if bez_tarife:
            problemi.append(f"⚠️ {len(bez_tarife)} bez tarife")
        if bez_zemlje:
            problemi.append(f"⚠️ {len(bez_zemlje)} bez zemlje")
        if bez_eur1:
            problemi.append(f"⚠️ {len(bez_eur1)} bez EUR1")

        zemlja_str = " | ".join(
            f"{country}:{count}"
            for country, count in sorted(countries.items(), key=lambda item: -item[1])
        )
        text = f"🌍 {zemlja_str}"
        if problemi:
            text += "  " + " | ".join(problemi)
        return text, "warning" if problemi else "success"

    def _refresh_analysis_summary_from_draft(self) -> None:
        if not self._analysis_summary_auto:
            return
        text, level = self._build_analysis_summary_from_draft()
        self._set_analysis_summary_text(text, level)

    def _validation_issue_counts(
        self, row_indexes: list[int] | None = None
    ) -> tuple[dict[str, int], dict[str, int]]:
        errors: dict[str, int] = {}
        warnings: dict[str, int] = {}
        rows = row_indexes if row_indexes is not None else range(len(self.draft.invoice_lines))
        for row in rows:
            if row >= len(self.draft.invoice_lines):
                continue
            line = self.draft.invoice_lines[row]
            result = self.validation_cache.get(row) or self.validator.validate(line)
            for err in result.errors:
                label = self._validation_issue_label(err.field, err.message)
                errors[label] = errors.get(label, 0) + 1
            for warn in result.warnings:
                label = self._validation_issue_label(warn.field, warn.message)
                warnings[label] = warnings.get(label, 0) + 1
        return errors, warnings

    @staticmethod
    def _validation_issue_label(field: str, message: str) -> str:
        msg = (message or "").lower()
        if field == "tarifni_broj":
            return "bez tarife" if "obavezan" in msg else "neispravna tarifa"
        if field == "zemlja_porijekla":
            return "bez zemlje"
        if field == "naziv_robe":
            return "bez naziva robe"
        if field == "bruto":
            return "bruto < neto"
        if field == "cijena":
            return "cijena 0/negativna"
        return message or field or "nepoznata greška"

    @staticmethod
    def _format_issue_counts(counts: dict[str, int], limit: int = 3) -> str:
        if not counts:
            return ""
        parts = [
            f"{count} {label}"
            for label, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        ]
        if len(parts) > limit:
            hidden = len(parts) - limit
            parts = parts[:limit] + [f"+{hidden} tip"]
        return " | ".join(parts)

    def _parse_number(self, value_str: str) -> float:
        """Parse broj (EU 1.234,56 ili US 1,234.56 format) u float.

        Delegira na _parse_weight_input() koji auto-detektuje format po
        poziciji zadnjeg separatora — stara implementacija je bezuslovno
        brisala tačke kao hiljadarke, pa je "1234.56" (bez zareza, čist
        decimalni zapis) davala 123456.0 umjesto 1234.56.
        """
        return self._parse_weight_input(value_str)

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
            self._refresh_analysis_summary_from_draft()
            return

        # Jednosmjerni latch: čim ima stavki (bilo kojim putem — ručni ili
        # Agent uvoz, čak i ručni unos reda po reda), uključi sažetak analize
        # (🌍 podjela po zemljama) u status baru. Ranije se uključivao SAMO
        # iz AgentController-a nakon Agent uvoza (set_analysis_summary),
        # pa ručni uvoz nikad nije prikazivao ovu liniju — korisnička prijava.
        if not self._analysis_summary_auto:
            self._analysis_summary_auto = True

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
        self.lbl_total_quantity.setText(f"📦 Komada: {int(round(total_quantity)):,}")
        # Use _format_weight to show full precision with thousands separator
        self.lbl_bruto.setText(f"⚖️ Bruto: {self._format_weight(total_bruto)} kg")
        self.lbl_neto.setText(f"📊 Neto: {self._format_weight(total_neto)} kg")

        # Validation status - koristi cache umesto ponovne validacije
        error_count = self.validation_cache.get_error_count()
        warning_count = self.validation_cache.get_warning_count()
        valid_count = self.validation_cache.get_valid_count()
        error_issues, warning_issues = self._validation_issue_counts()

        # Validation status and color
        if error_count > 0:
            details = self._format_issue_counts(error_issues)
            self.lbl_validation.setText(f"❌ {details or f'{error_count} greška'}")
            if details:
                self.lbl_validation.setToolTip(f"Greške: {details}")
            self.status_bar_widget.setProperty("status", "error")
            self.lbl_validation.setProperty("status", "error")
        elif warning_count > 0:
            details = self._format_issue_counts(warning_issues)
            self.lbl_validation.setText(f"⚠️ {details or f'{warning_count} upozorenja'}")
            if details:
                self.lbl_validation.setToolTip(f"Upozorenja: {details}")
            self.status_bar_widget.setProperty("status", "warning")
            self.lbl_validation.setProperty("status", "warning")
        elif valid_count == item_count:
            self.lbl_validation.setText("✅ Sve validne")
            self.lbl_validation.setToolTip("")
            self.status_bar_widget.setProperty("status", "success")
            self.lbl_validation.setProperty("status", "success")
        else:
            self.lbl_validation.setText("⚪ Neprovjereno")
            self.lbl_validation.setToolTip("")
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

        self._refresh_analysis_summary_from_draft()

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
            "Odaberi fakture (PDF/Excel, Ctrl/Shift za više fajlova)",
            "Fakture (*.pdf *.xlsx *.xls);;PDF Files (*.pdf);;Excel Files (*.xlsx *.xls);;All Files (*)",
        )

    def _on_import_excel(self):
        self._on_import_files(
            "Odaberi fakture (Excel/PDF, Ctrl/Shift za više fajlova)",
            "Fakture (*.xlsx *.xls *.pdf);;Excel Files (*.xlsx *.xls);;PDF Files (*.pdf);;All Files (*)",
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
                    self._push_undo_snapshot()
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
        Import više fajlova odjednom — parsiranje u background threadu,
        dijalozi i draft update na main threadu po završetku.
        """
        from gui.tabs.agent.models.file_item import FileItem
        from gui.tabs.agent.widgets.processing_worker import ProcessingWorker
        from services.import_worker import ManualBatchImportWorker

        sorted_filepaths = [
            f.filepath
            for f in sorted(
                (FileItem.from_filepath(path) for path in filepaths),
                key=ProcessingWorker._pair_sort_key,
            )
        ]

        # Mapping Excel (tarife/porekla/podela/ptp/15467) nije faktura — preskoči ga
        # u grupnom ručnom uvozu ako je u istom folderu sa PDF fakturama u ovom batch-u
        # (ista logika kao agent uvoz, vidi ProcessingWorker._is_mapping_xlsx).
        pdf_folders = {
            str(Path(p).parent)
            for p in sorted_filepaths
            if Path(p).suffix.lower() == ".pdf"
        }
        skipped_mapping = [
            p for p in sorted_filepaths
            if ProcessingWorker._is_mapping_xlsx(p) and str(Path(p).parent) in pdf_folders
        ]
        if skipped_mapping:
            for p in skipped_mapping:
                logger.info(f"⏭️ Preskačem mapping Excel (grupni ručni uvoz): {Path(p).name}")
            sorted_filepaths = [p for p in sorted_filepaths if p not in skipped_mapping]

        self._batch_progress = QProgressDialog(
            f"Uvoz {len(sorted_filepaths)} faktura...", "Otkaži",
            0, len(sorted_filepaths), self
        )
        self._batch_progress.setWindowTitle("Grupni uvoz")
        self._batch_progress.setWindowModality(Qt.WindowModal)
        self._batch_progress.setMinimumDuration(0)

        self._batch_failed: list = []
        self._batch_total: int = len(sorted_filepaths)

        self._batch_worker = ManualBatchImportWorker(sorted_filepaths, parent=self)
        self._batch_worker.progress.connect(self._on_batch_progress)
        self._batch_worker.parse_error.connect(self._on_batch_parse_error)
        self._batch_worker.all_done.connect(self._on_batch_done)
        self._batch_progress.canceled.connect(self._batch_worker.cancel)
        self._batch_worker.start()

    def _on_batch_progress(self, idx: int, filename: str) -> None:
        if hasattr(self, '_batch_progress'):
            self._batch_progress.setValue(idx)
            self._batch_progress.setLabelText(
                f"Uvoz {idx + 1}/{self._batch_total}: {filename}"
            )

    def _on_batch_parse_error(self, filepath: str, error: str) -> None:
        self._batch_failed.append((Path(filepath).name, error))

    def _on_batch_done(self, records: list) -> None:
        if hasattr(self, '_batch_progress'):
            self._batch_progress.setValue(self._batch_total)
            self._batch_progress.close()
        self._process_batch_records(records)

    def _postprocess_master_frigo_pairs_records(self, records: list) -> None:
        """Sparuj Master Frigo PDF + Excel u grupnom ručnom uvozu (kao agent uvoz).

        Finansije (cijena/iznos/kolicina) prepisuju se iz Excel-a u PDF stavke,
        a Excel record se markira kao 'skipped' da ne uđe kao posebna faktura.
        """
        from gui.tabs.agent.widgets.processing_worker import ProcessingWorker

        excel_by_token: dict[str, list[dict]] = {}
        for rec in records:
            if rec.get("skipped") or not rec.get("items"):
                continue
            if Path(rec["filepath"]).suffix.lower() not in (".xlsx", ".xls", ".xlsm"):
                continue
            token = ProcessingWorker._normalized_invoice_token(rec["filepath"])
            excel_by_token.setdefault(token, []).append(rec)

        for pdf_rec in records:
            if pdf_rec.get("skipped") or not pdf_rec.get("items"):
                continue
            if Path(pdf_rec["filepath"]).suffix.lower() != ".pdf":
                continue
            import_result = pdf_rec.get("_import_result")
            detected_format = (getattr(import_result, "_detected_format", "") or "").lower()
            if "master_frigo" not in detected_format:
                continue

            token = ProcessingWorker._normalized_invoice_token(pdf_rec["filepath"])
            candidates = excel_by_token.get(token) or []
            if not candidates:
                continue

            excel_rec = candidates[0]
            enriched = ProcessingWorker._apply_excel_financials(pdf_rec["items"], excel_rec["items"])
            if enriched <= 0:
                continue

            excel_rec["skipped"] = True
            excel_rec["items"] = []
            logger.info(
                f"🔗 Master Frigo pair (grupni ručni uvoz): {Path(pdf_rec['filepath']).name} + "
                f"{Path(excel_rec['filepath']).name} (ažurirano finansija: {enriched} stavki)"
            )

    def _process_batch_records(self, records: list) -> None:
        """Post-processing batch uvoza kroz zajednički import workflow."""
        if not FakturaView._can_use_unified_batch_import(self):
            return FakturaView._process_batch_records_legacy(self, records)

        self._postprocess_master_frigo_pairs_records(records)

        final_records = [r for r in records if not r.get("skipped") and r.get("items")]
        final_records = sorted(final_records, key=_manual_invoice_record_sort_key)
        failed_imports = list(self._batch_failed)

        if not final_records:
            QMessageBox.warning(
                self, "Grupni uvoz",
                "Nije uvezena nijedna stavka.\n\nProvjerite da li su fajlovi ispravni.",
            )
            return

        plan = FakturaView._prepare_manual_batch_import_plan(self, final_records)
        if plan.is_empty:
            QMessageBox.warning(
                self,
                "Grupni uvoz",
                "Parser nije vratio nijednu stavku za primjenu.",
            )
            return

        if failed_imports and not FakturaView._confirm_partial_batch_import(
            self, failed_imports, len(plan.invoices)
        ):
            return

        decisions = FakturaView._collect_manual_import_decisions(self, plan)
        if decisions.aborted:
            return

        self._push_undo_snapshot()

        from services.import_workflow.apply_service import apply_import_plan

        apply_result = apply_import_plan(self.draft, plan, decisions)
        if not apply_result.success:
            QMessageBox.warning(self, "Grupni uvoz nije primijenjen", apply_result.message)
            return

        FakturaView._sync_import_workflow_state_after_apply(self, plan, apply_result)
        self._load_data_from_draft()
        self._update_weight_totals()
        self._set_buttons_enabled(True)
        self._offer_split_by_country(list(self.draft.invoice_lines))

        excel_count, pdf_count = FakturaView._count_applied_batch_file_types(
            self, plan, apply_result
        )
        self.imported_excel_count += excel_count
        self.imported_pdf_count   += pdf_count

        self._update_status_bar()
        FakturaView._show_manual_batch_import_workflow_result(
            self, records, plan, apply_result, failed_imports
        )

        # Istorijska provjera tarifa ODMAH nakon uvoza — vidi napomenu u
        # _on_import_finished (isti obrazac, ista svrha; agent_mode uslov
        # uklonjen istog dana — bio je pogrešan, vidi napomenu tamo).
        self._run_historical_tariff_validation(auto=False)

        on_dirty = getattr(self, "on_dirty", None)
        if callable(on_dirty):
            on_dirty()
        self.data_changed.emit()

    def _process_batch_records_legacy(self, records: list) -> None:
        """Post-processing batch uvoza na main threadu: header, dijalozi, draft, display."""
        from importers.import_result import ImportResult

        self._postprocess_master_frigo_pairs_records(records)

        final_records = [r for r in records if not r.get("skipped") and r.get("items")]
        final_records = sorted(final_records, key=_manual_invoice_record_sort_key)
        failed_imports = list(self._batch_failed)

        # Primijeni header podatke i normalize tarife
        for rec in final_records:
            if rec.get("_import_result"):
                self._apply_import_result_to_header(rec["_import_result"])

        all_items = []
        total_bruto_kg = 0.0
        total_neto_kg = 0.0
        excel_count = 0
        pdf_count = 0

        from PySide6.QtWidgets import QApplication
        for i, record in enumerate(final_records):
            items = record["items"]
            bruto_kg = record["bruto_kg"]
            neto_kg  = record["neto_kg"]

            self._normalize_item_tariffs(items)
            self._distribute_invoice_weights(items, bruto_kg, neto_kg)

            all_items.extend(items)
            total_bruto_kg += bruto_kg
            total_neto_kg  += neto_kg
            self.draft.invoice_weights[
                normalize_invoice_key(record["invoice_name"])
            ] = (bruto_kg, neto_kg)

            suffix = Path(record["filepath"]).suffix.lower()
            if suffix in (".xlsx", ".xls"):
                excel_count += 1
            elif suffix == ".pdf":
                pdf_count += 1

            # Pusti event loop da dođe do zraka svakih 5 faktura
            if i % 5 == 4:
                QApplication.processEvents()

        if not all_items:
            QMessageBox.warning(
                self, "Grupni uvoz",
                "Nije uvezena nijedna stavka.\n\nProvjerite da li su fajlovi ispravni.",
            )
            return

        # Učitaj u assembly/draft
        if not self.assembly.master_list_loaded:
            self.assembly.load_master_list_from_lines(
                all_items, f"Grupni uvoz ({len(final_records)} faktura)"
            )
            draft = self.assembly.create_draft()
            self.draft.invoice_lines = draft.invoice_lines
        else:
            self.draft.invoice_lines.clear()
            self.draft.invoice_lines.extend(all_items)

        self._load_data_from_draft()

        if self._should_show_eur1_dialog(self.draft.invoice_lines):
            logger.info("📦 Grupni uvoz → otvaram jedan EUR.1 dialog za sve fakture")
            self._show_eur1_dialog()

        self.weight_manager.accumulated_bruto_kg = 0.0
        self.weight_manager.accumulated_neto_kg  = 0.0
        self._accumulate_weights(total_bruto_kg, total_neto_kg)

        self.imported_excel_count += excel_count
        self.imported_pdf_count   += pdf_count

        self._update_status_bar()
        self._set_buttons_enabled(True)
        self._offer_split_by_country(all_items)

        skipped_count = len(records) - len(final_records)
        message = "📦 Grupni uvoz završen!\n\n"
        message += f"✅ Uspješno faktura: {len(final_records)}\n"
        if skipped_count:
            message += f"🔗 Spojeno/preskočeno parova: {skipped_count}\n"
        message += f"📋 Ukupno stavki: {len(all_items)}\n"
        message += f"⚖️  Bruto: {self._format_weight(total_bruto_kg)} kg\n"
        message += f"⚖️  Neto: {self._format_weight(total_neto_kg)} kg\n"

        if failed_imports:
            message += f"\n❌ Neuspješno: {len(failed_imports)}\n"
            for fname, err in failed_imports[:3]:
                message += f"   • {fname}: {err[:80]}\n"
            if len(failed_imports) > 3:
                message += f"   ... i još {len(failed_imports) - 3}\n"

        all_warnings = []
        for rec in final_records:
            all_warnings.extend(rec.get("parser_warnings", []))
        if all_warnings:
            message += f"\n⚠️ Upozorenja parsera ({len(all_warnings)}):\n"
            for w in all_warnings[:5]:
                message += f"   • {w}\n"
            if len(all_warnings) > 5:
                message += f"   ... i još {len(all_warnings) - 5}\n"

        QMessageBox.information(self, "Grupni uvoz", message)

        # Istorijska provjera tarifa ODMAH nakon uvoza — vidi napomenu u
        # _on_import_finished (isti obrazac, ista svrha; agent_mode uslov
        # uklonjen istog dana — bio je pogrešan, vidi napomenu tamo).
        self._run_historical_tariff_validation(auto=False)

        self.data_changed.emit()

    _KG_FASHION_EXPORTER = '"K... G... FASHION" D.O.O.'

    def _offer_split_by_country(self, all_items: list) -> None:
        """
        Ako stavke imaju više od jedne grupe zemalja porijekla, ponudi
        korisniku automatsku podjelu na zasebne deklaracije.

        Podjela se nudi SAMO za KG Fashion ("PRET A PORTER") uvoz.
        Za sve ostale importere (Master Frigo, Blagić, itd.) sve ostaje
        u jednoj deklaraciji bez obzira na različite zemlje porijekla.
        """
        from services.faktura.declaration_split_service import (
            count_declaration_groups,
            split_draft_by_country,
        )

        # Provjeri da li je draft označen za split ILI da li stavke dolaze od KG Fashion
        draft_allows = getattr(self.draft, 'allow_country_split', False)
        kg_items = [
            it for it in all_items
            if getattr(getattr(it, 'exporter', None), 'name', '') == self._KG_FASHION_EXPORTER
        ]
        if not draft_allows and not kg_items:
            return  # Nije KG Fashion — ne nudimo podjelu

        n_groups = count_declaration_groups(all_items if not kg_items else kg_items)
        if n_groups <= 1:
            return

        odgovor = QMessageBox.question(
            self,
            "Podjela po zemljama porijekla",
            f"Detektovano <b>{n_groups} različite grupe zemalja</b> porijekla.\n\n"
            "Podijeliti uvoz na zasebne deklaracije po zemljama?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if odgovor != QMessageBox.Yes:
            return

        drafts = split_draft_by_country(self.draft)
        if len(drafts) <= 1:
            return

        self._multi_drafts = drafts
        if self._multi_draft_navigator:
            self._multi_draft_navigator.load_drafts(drafts, start_index=0)

        # Učitaj prvi draft
        self._switch_to_draft(0)

        # Informiši korisnika
        info_lines = []
        for d in drafts:
            from services.faktura.declaration_split_service import group_label
            cg = getattr(d, "_country_group", "")
            cv = getattr(d, "_currency_group", "")
            bruto = sum(v[0] for v in d.invoice_weights.values())
            info_lines.append(
                f"• {group_label(cg, cv)}: {len(d.invoice_lines)} stavki, bruto ≈ {bruto:.1f} kg"
            )
        QMessageBox.information(
            self,
            "Podjela završena",
            f"Uvoz je podijeljen na {len(drafts)} deklaracije:\n\n"
            + "\n".join(info_lines)
            + "\n\nKoristi ◀ ▶ navigator iznad tabele za prelaz između deklaracija.",
        )

    def _switch_to_draft(self, index: int) -> None:
        """Prebaci aktivni draft na draft na datom indeksu i osvježi prikaz."""
        if not self._multi_drafts or index >= len(self._multi_drafts):
            return

        self.draft = self._multi_drafts[index]

        # Osvježi težine u WeightManager-u
        total_bruto = sum(v[0] for v in self.draft.invoice_weights.values())
        total_neto = sum(v[1] for v in self.draft.invoice_weights.values())
        self.weight_manager.reset_weights()
        self._accumulate_weights(total_bruto, total_neto)

        # Osvježi tabelu i status
        self._load_data_from_draft()
        self._update_status_bar()

        # Ažuriraj navigator (ako je navigacija pokrenuta programski, ne klikovima)
        if self._multi_draft_navigator and self._multi_draft_navigator.current_index != index:
            self._multi_draft_navigator.load_drafts(self._multi_drafts, start_index=index)

        # Osvježi Naimenovanja i Zaglavlje tab za novi draft
        self._reload_naimenovanja_tab()

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
            if not getattr(item, "invoice_number", ""):
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
                from services.agent.learning.historical_learning_service_safe import enhance_preference_logic
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
        Agent mod: evidentiraj PE2/EUR1 kandidate bez primjene povlastice.

        PE2 slučaj (has_origin_statement=True):
          - Stavke ostaju bez povlastice dok deklarant ne potvrdi PE2/PE3 dijalog.
        EUR1 slučaj (has_origin_statement=False):
          - Povlastica se NE postavlja bez PE1/PE2/PE3 dokaza (Faza 2, vidi
            agent_tasks/2026-06-10_plan_unapredjenja_carinskog_agenta.md) — stavka
            ostaje neutralna dok korisnik ne potvrdi EUR.1/izjavu, a postojeća žuta
            oznaka (_apply_preference_confidence_color) na to upozorava.
          - eur1_pending broji stavke koje bi imale povlasticu DA postoji EUR.1.

        Returns:
            dict: {'pe2': int, 'eur1_pending': int}
        """
        updated_pe2 = 0
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
                updated_pe2 += 1
            elif item.zemlja_porijekla:
                # EUR1: nema izjave i nema PE1/PE2/PE3 → povlastica ostaje prazna,
                # samo evidentiraj da stavka čeka EUR.1 broj
                pov = self._suggest_preference_by_country(item.zemlja_porijekla, exporter_name)
                if pov and not getattr(item, 'povlastica', None) and not getattr(item, 'eur1_number', None):
                    eur1_pending += 1

        logger.info(
            f"🤖 [agent] Auto-povlastice: PE2={updated_pe2}, EUR1_pending={eur1_pending} "
            f"(bez PE dokaza povlastica ostaje neutralna)"
        )
        return {'pe2': updated_pe2, 'eur1_pending': eur1_pending}

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
                from services.validation.preference_validator import PreferenceValidator
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
                        # Automatska konverzija kroz decision servis (umjesto auto_fix_missing_eur1)
                        from services.decision.declaration_decision_service import (
                            Authorization, DeclarationDecisionService
                        )
                        from core.decision.decision_model import DecisionField
                        _svc = DeclarationDecisionService()
                        _auth = Authorization(action_type="dialog_confirmed", user_identity="deklarant")
                        fixed_count = 0
                        for _line in self.draft.invoice_lines:
                            pref = (_line.povlastica or "").strip().upper()
                            if pref in {'CEFTAP', 'EUP', 'TRP'} and not (_line.eur1_number or "").strip():
                                _svc.confirm_manual_value(_line, DecisionField.PREFERENCE, 'PE1', _auth)
                                fixed_count += 1
                        logger.debug("EUR.1 konverzija: %d stavki konvertovano u PE1 kroz decision servis", fixed_count)
                        QMessageBox.information(
                            self,
                            "Konverzija izvršena",
                            f"✅ Konvertovano {fixed_count} stavki u PE1.\n\n"
                            f"Sada unesi EUR.1 brojeve za ove stavke."
                        )
                
                # Reload table to show changes
                self._load_data_from_draft()

                # Sinhronizuj decision_state nakon EUR.1 primjene
                try:
                    from services.decision.integration import sync_decision_state_after_preference
                    for line in self.draft.invoice_lines:
                        if line.povlastica:
                            sync_decision_state_after_preference(
                                line, line.povlastica, eur1_number=line.eur1_number or "",
                                action_type="dialog_confirmed"
                            )
                except Exception:
                    logger.warning("Decision sync EUR.1 nije uspio", exc_info=True)

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

                # Sinhronizuj decision_state nakon PE2 primjene
                try:
                    from services.decision.integration import sync_decision_state_after_preference
                    for line in self.draft.invoice_lines:
                        if line.povlastica:
                            sync_decision_state_after_preference(
                                line, line.povlastica,
                                eur1_number=line.eur1_number if doc_code == "PE1" else "",
                                invoice_number=invoice_number,
                                action_type="dialog_confirmed"
                            )
                except Exception:
                    logger.warning("Decision sync PE2 nije uspio", exc_info=True)

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

    def _can_use_unified_manual_import(self, result) -> bool:
        if not isinstance(result, ImportResult):
            return False
        if getattr(self.assembly, "master_list_loaded", False):
            return False
        return isinstance(getattr(self.draft, "invoice_weights", None), dict)

    def _manual_import_source_path(self) -> str:
        return getattr(self.import_worker, "filepath", "") or ""

    def _existing_invoice_keys_for_import_workflow(self) -> set[str]:
        keys = set(getattr(self.draft, "invoice_weights", {}) or {})
        for line in getattr(self.draft, "invoice_lines", []) or []:
            key = normalize_invoice_key(getattr(line, "invoice_number", "") or "")
            if key:
                keys.add(key)
        return keys

    def _expected_import_partners(self) -> tuple[str, str]:
        exporter = getattr(self, "_expected_exporter", "")
        importer = getattr(self, "_expected_importer", "")
        exporter = exporter if isinstance(exporter, str) else ""
        importer = importer if isinstance(importer, str) else ""
        draft_exporter = getattr(self.draft, "izvoznik_naziv", "")
        draft_importer = getattr(self.draft, "primalac_naziv", "")
        if not exporter and isinstance(draft_exporter, str):
            exporter = draft_exporter
        if not importer and isinstance(draft_importer, str):
            importer = draft_importer
        return exporter or "", importer or ""

    def _prepare_manual_import_plan(self, result: ImportResult):
        from services.import_workflow.adapters import from_import_result
        from services.import_workflow.prepare_service import prepare_import

        candidate = from_import_result(result, self._manual_import_source_path())
        expected_exporter, expected_importer = FakturaView._expected_import_partners(self)
        return prepare_import(
            [candidate],
            existing_invoice_keys=FakturaView._existing_invoice_keys_for_import_workflow(self),
            expected_exporter=expected_exporter,
            expected_importer=expected_importer,
            expected_currency=getattr(self.draft, "valuta", "") or "",
        )

    def _can_use_unified_batch_import(self) -> bool:
        if getattr(self.assembly, "master_list_loaded", False):
            return False
        return isinstance(getattr(self.draft, "invoice_weights", None), dict)

    def _batch_record_to_import_candidate(self, record: dict):
        from copy import deepcopy

        from services.import_workflow.adapters import from_import_result
        from services.import_workflow.models import (
            ImportCandidate,
            _detect_file_type,
            _normalize_path,
        )

        path = record.get("filepath", "") or "unknown"
        result = record.get("_import_result")
        if result is not None:
            candidate = from_import_result(result, path)
            candidate.invoice_lines = deepcopy(list(record.get("items", []) or []))
            candidate.bruto_kg = record.get("bruto_kg", candidate.bruto_kg) or 0.0
            candidate.neto_kg = record.get("neto_kg", candidate.neto_kg) or 0.0
            candidate.warnings = list(record.get("parser_warnings", []) or candidate.warnings)
            return candidate

        invoice_name = (record.get("invoice_name", "") or "").strip()
        source_stem = Path(path).stem if path else ""
        lines = deepcopy(list(record.get("items", []) or []))
        line_numbers = {
            (getattr(line, "invoice_number", "") or "").strip()
            for line in lines
            if (getattr(line, "invoice_number", "") or "").strip()
        }
        explicit_invoice_number = ""
        if invoice_name and (invoice_name != source_stem or invoice_name in line_numbers):
            explicit_invoice_number = invoice_name

        return ImportCandidate(
            source_path=path,
            normalized_path=_normalize_path(path),
            file_type=_detect_file_type(path),
            parser="",
            invoice_lines=lines,
            explicit_invoice_number=explicit_invoice_number,
            display_name=invoice_name or source_stem or "faktura",
            bruto_kg=record.get("bruto_kg", 0.0) or 0.0,
            neto_kg=record.get("neto_kg", 0.0) or 0.0,
            has_origin_statement=record.get("has_origin_statement", False),
            is_authorized_exporter=record.get("is_authorized_exporter", False),
            warnings=list(record.get("parser_warnings", []) or []),
        )

    def _prepare_manual_batch_import_plan(self, records: list):
        from services.import_workflow.prepare_service import prepare_import

        candidates = [
            FakturaView._batch_record_to_import_candidate(self, record)
            for record in records
            if not record.get("skipped") and record.get("items")
        ]
        expected_exporter, expected_importer = FakturaView._expected_import_partners(self)
        return prepare_import(
            candidates,
            existing_invoice_keys=FakturaView._existing_invoice_keys_for_import_workflow(self),
            expected_exporter=expected_exporter,
            expected_importer=expected_importer,
            expected_currency=getattr(self.draft, "valuta", "") or "",
        )

    def _confirm_partial_batch_import(self, failed_imports: list, valid_count: int) -> bool:
        details = "\n".join(
            f"- {fname}: {str(err)[:100]}" for fname, err in failed_imports[:5]
        )
        if len(failed_imports) > 5:
            details += f"\n... i još {len(failed_imports) - 5}"
        reply = QMessageBox.question(
            self,
            "Grupni uvoz — djelimičan uspjeh",
            f"Uspješno je pripremljeno {valid_count} faktura, "
            f"ali {len(failed_imports)} fajlova nije uvezeno.\n\n"
            f"{details}\n\n"
            "Da li želite nastaviti sa ispravnim fakturama?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        return reply == QMessageBox.Yes

    def _count_applied_batch_file_types(self, plan, apply_result) -> tuple[int, int]:
        applied_keys = set(apply_result.applied_invoice_keys)
        excel_count = 0
        pdf_count = 0
        for invoice in plan.invoices:
            if invoice.internal_key not in applied_keys:
                continue
            for path in invoice.source_paths:
                suffix = Path(path).suffix.lower()
                if suffix in (".xlsx", ".xls", ".xlsm"):
                    excel_count += 1
                elif suffix == ".pdf":
                    pdf_count += 1
        return excel_count, pdf_count

    def _show_manual_batch_import_workflow_result(
        self,
        records: list,
        plan,
        apply_result,
        failed_imports: list,
    ) -> None:
        final_records = [r for r in records if not r.get("skipped") and r.get("items")]
        skipped_count = len(records) - len(final_records)
        message = "📦 Grupni uvoz završen!\n\n"
        message += f"✅ Faktura dodano: {apply_result.added_invoices}\n"
        if apply_result.replaced_invoices:
            message += f"🔁 Faktura zamijenjeno: {apply_result.replaced_invoices}\n"
        if apply_result.skipped_invoices:
            message += f"⏭️ Faktura preskočeno: {apply_result.skipped_invoices}\n"
        if skipped_count:
            message += f"🔗 Spojeno/preskočeno parova: {skipped_count}\n"
        message += f"📋 Ukupno stavki: {apply_result.total_items}\n"
        message += f"⚖️  Bruto: {self._format_weight(apply_result.total_bruto_kg)} kg\n"
        message += f"⚖️  Neto: {self._format_weight(apply_result.total_neto_kg)} kg\n"

        if failed_imports:
            message += f"\n❌ Neuspješno: {len(failed_imports)}\n"
            for fname, err in failed_imports[:3]:
                message += f"   • {fname}: {str(err)[:80]}\n"
            if len(failed_imports) > 3:
                message += f"   ... i još {len(failed_imports) - 3}\n"

        if apply_result.warnings:
            message += f"\n⚠️ Upozorenja ({len(apply_result.warnings)}):\n"
            for warning in apply_result.warnings[:5]:
                message += f"   • {warning}\n"
            if len(apply_result.warnings) > 5:
                message += f"   ... i još {len(apply_result.warnings) - 5}\n"

        QMessageBox.information(self, "Grupni uvoz", message)

    def _collect_manual_import_decisions(self, plan):
        from services.import_workflow.decision_models import (
            CurrencyConflictResponse,
            InvoiceDecision,
            PartnerConflictResolution,
            PartnerConflictResponse,
            UserDecisions,
        )

        decisions = UserDecisions()
        for invoice in plan.invoices:
            decisions.invoice_decisions[invoice.internal_key] = InvoiceDecision(
                invoice_key=invoice.internal_key
            )

        if plan.partner_conflicts:
            if not self._confirm_import_partner_conflicts(plan.partner_conflicts):
                decisions.aborted = True
                return decisions
            for conflict in plan.partner_conflicts:
                decisions.partner_conflict_responses.append(
                    PartnerConflictResponse(
                        invoice_key=conflict.invoice_key,
                        field_name=conflict.field_name,
                        expected=conflict.expected,
                        actual=conflict.actual,
                        resolution=PartnerConflictResolution.CONTINUE,
                    )
                )

        if plan.currency_conflicts:
            if not self._confirm_import_currency_conflicts(plan.currency_conflicts):
                decisions.aborted = True
                return decisions
            for conflict in plan.currency_conflicts:
                decisions.currency_conflict_responses.append(
                    CurrencyConflictResponse(
                        invoice_key=conflict.invoice_key,
                        expected=conflict.expected,
                        actual=conflict.actual,
                        resolution=PartnerConflictResolution.CONTINUE,
                    )
                )

        invoice_by_key = {invoice.internal_key: invoice for invoice in plan.invoices}
        for invoice_key, dialog_type in plan.origin_dialogs_needed:
            invoice = invoice_by_key.get(invoice_key)
            if invoice is None:
                continue
            response = self._collect_manual_origin_response(invoice, dialog_type)
            decisions.invoice_decisions[invoice_key].origin_response = response

        return decisions

    def _confirm_import_partner_conflicts(self, conflicts) -> bool:
        lines = []
        labels = {"exporter": "Pošiljalac (izvoznik)", "importer": "Uvoznik (primalac)"}
        for conflict in conflicts:
            label = labels.get(conflict.field_name, conflict.field_name)
            lines.append(
                f"<b>{label}:</b><br>"
                f"&nbsp;&nbsp;Očekivano: <b>{conflict.expected}</b><br>"
                f"&nbsp;&nbsp;Uvezeno:&nbsp;&nbsp; <b>{conflict.actual}</b>"
            )

        msg = QMessageBox(self)
        msg.setWindowTitle("Upozorenje — Pogrešan partner?")
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(
            "<b>⚠️ Podaci o partnerima se razlikuju od prethodnog uvoza!</b><br><br>"
            + "<br><br>".join(lines)
            + "<br><br>Da li želite nastaviti sa ovim uvozom?"
        )
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        msg.button(QMessageBox.StandardButton.Yes).setText("Nastavi svejedno")
        msg.button(QMessageBox.StandardButton.No).setText("Odustani od uvoza")
        return msg.exec() == QMessageBox.StandardButton.Yes

    def _confirm_import_currency_conflicts(self, conflicts) -> bool:
        details = "\n".join(
            f"- Očekivano: {c.expected}, uvezeno: {c.actual}" for c in conflicts
        )
        reply = QMessageBox.question(
            self,
            "Upozorenje — različita valuta",
            "Valuta uvezene fakture razlikuje se od valute u draftu.\n\n"
            f"{details}\n\n"
            "Da li želite nastaviti sa ovim uvozom?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return reply == QMessageBox.Yes

    def _collect_manual_origin_response(self, invoice, dialog_type):
        from services.import_workflow.decision_models import (
            OriginDialogResolution,
            OriginDialogResponse,
        )
        from services.import_workflow.plan_models import OriginDialogType

        dialog_data = {}
        result = QDialog.Rejected
        if dialog_type == OriginDialogType.PE2:
            dialog = PE2QuickDialog(
                invoice.invoice_lines, self,
                invoice_number=invoice.invoice_number,
                doc_code="PE2",
            )
            result = exec_dialog_preserving_geometry(dialog, self)
            if result == QDialog.Accepted:
                dialog_data = dialog.get_data()
        elif dialog_type == OriginDialogType.PE3:
            dialog = PE2QuickDialog(
                invoice.invoice_lines, self,
                invoice_number=invoice.invoice_number,
                doc_code="PE3",
            )
            result = exec_dialog_preserving_geometry(dialog, self)
            if result == QDialog.Accepted:
                dialog_data = dialog.get_data()
        elif dialog_type == OriginDialogType.EUR1:
            dialog = Eur1QuickDialog(
                invoice.invoice_lines, self,
                invoice_number=invoice.invoice_number,
            )
            result = exec_dialog_preserving_geometry(dialog, self)
            if result == QDialog.Accepted:
                dialog_data = dialog.get_data()

        resolution = (
            OriginDialogResolution.APPLIED
            if result == QDialog.Accepted and dialog_data
            else OriginDialogResolution.SKIPPED
        )
        return OriginDialogResponse(
            invoice_key=invoice.internal_key,
            dialog_type=dialog_type,
            resolution=resolution,
            dialog_data=dialog_data,
        )

    def _sync_import_workflow_state_after_apply(self, plan, apply_result) -> None:
        self.weight_manager.accumulated_bruto_kg = 0.0
        self.weight_manager.accumulated_neto_kg = 0.0
        for bruto, neto in (getattr(self.draft, "invoice_weights", {}) or {}).values():
            self.weight_manager.accumulated_bruto_kg += bruto or 0.0
            self.weight_manager.accumulated_neto_kg += neto or 0.0
        self.input_bruto.setText(self._format_weight(self.weight_manager.accumulated_bruto_kg))
        self.input_neto.setText(self._format_weight(self.weight_manager.accumulated_neto_kg))

        applied_keys = set(apply_result.applied_invoice_keys)
        applied = [invoice for invoice in plan.invoices if invoice.internal_key in applied_keys]
        if applied:
            self.last_invoice_name = applied[-1].invoice_number or applied[-1].display_name
            self.last_import_count = len(applied[-1].invoice_lines)
            exporter = applied[-1].exporter.name if applied[-1].exporter else ""
            importer = applied[-1].importer.name if applied[-1].importer else ""
            if exporter:
                self._expected_exporter = exporter
            if importer:
                self._expected_importer = importer

    def _show_manual_import_workflow_result(self, plan, apply_result) -> None:
        title = "Uvoz uspješan"
        if not apply_result.success:
            QMessageBox.warning(self, "Uvoz nije primijenjen", apply_result.message)
            return

        names = apply_result.applied_invoice_numbers or [
            invoice.display_name
            for invoice in plan.invoices
            if invoice.internal_key in set(apply_result.applied_invoice_keys)
        ]
        invoice_name = names[-1] if names else "faktura"
        message = (
            f"Uspješno uvezeno {apply_result.total_items} stavki iz '{invoice_name}'.\n\n"
        )
        if apply_result.added_invoices:
            message += f"Faktura dodano: {apply_result.added_invoices}\n"
        if apply_result.replaced_invoices:
            message += f"Faktura zamijenjeno: {apply_result.replaced_invoices}\n"
        if apply_result.skipped_invoices:
            message += f"Faktura preskočeno: {apply_result.skipped_invoices}\n"
        if apply_result.total_bruto_kg or apply_result.total_neto_kg:
            message += "\n"
            message += f"Bruto: {self._format_weight(apply_result.total_bruto_kg)} kg\n"
            message += f"Neto: {self._format_weight(apply_result.total_neto_kg)} kg\n"
            message += "\nAkumulirano ukupno:\n"
            message += f"- Bruto: {self._format_weight(self.weight_manager.accumulated_bruto_kg)} kg\n"
            message += f"- Neto: {self._format_weight(self.weight_manager.accumulated_neto_kg)} kg\n"
        if apply_result.warnings:
            message += "\n⚠️ Upozorenja:\n"
            for warning in apply_result.warnings[:5]:
                message += f"- {warning}\n"
            if len(apply_result.warnings) > 5:
                message += f"... i još {len(apply_result.warnings) - 5}\n"

        message = self._append_imported_files_message(message, min_files=2)
        QMessageBox.information(self, title, message)

    def _on_import_finished(self, result):
        if not FakturaView._can_use_unified_manual_import(self, result):
            return FakturaView._on_import_finished_legacy(self, result)

        try:
            self.progress_bar.setVisible(False)
            self.progress_bar.setValue(0)
            self._push_undo_snapshot()

            plan = FakturaView._prepare_manual_import_plan(self, result)
            if plan.is_empty:
                QMessageBox.warning(
                    self,
                    "Uvoz nije primijenjen",
                    "Parser nije vratio nijednu stavku za primjenu.",
                )
                return

            decisions = FakturaView._collect_manual_import_decisions(self, plan)
            if decisions.aborted:
                self.progress_bar.setVisible(False)
                return

            from services.import_workflow.apply_service import apply_import_plan

            apply_result = apply_import_plan(self.draft, plan, decisions)
            if not apply_result.success:
                QMessageBox.warning(self, "Uvoz nije primijenjen", apply_result.message)
                return

            self._track_file_type()
            FakturaView._sync_import_workflow_state_after_apply(self, plan, apply_result)
            self._load_data_from_draft()
            self._update_weight_totals()
            FakturaView._show_manual_import_workflow_result(self, plan, apply_result)
            self._update_status_bar()
            self._run_historical_tariff_validation(auto=False)

            if self.on_dirty:
                self.on_dirty()
            self.data_changed.emit()
        finally:
            # Dugmad se MORAJU ponovo omogućiti bez obzira na ishod (prazan
            # plan, korisnik odustao, apply neuspio, ili uspjeh) — ranije su
            # tri rane "return" grane izlazile prije ove linije, ostavljajući
            # toolbar trajno onemogućen.
            self._set_buttons_enabled(True)
            self._cleanup_import_worker()

    def _on_import_finished_legacy(self, result):
        """Handle successful import.

        Args:
            result: Either ImportResult (with metadata) or List[InvoiceLine]
        """
        try:
            # Hide progress bar
            self.progress_bar.setVisible(False)
            self.progress_bar.setValue(0)
            self._push_undo_snapshot()

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

            # Popuni zaglavlje (izvoznik/uvoznik/valuta) iz ImportResult - samo prazna polja
            if isinstance(result, ImportResult):
                self._apply_import_result_to_header(result)

            # Provjeri konzistentnost pošiljaoca/uvoznika
            if not self._check_partner_consistency(exporter_name, importer_name):
                # Korisnik je odbio uvoz — očisti progress i izađi
                self.progress_bar.setVisible(False)
                return

            # VAŽNO: NE akumuliraj težine ovdje - preuranjeno!
            # Težine će biti akumulirane kasnije, nakon što se utvrdi da li je isti invoice

            # DEBUG: Logiraj tarifne brojeve odmah nakon importa
            logger.debug(f"[DEBUG] Import items received: {len(items)} items")
            for i, item in enumerate(items):
                tariff = getattr(item, 'tarifni_broj', 'MISSING')
                logger.debug(f"  Item {i}: code={item.product_code}, tariff={tariff}, name={item.naziv_robe[:30]}...")

            # NOVI PRISTUP: NE koristiti Assembly sistem za obične importe!
            # Assembly se koristi SAMO kada korisnik eksplicitno učita Master Listu preko menija.
            # Za Blagić i druge kompletne fakture, direktno dodaj u draft i održi redoslijed.

            # Normalizuj tarifne brojeve na 8 cifara (Excel može izgubiti vodeće nule)
            self._normalize_item_tariffs(items)
            # DEBUG: Logiraj nakon normalizacije
            logger.debug(f"[DEBUG] Items after _normalize_item_tariffs:")
            for i, item in enumerate(items):
                tariff = getattr(item, 'tarifni_broj', 'MISSING')
                logger.debug(f"  Item {i}: code={item.product_code}, tariff={tariff}")
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

            # Istorijska provjera tarifa ODMAH nakon uvoza (korisnička primjedba
            # 2026-07-22 — SUSSINA slučaj): čekanje na ručni klik "Provjeri" znači
            # da se pogrešna tarifa lako provuče ako korisnik pređe dalje prije
            # klika. Tiho je (bez dijaloga) kad nema prijedloga — vidi
            # _run_historical_tariff_validation.
            #
            # NAPOMENA (ispravka iste sesije): raniji uslov "if not self._agent_mode"
            # je bio pogrešan — self._agent_mode je aktivan za SVE agent rute uvoza
            # ("Analiza", "Uvezi u deklaraciju", "Puna automatizacija"), ne samo za
            # punu automatizaciju. Samo "Puna automatizacija" ima naknadni
            # _on_validate_all(auto=True) poziv (import_pipeline_service.
            # _puna_auto_pipeline); ostale dvije rute NIKAD ne bi dobile provjeru
            # ako se ovdje preskoči. Pipeline se pokreće ODVOJENO i KASNIJE (radi na
            # već uvezenom draft-u, ne uvozi sam) — nema stvarnog preklapanja jer
            # njegov auto=True poziv ostaje tih (samo log), bez obzira da li je
            # ovaj eager poziv već nešto prikazao.
            self._run_historical_tariff_validation(auto=False)

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
                # Undo snapshot PRIJE mutacije — omogući Ctrl+Z za "Dodaj"
                self._push_undo_snapshot()

                # Add to draft
                self.draft.invoice_lines.append(new_item)

                # Add to table — _add_item_to_table SAMA radi insertRow (na
                # osnovu trenutnog rowCount()), pa se ovdje NE smije unaprijed
                # umetnuti prazan red — inače tabela dobije jedan prazan i
                # jedan popunjen red za samo jednu novu stavku u draftu.
                row_number = self.table.rowCount()
                self._add_item_to_table(row_number, new_item)

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
            self._push_undo_snapshot()
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
            f"Da li ste sigurni da želite obrisati SVE stavke?\n\nUkupno stavki: {item_count}\n\nMoguće poništiti sa Ctrl+Z.",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self._push_undo_snapshot()
            # Clear all items
            self.draft.invoice_lines.clear()

            # Očisti i knjigovodstvene strukture vezane za fakture — bez ovoga
            # invoice_weights zadržava stare ključeve, pa naredni uvoz "nove"
            # fakture sa istim brojem faktura može biti pogrešno tretiran kao
            # REPLACE postojeće (umjesto novog uvoza u prazan draft).
            self.draft.invoice_weights.clear()
            self.draft.source_files.clear()

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

    def _on_create_naimenovanja(self, auto=False) -> bool:
        """Handle Create Naimenovanja button click.

        Args:
            auto: Ako True, preskoči sve dijaloge (za punu automatizaciju).

        Returns:
            True ako su naimenovanja stvarno kreirana, False ako nije bilo
            stavki, korisnik je odustao na pre-flight dijalogu, ili je greška
            spriječila kreiranje — vidi
            docs/agent/AGENT_MODE_IMPROVEMENT_IMPLEMENTATION_PLAN.md §7.
        """
        geometry_state = capture_window_geometry(self) if not auto else None
        button_text = None
        if not auto and hasattr(self, "btn_create_naimenovanja"):
            button_text = self.btn_create_naimenovanja.text()
            self.btn_create_naimenovanja.setEnabled(False)
            self.btn_create_naimenovanja.setText("Kreiram...")
            QCoreApplication.processEvents()
        from services.naimenovanja.create_naimenovanja_service import CreateNaimenovanjaService
        from services.faktura.declaration_split_service import group_label as _group_label

        try:
            logger.debug(f"\n{'='*80}")
            logger.debug(f"🔍 [_on_create_naimenovanja] START (auto={auto})")

            # Ako split još nije urađen, provjeri da li treba podjelu po zemljama
            if len(self._multi_drafts) <= 1 and self.draft.invoice_lines and not auto:
                from services.faktura.declaration_split_service import count_declaration_groups
                if count_declaration_groups(self.draft.invoice_lines) > 1:
                    self._offer_split_by_country(self.draft.invoice_lines)

            # Odaberi koje draftove obraditi: sve split draftove ili samo trenutni
            drafts_to_process = self._multi_drafts if len(self._multi_drafts) > 1 else [self.draft]

            # Provjera: mora biti bar jedna stavka u svim draftovima
            all_lines = [ln for d in drafts_to_process for ln in d.invoice_lines]
            if not all_lines:
                if not auto:
                    QMessageBox.warning(
                        self,
                        "Nema faktura",
                        "Molimo prvo uvezite fakture (PDF/Excel/XML) prije kreiranja naimenovanja.",
                    )
                return False

            logger.debug(f"🔍 [_on_create_naimenovanja] Draftovi za obradu: {len(drafts_to_process)}, ukupno stavki: {len(all_lines)}")

            # Pre-flight provjera (zamjenjuje stare fragmetnarne QMessageBox poruke)
            if not auto:
                from gui.dialogs.preflight_naimenovanja_dialog import (
                    PreFlightNaimenovanjaDialog,
                    analyse_preflight,
                )
                pf = analyse_preflight(all_lines)
                dlg = PreFlightNaimenovanjaDialog(pf, parent=self)
                if dlg.exec() != PreFlightNaimenovanjaDialog.Accepted:
                    logger.debug("🔍 [_on_create_naimenovanja] Korisnik odustao na pre-flight")
                    return False

            # Kreiraj naimenovanja za svaki draft
            results = []  # [(draft, count, split_info)]
            for draft in drafts_to_process:
                svc = CreateNaimenovanjaService(draft)
                cnt = svc.create_smart_group()
                si = getattr(svc, "last_split_info", None)
                results.append((draft, cnt, si))
                logger.info(
                    f"✅ [_on_create_naimenovanja] {_group_label(getattr(draft, '_country_group', ''), getattr(draft, '_currency_group', ''))}"
                    f": {cnt} naimenovanja"
                    if len(drafts_to_process) > 1
                    else f"✅ [_on_create_naimenovanja] Kreirano {cnt} naimenovanja"
                )
                # Auto-učenje za svaki draft
                try:
                    from services.tariff_facade import TariffFacade
                    TariffFacade.get_instance().learn_from_draft(draft.invoice_lines)
                except Exception as e:
                    logger.warning("Auto-učenje tarifa nije uspjelo: %s", e)

            # Prikaz rezultata (samo u interaktivnom modu)
            if not auto:
                overflow_drafts = [(d, cnt, si) for d, cnt, si in results if si and si.overflow_count > 0]
                if overflow_drafts:
                    _, cnt, si = overflow_drafts[0]
                    QMessageBox.warning(
                        self,
                        "ASYCUDA limit — 99 naimenovanja",
                        f"ASYCUDA World u BiH podržava najviše 99 naimenovanja po deklaraciji.\n\n"
                        f"Ukupno je formirano {si.total_count} naimenovanja.\n"
                        f"Trenutna deklaracija je ograničena na prvih {si.current_count}.\n"
                        f"Preostalih {si.overflow_count} naimenovanja je pripremljeno za sljedeću deklaraciju.\n\n"
                        f"Završite i izvezite ovu deklaraciju, pa će aplikacija ponuditi nastavak sa ostatkom.",
                    )
                elif len(results) > 1:
                    linije = "\n".join(
                        f"  • {_group_label(getattr(d, '_country_group', ''), getattr(d, '_currency_group', ''))}: {cnt} naimenovanja"
                        for d, cnt, _ in results
                    )
                    QMessageBox.information(
                        self,
                        "Uspjeh!",
                        f"✅ Kreirano naimenovanja za {len(results)} deklaracije:\n\n"
                        f"{linije}\n\n"
                        f"Koristite navigator ◀ ▶ za pregled svake deklaracije.",
                    )
                else:
                    _, count, _ = results[0]
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
            self._sync_pe_docs_to_header()
            self._sync_inspection_docs_to_header()

            # Reload table to show assigned naimenovanje numbers in column
            logger.debug(f"🔍 [_on_create_naimenovanja] Pozivanje _load_data_from_draft()...")
            self._set_weight_inputs_from_draft()
            self._load_data_from_draft()
            logger.info(f"✅ [_on_create_naimenovanja] Faktura tab ažuriran")

            # Notify Naimenovanja Tab to reload data
            logger.debug(f"🔍 [_on_create_naimenovanja] Pozivanje _reload_naimenovanja_tab()...")
            self._reload_naimenovanja_tab()
            logger.info(f"✅ [_on_create_naimenovanja] Naimenovanja i Zaglavlje tab ažurirani")

            try:
                self.naimenovanja_created.emit()
            except Exception as e:
                logger.warning(f"⚠️ [_on_create_naimenovanja] Signal naimenovanja_created nije uspio: {e}")

            # Clear import service memory (za auto-kombinovanje Loren parova)
            try:
                from services.import_service import get_import_service
                service = get_import_service()
                service.clear_memory()
            except Exception as e:
                pass  # Ne blokiraj ako clear_memory ne uspije

            return True

        except Exception as e:
            logger.error(f"[_on_create_naimenovanja] Greška: {e}", exc_info=True)
            if not auto:
                QMessageBox.critical(
                    self, "Greška", f"Greška prilikom kreiranja naimenovanja:\n\n{str(e)}"
                )
            return False
        finally:
            if button_text is not None and hasattr(self, "btn_create_naimenovanja"):
                self.btn_create_naimenovanja.setText(button_text)
                self.btn_create_naimenovanja.setEnabled(True)
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
                # Ažuriraj draft u NaimenovanjaView na trenutno aktivni draft
                naim_view = getattr(main_window.naimenovanje_tab, "view", None)
                if naim_view and hasattr(naim_view, "draft"):
                    naim_view.draft = self.draft
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

    def _on_validate_all(self, auto=False) -> tuple[bool, int, int]:
        """
        Handle Validate button click.

        Returns:
            (ok, error_count, warning_count) — ok=False kad validacija nije ni
            pokrenuta (nema stavki) ili je pukla izuzetkom (error_count=-1 u
            tom slučaju). Vidi docs/agent/AGENT_MODE_IMPROVEMENT_IMPLEMENTATION_PLAN.md §7.
        """
        if not self.draft.invoice_lines:
            if not auto:
                QMessageBox.information(self, "Nema stavki", "Nema stavki za validaciju.")
            return (False, 0, 0)

        try:
            # Sync table data to draft first (in case user edited cells)
            self._sync_table_to_draft()

            # Selekcija redova (isti obrazac kao Auto-popuni i istorijska tarifna
            # provjera): ako korisnik ima selektovane redove, sažetak/brojevi se
            # odnose SAMO na te redove — bez ovoga bi "Provjeri" na 2 selektovane
            # stavke ipak prijavio grešku/upozorenja iz svih 94 stavki fakture.
            row_indexes = None
            if not auto and hasattr(self, "table"):
                selection = self.table.selectionModel()
                selected_rows = selection.selectedRows() if selection else []
                if selected_rows:
                    candidate_indexes = sorted(
                        {
                            idx.row()
                            for idx in selected_rows
                            if 0 <= idx.row() < len(self.draft.invoice_lines)
                        }
                    )
                    if candidate_indexes:
                        row_indexes = candidate_indexes

            # Revalidate all rows (bojenje ostaje na SVIM redovima — jeftino i
            # održava tabelu vizuelno ažurnom bez obzira na selekciju)
            self.table.blockSignals(True)
            try:
                for row in range(self.table.rowCount()):
                    item = self.draft.invoice_lines[row]
                    self._validate_and_color_row(row, item)
            finally:
                self.table.blockSignals(False)

            # Force table repaint to show updated colors
            self.table.viewport().update()

            # Update status bar
            self._update_status_bar()

            # Count results iz cache-a (već ažuriran u prethodnoj petlji) —
            # scoped na selekciju ako je aktivna, inače sve stavke (staro ponašanje)
            if row_indexes is not None:
                error_count = warning_count = valid_count = 0
                for row in row_indexes:
                    result = self.validation_cache.get(row)
                    if result is None:
                        continue
                    if result.has_blocking_errors():
                        error_count += 1
                    elif result.warnings:
                        warning_count += 1
                    elif result.valid:
                        valid_count += 1
                total_count = len(row_indexes)
            else:
                error_count = self.validation_cache.get_error_count()
                warning_count = self.validation_cache.get_warning_count()
                valid_count = self.validation_cache.get_valid_count()
                total_count = len(self.draft.invoice_lines)
            error_issues, warning_issues = self._validation_issue_counts(row_indexes)

            # Show summary
            message = ""
            if row_indexes is not None:
                message += f"📌 Prikazano samo za {len(row_indexes)} selektovanih stavki.\n\n"
            message += "╔══════════════════════════════════════╗\n"
            message += "║      REZULTAT VALIDACIJE             ║\n"
            message += "╠══════════════════════════════════════╣\n"
            message += f"║  Ukupno stavki: {total_count:>4}                ║\n"
            message += f"║  ✅ Validne:     {valid_count:>4}                ║\n"
            message += f"║  ❌ Nevažeće:    {error_count:>4}                ║\n"
            message += "╠══════════════════════════════════════╣\n"
            message += f"║  🔴 Greške:      {error_count:>4}                ║\n"
            message += f"║  🟡 Upozorenja:  {warning_count:>4}                ║\n"
            message += "╚══════════════════════════════════════╝\n"
            if error_issues:
                message += "\nGreške po tipu:\n"
                for label, count in sorted(error_issues.items(), key=lambda item: (-item[1], item[0])):
                    message += f"  • {count} {label}\n"
            if warning_issues:
                message += "\nUpozorenja po tipu:\n"
                for label, count in sorted(warning_issues.items(), key=lambda item: (-item[1], item[0])):
                    message += f"  • {count} {label}\n"

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
            self._run_historical_tariff_validation(auto=auto)

            return (True, error_count, warning_count)

        except Exception as e:
            logger.error("Validacija greška: %s", e, exc_info=True)
            if not auto:
                self.error_handler.handle_validation_error(e)
            return (False, -1, -1)

    def _run_historical_tariff_validation(self, modal=False, auto=False):
        """
        Pokreni istorijsku validaciju tarifa u pozadinskom threadu i prikaži
        dialog ako ima prijedloga (vidi HistoricalValidationWorker — DB upiti
        po stavci su prespori za UI thread, ranije je ovo blokiralo UI poslije
        svakog importa, docs/CONTEXT.md §59).

        auto=True (puna automatizacija): dijalog se NIKAD ne prikazuje, čak ni
        modalno — inače bi pipeline visio čekajući korisnika za nešto što nije
        jedina obavezna deklarantska potvrda (vidi plan §7, korak 4). Prijedlozi
        se samo loguju kao informacija.

        Selekcija redova (korisnička primjedba 2026-07-21): ako korisnik ima
        selektovane redove u tabeli, "Provjeri" provjerava SAMO te redove —
        isti obrazac kao Auto-popuni (_on_auto_fill). Bez ovoga se uvijek
        provjeravaju SVE stavke, pa dijalog sa prijedlozima za desetine
        nepovezanih redova zbunjuje korisnika koji je namjerno selektovao
        konkretnu(e) stavku(e) i pokušava prihvatiti baš njen prijedlog.
        """
        try:
            izvoznik = getattr(self.draft, 'izvoznik_naziv', '') or ''
            primalac = getattr(self.draft, 'primalac_naziv', '') or ''

            target_lines = self.draft.invoice_lines
            row_indexes = None
            if not auto and hasattr(self, "table"):
                selection = self.table.selectionModel()
                selected_rows = selection.selectedRows() if selection else []
                if selected_rows:
                    candidate_indexes = sorted(
                        {
                            idx.row()
                            for idx in selected_rows
                            if 0 <= idx.row() < len(self.draft.invoice_lines)
                        }
                    )
                    if candidate_indexes:
                        row_indexes = candidate_indexes
                        target_lines = [
                            self.draft.invoice_lines[row] for row in row_indexes
                        ]

            if not target_lines:
                return

            # Prethodni worker (ako još radi) se otkazuje — best-effort, DB
            # upit koji je već u toku se ne prekida, ali token guard u
            # _on_historical_validation_finished odbacuje njegov (kasniji,
            # zastarjeli) rezultat.
            if (
                self.historical_validation_worker is not None
                and self.historical_validation_worker.isRunning()
            ):
                self.historical_validation_worker.cancel()

            self._historical_validation_token += 1
            my_token = self._historical_validation_token
            my_generation = self._validation_generation

            worker = HistoricalValidationWorker(target_lines, izvoznik, primalac)
            self.historical_validation_worker = worker
            worker.finished_validation.connect(
                lambda matches, auto_applied, auto_rejected: self._on_historical_validation_finished(
                    matches,
                    auto_applied,
                    auto_rejected,
                    row_indexes=row_indexes,
                    auto=auto,
                    modal=modal,
                    token=my_token,
                    generation=my_generation,
                )
            )
            worker.error_occurred.connect(
                lambda message: self._on_historical_validation_error(message, auto=auto)
            )
            worker.finished.connect(
                lambda: self._cleanup_historical_validation_worker(worker)
            )
            worker.start()

        except Exception as e:
            logger.warning("Istorijska validacija greška: %s", e)

    def _cleanup_historical_validation_worker(self, worker) -> None:
        if self.historical_validation_worker is worker:
            self.historical_validation_worker = None
        worker.deleteLater()

    def _on_historical_validation_error(self, message: str, auto: bool = False) -> None:
        logger.warning("Istorijska validacija greška: %s", message)
        # auto=True (puna automatizacija): dijalog se NIKAD ne prikazuje, isti
        # razlog kao u _on_historical_validation_finished — samo se loguje.
        if not auto:
            QMessageBox.warning(self, "Istorijska provjera nije uspjela", message)

    def _on_historical_validation_finished(
        self,
        matches: list,
        auto_applied: list,
        auto_rejected: list,
        row_indexes,
        auto: bool,
        modal: bool,
        token: int,
        generation: int,
    ) -> None:
        """
        Slot pozvan na glavnom threadu kad HistoricalValidationWorker završi.
        Sadržaj je neizmijenjen iz ranije sinhrone verzije — samo mjesto
        izvršavanja logike za primjenu/dijalog je premješteno ovdje.
        """
        if token != self._historical_validation_token:
            logger.debug("Istorijska validacija (worker) odbačena — zamijenjena novijim pozivom")
            return
        if generation != self._validation_generation:
            logger.debug("Istorijska validacija (worker) odbačena — draft promijenjen u međuvremenu")
            return

        from gui.tabs.agent.widgets.tariff_validation_dialog import TariffValidationDialog

        try:
            # KRITIČNO: match.line_index i auto_applied/auto_rejected indeksi
            # su pozicije UNUTAR target_lines (0..len(target_lines)-1), ne
            # stvarni red u self.draft.invoice_lines — kad je target_lines
            # filtrirana selekcija, indeks mora nazad na pravi red prije upisa
            # u tabelu ili u draft, inače se promjena upiše u POGREŠAN red.
            if row_indexes is not None:
                for match in matches:
                    if 0 <= match.line_index < len(row_indexes):
                        match.line_index = row_indexes[match.line_index]
                auto_applied = [
                    (row_indexes[local_idx], tarif)
                    for local_idx, tarif in auto_applied
                    if 0 <= local_idx < len(row_indexes)
                ]
                auto_rejected = [
                    (row_indexes[local_idx], tarif)
                    for local_idx, tarif in auto_rejected
                    if 0 <= local_idx < len(row_indexes)
                ]
            if auto_applied:
                self.table.blockSignals(True)
                try:
                    for idx, tarif in auto_applied:
                        if 0 <= idx < len(self.draft.invoice_lines):
                            self._set_table_item(idx, 4, tarif, align=Qt.AlignCenter)
                            self._validate_and_color_row(idx, self.draft.invoice_lines[idx])
                finally:
                    self.table.blockSignals(False)
                self.table.viewport().update()
                self._update_status_bar()

                # Transparentnost (korisnička primjedba 2026-07-21): ovo se
                # ranije dešavalo POTPUNO tiho kad god postoji ranija ručna
                # potvrda (user_feedback) za baš ovaj par naziv→tarifa — jača
                # dokaz od "korišten Nx u deklaracijama" (carina nije odbila
                # ≠ neko je stvarno provjerio), ali je i dalje samo JEDNA
                # ranija ljudska odluka koja se od tad tiho ponavlja bez ikad
                # ponovnog pregleda — isti obrazac kao poznat bug GREJAC
                # SPIRALA/Plamenik. Korisnik sad MORA vidjeti šta se i zašto
                # promijenilo, u interaktivnom modu.
                if not auto:
                    self._notify_auto_applied_tariffs(auto_applied)
                else:
                    logger.info(
                        "Istorijska validacija (auto mod): %d tarifa automatski "
                        "primijenjeno na osnovu ranije ručne potvrde",
                        len(auto_applied),
                    )

            if auto_rejected:
                # Simetrično sa auto_applied transparentnošću: ranije se ODBIJANJE
                # (baš kao i prihvatanje) dešavalo potpuno tiho — korisnik nikad
                # nije vidio DA je prijedlog za neku stavku preskočen niti ZAŠTO
                # (ranija eksplicitna odluka "Odbij" u 'Provjeri' dijalogu).
                if not auto:
                    self._notify_auto_rejected_tariffs(auto_rejected)
                else:
                    logger.info(
                        "Istorijska validacija (auto mod): %d prijedloga preskočeno "
                        "na osnovu ranije ručne odluke 'Odbij'",
                        len(auto_rejected),
                    )

            if not matches:
                # Kad je korisnik eksplicitno selektovao stavke i kliknuo
                # "Provjeri", tišina (bez ijedne poruke) se lako protumači kao
                # da dijalog "nije htio" da se otvori. Bez selekcije (provjera
                # cijele fakture) tišina ostaje namjerna — ne zamarati porukom
                # na svaki klik kad nema šta reći za desetine stavki.
                if row_indexes is not None and not auto_applied and not auto_rejected:
                    n = len(row_indexes)
                    QMessageBox.information(
                        self,
                        "Provjeri",
                        f"Provjereno {n} selektovan{'a' if n == 1 else 'ih'} "
                        f"stavk{'a' if n == 1 else 'i'} — nema boljeg istorijskog "
                        f"prijedloga od trenutno unesenog tarifnog broja.",
                    )
                return  # Nema prijedloga — tiho

            if auto:
                logger.info(
                    "Istorijska validacija: %d prijedloga tarifa (auto mod — dijalog preskočen)",
                    len(matches),
                )
                return

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

    def _notify_auto_applied_tariffs(self, auto_applied: list) -> None:
        """
        Prikaži jasnu poruku kad se tarifa automatski upiše zbog RANIJE
        RUČNE potvrde (user_feedback), ne samo zato što je viđena u ranijim
        deklaracijama. Ovo je jača evidencija od "korišten Nx", ali je i
        dalje samo JEDNA ljudska odluka koja se od tad tiho ponavlja bez
        ikad ponovnog pregleda — korisnik mora imati priliku da je uhvati
        ako je bila pogrešna (vidi project_rooms/2026-07-21_preciznost-tarifnih-prijedloga.md).

        Tabela sa opisom tarife (isti format kao _show_tariff_preview_dialog,
        vidi _build_tariff_table_widget) — korisnička primjedba 2026-07-26:
        goli tekst "naziv → tarifa" tjera deklaranta da opis nove tarife sam
        traži u tarifniku/šifarniku, što remeti radni tok.
        """
        naziv_by_idx = {
            idx: (self.draft.invoice_lines[idx].naziv_robe or "")
            for idx, _ in auto_applied
            if 0 <= idx < len(self.draft.invoice_lines)
        }
        rows = [
            {
                "rb": idx + 1,
                "naziv": naziv_by_idx.get(idx, ""),
                "tarif": tarif,
                "izvor": "Ranija ručna potvrda (100%)",
                "opis": self._get_tariff_description(tarif),
            }
            for idx, tarif in auto_applied
        ]
        self._show_tariff_table_info_dialog(
            "Automatski ažurirane tarife (ranija potvrda)",
            f"Automatski je ažurirano <b>{len(auto_applied)}</b> tarifnih brojeva jer ste ih "
            "RANIJE RUČNO potvrdili kroz 'Provjeri' — to je jača evidencija od pukog "
            "korištenja u prethodnim deklaracijama, ali je i dalje samo jedna ranija "
            "odluka koja se ponavlja bez novog pregleda.<br>"
            "Provjerite da li su opisi i dalje tačni za date proizvode.",
            rows,
        )

    def _notify_auto_rejected_tariffs(self, auto_rejected: list) -> None:
        """
        Simetrično sa _notify_auto_applied_tariffs — prikaži jasnu poruku kad
        se istorijski prijedlog PRESKOČI zbog ranije eksplicitne odluke
        "Odbij" u 'Provjeri' dijalogu. Bez ovoga korisnik ne zna DA je nešto
        preskočeno niti ZAŠTO — tišina se lako protumači kao "nema prijedloga"
        umjesto "prijedlog postoji ali ste ga ranije odbili".
        """
        naziv_by_idx = {
            idx: (self.draft.invoice_lines[idx].naziv_robe or "")
            for idx, _ in auto_rejected
            if 0 <= idx < len(self.draft.invoice_lines)
        }
        lines_txt = "\n".join(
            f"  Rb.{idx + 1}: {naziv_by_idx.get(idx, '')[:45]} (bio bi predložen: {tarif})"
            for idx, tarif in auto_rejected
        )
        self._show_scrollable_info_dialog(
            "Prijedlozi preskočeni (ranije odbijeno)",
            f"Preskočeno je {len(auto_rejected)} istorijskih prijedloga jer ste ih "
            f"RANIJE EKSPLICITNO ODBILI kroz 'Provjeri' — trenutni tarifni brojevi na "
            f"tim stavkama ostaju nepromijenjeni.\n\n"
            f"{lines_txt}\n\n"
            f"Ako se predomislite, ručno izmijenite tarifni broj pa ponovo pokrenite "
            f"'Provjeri'."
        )

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

    def _on_calculate_masses(self, auto=False) -> bool:
        """
        Handle Calculate Masses button click - proporcionalno raspodjeli težine.

        Returns:
            True ako je bar jedna stavka ažurirana, False ako nije (nedostaju
            unosi, neispravna vrijednost, nema stavki za update, itd.) — vidi
            docs/agent/AGENT_MODE_IMPROVEMENT_IMPLEMENTATION_PLAN.md §7.
        """
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
                return False

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
                return False

        except ValueError as e:
            logger.error(f"❌ ValueError: {e}")
            if not auto:
                QMessageBox.critical(
                    self,
                    "Greška",
                    "Neispravna vrijednost težine. Koristite brojeve (npr. 1234.56).",
                )
            return False

        logger.debug(f"\n🔍 Ukupno stavki u draft-u: {len(self.draft.invoice_lines)}")

        from services.faktura.mass_calculator import MassCalculator

        invoice_groups, no_invoice_lines, invoice_labels = group_lines_by_invoice(
            self.draft.invoice_lines
        )
        invoice_weights = normalized_invoice_weights(self.draft.invoice_weights)

        # Ako je neto unesen u toolbar a sve sačuvane neto vrijednosti su 0
        # (neto nije bio dostupan u fajlu), rasporedi toolbar neto proporcionalno.
        # Ovo pokriva slučaj kad korisnik upiše neto=bruto (ili bilo koji neto)
        # za fakture gdje ga fajl nije sadržavao (npr. Šumaprom XLS bez neto težine).
        if neto_total > 0 and invoice_weights:
            stored_neto_sum = sum(n for _, n in invoice_weights.values())
            if stored_neto_sum == 0:
                total_stored_bruto = sum(b for b, _ in invoice_weights.values())
                if total_stored_bruto > 0:
                    for key in list(invoice_weights.keys()):
                        inv_bruto, _ = invoice_weights[key]
                        proportion = inv_bruto / total_stored_bruto
                        invoice_weights[key] = (inv_bruto, round(neto_total * proportion, 3))
                    logger.debug(
                        f"   ℹ️ Neto iz toolbar-a ({neto_total:.3f} kg) raspoređen proporcionalno "
                        f"na {len(invoice_weights)} faktura(e)"
                    )

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
                return False
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
                return False
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
                return False
            logger.debug("   ❌ Nema stavki za update - sve imaju obe težine")
            if not auto:
                QMessageBox.information(
                    self,
                    "Sve težine popunjene",
                    "Sve stavke već imaju upisane obe težine (bruto i neto). Nema šta da se računa.",
                )
            return False

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
        return True

    def _on_auto_fill(self, auto=False):
        """
        Auto-popuni tarifne brojeve iz baze znanja.

        Args:
            auto: Ako True, preskoči dijaloge i preskači ako su sve tarife popunjene.

        Returns:
            MappingResult ako je popunjavanje izvršeno, inače None.
        """
        if not self.draft.invoice_lines:
            if not auto:
                QMessageBox.information(
                    self,
                    "Auto-popuni",
                    "Nema stavki za popunjavanje.\n\nPrvo učitajte fakturu.",
            )
            return None

        # U auto modu preskači ako su sve tarife već popunjene
        if auto:
            bez_tarife = [l for l in self.draft.invoice_lines if not getattr(l, 'tarifni_broj', None)]
            if not bez_tarife:
                logger.info("✅ [Auto-popuni] Sve stavke imaju tarifni broj — preskačem")
                return None

        selected_row = -1
        selected_row_indexes = []
        target_lines = self.draft.invoice_lines
        if not auto and hasattr(self, "table"):
            selection = self.table.selectionModel()
            selected_rows = selection.selectedRows() if selection else []
            if selected_rows:
                row_indexes = sorted(
                    {
                        idx.row()
                        for idx in selected_rows
                        if 0 <= idx.row() < len(self.draft.invoice_lines)
                    }
                )
                if row_indexes:
                    selected_row_indexes = row_indexes
                    selected_row = row_indexes[0]
                    target_lines = [self.draft.invoice_lines[row] for row in row_indexes]
            else:
                # Nema selekcije — ograniči samo na stavke bez tarifnog broja
                target_lines = [l for l in self.draft.invoice_lines if not getattr(l, 'tarifni_broj', None)]

        # Undo snapshot PRIJE fill_basic_fields() — ta metoda MUTIRA stavke
        # odmah, i prije preview dijaloga i prije eventualnog otkazivanja;
        # bez snapshot-a ovdje "Otkaži" u dijalogu ostavlja neundo-vateljivu
        # mutaciju (Codex nalaz #5).
        self._push_undo_snapshot()

        # Prvo popuni osnovna polja (valuta, jm, iznos)
        basic_filled_count = self.auto_fill_service.fill_basic_fields(
            target_lines
        )

        # Auto-popuni tarifne iz baze znanja — docs/architecture/TARIFF_FACADE_REFACTORING.md
        try:
            from services.tariff_facade import TariffFacade

            facade = TariffFacade.get_instance()

            # Skupi skipped stavke (već imaju tarifni broj)
            skipped_details = [
                (
                    line.line_no,
                    line.product_code or line.naziv_robe[:30],
                    line.tarifni_broj,
                )
                for line in target_lines
                if line.tarifni_broj
            ]

            supplier_name = ""
            if target_lines:
                supplier_name = target_lines[0].exporter.name or ""

            # U interaktivnom modu: preview prijedloga PRIJE pisanja
            if not auto:
                progress = QProgressDialog(
                    "Tražim prijedloge tarifnih brojeva...",
                    "Otkaži",
                    0,
                    len(target_lines),
                    self,
                )
                progress.setWindowTitle("Auto-popuni tarifne")
                progress.setWindowModality(Qt.WindowModal)
                progress.setMinimumDuration(300)
                progress.setValue(0)
                QCoreApplication.processEvents()

                preview_result = self._collect_tariff_previews(target_lines, facade, supplier_name)
                progress.setValue(len(target_lines))

                if not preview_result or not preview_result.proposals:
                    # Nema prijedloga — prikaži poruku i završi bez pisanja
                    from services.tariff.tariff_mapping_service import MappingResult
                    empty = MappingResult(
                        total_items=len(target_lines),
                        matched_items=0,
                        unmatched_items=len(target_lines) - len(skipped_details),
                    )
                    empty.skipped_items = len(skipped_details)
                    empty.skipped_details = skipped_details
                    self._show_tariff_mapping_result(empty, basic_filled_count)
                    return empty

                # Prikaži dijalog potvrde s opisima tarifa PRIJE popunjavanja
                confirmed = self._show_tariff_preview_dialog(target_lines, preview_result.proposals)
                if not confirmed:
                    return None

            else:
                progress = None
                preview_result = None

            # Primijeni (ili auto mod bez potvrde) — undo snapshot je već
            # napravljen prije fill_basic_fields() iznad.
            if preview_result is not None:
                # Interaktivni tok: upiši TAČNO ono što je odobreno u dijalogu,
                # bez ponovnog računanja (preview ≡ upis — vidi
                # project_rooms/2026-07-21_preciznost-tarifnih-prijedloga.md).
                result = facade.commit_proposals(target_lines, preview_result.proposals)
            else:
                result = facade.auto_populate_tariffs(
                    target_lines,
                    min_similarity=0.92,
                    overwrite_existing=False,
                    supplier=supplier_name,
                )

            # Dodaj skipped info u result
            result.skipped_items = len(skipped_details)
            result.skipped_details = skipped_details

            if progress is not None:
                progress.setValue(len(target_lines))

            # Reload table to show changes
            self._load_data_from_draft()
            if selected_row_indexes:
                selection_model = self.table.selectionModel()
                if selection_model is not None:
                    selection_model.clearSelection()
                    for row in selected_row_indexes:
                        if 0 <= row < self.table.rowCount():
                            selection = QItemSelection(
                                self.table.model().index(row, 0),
                                self.table.model().index(row, self.table.columnCount() - 1),
                            )
                            selection_model.select(
                                selection,
                                QItemSelectionModel.Select | QItemSelectionModel.Rows,
                            )
                    if selected_row >= 0 and selected_row < self.table.rowCount():
                        selection_model.setCurrentIndex(
                            self.table.model().index(selected_row, 0),
                            QItemSelectionModel.NoUpdate,
                        )

            # Update status bar
            self._update_status_bar()

            # Mark as dirty
            if result.matched_items > 0 or basic_filled_count > 0:
                self.data_changed.emit()
                if self.on_dirty:
                    self.on_dirty()

            # Izvještaj poslije popunjavanja (samo u interaktivnom modu)
            if not auto:
                self._show_tariff_mapping_result(result, basic_filled_count)

            # Sinhronizuj decision_state nakon auto-popune
            if result.matched_items > 0:
                try:
                    from services.decision.integration import sync_decision_state_after_autofill
                    sync_decision_state_after_autofill(
                        target_lines, supplier=supplier_name, action_type="auto_fill_clicked"
                    )
                except Exception:
                    logger.warning("Decision sync autofill nije uspio", exc_info=True)

            return result

        except Exception as e:
            logger.error("Auto-popuni greška: %s", e, exc_info=True)
            if not auto:
                self.error_handler.handle_auto_fill_error(e)
            return None

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

        # Prikaži ŠTA je popunjeno — korisnik mora moći provjeriti da li je tarifa
        # ispravna (baza znanja može sadržati pogrešno naučene mappinge — vidi
        # agent_reports/2026-06-07_pogresna-tarifa-grejac-spirala.md).
        # Koristimo naziv_robe iz drafta (čitljiv korisniku), ne šifru proizvoda
        # koju vraća servis u matched_details — šifre poput "609ER004" korisniku
        # ništa ne znače, dok naziv ("GREJAC SPIRALA 600W") odmah otkriva grešku.
        naziv_by_line = {
            line.line_no: line.naziv_robe
            for line in self.draft.invoice_lines
            if getattr(line, 'naziv_robe', None)
        }
        if result.matched_details:
            message += "\nPopunjene stavke (provjerite da li su tarife ispravne):\n"
            for i, (line_no, product_info, tarif) in enumerate(result.matched_details[:15], 1):
                naziv = naziv_by_line.get(line_no) or product_info
                message += f"  {i}. Stavka #{line_no}: {naziv[:40]} → {tarif}\n"

            if len(result.matched_details) > 15:
                message += f"  ... i još {len(result.matched_details) - 15} stavki\n"

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

        self._show_scrollable_info_dialog("Auto-popuni - Rezultati", message)

    def _get_tariff_description(self, tariff_code: str) -> str:
        """Dohvati kratki opis tarifnog broja iz tarifa_2026 (hijerarhijski).

        Delegira na TariffService.load_hierarchical_label — frozen-svjestan
        putanja (vidi fix §44) i sa cache-om (sprječava N+1 u _show_tariff_preview_dialog).
        """
        if not tariff_code or not tariff_code.isdigit():
            return ""
        try:
            from services.naimenovanja.tariff_service import TariffService
            svc = getattr(self, "_tariff_desc_service", None) or TariffService()
            self._tariff_desc_service = svc
            return svc.load_hierarchical_label(tariff_code)
        except Exception:
            return tariff_code

    def _collect_tariff_previews(self, target_lines: list, facade, supplier: str = ""):
        """
        Izračunaj prijedloge tarifnih brojeva za sve stavke BEZ pisanja u draft
        (dry_run). Vraća MappingResult sa popunjenim .proposals.

        VAŽNO: ovo je ISTI proračun koji će _on_auto_fill kasnije stvarno upisati
        preko facade.commit_proposals(target_lines, result.proposals) — preview
        i upis se više NE računaju odvojeno (raniji suggest_fast() nije uzimao
        u obzir dobavljača ni istoriju XML deklaracija, pa je prikazana tarifa
        mogla biti drugačija od one koja se stvarno upiše). Vidi
        project_rooms/2026-07-21_preciznost-tarifnih-prijedloga.md.
        """
        try:
            result = facade.auto_populate_tariffs(
                target_lines,
                min_similarity=0.92,
                overwrite_existing=False,
                supplier=supplier,
                dry_run=True,
            )
            logger.debug(
                "Auto-popuni preview: %d prijedloga od %d stavki",
                len(result.proposals), len(target_lines),
            )
            return result
        except Exception as e:
            logger.warning("Auto-popuni preview greška: %s", e, exc_info=True)
            return None

    _TARIFF_SOURCE_LABELS = {
        "istorija": "Istorija dobavljača",
        "baza_znanja": "Baza znanja",
    }

    def _build_tariff_table_widget(self, rows: list):
        """
        Zajednička tabela Rb | Naziv proizvoda | Tarifa | Izvor / Pouzdanost |
        Opis tarife — dijeli je dijalog potvrde auto-popune
        (_show_tariff_preview_dialog) i info-dijalog za automatski primijenjene
        tarife (_notify_auto_applied_tariffs), da izgledaju identično i da se
        ne duplira ~50 linija stilizacije.
        rows: lista dict-ova sa ključevima rb, naziv, tarif, izvor, opis.
        """
        from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QFont, QColor

        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(
            ["Rb.", "Naziv proizvoda", "Tarifa", "Izvor / Pouzdanost", "Opis tarife"]
        )
        table.setRowCount(len(rows))
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setAlternatingRowColors(False)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                color: #1a1a1a;
                gridline-color: #d0d0d0;
                font-size: 13px;
            }
            QTableWidget::item {
                background-color: #ffffff;
                color: #1a1a1a;
                padding: 4px 6px;
            }
            QTableWidget::item:alternate {
                background-color: #f5f7fa;
            }
            QTableWidget::item:selected {
                background-color: #cce0ff;
                color: #1a1a1a;
            }
            QHeaderView::section {
                background-color: #e8ecf0;
                color: #1a1a1a;
                font-weight: bold;
                padding: 5px;
                border: 1px solid #c0c8d0;
            }
        """)

        bold_font = QFont()
        bold_font.setBold(True)
        clr_even = QColor("#ffffff")
        clr_odd = QColor("#f5f7fa")

        for i, row in enumerate(rows):
            bg = clr_even if i % 2 == 0 else clr_odd

            item_rb = QTableWidgetItem(str(row.get("rb", "")))
            item_rb.setTextAlignment(Qt.AlignCenter)
            item_naziv = QTableWidgetItem(str(row.get("naziv", ""))[:60])
            item_tarif = QTableWidgetItem(str(row.get("tarif", "")))
            item_tarif.setFont(bold_font)
            item_tarif.setTextAlignment(Qt.AlignCenter)
            item_izvor = QTableWidgetItem(str(row.get("izvor", "")))
            item_opis = QTableWidgetItem(str(row.get("opis", "")))

            for item in (item_rb, item_naziv, item_tarif, item_izvor, item_opis):
                item.setBackground(bg)
                item.setForeground(QColor("#1a1a1a"))

            table.setItem(i, 0, item_rb)
            table.setItem(i, 1, item_naziv)
            table.setItem(i, 2, item_tarif)
            table.setItem(i, 3, item_izvor)
            table.setItem(i, 4, item_opis)

        table.setColumnWidth(0, 45)
        table.setColumnWidth(2, 90)
        table.setColumnWidth(3, 160)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        table.resizeRowsToContents()
        return table

    def _show_tariff_preview_dialog(self, target_lines: list, proposals: list) -> bool:
        """
        Prikaži dijalog potvrde PRIJE auto-popunjavanja.
        Tabela: Rb | Naziv proizvoda | Tarifa | Izvor / Pouzdanost | Opis tarife
        proposals: lista TariffProposal (iz auto_populate_tariffs(dry_run=True)) —
        isti proračun koji će _on_auto_fill kasnije stvarno upisati preko
        facade.commit_proposals(), pa je i confidence/source ovdje istinit,
        ne odbačen kao ranije (vidi
        project_rooms/2026-07-21_preciznost-tarifnih-prijedloga.md).
        Vraća True ako korisnik potvrdi, False ako odustane.
        """
        from PySide6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        )

        dialog = QDialog(self)
        dialog.setWindowTitle("Potvrda auto-popunjavanja tarifnih brojeva")
        layout = QVBoxLayout(dialog)
        layout.setSpacing(10)

        label = QLabel(
            f"Pronađeno <b>{len(proposals)}</b> prijedloga tarifnih brojeva.<br>"
            "Provjerite opise tarifa — ako je opis netačan za dati proizvod, kliknite <b>Odustani</b>."
        )
        label.setWordWrap(True)
        layout.addWidget(label)

        naziv_by_line = {
            line.line_no: (getattr(line, 'naziv_robe', '') or '')
            for line in target_lines
        }

        rows = []
        for proposal in proposals:
            naziv = naziv_by_line.get(proposal.line_no) or proposal.naziv_ili_kod
            tarif = proposal.tarifni_broj
            izvor_label = self._TARIFF_SOURCE_LABELS.get(proposal.source, proposal.source or "?")
            rows.append({
                "rb": proposal.line_no,
                "naziv": naziv,
                "tarif": tarif,
                "izvor": f"{izvor_label} ({int(proposal.confidence * 100)}%)",
                "opis": self._get_tariff_description(tarif),
            })

        table = self._build_tariff_table_widget(rows)
        table.horizontalHeaderItem(4).setText("Opis tarife (provjeri!)")
        layout.addWidget(table)

        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("Potvrdi i popuni")
        btn_ok.setDefault(True)
        btn_cancel = QPushButton("Odustani")
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)

        btn_ok.clicked.connect(dialog.accept)
        btn_cancel.clicked.connect(dialog.reject)

        from PySide6.QtWidgets import QApplication
        screen = self.screen() or QApplication.primaryScreen()
        available = screen.availableGeometry()
        dialog.resize(
            min(1100, available.width() - 80),
            min(600, available.height() - 80),
        )

        return dialog.exec() == QDialog.Accepted

    def _show_tariff_table_info_dialog(self, title: str, intro_html: str, rows: list) -> None:
        """
        Info-only varijanta _show_tariff_preview_dialog-a (bez Potvrdi/Odustani,
        samo OK) — koristi se za notifikacije o tarifama koje su VEĆ primijenjene
        (auto_applied), gdje korisnik ništa ne bira, samo vidi šta se desilo i
        zašto — sa istom Rb/Naziv/Tarifa/Izvor/Opis tabelom kao dijalog potvrde,
        umjesto običnog teksta bez opisa tarife.
        """
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QDialogButtonBox, QApplication

        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        layout = QVBoxLayout(dialog)
        layout.setSpacing(10)

        label = QLabel(intro_html)
        label.setWordWrap(True)
        layout.addWidget(label)

        table = self._build_tariff_table_widget(rows)
        layout.addWidget(table)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(dialog.accept)
        layout.addWidget(button_box)

        screen = self.screen() or QApplication.primaryScreen()
        available = screen.availableGeometry()
        dialog.resize(
            min(1100, available.width() - 80),
            min(600, available.height() - 80),
        )

        dialog.exec()

    def _show_scrollable_info_dialog(self, title: str, text: str):
        """
        Prikaži duži informativni tekst u dijalogu sa scroll-om.

        QMessageBox se nekontrolisano širi sa dužinom teksta — kod rezultata
        Auto-popuni sa puno stavki prozor postane veći od ekrana i dugme OK
        ispadne van vidljivog područja (korisnik ne može zatvoriti dijalog).
        Ovaj dijalog ima fiksnu maksimalnu veličinu i scroll-ujući QTextEdit.
        """
        dialog = QDialog(self)
        dialog.setWindowTitle(title)

        layout = QVBoxLayout(dialog)

        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setFont(QFont("Segoe UI", 10))
        text_edit.setPlainText(text)
        layout.addWidget(text_edit)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(dialog.accept)
        layout.addWidget(button_box)

        from PySide6.QtWidgets import QApplication
        screen = self.screen() or QApplication.primaryScreen()
        available = screen.availableGeometry()
        dialog.resize(
            min(560, available.width() - 100),
            min(620, available.height() - 100),
        )

        dialog.exec()

    def _on_selection_changed(self):
        """Handle table selection change."""
        current = self.table.currentRow()
        has_selection = current >= 0
        self.btn_delete.setEnabled(has_selection)

        if current >= 0 and current == self.table.rowCount() - 1:
            # EnsureVisible skroluje minimum potrebno — ne koristi scrollToBottom()
            # jer _install_bottom_scroll_buffer proširuje max za jedan row_h,
            # pa scrollToBottom() skroluje past sadržaja i sakriva redove.
            from PySide6.QtWidgets import QAbstractItemView
            self.table.scrollTo(self.table.currentIndex(), QAbstractItemView.EnsureVisible)

    def _on_export_excel(self):
        # docs/sections/export-pdf-excel.md — Excel izvoz, grupisanje po naimenovanjima
        """Export fakturnih stavki u Excel."""
        if not self.draft.invoice_lines:
            self._show_no_export_items("Export u Excel")
            return

        # ExportService.export_to_excel grupiše isključivo po
        # assigned_naimenovanje_ordinal > 0 — stavke bez dodijeljenog
        # naimenovanja se TIHO izostavljaju iz fajla (Codex nalaz #3).
        # Upozori korisnika PRIJE izvoza umjesto da otkrije nedostatak
        # tek pri pregledu gotovog fajla.
        missing_ordinal = [
            line for line in self.draft.invoice_lines
            if getattr(line, "assigned_naimenovanje_ordinal", 0) <= 0
        ]
        if missing_ordinal:
            reply = QMessageBox.question(
                self,
                "Nedodijeljene stavke",
                f"{len(missing_ordinal)} od {len(self.draft.invoice_lines)} stavki "
                "nije dodijeljeno nijednom naimenovanju i NEĆE biti u Excel izvozu.\n\n"
                "Da li želite nastaviti izvoz bez tih stavki?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
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

    def _apply_import_result_to_header(self, result) -> None:
        """Prenesi izvoznika, uvoznika i valutu iz ImportResult u draft zaglavlje.

        Popunjava samo prazna polja — ne prepisuje ono što je korisnik već unio.
        """
        exp = getattr(result, 'exporter', None)
        if exp:
            name = (getattr(exp, 'name', '') or '').strip().split('\n')[0].strip()
            if name and not self.draft.izvoznik_naziv:
                self.draft.izvoznik_naziv = name
            addr = (getattr(exp, 'address', '') or '').strip()
            if addr and not self.draft.izvoznik_adresa:
                self.draft.izvoznik_adresa = addr
            city = (getattr(exp, 'city', '') or '').strip()
            if city and not self.draft.izvoznik_grad:
                self.draft.izvoznik_grad = city
            country = (getattr(exp, 'country', '') or '').strip()
            if country and not self.draft.izvoznik_drzava:
                self.draft.izvoznik_drzava = country

        imp = getattr(result, 'importer', None)
        if imp:
            name = (getattr(imp, 'name', '') or '').strip().split('\n')[0].strip()
            if name and not self.draft.primalac_naziv:
                self.draft.primalac_naziv = name
            vat = (getattr(imp, 'vat_or_id', '') or '').strip()
            if vat and not self.draft.primalac_id:
                self.draft.primalac_id = vat
            addr = (getattr(imp, 'address', '') or '').strip()
            if addr and not self.draft.primalac_adresa:
                self.draft.primalac_adresa = addr

        currency = (getattr(result, 'currency', '') or '').strip()
        if currency and currency != 'EUR' and not self.draft.valuta:
            self.draft.valuta = currency

        incoterm_code = (getattr(result, 'incoterm_code', '') or '').strip()
        if incoterm_code and not self.draft.uslovi_kod:
            self.draft.uslovi_kod = incoterm_code

    def _on_load_previous_declaration(self):
        """Učitaj zaglavlje iz prethodne deklaracije istog izvoznika."""
        # Prioritet: draft zaglavlje (popunjeno iz _apply_import_result_to_header)
        # → exporter na prvoj invoice liniji → ručni odabir
        izvoznik = (self.draft.izvoznik_naziv or '').strip()
        if not izvoznik and self.draft.invoice_lines:
            for line in self.draft.invoice_lines:
                cand = (getattr(getattr(line, 'exporter', None), 'name', '') or '').strip()
                if cand:
                    izvoznik = cand.split('\n')[0].strip()
                    break

        xml_path = None

        if izvoznik:
            try:
                from services.agent.learning.exporter_xml_indexer import find_xml_for_pair
                result = find_xml_for_pair(izvoznik)
                if result:
                    xml_path = result.get('xml_filepath')
            except Exception as exc:
                logger.warning("find_xml_for_pair greška: %s", exc)

        # Ako nije pronađen automatski — ponudi ručni odabir
        if not xml_path:
            msg = (
                f"Nije pronađena prethodna deklaracija za izvoznika '{izvoznik}'.\n\n"
                if izvoznik else
                "Nije poznat izvoznik — nije moguća automatska pretraga.\n\n"
            )
            msg += "Odaberi XML fajl ručno?"
            reply = QMessageBox.question(
                self, "Prethodna deklaracija", msg,
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
            )
            if reply != QMessageBox.Yes:
                return
            path, _ = QFileDialog.getOpenFileName(
                self, "Odaberi ASYCUDA XML deklaraciju", "", "XML Files (*.xml)"
            )
            if not path:
                return
            xml_path = path

        # Parsiraj header iz XML-a
        try:
            header = self._extract_header_from_xml(xml_path)
        except Exception as exc:
            QMessageBox.critical(self, "Greška", f"Nije moguće parsirati XML:\n{exc}")
            return

        if not header:
            QMessageBox.warning(self, "Prethodna deklaracija", "XML ne sadrži prepoznatljive header podatke.")
            return

        # Prikaži šta će biti učitano
        lines = []
        field_labels = {
            'izvoznik_naziv': 'Izvoznik',
            'drzava_izvoza_sifra': 'Država izvoza',
            'valuta': 'Valuta',
            'uslovi_kod': 'Incoterm',
            'uslovi_mjesto': 'Mjesto isporuke',
            'deklaracija_tip': 'Tip deklaracije',
            'deklaracija_a': 'Oznaka',
            'deklaracija_oznaka': 'Procedura',
        }
        for field, label in field_labels.items():
            if header.get(field):
                lines.append(f"  {label}: {header[field]}")

        confirm = QMessageBox.question(
            self,
            "Prethodna deklaracija",
            f"Pronađena prethodna deklaracija:\n\n" + "\n".join(lines) +
            "\n\nUčitati ove podatke u zaglavlje?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if confirm != QMessageBox.Yes:
            return

        # Upiši u draft
        for field, value in header.items():
            if value and hasattr(self.draft, field):
                setattr(self.draft, field, value)

        # Obavijesti ZaglavljeView da se reload-uje
        try:
            main_window = self.window()
            if hasattr(main_window, 'zaglavlje_tab'):
                main_window.zaglavlje_tab.load_from_draft(self.draft)
        except Exception as exc:
            logger.warning("Zaglavlje reload greška: %s", exc)

        self._notify_data_changed()
        self.lbl_validation.setText("✓ Zaglavlje učitano iz prethodne deklaracije")
        self.lbl_validation.setProperty("status", "success")
        self.lbl_validation.style().unpolish(self.lbl_validation)
        self.lbl_validation.style().polish(self.lbl_validation)
        self._learn_notify_timer.start()

    @staticmethod
    def _extract_header_from_xml(xml_path: str) -> dict:
        """Parsira ASYCUDA XML i vraća dict sa header poljima za DeclarationDraft."""
        tree = safe_parse(xml_path)
        root = tree.getroot()

        def _text(xpath: str) -> str:
            el = root.find(xpath)
            return (el.text or '').strip().split('\n')[0].strip() if el is not None else ''

        header = {}

        # Izvoznik — samo prva linija (ostale su adresa)
        izvoznik = _text('.//Traders/Exporter/Exporter_name')
        if izvoznik:
            header['izvoznik_naziv'] = izvoznik

        # Zemlja izvoza
        zem = _text('.//General_information/Country/Export/Export_country_code')
        if zem:
            header['drzava_izvoza_sifra'] = zem
            naziv = _text('.//General_information/Country/Export/Export_country_name')
            if naziv:
                header['drzava_izvoza_naziv'] = naziv

        # Valuta (iz Gs_Invoice bloka)
        val = _text('.//Valuation/Gs_Invoice/Currency_code')
        if val:
            header['valuta'] = val

        # Incoterm i mjesto — uzimamo iz prve stavke
        incoterm = _text('.//Item/IncoTerms/Code')
        if incoterm:
            header['uslovi_kod'] = incoterm
        place = _text('.//Item/IncoTerms/Place')
        if place:
            header['uslovi_mjesto'] = place

        # Tip deklaracije
        tip = _text('.//Identification/Type/Type_of_declaration')
        if tip:
            header['deklaracija_tip'] = tip
        ozn = _text('.//Identification/Type/Declaration_gen_procedure_code')
        if ozn:
            header['deklaracija_oznaka'] = ozn
        tip_x = _text('.//Identification/Type/Type_of_Declaration_X')
        if tip_x:
            header['deklaracija_a'] = tip_x

        return header

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
            _clear_secondary_pe_documents(item)
            raw_doc4 = (getattr(item, 'attached_document4', '') or '').strip()
            doc4 = _normalize_pe_document_text(raw_doc4)
            if doc4 != raw_doc4:
                item.attached_document4 = doc4
            if not doc4:
                continue
            parts = doc4.split(' ', 1)
            sifra = parts[0].strip()
            broj = parts[1].strip() if len(parts) > 1 else ''
            if sifra in _PE_DOC_CODES:
                key = (sifra, broj)
                if key not in seen:
                    seen.add(key)
                    pe_entries.append(key)

        # 2. Ukloni postojeće PE1/PE2/PE3 unose iz header_attached_documents
        header_docs[:] = [d for d in header_docs if d.code not in _PE_DOC_CODES]

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
