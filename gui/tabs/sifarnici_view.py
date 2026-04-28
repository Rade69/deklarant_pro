# gui/tabs/sifarnici_tab.py
import logging
import re
import traceback

# Čisti sufiks s tarifnim stopama iz opisa (npr. "kd 0 0 0 0 0 0 0 0")
_TAIL_RATES_RE = re.compile(r'(?:\s+\w{1,3})?(?:\s+\d+){4,}\s*$')
from typing import Optional, Callable, Dict, Any, List, Tuple, Union
from dataclasses import dataclass
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QFrame,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QTableWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QHeaderView,
    QPushButton,
    QLineEdit,
    QComboBox,
    QToolButton,
    QGridLayout,
    QGroupBox,
    QFormLayout,
    QTableWidgetItem,
    QMessageBox,
    QApplication,
    QMainWindow,
    QMenu,
)
from PySide6.QtCore import Qt, Signal, QSize, QTimer
from PySide6.QtGui import QIcon, QKeySequence, QShortcut, QPalette, QColor, QFont
import psycopg2

try:
    import qtawesome as qta
    QTAWESOME_AVAILABLE = True
except ImportError:
    QTAWESOME_AVAILABLE = False

from core.draft import DeclarationDraft
from gui.tabs.base_view import BaseTabView

# Import database functions
from services.sifarnici_service import SifarniciService

# Izdvojene komponente
from gui.tabs.sifarnici import PartnerFormStrip, populate_tariff_hierarchy, is_code_search

# Core utils — generičke klase
from core.utils import FormValidator, ValidationRule, UIHelper

logger = logging.getLogger(__name__)


@dataclass
class PosiljalacData:
    """Data class za pošiljaoca"""

    jib: str
    naziv: str
    adresa: str = ""
    grad: str = ""
    postanski_broj: str = ""
    zemlja: str = ""
    telefon: str = ""
    email: str = ""
    kontakt: str = ""
    pdv: str = ""
    maticni: str = ""


class SifarniciView(BaseTabView):
    """
    Šifrarnici Tab - Production Version
    Tačan layout kao na slici sa 2-column detail form
    """

    def __init__(
        self, draft: Optional[DeclarationDraft] = None, on_dirty: Optional[Callable] = None
    ):
        super().__init__()
        logger.info("Inicijalizacija SifarniciTab komponente")

        self.draft = draft if draft else DeclarationDraft()
        self.on_dirty = on_dirty
        self.current_category = None
        self.is_editing = False
        self.current_row_index = -1
        self.validator = FormValidator()
        self.ui_helper = UIHelper()
        self.service = SifarniciService()
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._execute_db_search)

        self.setObjectName("SifarniciTab")

        try:
            self._init_ui()
            self._setup_shortcuts()
            self._load_category("Pošiljaoci")
            logger.info("SifarniciTab uspešno inicijalizovan")
        except Exception as e:
            logger.error(f"Greška pri inicijalizaciji SifarniciTab: {str(e)}")
            raise

    def _init_ui(self):
        """Main UI setup"""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        sidebar = self._create_sidebar()
        main_layout.addWidget(sidebar)

        # Main area
        main_area = self._create_main_area()
        main_layout.addWidget(main_area, stretch=1)

    def _create_sidebar(self) -> QWidget:
        """Sidebar sa kategorijama — stil usklađen sa Admin tabom (admin_tab.qss)."""
        sidebar = QFrame()
        sidebar.setFrameShape(QFrame.NoFrame)
        sidebar.setMaximumWidth(220)
        sidebar.setMinimumWidth(180)
        sidebar.setStyleSheet(
            "QFrame { background-color: #e8f2e8; border-right: 1px solid #c8dcc8; }"
        )

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header — sage green stil
        title = QLabel("<h3>Šifrarnici</h3>")
        title.setStyleSheet(
            "padding: 12px 16px; font-size: 14px; font-weight: bold;"
            " color: #1e3820; background-color: #e8f2e8;"
            " border-bottom: 1px solid #c8dcc8;"
        )
        layout.addWidget(title)

        # Categories list — sage green nav
        self.categories_list = QListWidget()
        self.categories_list.setFrameShape(QFrame.NoFrame)
        self.categories_list.setStyleSheet(
            """
            QListWidget {
                background-color: #e8f2e8;
                border: none;
                outline: none;
                font-size: 13px;
                padding: 8px;
            }
            QListWidget::item {
                padding: 10px 8px;
                border-radius: 4px;
                margin: 2px 0;
                color: #1e3820;
            }
            QListWidget::item:hover {
                background-color: #c8dcc8;
            }
            QListWidget::item:selected {
                background-color: #5a8060;
                color: white;
                font-weight: bold;
            }
            """
        )

        # Kategorije sa Font Awesome 5 Solid ikonicama
        categories = [
            ("fa5s.list-alt",      "Carinske tarife",      "Carinske tarife"),
            ("fa5s.paper-plane",   "Pošiljaoci",            "Pošiljaoci"),
            ("fa5s.truck",         "Uvoznici",              "Uvoznici"),
            ("fa5s.id-card",       "Deklaranti",            "Deklaranti"),
            ("fa5s.landmark",      "Carinarnice",           "Carinarnice"),
            ("fa5s.cogs",          "Carinski postupci",     "Carinski postupci"),
            ("fa5s.globe",         "Zemlje",                "Zemlje"),
            ("fa5s.clipboard-check", "Inspekcijska pravila", "Inspekcijska pravila"),
            ("fa5s.exchange-alt",  "Inkoterms",             "Inkoterms"),
            ("fa5s.chart-bar",     "Tarifne kvote",         "Tarifne kvote"),
        ]
        fallback_emojis = ["📦", "📤", "📥", "💼", "🏛", "⚙️", "🌐", "🔬", "🚢", "📊"]

        for i, (icon_name, display, data) in enumerate(categories):
            if QTAWESOME_AVAILABLE:
                try:
                    qta_icon = qta.icon(
                        icon_name,
                        color="#333333",
                        color_active="white",
                        color_selected="white",
                        scale_factor=1.0,
                    )
                    item = QListWidgetItem(qta_icon, f"  {display}")
                except Exception:
                    item = QListWidgetItem(f"{fallback_emojis[i]}  {display}")
            else:
                item = QListWidgetItem(f"{fallback_emojis[i]}  {display}")

            item.setData(Qt.UserRole, data)
            self.categories_list.addItem(item)

        # Signal
        self.categories_list.currentRowChanged.connect(self._on_category_changed)

        layout.addWidget(self.categories_list)

        return sidebar

    def _create_main_area(self) -> QWidget:
        """Main content area"""
        try:
            logger.info("Kreiranje glavnog prostora")

            main_area = QWidget()
            palette = main_area.palette()
            palette.setColor(QPalette.Window, QColor("white"))
            main_area.setPalette(palette)
            main_area.setAutoFillBackground(True)
            layout = QVBoxLayout(main_area)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)

            # Header bar
            header_bar = self._create_header_bar()
            layout.addWidget(header_bar)

            # Content with margins
            content = QWidget()
            content_layout = QVBoxLayout(content)
            content_layout.setContentsMargins(15, 15, 15, 15)
            content_layout.setSpacing(15)

            # Toolbar
            toolbar = self._create_toolbar()
            content_layout.addWidget(toolbar)

            # Search panel
            self.search_panel = self._create_search_panel()
            content_layout.addWidget(self.search_panel)

            # Filter panel za Inspekcijska pravila (hidden by default)
            self.inspection_filter_panel = self._create_inspection_filter_panel()
            self.inspection_filter_panel.setVisible(False)
            content_layout.addWidget(self.inspection_filter_panel)

            # Tabela BEZ scroll area
            self.table = QTableWidget()
            self.table.cellClicked.connect(self._on_table_cell_clicked)
            self.table.setSelectionBehavior(QTableWidget.SelectRows)
            self.table.setSelectionMode(QTableWidget.SingleSelection)
            self.table.setAlternatingRowColors(True)
            self.table.setStyleSheet(
                """
                QTableWidget {
                    border: 2px solid #5a8060;
                    gridline-color: #c8dcc8;
                    font-size: 13pt;
                    background: white;
                    color: #1e3820;
                }
                QTableWidget::item {
                    padding: 12px 8px;
                    min-height: 35px;
                    border: 1px solid #c8dcc8;
                    color: #1e3820;
                }
                QTableWidget::item:selected {
                    background-color: #d4e8d4;
                    color: #1e3820;
                }
                QHeaderView::section {
                    background: #dce8dc;
                    padding: 14px 10px;
                    border: 1px solid #5a8060;
                    font-weight: bold;
                    font-size: 14pt;
                    color: #1e3820;
                }
            """
            )
            # Povećaj visinu redova
            self.table.verticalHeader().setDefaultSectionSize(45)
            self.table.itemSelectionChanged.connect(self._on_row_selected)
            self.table.itemDoubleClicked.connect(self._on_uredi)

            # VAŽNO - forsiraj minimalnu veličinu
            self.table.setMinimumHeight(400)
            self.table.setMinimumWidth(800)

            logger.debug(f"Tabela kreirana: {type(self.table)}")

            # Direktno dodaj tabelu u layout
            content_layout.addWidget(self.table, stretch=1)
            logger.debug("Tabela direktno dodata u layout sa stretch=1")

            # Advanced search (hidden by default)
            self.advanced_panel = self._create_advanced_search()
            content_layout.addWidget(self.advanced_panel)

            # Detail panel container (GRID layout)
            self.detail_container = QWidget()
            content_layout.addWidget(self.detail_container)

            # Pager
            pager = self._create_pager()
            content_layout.addWidget(pager)

            # QStackedWidget za prebacivanje između standardnog sadržaja i quota panela
            from PySide6.QtWidgets import QStackedWidget
            self._stack = QStackedWidget()
            self.standard_content = content
            self._stack.addWidget(content)   # index 0 — standardni sadržaj

            # Quota panel placeholder (lazy init na prvom klik-u)
            self._quota_placeholder = QWidget()
            self._stack.addWidget(self._quota_placeholder)  # index 1 — kvote
            self._quota_panel = None

            layout.addWidget(self._stack, stretch=1)

            # Status bar
            status = self._create_status_bar()
            layout.addWidget(status)

            logger.info("Glavni prostor uspešno kreiran")

            return main_area

        except Exception as e:
            logger.error(f"Greška pri kreiranju glavnog prostora: {str(e)}")
            raise

    def _create_header_bar(self) -> QWidget:
        """Header sa title + dark toggle"""
        header = QWidget()
        header.setStyleSheet("background: #f0f7f0; border-bottom: 1px solid #c8dcc8;")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 10, 20, 10)

        icon = QLabel("≡")
        icon.setStyleSheet("font-size: 18px; color: #5a8060;")

        self.title_label = QLabel()
        self.title_label.setStyleSheet(
            """
            font-size: 14px;
            font-weight: bold;
            color: #1e3820;
        """
        )

        layout.addWidget(icon)
        layout.addWidget(self.title_label)
        layout.addStretch()

        return header

    def set_title(self, title: str):
        """Postavi naslov u header bar-u"""
        try:
            if hasattr(self, 'title_label') and self.title_label:
                self.title_label.setText(title)
            else:
                logger.warning(f"⚠️ WARNING: title_label ne postoji ili nije inicijalizovan")
        except Exception as e:
            logger.error(f"Greška pri postavljanju naslova: {str(e)}")

    def _create_toolbar(self) -> QWidget:
        """CRUD toolbar sa shortcuts"""
        toolbar = QWidget()
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Novi
        self.btn_novi = self.ui_helper.create_styled_button(
            "Novi (Ctrl+N)", "success", "fa5s.plus-square"
        )
        self.btn_novi.clicked.connect(self._on_novi)

        # Uredi
        self.btn_uredi = self.ui_helper.create_styled_button(
            "Uredi (Ctrl+E)", "primary", "fa5s.edit"
        )
        self.btn_uredi.setEnabled(False)
        self.btn_uredi.clicked.connect(self._on_uredi)

        # Obriši
        self.btn_obrisi = self.ui_helper.create_styled_button(
            "Obriši (Del)", "danger", "fa5s.trash-alt"
        )
        self.btn_obrisi.setEnabled(False)
        self.btn_obrisi.clicked.connect(self._on_obrisi)

        # Snimi
        self.btn_snimi = self.ui_helper.create_styled_button(
            "Snimi (Ctrl+S)", "default", "fa5.save"
        )
        self.btn_snimi.setEnabled(False)
        self.btn_snimi.clicked.connect(self._on_snimi)

        layout.addWidget(self.btn_novi)
        layout.addWidget(self.btn_uredi)
        layout.addWidget(self.btn_obrisi)
        layout.addWidget(self.btn_snimi)
        layout.addStretch()

        return toolbar

    def _clear_form(self):
        """Clear all form fields"""
        try:
            logger.debug("Čišćenje forme")

            field_names = [
                "jib_field",
                "naziv_field",
                "adresa_field",
                "grad_field",
                "postanski_broj_field",
                "zemlja_field",
                "telefon_field",
                "email_field",
                "kontakt_field",
                "pdv_field",
                "maticni_field",
            ]

            for field_name in field_names:
                if hasattr(self, field_name):
                    field = getattr(self, field_name)
                    try:
                        if field and hasattr(field, "clear"):
                            field.clear()
                    except RuntimeError:
                        # Widget je već obrisan, ignoriši
                        pass

            logger.debug("Forma uspešno očišćena")
        except Exception as e:
            logger.error(f"Greška pri čišćenju forme: {str(e)}")

    def _create_search_panel(self) -> QWidget:
        """Basic search panel (advanced je odvojeno)"""
        search = QWidget()
        layout = QHBoxLayout(search)
        layout.setContentsMargins(0, 0, 0, 0)

        # Icon
        icon = QLabel("🔍")
        icon.setStyleSheet("font-size: 20px;")

        # Pretraga label
        label = QLabel("Pretraga:")
        label.setStyleSheet("font-size: 13pt; font-weight: bold;")

        # Search input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Pretraži...")
        self.search_input.setStyleSheet(
            "font-size: 13pt; padding: 8px; min-height: 35px;"
        )
        self.search_input.returnPressed.connect(self._apply_search)
        self.search_input.textChanged.connect(self._on_search_text_changed)

        # Search button
        btn_search = QPushButton("🔍 Pretraži")
        btn_search.setStyleSheet(
            """
            QPushButton {
                background: #0078d7;
                color: white;
                border: none;
                padding: 10px 16px;
                border-radius: 4px;
                font-size: 13pt;
                min-height: 35px;
            }
            QPushButton:hover {
                background: #006abc;
            }
        """
        )
        btn_search.clicked.connect(self._apply_search)

        layout.addWidget(icon)
        layout.addWidget(label)
        layout.addWidget(self.search_input, stretch=1)
        layout.addWidget(btn_search)

        return search

    def _create_advanced_search(self) -> QWidget:
        """Advanced search panel (collapsible)"""
        container = QWidget()
        container.setVisible(False)  # Hidden by default
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 10, 0, 0)
        main_layout.setSpacing(10)

        # Toggle button
        self.advanced_toggle = QToolButton()
        self.advanced_toggle.setText("Napredna pretraga ▼")
        self.advanced_toggle.setCheckable(True)
        self.advanced_toggle.setStyleSheet(
            """
            QToolButton {
                border: none;
                background: transparent;
                color: #0078d7;
                padding: 5px;
                font-weight: bold;
            }
            QToolButton:hover {
                text-decoration: underline;
            }
        """
        )
        self.advanced_toggle.toggled.connect(self._toggle_advanced)
        main_layout.addWidget(self.advanced_toggle)

        # Advanced fields panel
        self.advanced_fields = QWidget()
        self.advanced_fields.setVisible(False)
        fields_layout = QHBoxLayout(self.advanced_fields)

        # Extra search fields (example)
        self.search_pib = QLineEdit()
        self.search_pib.setPlaceholderText("PIB...")

        self.search_zemlja = QComboBox()
        self.search_zemlja.addItem("Sve zemlje")

        btn_reset = QPushButton("🔄 Resetuj")
        btn_reset.clicked.connect(self._reset_search)

        btn_adv_search = QPushButton("🔍 Pretraži")
        btn_adv_search.setStyleSheet(
            """
            background: #0078d7;
            color: white;
            border: none;
            padding: 6px 12px;
            border-radius: 4px;
        """
        )
        btn_adv_search.clicked.connect(self._apply_search)

        fields_layout.addWidget(QLabel("PIB:"))
        fields_layout.addWidget(self.search_pib)
        fields_layout.addWidget(QLabel("Zemlja:"))
        fields_layout.addWidget(self.search_zemlja)
        fields_layout.addStretch()
        fields_layout.addWidget(btn_reset)
        fields_layout.addWidget(btn_adv_search)

        main_layout.addWidget(self.advanced_fields)

        return container

    def _toggle_advanced(self, checked: bool):
        """Toggle advanced search visibility"""
        self.advanced_fields.setVisible(checked)
        arrow = "▲" if checked else "▼"
        self.advanced_toggle.setText(f"Napredna pretraga {arrow}")

    def _create_pager(self) -> QWidget:
        """Navigation pager"""
        pager = QWidget()
        layout = QHBoxLayout(pager)
        layout.setContentsMargins(0, 10, 0, 0)

        self.btn_prev = QPushButton("◀ Prethodni")
        self.btn_prev.clicked.connect(self._prev_record)

        self.lbl_position = QLabel("Pošiljalac 1 od 0")
        self.lbl_position.setAlignment(Qt.AlignCenter)
        self.lbl_position.setStyleSheet("font-weight: bold; font-size: 13pt;")

        self.btn_next = QPushButton("Sledeći ▶")
        self.btn_next.clicked.connect(self._next_record)

        # Quick nav buttons
        btn_first = QPushButton("◀")
        btn_first.setMaximumWidth(30)
        btn_first.clicked.connect(lambda: self._goto_record(0))

        btn_last = QPushButton("▶")
        btn_last.setMaximumWidth(30)
        btn_last.clicked.connect(lambda: self._goto_record(self.table.rowCount() - 1))

        layout.addWidget(self.btn_prev)
        layout.addStretch()
        layout.addWidget(self.lbl_position)
        layout.addStretch()
        layout.addWidget(self.btn_next)
        layout.addWidget(btn_first)
        layout.addWidget(btn_last)

        return pager

    def _create_status_bar(self) -> QWidget:
        """Status bar sa totals + last change"""
        status = QFrame()
        status.setFrameShape(QFrame.StyledPanel)
        status.setStyleSheet(
            """
            background: #f0f0f0;
            border-top: 1px solid #ccc;
            padding: 8px;
        """
        )

        layout = QHBoxLayout(status)
        layout.setContentsMargins(15, 5, 15, 5)

        self.lbl_totals = QLabel("Ukupno: 0 pošiljalaca | Prikazano: 0")
        self.lbl_totals.setStyleSheet("color: #666; font-size: 12pt;")

        self.lbl_last_change = QLabel("Posljednja izmjena: -")
        self.lbl_last_change.setStyleSheet("color: #666; font-size: 12pt;")

        layout.addWidget(self.lbl_totals)
        layout.addStretch()
        layout.addWidget(self.lbl_last_change)

        return status

    def update_totals(self, total: int, displayed: int):
        """Ažuriraj prikaz ukupnog broja zapisa"""
        try:
            if hasattr(self, 'lbl_totals') and self.lbl_totals:
                # Pronađi trenutnu kategoriju za prikaz
                category = self.current_category or "zapisa"
                if category == "Pošiljaoci":
                    category_text = "pošiljalaca"
                elif category == "Uvoznici":
                    category_text = "uvoznika"
                elif category == "Carinske tarife":
                    category_text = "tarifa"
                elif category == "Deklaranti":
                    category_text = "deklaranta"
                elif category == "Carinarnice":
                    category_text = "carinarnica"
                elif category == "Carinski postupci":
                    category_text = "postupaka"
                elif category == "Zemlje":
                    category_text = "zemalja"
                else:
                    category_text = "zapisa"
                
                self.lbl_totals.setText(f"Ukupno: {total} {category_text} | Prikazano: {displayed}")
            else:
                logger.warning(f"⚠️ WARNING: lbl_totals ne postoji ili nije inicijalizovan")
        except Exception as e:
            logger.error(f"Greška pri ažuriranju totals: {str(e)}")

    def update_position(self, current: int, total: int):
        """Ažuriraj prikaz trenutne pozicije (za pager)"""
        try:
            pass  # pager widget nije implementiran
        except Exception as e:
            logger.error(f"Greška pri ažuriranju pozicije: {str(e)}")

    def _restore_table_widget(self):
        """Restore QTableWidget when switching from Carinarnice (which uses QTreeWidget)"""
        # If current table is a TreeWidget, we need to restore the TableWidget
        if hasattr(self, "tree_widget") and self.table == self.tree_widget:
            # Hide tree widget
            if self.tree_widget:
                self.tree_widget.hide()

            # Check if we still have the original table, otherwise create new one
            if hasattr(self, "_original_table") and self._original_table is not None:
                # Restore original table
                old_parent = self.tree_widget.parent()
                if old_parent:
                    layout = old_parent.layout()
                    if layout:
                        layout.replaceWidget(self.tree_widget, self._original_table)
                self._original_table.show()
                self.table = self._original_table
            else:
                # Create new table widget
                self._original_table = self._create_table_widget()
                old_parent = self.tree_widget.parent()
                if old_parent:
                    layout = old_parent.layout()
                    if layout:
                        layout.replaceWidget(self.tree_widget, self._original_table)
                self._original_table.show()
                self.table = self._original_table

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        # Ctrl+N - Novi
        QShortcut(QKeySequence("Ctrl+N"), self, self._on_novi)

        # Ctrl+E - Uredi
        QShortcut(QKeySequence("Ctrl+E"), self, self._on_uredi)

        # Del - Obriši
        QShortcut(QKeySequence("Del"), self, self._on_obrisi)

        # Ctrl+S - Snimi
        QShortcut(QKeySequence("Ctrl+S"), self, self._on_snimi)

    def _on_category_changed(self, row: int):
        """Category changed u sidebar-u"""
        if row < 0:
            return

        item = self.categories_list.item(row)
        category = item.data(Qt.UserRole)
        self._load_category(category)

    def _load_category(self, category: str):
        """Load category with error handling"""
        try:
            logger.info(f"Učitavanje kategorije: {category}")
            self.current_category = category
            self.title_label.setText(category)

            # ── Tarifne kvote: poseban panel ─────────────────
            if category == "Tarifne kvote":
                if self._quota_panel is None:
                    from gui.tabs.sifarnici.quota_panel import QuotaPanel
                    self._quota_panel = QuotaPanel(parent=self)
                    # Zamijeni placeholder sa pravim panelom u stacku
                    self._stack.removeWidget(self._quota_placeholder)
                    self._quota_placeholder.deleteLater()
                    self._stack.addWidget(self._quota_panel)
                self._stack.setCurrentWidget(self._quota_panel)
                return
            else:
                self._stack.setCurrentWidget(self.standard_content)

            # Clear detail panel
            self._clear_detail_panel()

            # VAŽNO: Reset table to QTableWidget before setting up new category
            # (in case we came from Carinarnice which uses QTreeWidget)
            self._restore_table_widget()

            # Reset table settings koje može postaviti neka kategorija (npr. Inspekcijska pravila)
            if hasattr(self, 'table') and hasattr(self.table, 'setWordWrap'):
                self.table.setWordWrap(False)
                vh = self.table.verticalHeader()
                vh.setDefaultSectionSize(50)          # Resetuj visinu PRIJE zaključavanja
                vh.setSectionResizeMode(QHeaderView.Fixed)

            # Sakrij inspection filter panel — prikazuje se samo za Inspekcijska pravila
            if hasattr(self, 'inspection_filter_panel'):
                self.inspection_filter_panel.setVisible(category == "Inspekcijska pravila")

            # Setup per category
            setup_methods = {
                "Pošiljaoci": self._setup_posiljaoci,
                "Carinske tarife": self._setup_trgovacki_nazivi,
                "Uvoznici": self._setup_uvoznici,
                "Deklaranti": self._setup_deklaranti,
                "Carinarnice": self._setup_carinarnice,
                "Carinski postupci": self._setup_carinski_postupci,
                "Inspekcijska pravila": self._setup_inspekcijska_pravila,
                "Inkoterms": self._setup_inkoterms,
            }

            # Reset skrivenih kolona pri svakoj promjeni kategorije
            for col in range(self.table.columnCount()):
                self.table.setColumnHidden(col, False)

            if category in setup_methods:
                setup_methods[category]()
            else:
                # Carinarnice, Zemlje, Carinski postupci - read-only
                self._setup_readonly(category)

            # Napredna pretraga nije potrebna za Pošiljaoci/Uvoznici
            self.advanced_panel.setVisible(False)

            # Load data
            self._load_data()

            # Update status
            self._update_status()

            logger.info(f"Kategorija {category} uspešno učitana")

        except Exception as e:
            logger.error(f"Greška pri učitavanju kategorije {category}: {str(e)}")
            QMessageBox.critical(
                self,
                "Greška",
                f"Greška pri učitavanju kategorije {category}:\n{str(e)}",
            )

    def _clear_detail_panel(self):
        """Clear detail panel and create grid layout"""
        # Remove old layout
        old_layout = self.detail_container.layout()
        if old_layout:
            QWidget().setLayout(old_layout)

        # Create NEW grid layout
        grid = QGridLayout(self.detail_container)
        grid.setSpacing(15)
        grid.setContentsMargins(0, 15, 0, 0)

    def _build_partner_form_strip(self) -> PartnerFormStrip:
        """
        Kreira kompaktni info-strip za pošiljaoca/uvoznika.

        Delegira na PartnerFormStrip klasu.
        """
        strip = PartnerFormStrip(self)

        # Expose fields kao atributi za backward compatibility
        self.jib_field = strip.jib_field
        self.naziv_field = strip.naziv_field
        self.adresa_field = strip.adresa_field
        self.grad_field = strip.grad_field
        self.postanski_broj_field = strip.postanski_broj_field
        self.zemlja_field = strip.zemlja_field
        self.telefon_field = strip.telefon_field
        self.email_field = strip.email_field
        self.pdv_field = strip.pdv_field
        self.maticni_field = strip.maticni_field
        self.kontakt_field = strip.kontakt_field

        return strip

    def _setup_posiljaoci(self):
        """Setup Pošiljaoci - INFO STRIP LAYOUT"""
        try:
            logger.info("Podešavanje Pošiljalaca kategorije")

            # Proveri da li je self.table QTreeWidget i vrati ga u QTableWidget ako jeste
            if hasattr(self, "tree_widget") and self.table == self.tree_widget:
                logger.debug("Vraćanje sa QTreeWidget na QTableWidget za Pošiljaoce")
                # Sakrij tree widget
                self.tree_widget.hide()
                # Kreiraj novu tabelu ako ne postoji
                if not hasattr(self, "_original_table"):
                    # Sačuvaj referencu na originalnu tabelu
                    self._original_table = self._create_table_widget()
                # Vrati originalnu tabelu
                self.table = self._original_table
                self.table.show()
                # Osveži layout
                layout = self.table.parent().layout()
                if layout:
                    layout.replaceWidget(self.tree_widget, self.table)

            # Table columns — JIB je u koloni 0 ali skrivena (koristi se za delete/edit)
            # Pošiljaoci su strani partneri — nemaju BiH JIB, prikazujemo samo poslovne podatke
            self.table.setColumnCount(5)
            self.table.setHorizontalHeaderLabels(
                ["JIB", "Naziv", "Adresa", "Grad", "Zemlja"]
            )
            self.table.setColumnHidden(0, True)
            self.table.setColumnWidth(1, 280)  # Naziv
            self.table.setColumnWidth(2, 370)  # Adresa
            self.table.setColumnWidth(3, 200)  # Grad
            self.table.setColumnWidth(4, 100)  # Zemlja

            logger.debug(f"Tabela podešena sa {self.table.columnCount()} kolona")

            # Info strip (spanning oba grid kolone)
            grid = self.detail_container.layout()
            strip = self._build_partner_form_strip()
            grid.addWidget(strip, 0, 0, 1, 2)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 1)

            logger.info("Pošiljaoci kategorija uspešno podešena")

        except Exception as e:
            logger.error(f"Greška pri podešavanju Pošiljalaca: {str(e)}")
            raise

    def _setup_trgovacki_nazivi(self):
        """Setup Trgovački nazivi (Carinske tarife)"""
        self.table.setColumnCount(
            2
        )  # Smanjeno na 2 kolone: Tarifni kod, Naziv robe (uklonjena Akcije kolona)
        self.table.setHorizontalHeaderLabels(["Tarifni kod", "Naziv robe"])
        # Podesi širinu kolona - fiksna širina za tarifni kod, ostatak ide nazivu robe
        self.table.setColumnWidth(0, 150)  # Tarifni kod - fiksna širina
        # Kolona 1 (Naziv robe) će se automatski protegnuti da popuni ostatak prostora

        # Omogući automatsko širenje kolona - kolona 1 (Naziv robe) će popuniti ostatak prostora
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)  # Tarifni kod
        header.setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )  # Naziv robe - popunjava ostatak

        # Povećaj font u tabeli
        font = self.table.font()
        font.setPointSize(14)  # Povećaj font na 14pt
        self.table.setFont(font)

        # Povećaj visinu redova
        self.table.verticalHeader().setDefaultSectionSize(50)

        grid = self.detail_container.layout()

        # Single column for this one
        group = QGroupBox("≡ DETALJI")
        form = QFormLayout(group)

        self.tarifni_kod_field = QLineEdit()
        self.naziv_robe_field = QLineEdit()

        form.addRow("Tarifni kod:", self.tarifni_kod_field)
        form.addRow("Naziv robe:", self.naziv_robe_field)

        grid.addWidget(group, 0, 0, 2, 2)  # Span both rows/cols

    def _setup_uvoznici(self):
        """Setup Uvoznici - INFO STRIP LAYOUT"""
        try:
            logger.info("Podešavanje Uvoznika kategorije")

            # Proveri da li je self.table QTreeWidget i vrati ga u QTableWidget ako jeste
            if hasattr(self, "tree_widget") and self.table == self.tree_widget:
                logger.debug("Vraćanje sa QTreeWidget na QTableWidget za Uvoznike")
                # Sakrij tree widget
                self.tree_widget.hide()
                # Kreiraj novu tabelu ako ne postoji
                if not hasattr(self, "_original_table"):
                    # Sačuvaj referencu na originalnu tabelu
                    self._original_table = self._create_table_widget()
                # Vrati originalnu tabelu
                self.table = self._original_table
                self.table.show()
                # Osveži layout
                layout = self.table.parent().layout()
                if layout:
                    layout.replaceWidget(self.tree_widget, self.table)

            # Table columns (BEZ ACTION kolone)
            self.table.setColumnCount(5)
            self.table.setHorizontalHeaderLabels(
                ["JIB", "Naziv", "Adresa", "Grad", "Zemlja"]
            )
            self.table.setColumnWidth(0, 180)  # JIB - prošireno
            self.table.setColumnWidth(1, 250)  # Naziv
            self.table.setColumnWidth(2, 350)  # Adresa - prošireno za pune adrese
            self.table.setColumnWidth(3, 200)  # Grad - prošireno za pune nazive
            self.table.setColumnWidth(4, 100)  # Zemlja

            logger.debug(f"Tabela podešena sa {self.table.columnCount()} kolona")

            # Info strip (spanning oba grid kolone)
            grid = self.detail_container.layout()
            strip = self._build_partner_form_strip()
            grid.addWidget(strip, 0, 0, 1, 2)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 1)

            logger.info("Uvoznici kategorija uspešno podešena")

        except Exception as e:
            logger.error(f"Greška pri podešavanju Uvoznika: {str(e)}")
            raise

    def _setup_deklaranti(self):
        """Setup Deklaranti"""
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["Kod", "Naziv", "Licenca", "Kontakt", "Akcije"]
        )

        grid = self.detail_container.layout()

        group = QGroupBox("≡ DETALJI DEKLARANTA")
        form = QFormLayout(group)

        self.kod_field = QLineEdit()
        self.naziv_field = QLineEdit()
        self.licenca_field = QLineEdit()
        self.kontakt_field = QLineEdit()

        form.addRow("Kod:", self.kod_field)
        form.addRow("Naziv:", self.naziv_field)
        form.addRow("Licenca:", self.licenca_field)
        form.addRow("Kontakt:", self.kontakt_field)

        grid.addWidget(group, 0, 0, 2, 2)

    def _setup_carinarnice(self):
        """Setup Carinarnice - hijerarhijski prikaz po regionalnim centrima"""
        try:
            logger.info("Podešavanje Carinarnica kategorije sa hijerarhijom")

            # Sačuvaj originalnu tabelu ako već ne postoji
            if not hasattr(self, "_original_table"):
                self._original_table = self.table
                logger.debug("Originalna tabela sačuvana")

            # Promeni tabelu u tree widget za hijerarhijski prikaz
            # Prvo ukloni staru tabelu ako postoji
            old_table = self.table
            old_parent = old_table.parent()

            # Kreiraj novi QTreeWidget
            self.tree_widget = QTreeWidget()
            
            try:
                self.tree_widget.setHeaderLabels(
                    ["Šifra", "Naziv"]
                )  # Uklonjena Akcije kolona
            except Exception as e:
                logger.error(f"setHeaderLabels FAILED na QTreeWidget: {str(e)}")
                raise

            # Stylesheet za povećan font (20pt) - mora biti PRIJE setFont!
            self.tree_widget.setStyleSheet(
                """
                QTreeWidget {
                    font-size: 20pt;
                    border: 2px solid #333;
                }
                QTreeWidget::item {
                    padding: 10px 5px;
                    min-height: 40px;
                }
                QTreeWidget::item:selected {
                    background: #0078d7;
                    color: white;
                }
                QHeaderView::section {
                    background: #f5f5f5;
                    padding: 12px;
                    border: 1px solid #333;
                    font-weight: bold;
                    font-size: 18pt;
                }
                """
            )

            # Povećaj font u tree widgetu (dodatno pojačanje)
            font = self.tree_widget.font()
            font.setPointSize(20)
            self.tree_widget.setFont(font)

            # Podesi širinu kolona
            self.tree_widget.setColumnWidth(0, 250)  # Šifra - šira kolona da se vidi

            # Enable stretching for the "Naziv" column
            header = self.tree_widget.header()
            header.setSectionResizeMode(
                0, QHeaderView.ResizeMode.Fixed
            )  # Šifra - fiksna širina
            header.setSectionResizeMode(
                1, QHeaderView.ResizeMode.Stretch
            )  # Naziv - popunjava ostatak

            # Zameni staru tabelu sa novim tree widget-om
            layout = old_parent.layout()
            if layout:
                # Nađi indeks stare tabele u layout-u i zameni je
                for i in range(layout.count()):
                    item = layout.itemAt(i)
                    if item and item.widget() == old_table:
                        layout.replaceWidget(old_table, self.tree_widget)
                        break

            # Sakrij staru tabelu i prikaži novu
            old_table.hide()
            self.tree_widget.show()

            # Ažuriraj referencu na trenutnu tabelu (koristićemo tree kao tabelu za ovu kategoriju)
            self.table = self.tree_widget

            logger.debug("Tree widget za hijerarhijski prikaz carinarnica podešen")

            # === DETAIL FORM - SINGLE COLUMN ===
            grid = self.detail_container.layout()

            # Single column for this one
            group = QGroupBox("≡ DETALJI")
            form = QFormLayout(group)

            self.sifra_field = QLineEdit()
            self.naziv_field = QLineEdit()

            form.addRow("Šifra:", self.sifra_field)
            form.addRow("Naziv:", self.naziv_field)

            grid.addWidget(group, 0, 0, 2, 2)  # Span both rows/cols

            logger.info("Carinarnice kategorija sa hijerarhijom uspešno podešena")

        except Exception as e:
            logger.error(
                f"Greška pri podešavanju Carinarnica sa hijerarhijom: {str(e)}"
            )
            raise

    def _setup_readonly(self, category: str):
        """Read-only kategorije"""
        if category == "Zemlje":
            self.table.setColumnCount(2)
            self.table.setHorizontalHeaderLabels(["Šifra", "Naziv"])
            # Set column widths
            header = self.table.horizontalHeader()
            if header:
                header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
                header.setSectionResizeMode(1, QHeaderView.Stretch)

        # Disable edit buttons
        self.btn_novi.setEnabled(False)
        self.btn_uredi.setEnabled(False)
        self.btn_obrisi.setEnabled(False)

    def _populate_zemlje(self):
        """Populate zemlje combo sa zastavicama"""
        zemlje = [
            ("🇮🇹", "IT", "Italia"),
            ("🇰🇷", "KR", "South Korea"),
            ("🇨🇳", "CN", "China"),
            ("🇩🇪", "DE", "Germany"),
            ("🇫🇷", "FR", "France"),
            ("🇷🇸", "RS", "Serbia"),
            ("🇧🇦", "BA", "Bosnia and Herzegovina"),
        ]

        for zastava, kod, naziv in zemlje:
            self.zemlja_combo.addItem(f"{zastava} {kod} - {naziv}", kod)

    def _load_not_implemented(self, category_name: str):
        """Clear table + show friendly info for categories without DB implementation yet."""
        # Clear table so old data doesn't remain visible
        self.table.setUpdatesEnabled(False)
        self.table.setRowCount(0)
        self.table.clearContents()
        self.table.setUpdatesEnabled(True)

        # Update status/pager text to avoid confusion
        try:
            self.lbl_totals.setText(f"Ukupno: 0 | Prikazano: 0")
        except Exception:
            pass
        try:
            # keep current label but set count to 0
            self.lbl_position.setText("0 od 0")
        except Exception:
            pass

        logger.info(
            f"Kategorija '{category_name}' trenutno nema implementirano učitavanje iz baze."
        )

    def _load_data(self):
        """Load data for current category.

        VAŽNO: Ako kategorija nema implementiran DB loader, tabela se mora očistiti
        da ne ostanu podaci iz prethodne kategorije (to je izgledalo kao 'bug' u GUI).
        """
        try:
            logger.info(f"Učitavanje podataka za kategoriju: {self.current_category}")

            if self.current_category == "Pošiljaoci":
                self._load_posiljaoci_data()
            elif self.current_category == "Carinske tarife":
                self._load_trgovacki_nazivi_data()
            elif self.current_category == "Uvoznici":
                self._load_uvoznici_data()
            elif self.current_category == "Deklaranti":
                self._load_deklaranti_data()
            elif self.current_category == "Carinarnice":
                self._load_carinarnice_data()
            elif self.current_category == "Carinski postupci":
                self._load_carinski_postupci_data()
            elif self.current_category == "Zemlje":
                self._load_zemlje_data()
            elif self.current_category == "Inspekcijska pravila":
                self._load_inspekcijska_pravila_data()
            elif self.current_category == "Inkoterms":
                self._load_inkoterms_data()
            else:
                self._load_not_implemented(str(self.current_category))

            logger.info("Podaci uspešno učitani")

            # Set table and forms to readonly mode initially
            self._set_readonly_mode(readonly=True)

        except Exception as e:
            logger.error(f"Greška pri učitavanju podataka: {str(e)}")
            QMessageBox.critical(
                self, "Greška", f"Greška pri učitavanju podataka: {str(e)}"
            )

    def _create_table_widget(self) -> QTableWidget:
        """Kreira novu instancu QTableWidget sa osnovnim podešavanjima"""
        table = QTableWidget()
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setAlternatingRowColors(True)
        table.setStyleSheet(
            """
            QTableWidget {
                border: 1px solid #ddd;
                gridline-color: #ddd;
                font-size: 13pt;
            }
            QTableWidget::item {
                padding: 12px 8px;
                min-height: 35px;
            }
            QHeaderView::section {
                background: #f5f5f5;
                padding: 14px 10px;
                border: 1px solid #ddd;
                font-weight: bold;
                font-size: 14pt;
            }
        """
        )
        # Povećaj visinu redova
        table.verticalHeader().setDefaultSectionSize(45)
        table.itemSelectionChanged.connect(self._on_row_selected)
        table.itemDoubleClicked.connect(self._on_uredi)
        return table

    def _load_uvoznici_data(self):
        """Load data from catalogs.uvoznici table using Service layer."""
        try:
            logger.info("Učitavanje podataka o uvoznicima iz baze (preko Service)")

            results = self.service.load_uvoznici_data()

            self._populate_table_from_service(
                results,
                columns=["jib", "naziv", "adresa", "grad", "drzava"],
            )

            logger.info(f"Uspešno učitano {len(results)} uvoznika")
        except Exception as e:
            logger.error(f"Greška pri učitavanju uvoznika: {str(e)}")
            QMessageBox.critical(
                self, "Greška", f"Greška pri učitavanju uvoznika:\n{str(e)}"
            )

    def _load_posiljaoci_data(self):
        """Load data from catalogs.izvoznici table using Service layer."""
        try:
            logger.info("Učitavanje podataka o pošiljaocima iz baze (preko Service)")

            results = self.service.load_posiljaoci_data()

            self._populate_table_from_service(
                results,
                columns=["jib", "naziv", "adresa", "grad", "drzava"],
            )

            logger.info(f"Uspešno učitano {len(results)} pošiljalaca")
        except Exception as e:
            logger.error(f"Greška pri učitavanju pošiljalaca: {str(e)}")
            QMessageBox.critical(
                self, "Greška", f"Greška pri učitavanju pošiljalaca:\n{str(e)}"
            )

    def _load_trgovacki_nazivi_data(self):
        """Load Trgovački nazivi data — hijerarhijski prikaz za brojeve."""
        try:
            logger.info("Učitavanje podataka o tarifnim nazivima robe iz baze")

            # Provjeri da li je pretraga broj (hijerarhijski prikaz)
            search_text = self.search_input.text().strip() if hasattr(self, 'search_input') else ''
            is_code_search = bool(re.match(r'^\d{2,}$', search_text)) if search_text else False

            def _clean_tariff_opis(v):
                if not v:
                    return v
                return _TAIL_RATES_RE.sub('', str(v)).rstrip(' –-').strip()

            if is_code_search:
                # Guard: populate_tariff_hierarchy zahtijeva QTableWidget
                if not hasattr(self.table, 'setRowCount'):
                    logger.warning("_load_trgovacki_nazivi_data: self.table je QTreeWidget — restauriram")
                    self._restore_table_widget()
                # Hijerarhijski prikaz iz SQLite — delegiraj na modul
                populate_tariff_hierarchy(
                    self.table,
                    prefix=search_text.replace(' ', '').replace('.', ''),
                    clean_opis_fn=_clean_tariff_opis,
                )
            else:
                # Obična pretraga — prikaži sve tarife iz PostgreSQL
                results = self.service.load_trgovacki_nazivi_data()
                self._populate_table_from_service(
                    results,
                    columns=["tarifni_kod", "opis"],
                    format_fn=_clean_tariff_opis,
                    max_rows=20000,
                )

            logger.info("Uspešno učitano trgovački nazivi")
        except Exception as e:
            logger.error(f"Greška pri učitavanju tarifnih naziva robe: {str(e)}")
            raise

    def _populate_table_from_service(
        self,
        results: List[Dict[str, Any]],
        columns: List[str],
        format_fn: Optional[Callable] = None,
        max_rows: int = 20000,
    ):
        """Popuni tabelu sa rezultatima iz Service layer-a (lista dict-ova).

        Args:
            results: Lista dict-ova iz Service-a
            columns: Koje kolone prikazati (ključevi iz dict-a)
            format_fn: Optional funkcija za formatiranje vrednosti
            max_rows: Maksimalni broj redova
        """
        # Guard: ako je self.table slučajno ostao QTreeWidget (od Carinarnice), restauriraj
        if not hasattr(self.table, 'setRowCount'):
            logger.warning("_populate_table_from_service: self.table je QTreeWidget — restauriram QTableWidget")
            self._restore_table_widget()

        self.table.setSortingEnabled(False)
        self.table.setUpdatesEnabled(False)

        actual_rows = min(len(results), max_rows)
        self.table.setRowCount(actual_rows)

        for row in range(actual_rows):
            row_data = results[row]
            for col, col_name in enumerate(columns):
                value = row_data.get(col_name, "")
                formatted_value = format_fn(value) if format_fn else value
                self.table.setItem(
                    row, col, QTableWidgetItem(str(formatted_value or ""))
                )

        self.table.setUpdatesEnabled(True)
        self.table.setSortingEnabled(True)
        self.table.viewport().update()
        QApplication.processEvents()

        try:
            self._update_status()
        except Exception:
            pass
        try:
            self._update_pager()
        except Exception:
            pass

    def _load_carinarnice_data(self):
        """Load Carinarnice data using Service layer (hierarchical view)."""
        try:
            logger.info(
                "Učitavanje podataka o carinarnicama iz baze (hijerarhijski prikaz, preko Service)"
            )

            regional_centers = self.service.load_carinarnice_hierarchical()

            # Clear tree widget
            self.table.clear()

            # Add regional centers and their customs posts to the tree
            for rc_data in regional_centers:
                # Create top-level item for regional center
                rc_item = QTreeWidgetItem(self.table)
                rc_item.setText(0, str(rc_data["rc_sifra"] or ""))
                rc_item.setText(1, str(rc_data["rc_naziv"] or ""))
                rc_item.setText(2, "")

                # Make regional center item bold
                font = rc_item.font(0)
                font.setBold(True)
                rc_item.setFont(0, font)
                rc_item.setFont(1, font)

                # Add child items for each customs post
                for ci_data in rc_data["ispostave"]:
                    ci_item = QTreeWidgetItem(rc_item)
                    ci_item.setText(0, str(ci_data["ci_sifra"] or ""))
                    ci_item.setText(1, str(ci_data["ci_naziv"] or ""))

            # Expand all items by default
            self.table.expandAll()

            logger.info(
                f"Uspešno učitano {len(regional_centers)} regionalnih centara sa ispostavama"
            )

            try:
                self._update_status()
            except Exception:
                pass
            try:
                self._update_pager()
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Greška pri učitavanju carinarnica: {str(e)}")
            raise

    def _search_carinarnice(self, query: str):
        """Search Carinarnice in tree widget based on search query"""
        try:
            logger.info(f"Pretraga carinarnica sa query-jem: '{query}'")

            clean_query = self.validator.sanitize_input(query).lower().strip()

            # Get all top-level items (regional centers)
            root = self.table.invisibleRootItem()
            if not root:
                logger.warning("Nema root itema za pretragu carinarnica")
                return

            # Track which regional centers should be visible
            visible_rc_items = set()

            # First pass: check all items and mark visible regional centers
            for i in range(root.childCount()):
                rc_item = root.child(i)
                rc_sifra = rc_item.text(0).lower()
                rc_naziv = rc_item.text(1).lower()

                rc_matches = False
                child_matches = 0
                total_children = rc_item.childCount()

                # Check regional center itself
                if not clean_query:
                    rc_matches = True
                else:
                    if rc_sifra.startswith(clean_query) or rc_naziv.startswith(
                        clean_query
                    ):
                        rc_matches = True

                # Check all child items (customs posts)
                for j in range(rc_item.childCount()):
                    ci_item = rc_item.child(j)
                    ci_sifra = ci_item.text(0).lower()
                    ci_naziv = ci_item.text(1).lower()

                    if not clean_query:
                        # Show all children if no query
                        ci_item.setHidden(False)
                        child_matches += 1
                    else:
                        if ci_sifra.startswith(clean_query) or ci_naziv.startswith(
                            clean_query
                        ):
                            ci_item.setHidden(False)
                            child_matches += 1
                        else:
                            ci_item.setHidden(True)

                # Show regional center if it matches or has visible children
                if rc_matches or child_matches > 0:
                    rc_item.setHidden(False)
                    visible_rc_items.add(id(rc_item))
                else:
                    rc_item.setHidden(True)

            # Second pass: collapse regional centers that have hidden children
            for i in range(root.childCount()):
                rc_item = root.child(i)
                if not rc_item.isHidden():
                    # Check if all children are hidden
                    all_children_hidden = True
                    for j in range(rc_item.childCount()):
                        if not rc_item.child(j).isHidden():
                            all_children_hidden = False
                            break

                    if all_children_hidden and clean_query:
                        # Collapse if all children are hidden but regional center matches
                        rc_item.setExpanded(False)
                    else:
                        rc_item.setExpanded(True)

            logger.info(f"Pretraga carinarnica završena - pronađeno rezultata")

        except Exception as e:
            logger.error(f"Greška pri pretrazi carinarnica: {str(e)}")
            raise

    def _setup_carinski_postupci(self):
        """Setup Carinski postupci - read-only tabela sa kolonama: Šifra, Postupak, Vrsta, Oznaka"""
        try:
            logger.info("Podešavanje Carinski postupci kategorije")

            # Restore table widget first
            self._restore_table_widget()

            # Setup table for read-only (like Carinarnice)
            self.table.setColumnCount(4)
            self.table.setHorizontalHeaderLabels(
                ["Šifra", "Carinski postupci", "Vrsta", "Oznaka"]
            )

            # Disable editing
            self.table.setEditTriggers(QTableWidget.NoEditTriggers)
            self.table.setSelectionBehavior(QTableWidget.SelectRows)

            # Column widths - Postupak se automatski širi da popuni prostor
            header = self.table.horizontalHeader()
            if header:
                # Šifra, Vrsta, Oznaka - fiksne širine
                header.setSectionResizeMode(0, QHeaderView.Fixed)
                header.setSectionResizeMode(2, QHeaderView.Fixed)
                header.setSectionResizeMode(3, QHeaderView.Fixed)

                # Postupak - stretch da popuni sav preostali prostor
                header.setSectionResizeMode(1, QHeaderView.Stretch)

                self.table.setColumnWidth(0, 80)  # Šifra
                self.table.setColumnWidth(2, 80)  # Vrsta
                self.table.setColumnWidth(3, 100)  # Oznaka - prošireno

            # Disable buttons (like other read-only categories)
            self.btn_novi.setEnabled(False)
            self.btn_uredi.setEnabled(False)
            self.btn_obrisi.setEnabled(False)

            logger.info("Carinski postupci kategorija uspešno podešena")

        except Exception as e:
            logger.error(f"Greška pri podešavanju Carinski postupci: {str(e)}")
            raise

    def _load_carinski_postupci_data(self):
        """Load Carinski postupci data using Service layer."""
        try:
            logger.info("Učitavanje carinskih postupaka iz baze (preko Service)")

            results = self.service.load_carinski_postupci_data()

            self._populate_table_from_service(
                results,
                columns=["sifra", "opis", "vrsta", "oznaka"],
            )

            logger.info(f"Uspešno učitano {len(results)} carinskih postupaka")
        except Exception as e:
            logger.error(f"Greška pri učitavanju carinskih postupaka: {str(e)}")
            raise

    # ============================================================
    # INSPEKCIJSKA PRAVILA — novi panel
    # ============================================================

    # Kratke oznake po tipu inspekcije
    _INSP_LABELS = {
        "sanitary":        ("SAN", "#c8e6c9"),
        "veterinary":      ("VET", "#fff9c4"),
        "phytosanitary":   ("FIT", "#a5d6a7"),
        "quality_control": ("UVK", "#bbdefb"),
        "medicines_agency": ("AGL", "#e1bee7"),
    }

    def _create_inspection_filter_panel(self) -> QWidget:
        """Kreira filter traku za Inspekcijska pravila (hidden by default)."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(6)

        # --- Red 1: tip inspekcije ---
        type_row = QHBoxLayout()
        type_row.setSpacing(6)
        type_label = QLabel("Tip:")
        type_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        type_row.addWidget(type_label)

        self._insp_type_filters: dict[str, QPushButton] = {}
        type_defs = [
            ("sve",              "Sve",  "#5a8060", "white"),
            ("sanitary",         "SAN",  "#2e7d32", "white"),
            ("veterinary",       "VET",  "#f57f17", "white"),
            ("phytosanitary",    "FIT",  "#1b5e20", "white"),
            ("quality_control",  "UVK",  "#0d47a1", "white"),
            ("medicines_agency", "AGL",  "#6a1b9a", "white"),
        ]
        for key, label, bg, fg in type_defs:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(key == "sve")
            btn.setFixedHeight(28)
            btn.setStyleSheet(
                f"QPushButton {{ background: {bg}; color: {fg}; border-radius: 4px;"
                f" padding: 4px 12px; font-weight: bold; font-size: 11pt; }}"
                f"QPushButton:!checked {{ background: #e0e0e0; color: #555; }}"
            )
            btn.clicked.connect(lambda checked, k=key: self._on_insp_type_filter(k))
            self._insp_type_filters[key] = btn
            type_row.addWidget(btn)
        type_row.addStretch()

        # --- Red 2: status ---
        status_row = QHBoxLayout()
        status_row.setSpacing(6)
        status_label = QLabel("Status:")
        status_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        status_row.addWidget(status_label)

        self._insp_status_filter: dict[str, QPushButton] = {}
        status_defs = [
            ("sve",          "Sve"),
            ("auto",         "Automatski"),
            ("conditional",  "Uslovno"),
            ("manual",       "Ručni pregled"),
        ]
        for key, label in status_defs:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(key == "sve")
            btn.setFixedHeight(28)
            btn.setStyleSheet(
                "QPushButton { background: #5a8060; color: white; border-radius: 4px;"
                " padding: 4px 12px; font-size: 11pt; }"
                "QPushButton:!checked { background: #e0e0e0; color: #555; }"
            )
            btn.clicked.connect(lambda checked, k=key: self._on_insp_status_filter(k))
            self._insp_status_filter[key] = btn
            status_row.addWidget(btn)
        status_row.addStretch()

        layout.addLayout(type_row)
        layout.addLayout(status_row)

        # Interno stanje filtera
        self._active_insp_type = "sve"
        self._active_insp_status = "sve"

        return panel

    def _on_insp_type_filter(self, key: str):
        """Tip-filter kliknut."""
        self._active_insp_type = key
        for k, btn in self._insp_type_filters.items():
            btn.setChecked(k == key)
        self._load_inspekcijska_pravila_data()

    def _on_insp_status_filter(self, key: str):
        """Status-filter kliknut."""
        self._active_insp_status = key
        for k, btn in self._insp_status_filter.items():
            btn.setChecked(k == key)
        self._load_inspekcijska_pravila_data()

    def _setup_inkoterms(self):
        """Setup tabele za Incoterms 2020 (read-only pregled)."""
        self._restore_table_widget()

        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            ["Kod", "Naziv (EN)", "Vidovi transporta", "Vozarina u cijeni"]
        )
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)

        header = self.table.horizontalHeader()
        if header:
            header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.Stretch)
            header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(3, QHeaderView.ResizeToContents)

        self.btn_novi.setEnabled(False)
        self.btn_uredi.setEnabled(False)
        self.btn_obrisi.setEnabled(False)

    def _load_inkoterms_data(self):
        """Učitaj Incoterms 2020 iz catalogs.incoterms."""
        # Transport mode — čitljivi opisi
        _TRANSPORT_LABELS = {
            "any": "Svi vidovi",
            "sea_inland_waterway": "Pomorski / unutrašnji vodeni",
        }
        # Incoterms gdje je vozarina uključena u cijenu fakture
        _VOZ_U_CIJENI = {"CIF", "CIP", "CFR", "CPT", "DAP", "DPU", "DDP"}

        try:
            rows = self.service.load_incoterms()
        except Exception as e:
            logger.error(f"Greška pri učitavanju Incoterms: {e}")
            rows = []

        # Fallback na hardkodovanu listu ako tabela još ne postoji
        if not rows:
            rows = [
                {"code": "EXW", "name_en": "Ex Works",                       "name_bs": "Franko fabrika",                       "transport_mode": "any"},
                {"code": "FCA", "name_en": "Free Carrier",                   "name_bs": "Franko prevoznik",                     "transport_mode": "any"},
                {"code": "CPT", "name_en": "Carriage Paid To",               "name_bs": "Prevoz plaćen do",                     "transport_mode": "any"},
                {"code": "CIP", "name_en": "Carriage and Insurance Paid To", "name_bs": "Prevoz i osiguranje plaćeni do",        "transport_mode": "any"},
                {"code": "DAP", "name_en": "Delivered At Place",             "name_bs": "Isporučeno na odredištu",              "transport_mode": "any"},
                {"code": "DPU", "name_en": "Delivered at Place Unloaded",    "name_bs": "Isporučeno na odredištu — istovareno", "transport_mode": "any"},
                {"code": "DDP", "name_en": "Delivered Duty Paid",            "name_bs": "Isporučeno, carina plaćena",           "transport_mode": "any"},
                {"code": "FAS", "name_en": "Free Alongside Ship",            "name_bs": "Franko uz bok broda",                  "transport_mode": "sea_inland_waterway"},
                {"code": "FOB", "name_en": "Free On Board",                  "name_bs": "Franko brod",                          "transport_mode": "sea_inland_waterway"},
                {"code": "CFR", "name_en": "Cost and Freight",               "name_bs": "Cijena i vozarina",                    "transport_mode": "sea_inland_waterway"},
                {"code": "CIF", "name_en": "Cost, Insurance and Freight",    "name_bs": "Cijena, osiguranje i vozarina",         "transport_mode": "sea_inland_waterway"},
            ]

        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            code = row.get("code", "")
            voz_u_cijeni = code in _VOZ_U_CIJENI
            transport_label = _TRANSPORT_LABELS.get(
                row.get("transport_mode", "any"), row.get("transport_mode", "")
            )

            name_en = row.get("name_en", "")
            name_bs = row.get("name_bs", "")
            combined = f"{name_en} — {name_bs}" if name_bs else name_en

            self.table.setItem(r, 0, QTableWidgetItem(code))
            self.table.setItem(r, 1, QTableWidgetItem(combined))
            self.table.setItem(r, 2, QTableWidgetItem(transport_label))

            voz_item = QTableWidgetItem("Da — vozarina uključena" if voz_u_cijeni else "Ne — vozarina posebna")
            if voz_u_cijeni:
                voz_item.setForeground(QColor("#1B5E20"))
            else:
                voz_item.setForeground(QColor("#B71C1C"))
            self.table.setItem(r, 3, voz_item)

        self.table.resizeRowsToContents()
        self._update_status()

    def _setup_inspekcijska_pravila(self):
        """Setup tabele za Inspekcijska pravila (read-only)."""
        try:
            self._restore_table_widget()

            self.table.setColumnCount(5)
            self.table.setHorizontalHeaderLabels(
                ["Tarifni kod", "Opis robe", "Inspekcije", "Status", "Napomena"]
            )
            self.table.setEditTriggers(QTableWidget.NoEditTriggers)
            self.table.setSelectionBehavior(QTableWidget.SelectRows)
            self.table.setWordWrap(True)

            header = self.table.horizontalHeader()
            if header:
                header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Tarifni kod
                header.setSectionResizeMode(1, QHeaderView.Stretch)            # Opis robe
                header.setSectionResizeMode(2, QHeaderView.ResizeToContents)   # Inspekcije
                header.setSectionResizeMode(3, QHeaderView.ResizeToContents)   # Status
                header.setSectionResizeMode(4, QHeaderView.Stretch)            # Napomena
            # Vertikalni header ostaje Fixed — ResizeToContents je presporo za >1000 redova

            # CRUD dugmad — ne primjenjuju se ovdje
            self.btn_novi.setEnabled(False)
            self.btn_uredi.setEnabled(False)
            self.btn_obrisi.setEnabled(False)
            # Detalji se prikazuju kroz postojeći _on_row_selected handler

        except Exception as e:
            logger.error(f"Greška pri podešavanju Inspekcijska pravila: {e}")
            raise

    def _load_inspekcijska_pravila_data(self):
        """Učitaj inspekcijska pravila iz PostgreSQL (catalogs.inspection_rules)."""
        from collections import defaultdict

        search_text = self.search_input.text().strip() if hasattr(self, 'search_input') else ''
        insp_type = self._active_insp_type if self._active_insp_type != "sve" else ""

        try:
            all_rows = self.service.load_inspection_rules(
                search=search_text,
                insp_type=insp_type,
                only_active=True,
                limit=2000,
            )

            # Status filter (radimo u Pythonu jer servis nema taj parametar)
            status = self._active_insp_status
            if status == "auto":
                all_rows = [
                    r for r in all_rows
                    if r["can_auto_decide"] and not r["condition_text"]
                ]
            elif status == "conditional":
                all_rows = [r for r in all_rows if r["condition_text"]]
            elif status == "manual":
                all_rows = [
                    r for r in all_rows
                    if not r["can_auto_decide"] and not r["condition_text"]
                ]

            # Grupisanje po tariff_code_norm (jedan red po tarifnom kodu)
            groups: dict = defaultdict(list)
            for r in all_rows:
                groups[r["tariff_code_norm"]].append(r)

            sorted_norms = sorted(groups.keys())

            self.table.setSortingEnabled(False)
            self.table.setUpdatesEnabled(False)
            self.table.setRowCount(len(sorted_norms))

            for i, norm in enumerate(sorted_norms):
                rule_list = groups[norm]
                first = rule_list[0]

                # Tarifni kod (prikazujemo čisti kod bez markera)
                self.table.setItem(i, 0, QTableWidgetItem(first["tariff_code"] or norm))

                # Opis robe
                desc = first["description"] or ""
                self.table.setItem(i, 1, QTableWidgetItem(desc))

                # Inspekcije (kratke oznake)
                type_order = ["sanitary", "veterinary", "phytosanitary", "quality_control", "medicines_agency"]
                types_in_group = {r["inspection_type"] for r in rule_list}
                labels = [
                    self._INSP_LABELS.get(t, (t.upper(), "#eee"))[0]
                    for t in type_order if t in types_in_group
                ]
                self.table.setItem(i, 2, QTableWidgetItem(", ".join(labels)))

                # Status (najrestriktivniji od svih pravila za taj kod)
                has_condition = any(r["condition_text"] for r in rule_list)
                all_auto = all(r["can_auto_decide"] for r in rule_list)
                if has_condition:
                    status_txt = "uslovno"
                elif all_auto:
                    status_txt = "automatski"
                else:
                    status_txt = "ručni pregled"
                self.table.setItem(i, 3, QTableWidgetItem(status_txt))

                # Napomena — svi condition_text-ovi, bez duplikata
                conds = list(dict.fromkeys(
                    r["condition_text"] for r in rule_list if r["condition_text"]
                ))
                self.table.setItem(i, 4, QTableWidgetItem("; ".join(conds)))

                # Sačuvaj norm kod i ID za detalje
                self.table.item(i, 0).setData(Qt.UserRole, norm)

            self.table.setUpdatesEnabled(True)
            self.table.setSortingEnabled(True)
            self._update_status()

        except Exception as e:
            logger.error(f"Greška pri učitavanju inspekcijskih pravila: {e}")

    def _on_inspekcijska_row_selected(self):
        """Prikaz detalja za odabrani tarifni kod u inspection tabeli."""
        if self.current_category != "Inspekcijska pravila":
            return

        selected = self.table.selectedItems()
        if not selected:
            return

        row = selected[0].row()
        code_item = self.table.item(row, 0)
        if not code_item:
            return

        tariff_code = code_item.text()
        norm_code = code_item.data(Qt.UserRole) or tariff_code.replace(" ", "")

        try:
            all_rules = self.service.load_inspection_rules(
                search=norm_code, only_active=False, limit=50
            )
            # Filtriraj tačan pogodak po norm kodu
            rules = [r for r in all_rules if r["tariff_code_norm"] == norm_code]
        except Exception as e:
            logger.error(f"Greška pri učitavanju detalja: {e}")
            return

        # Prikaz u detail_container
        self._clear_detail_panel()
        grid = self.detail_container.layout()

        detail_widget = QWidget()
        detail_layout = QVBoxLayout(detail_widget)
        detail_layout.setContentsMargins(0, 8, 0, 0)
        detail_layout.setSpacing(10)

        # ── Naslov + opis robe ──────────────────────────────────────
        title = QLabel(f"<b>Tarifni broj: {tariff_code}</b>")
        title.setStyleSheet("font-size: 14pt; color: #1e3820; padding-bottom: 2px;")
        detail_layout.addWidget(title)

        # Opis robe — uzimamo iz prvog pravila (isti za sve tipove)
        first_desc = next((r["description"] for r in rules if r.get("description")), "")
        if first_desc:
            desc_lbl = QLabel(first_desc)
            desc_lbl.setWordWrap(True)
            desc_lbl.setStyleSheet("font-size: 12pt; color: #333; padding-bottom: 4px;")
            detail_layout.addWidget(desc_lbl)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #c0d8c0;")
        detail_layout.addWidget(sep)

        # ── Blok po tipu inspekcije ─────────────────────────────────
        type_order = ["sanitary", "veterinary", "phytosanitary", "quality_control", "medicines_agency"]
        type_names = {
            "sanitary":         "SAN — Sanitarna inspekcija",
            "veterinary":       "VET — Veterinarska inspekcija",
            "phytosanitary":    "FIT — Fitosanitarna inspekcija",
            "quality_control":  "UVK — Kontrola kvaliteta",
            "medicines_agency": "AGL — Agencija za lijekove",
        }

        for itype in type_order:
            matching = [r for r in rules if r["inspection_type"] == itype]
            if not matching:
                continue

            _, bg = self._INSP_LABELS.get(itype, (itype, "#f5f5f5"))

            block = QFrame()
            block.setFrameShape(QFrame.StyledPanel)
            block.setStyleSheet(
                f"QFrame {{ background: {bg}; border-radius: 6px; }}"
            )
            block_layout = QVBoxLayout(block)
            block_layout.setContentsMargins(12, 8, 12, 8)
            block_layout.setSpacing(4)

            header_lbl = QLabel(f"<b>{type_names.get(itype, itype)}</b>")
            header_lbl.setStyleSheet("font-size: 13pt;")
            block_layout.addWidget(header_lbl)

            # Svaki red posebno (može biti više redova za isti tip)
            for r in matching:
                # Status
                if r["condition_text"]:
                    status_txt = "Status: <b>uslovno</b>"
                elif r["can_auto_decide"]:
                    status_txt = "Status: <b>automatski</b>"
                else:
                    status_txt = "Status: <b>ručni pregled</b>"
                status_lbl = QLabel(status_txt)
                status_lbl.setStyleSheet("font-size: 12pt;")
                block_layout.addWidget(status_lbl)

                # Marker (**, *, +)
                if r.get("marker"):
                    marker_lbl = QLabel(f"Oznaka: <b>{r['marker']}</b>")
                    marker_lbl.setStyleSheet("font-size: 11pt; color: #555;")
                    block_layout.addWidget(marker_lbl)

                # Uslov
                if r["condition_text"]:
                    cond_lbl = QLabel(f"Uslov: {r['condition_text']}")
                    cond_lbl.setWordWrap(True)
                    cond_lbl.setStyleSheet("font-size: 12pt; color: #222;")
                    block_layout.addWidget(cond_lbl)

                # Napomena korisnika
                if r.get("notes"):
                    notes_lbl = QLabel(f"Napomena: {r['notes']}")
                    notes_lbl.setWordWrap(True)
                    notes_lbl.setStyleSheet(
                        "font-size: 11pt; color: #444; font-style: italic;"
                    )
                    block_layout.addWidget(notes_lbl)

                # Izvor + stranica
                src_parts = []
                if r.get("source_dataset"):
                    src_parts.append(r["source_dataset"])
                if r.get("source_page"):
                    src_parts.append(f"str. {r['source_page']}")
                if src_parts:
                    src_lbl = QLabel(f"Izvor: {', '.join(src_parts)}")
                    src_lbl.setStyleSheet("font-size: 11pt; color: #666;")
                    block_layout.addWidget(src_lbl)

                # Scope / match strength
                scope_txt = f"Podudaranje: {r.get('match_strength', '—')} / {r.get('scope', '—')}"
                scope_lbl = QLabel(scope_txt)
                scope_lbl.setStyleSheet("font-size: 10pt; color: #888;")
                block_layout.addWidget(scope_lbl)

            detail_layout.addWidget(block)

        if not any(r["inspection_type"] in type_order for r in rules):
            empty_lbl = QLabel("Nema inspekcijskih pravila za ovaj tarifni broj.")
            empty_lbl.setStyleSheet("font-size: 12pt; color: #888;")
            detail_layout.addWidget(empty_lbl)

        detail_layout.addStretch()
        grid.addWidget(detail_widget, 0, 0, 1, 2)

    def _load_zemlje_data(self):
        """Load Zemlje data using Service layer."""
        try:
            logger.info("Učitavanje zemalja iz baze (preko Service)")

            results = self.service.load_zemlje_data()

            self._populate_table_from_service(
                results,
                columns=["sifra", "naziv"],
            )

            logger.info(f"Uspešno učitano {len(results)} zemalja")
        except Exception as e:
            logger.error(f"Greška pri učitavanju zemalja: {str(e)}")
            raise

    def _load_deklaranti_data(self):
        """Load Deklaranti data using Service layer."""
        try:
            logger.info("Učitavanje deklaranta iz baze (preko Service)")

            results = self.service.load_deklaranti_data()

            self._populate_table_from_service(
                results,
                columns=["jib", "naziv", "adresa", "grad", "drzava"],
            )

            logger.info(f"Uspešno učitano {len(results)} deklaranta")
        except Exception as e:
            logger.error(f"Greška pri učitavanju deklaranta: {str(e)}")
            QMessageBox.critical(
                self, "Greška", f"Greška pri učitavanju deklaranta:\n{str(e)}"
            )

    def _search_zemlje(self, query: str):
        """Search zemlje using Service layer."""
        try:
            logger.info(f"Pretraga zemalja sa query-jem: '{query}'")

            results = self.service.search_zemlje(query)

            self._populate_table_from_service(
                results,
                columns=["sifra", "naziv"],
            )

            logger.info(f"Uspešno učitano {len(results)} zemalja")

        except Exception as e:
            logger.error(f"Greška pri pretrazi zemalja: {str(e)}")
            raise

    def _on_table_cell_clicked(self, row: int, col: int):
        """Handle clicks on table cells.

        NOTE: Akcije kolona je uklonjena za Pošiljaoci i Uvoznici.
        Ova funkcija sada ne radi ništa jer nema Akcije kolone.
        Koristite toolbar dugmad za uređivanje i brisanje.
        """
        try:
            # Akcije kolona je uklonjena - ne radimo ništa pri kliku
            # Koristite toolbar dugmad (+ Novi, ✏ Uredi, 🗑 Obriši)
            return
        except Exception as e:
            logger.error(f"Greška u akcijama tabele: {e}")

    def _edit_row(self, row: int):
        """Handle edit action for a row"""
        try:
            logger.info(f"Uređivanje reda {row}")

            # Extract data from the row
            data = self._extract_row_data(row)
            if not data:
                QMessageBox.warning(self, "Greška", "Nije moguće učitati podatke reda.")
                return

            # Populate form with data
            self._populate_form(data)

            # Enable editing mode
            self._set_readonly_mode(readonly=False)

            # Mark as editing (not new)
            self.is_editing = True
            self.current_row_index = row

            logger.info(f"Forma popunjena za uređivanje reda {row}")
        except Exception as e:
            logger.error(f"Greška pri uređivanju reda {row}: {str(e)}")
            QMessageBox.critical(self, "Greška", f"Greška pri uređivanju:\n{str(e)}")

    def _delete_row(self, row: int):
        """Handle delete action for a row"""
        try:
            logger.info(f"Brisanje reda {row}")

            # Confirm deletion
            reply = QMessageBox.question(
                self,
                "Potvrda brisanja",
                "Da li ste sigurni da želite da obrišete ovaj zapis?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )

            if reply == QMessageBox.No:
                return

            # Extract data from the row
            data = self._extract_row_data(row)
            if not data:
                QMessageBox.warning(self, "Greška", "Nije moguće učitati podatke reda.")
                return

            # Delete from database
            self._delete_from_database(data)

            # Reload data
            self._load_data()

            logger.info(f"Red {row} uspešno obrisan")
        except Exception as e:
            logger.error(f"Greška pri brisanju reda {row}: {str(e)}")
            QMessageBox.critical(self, "Greška", f"Greška pri brisanju:\n{str(e)}")

    def _extract_row_data(self, row: int) -> Optional[Dict[str, Any]]:
        """Extract data from a table row"""
        try:
            if not self.current_category:
                return None

            data = {}

            if self.current_category in ["Pošiljaoci", "Uvoznici"]:
                data = {
                    "jib": (
                        self.table.item(row, 0).text()
                        if self.table.item(row, 0)
                        else ""
                    ),
                    "naziv": (
                        self.table.item(row, 1).text()
                        if self.table.item(row, 1)
                        else ""
                    ),
                    "adresa": (
                        self.table.item(row, 2).text()
                        if self.table.item(row, 2)
                        else ""
                    ),
                    "grad": (
                        self.table.item(row, 3).text()
                        if self.table.item(row, 3)
                        else ""
                    ),
                    "drzava": (
                        self.table.item(row, 4).text()
                        if self.table.item(row, 4)
                        else ""
                    ),
                }
            elif self.current_category == "Carinske tarife":
                data = {
                    "tarifni_kod": (
                        self.table.item(row, 0).text()
                        if self.table.item(row, 0)
                        else ""
                    ),
                    "naziv_robe": (
                        self.table.item(row, 1).text()
                        if self.table.item(row, 1)
                        else ""
                    ),
                }
            elif self.current_category == "Carinarnice":
                data = {
                    "sifra": (
                        self.table.item(row, 0).text()
                        if self.table.item(row, 0)
                        else ""
                    ),
                    "naziv": (
                        self.table.item(row, 1).text()
                        if self.table.item(row, 1)
                        else ""
                    ),
                }

            return data
        except Exception as e:
            logger.error(f"Greška pri izdvajanju podataka iz reda {row}: {str(e)}")
            return None

    def _populate_form(self, data: Dict[str, Any]):
        """Populate form with data"""
        try:
            if self.current_category in ["Pošiljaoci", "Uvoznici"]:
                self.jib_field.setText(data.get("jib", ""))
                self.naziv_field.setText(data.get("naziv", ""))
                self.adresa_field.setText(data.get("adresa", ""))
                self.grad_field.setText(data.get("grad", ""))
                self.zemlja_field.setText(data.get("drzava", ""))
            elif self.current_category == "Carinske tarife":
                self.tarifni_kod_field.setText(data.get("tarifni_kod", ""))
                self.naziv_robe_field.setText(data.get("naziv_robe", ""))
            elif self.current_category == "Carinarnice":
                self.sifra_field.setText(data.get("sifra", ""))
                self.naziv_field.setText(data.get("naziv", ""))
        except Exception as e:
            logger.error(f"Greška pri popunjavanju forme: {str(e)}")

    def _delete_from_database(self, data: Dict[str, Any]):
        """Delete record from database using Service layer"""
        try:
            if self.current_category in ["Pošiljaoci", "Uvoznici"]:
                jib = data.get("jib")
                if jib:
                    if self.current_category == "Pošiljaoci":
                        self.service.delete_posiljalac(jib)
                    else:
                        self.service.delete_uvoznik(jib)
                    logger.info(f"Zapis sa JIB {jib} obrisan")
            elif self.current_category == "Carinske tarife":
                tarifni_kod = data.get("tarifni_kod")
                if tarifni_kod:
                    self.service.delete_trgovacki_naziv(tarifni_kod)
                    logger.info(
                        f"Zapis sa tarifnim kodom {tarifni_kod} obrisan"
                    )
            elif self.current_category == "Carinarnice":
                sifra = data.get("sifra")
                if sifra:
                    self.service.delete_carinarnica(sifra)
                    logger.info(f"Zapis sa šifrom {sifra} obrisan")
        except Exception as e:
            logger.error(f"Greška pri brisanju iz baze: {str(e)}")
            raise

    def _create_action_buttons(self, row: int) -> QWidget:
        """Create edit/delete buttons za red"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        # Edit button
        btn_edit = QToolButton()
        btn_edit.setText("✏️")
        btn_edit.setToolTip("Uredi")
        btn_edit.setStyleSheet(
            """
            QToolButton {
                background: #007bff;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 4px 8px;
            }
            QToolButton:hover {
                background: #0056b3;
            }
        """
        )
        btn_edit.clicked.connect(lambda: self._edit_row(row))

        # Delete button
        btn_delete = QToolButton()
        btn_delete.setText("🗑️")
        btn_delete.setToolTip("Obriši")
        btn_delete.setStyleSheet(
            """
        QToolButton {
            background: #dc3545;
            color: white;
            border: none;
            border-radius: 3px;
            padding: 4px 8px;
        }
        QToolButton:hover {
            background: #bd2130;
        }
    """
        )
        btn_delete.clicked.connect(lambda: self._delete_row(row))

        layout.addWidget(btn_edit)
        layout.addWidget(btn_delete)
        layout.addStretch()

        return widget

    def _validate_form_data(self, category_data):
        """Centralizovana validacija forme"""
        if self.current_category in ["Pošiljaoci", "Uvoznici"]:
            required_fields = {
                "JIB": category_data.get("jib"),
                "Naziv": category_data.get("naziv"),
            }
            return self.validator.validate_required_fields(required_fields)
        elif self.current_category == "Carinske tarife":
            required_fields = {
                "Tarifni kod": category_data.get("tarifni_kod"),
                "Opis": category_data.get("opis"),
            }
            return self.validator.validate_required_fields(required_fields)
        elif self.current_category == "Carinarnice":
            required_fields = {
                "Šifra": category_data.get("sifra"),
                "Naziv": category_data.get("naziv"),
            }
            return self.validator.validate_required_fields(required_fields)
        return []

    def _prepare_form_data(self):
        """Priprema podatke iz forme za snimanje"""
        if self.current_category in ["Pošiljaoci", "Uvoznici"]:
            return {
                "jib": self.validator.sanitize_input(self.jib_field.text()),
                "naziv": self.validator.sanitize_input(self.naziv_field.text()),
                "adresa": self.validator.sanitize_input(self.adresa_field.text()),
                "grad": self.validator.sanitize_input(self.grad_field.text()),
                "postanski_broj": self.validator.sanitize_input(
                    self.postanski_broj_field.text()
                ),
                "zemlja": self.validator.sanitize_input(self.zemlja_field.text()),
                "telefon": self.validator.sanitize_input(self.telefon_field.text()),
                "email": self.validator.sanitize_input(self.email_field.text()),
                "kontakt": self.validator.sanitize_input(self.kontakt_field.text()),
                "pdv": self.validator.sanitize_input(self.pdv_field.text()),
                "maticni": self.validator.sanitize_input(self.maticni_field.text()),
            }
        elif self.current_category == "Carinske tarife":
            # Ukloni razmake iz tarifnog koda pri snimanju
            tarifni_kod = self.validator.sanitize_input(
                self.tarifni_kod_field.text()
            ).replace(" ", "")
            return {
                "tarifni_kod": tarifni_kod,
                "opis": self.validator.sanitize_input(self.naziv_robe_field.text()),
            }
        elif self.current_category == "Carinarnice":
            return {
                "sifra": self.validator.sanitize_input(self.sifra_field.text()),
                "naziv": self.validator.sanitize_input(self.naziv_field.text()),
            }
        return {}

    def _apply_search(self):
        """Apply search/filter"""
        try:
            query = self.search_input.text().strip()
            logger.info(f"Primena pretrage sa query-jem: '{query}'")

            # Clear highlighting
            self._clear_highlights()

            if self.current_category == "Pošiljaoci":
                self._search_posiljaoci(query)
            elif self.current_category == "Uvoznici":
                self._search_uvoznici(query)
            elif self.current_category == "Carinske tarife":
                self._search_trgovacki_nazivi(query)
            elif self.current_category == "Inspekcijska pravila":
                self._load_inspekcijska_pravila_data()
            elif self.current_category == "Carinarnice":
                self._search_carinarnice(query)
            elif self.current_category == "Primaoci":
                self._filter_table(query)
            elif self.current_category == "Deklaranti":
                self._filter_table(query)
            elif self.current_category == "Zemlje":
                self._search_zemlje(query)
            else:
                # Carinarnice, Carinski postupci - read-only
                self._filter_table(query)

            # EKSTREMNO FORSIRANJE PRIKAZA TABELE
            logger.info("=== FORSIRANJE PRIKAZA TABELE ===")

            # 1. Forsiraj vidljivost
            self.table.show()
            self.table.setVisible(True)
            self.table.raise_()
            self.table.activateWindow()

            # 2. Forsiraj osvežavanje na svim nivoima
            self.table.viewport().update()
            self.table.update()
            self.table.repaint()

            # 3. Forsiraj parent komponente
            if self.table.parent():
                parent = self.table.parent()
                parent.show()
                parent.update()
                parent.repaint()
                if hasattr(parent, "parent") and parent.parent():
                    grandparent = parent.parent()
                    grandparent.show()
                    grandparent.update()
                    grandparent.repaint()

            # 4. Forsiraj celu formu
            self.show()
            self.update()
            self.repaint()

            logger.info("=== KRAJ FORSIRANJA PRIKAZA ===")

            self._update_status()

        except Exception as e:
            logger.error(f"Greška pri primeni pretrage: {str(e)}")

    # Kategorije koje pretražuju direktno u bazi (debounced)
    _DB_SEARCH_CATEGORIES = frozenset(
        ["Pošiljaoci", "Uvoznici", "Zemlje", "Carinske tarife"]
    )

    def _on_search_text_changed(self, text: str):
        """Live pretraga dok korisnik kuca — DB kategorije debounced 300ms."""
        try:
            if self.current_category in self._DB_SEARCH_CATEGORIES:
                # Odgodi DB query da ne gađamo bazu na svaki karakter
                self._search_timer.start()
            elif self.current_category == "Carinarnice":
                self._search_carinarnice(text)
                self._update_status()
            else:
                # Lokalni filter (Carinski postupci, Deklaranti, Inkoterms...)
                self._filter_table(text)
                self._update_status()
        except Exception as e:
            logger.error(f"Greška pri live pretrazi: {str(e)}")

    def _execute_db_search(self):
        """Pokrenuto debounce timerom — izvršava DB pretragu za trenutnu kategoriju."""
        try:
            text = self.search_input.text().strip()
            cat = self.current_category
            if cat == "Pošiljaoci":
                self._search_posiljaoci(text)
            elif cat == "Uvoznici":
                self._search_uvoznici(text)
            elif cat == "Zemlje":
                self._search_zemlje(text)
            elif cat == "Carinske tarife":
                self._search_trgovacki_nazivi(text)
            self._update_status()
        except Exception as e:
            logger.error(f"Greška pri DB pretrazi: {str(e)}")

    def _search_posiljaoci(self, query: str):
        """Search posiljaoci using Service layer."""
        try:
            logger.info(f"Pretraga pošiljalaca sa query-jem: '{query}'")

            results = self.service.search_posiljaoci(query)

            self._populate_table_from_service(
                results,
                columns=["jib", "naziv", "adresa", "grad", "drzava"],
            )

            logger.info(f"Uspešno prikazano {len(results)} rezultata za pošiljaoce")
        except Exception as e:
            logger.error(f"Greška pri pretrazi pošiljalaca: {str(e)}")
            QMessageBox.critical(
                self, "Greška", f"Greška pri pretrazi pošiljalaca:\n{str(e)}"
            )

    def _filter_table(self, search_text: str):
        """Filter table rows based on search text — substring match across all columns."""
        try:
            search_text = search_text.lower().strip()

            for row in range(self.table.rowCount()):
                if not search_text:
                    self.table.setRowHidden(row, False)
                    continue
                match = any(
                    search_text in (self.table.item(row, col).text().lower() if self.table.item(row, col) else "")
                    for col in range(self.table.columnCount())
                )
                self.table.setRowHidden(row, not match)

        except Exception as e:
            logger.error(f"Greška pri filtriranju tabele: {str(e)}")
            raise

    def _clear_highlights(self):
        """Clear any highlighted items in the table"""
        try:
            # For now, just ensure all items have default appearance
            for row in range(self.table.rowCount()):
                for col in range(self.table.columnCount()):  # Sve kolone
                    item = self.table.item(row, col)
                    if item:
                        item.setBackground(self.palette().window())
            logger.debug("Isticanja u tabeli očišćena")
        except Exception as e:
            logger.error(f"Greška pri čišćenju isticanja: {str(e)}")

    def _reset_search(self):
        """Reset all search fields"""
        try:
            logger.info("Resetovanje pretrage")
            self.search_input.clear()

            if hasattr(self, "search_pib"):
                self.search_pib.clear()

            if hasattr(self, "search_zemlja"):
                self.search_zemlja.setCurrentIndex(0)

            # For Pošiljaoci, Uvoznici and Trgovački nazivi, reload all data from database
            if self.current_category == "Pošiljaoci":
                self._load_posiljaoci_data()
            elif self.current_category == "Uvoznici":
                self._load_uvoznici_data()
            elif self.current_category == "Trgovački nazivi":
                self._load_trgovacki_nazivi_data()
            else:
                # Show all rows for other categories
                for row in range(self.table.rowCount()):
                    self.table.setRowHidden(row, False)

            self._update_status()
            logger.info("Pretraga resetovana")

        except Exception as e:
            logger.error(f"Greška pri resetovanju pretrage: {str(e)}")
            QMessageBox.critical(
                self, "Greška", f"Greška pri resetovanju pretrage:\n{str(e)}"
            )

    def _prev_record(self):
        """Navigate to previous record"""
        try:
            current = self.table.currentRow()
            if current > 0:
                self.table.selectRow(current - 1)
                logger.debug(f"Navigacija na prethodni zapis: {current - 1}")
        except Exception as e:
            logger.error(f"Greška pri navigaciji na prethodni zapis: {str(e)}")

    def _next_record(self):
        """Navigate to next record"""
        try:
            current = self.table.currentRow()
            if current < self.table.rowCount() - 1:
                self.table.selectRow(current + 1)
                logger.debug(f"Navigacija na sledeći zapis: {current + 1}")
        except Exception as e:
            logger.error(f"Greška pri navigaciji na sledeći zapis: {str(e)}")

    def _goto_record(self, row: int):
        """Go to specific record"""
        try:
            if 0 <= row < self.table.rowCount():
                self.table.selectRow(row)
                logger.debug(f"Navigacija na zapis: {row}")
        except Exception as e:
            logger.error(f"Greška pri navigaciji na zapis {row}: {str(e)}")

    def _update_pager(self):
        """Update pager position"""
        try:
            current = 0
            total = 0

            # Check if table is QTableWidget or QTreeWidget and handle accordingly
            if hasattr(self.table, "currentRow"):  # QTableWidget
                current = self.table.currentRow() + 1
                total = self.table.rowCount()
            elif hasattr(self.table, "selectedItems"):  # QTreeWidget
                # For QTreeWidget, get current selection differently
                selected_items = self.table.selectedItems()
                if selected_items:
                    # Find the position of the selected item among all visible items
                    item = selected_items[0]
                    # Only count if it's a leaf node (customs post), not a parent node (regional center)
                    if item.parent():  # It's a child item (customs post)
                        # Count how many visible items come before this one
                        all_items = []

                        def collect_items(parent_item):
                            if parent_item.childCount() == 0:  # Leaf node
                                all_items.append(parent_item)
                            else:  # Parent node
                                for i in range(parent_item.childCount()):
                                    child = parent_item.child(i)
                                    collect_items(child)

                        # Collect all leaf items (customs posts)
                        for i in range(self.table.topLevelItemCount()):
                            top_item = self.table.topLevelItem(i)
                            collect_items(top_item)

                        # Find position of current item
                        if item in all_items:
                            current = all_items.index(item) + 1
                        else:
                            current = 0
                    else:  # It's a parent item (regional center)
                        current = 0
                else:
                    current = 0

                # Total is the number of leaf items (customs posts)
                total = self._get_tree_widget_leaf_count()
            else:
                current = 0
                total = 0

            category_singular = {
                "Pošiljaoci": "Pošiljalac",
                "Uvoznici": "Uvoznik",
                "Primaoci": "Primalac",
                "Carinske tarife": "Tarifa",
                "Deklaranti": "Deklarant",
                "Carinarnice": "Carinarnica",
                "Zemlje": "Zemlja",
            }

            name = category_singular.get(self.current_category, "Stavka")
            self.lbl_position.setText(f"{name} {current} od {total}")
            logger.debug(f"Ažuriran pager: {current}/{total}")
        except Exception as e:
            logger.error(f"Greška pri ažuriranju pager-a: {str(e)}")

    def _get_tree_widget_leaf_count(self) -> int:
        """Count only leaf items (customs posts) in tree widget, excluding parent nodes (regional centers)"""
        if not hasattr(self, "tree_widget") or self.table != self.tree_widget:
            return 0

        count = 0

        def count_leaves(item):
            nonlocal count
            # If item has no children, it's a leaf (customs post)
            if item.childCount() == 0:
                count += 1
            else:
                # If item has children, recursively count leaves in children
                for i in range(item.childCount()):
                    child = item.child(i)
                    count_leaves(child)

        for i in range(self.tree_widget.topLevelItemCount()):
            top_item = self.tree_widget.topLevelItem(i)
            count_leaves(top_item)

        return count

    def _update_status(self):
        """Update status bar totals"""
        try:
            # Check if table is QTableWidget or QTreeWidget
            if hasattr(self.table, "rowCount"):  # QTableWidget
                total = self.table.rowCount()
                visible = sum(1 for row in range(total) if not self.table.isRowHidden(row))
            elif hasattr(self.table, "topLevelItemCount"):  # QTreeWidget (Carinarnice)
                # For QTreeWidget, count all items (both parent and child)
                total = self._get_tree_widget_count()
                visible = total  # For now, assume all are visible
            else:
                total = 0
                visible = 0

            category_plural = {
                "Pošiljaoci": "pošiljalaca",
                "Uvoznici": "uvoznika",
                "Primaoci": "primalaca",
                "Carinske tarife": "tarifa",
                "Deklaranti": "deklaranata",
                "Carinarnice": "carinarnica",
                "Zemlje": "zemalja",
            }

            if self.current_category == "Pošiljaoci":
                total = self.service.count_izvoznici()
                self.lbl_totals.setText(f"Ukupno: {total} pošiljalaca | Prikazano: {total}")
            elif self.current_category == "Uvoznici":
                total = self.service.count_uvoznici()
                self.lbl_totals.setText(f"Ukupno: {total} uvoznika | Prikazano: {total}")
            elif self.current_category == "Carinske tarife":
                total = self.service.count_zvanicna_tarifa()
                self.lbl_totals.setText(f"Ukupno: {total} carinskih tarifa | Prikazano: {total}")
            elif self.current_category == "Carinarnice":
                total = self.service.count_carinske_ispostave()
                self.lbl_totals.setText(f"Ukupno: {total} carinarnica | Prikazano: {total}")
            else:
                name = category_plural.get(self.current_category, "stavki")
                self.lbl_totals.setText(
                    f"Ukupno: {total} {name} | Prikazano: {visible}"
                )
                logger.debug(f"Ažuriran status: {total} {name}, prikazano: {visible}")

        except Exception as e:
            logger.error(f"Greška pri ažuriranju statusa: {str(e)}")

    def _update_last_change(self):
        """Update last change timestamp"""
        try:
            now = datetime.now()
            timestamp = now.strftime("%d.%m.%Y %H:%M")
            self.lbl_last_change.setText(f"Posljednja izmjena: {timestamp}")
            logger.debug(f"Ažuriran timestamp poslednje izmene: {timestamp}")
        except Exception as e:
            logger.error(f"Greška pri ažuriranju timestamp-a: {str(e)}")

    def _get_tree_widget_count(self) -> int:
        """Count total items in tree widget (both parent and child nodes)"""
        if not hasattr(self.table, "topLevelItemCount"):
            return 0

        total = 0

        def count_children(item):
            count = 1  # Count the parent item itself
            for i in range(item.childCount()):
                child = item.child(i)
                count += count_children(child)  # Recursively count children
            return count

        for i in range(self.table.topLevelItemCount()):
            top_item = self.table.topLevelItem(i)
            total += count_children(top_item)

        return total

    def _set_readonly_mode(self, readonly: bool = True):
        """Set table and detail form to readonly mode"""
        try:
            # Check if table is QTableWidget or QTreeWidget and handle accordingly
            if hasattr(self.table, "rowCount"):  # QTableWidget
                # Set table cells to readonly for QTableWidget
                for row in range(self.table.rowCount()):
                    for col in range(self.table.columnCount()):
                        item = self.table.item(row, col)
                        if item:
                            if readonly:
                                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                            else:
                                item.setFlags(item.flags() | Qt.ItemIsEditable)
            elif hasattr(self.table, "topLevelItemCount"):  # QTreeWidget
                # For QTreeWidget, we don't typically make items readonly in the same way
                # Instead, we might adjust their flags if needed
                def set_tree_item_flags(item, readonly):
                    for col in range(self.table.columnCount()):
                        if readonly:
                            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                        else:
                            item.setFlags(item.flags() | Qt.ItemIsEditable)

                    # Recursively set children
                    for i in range(item.childCount()):
                        child = item.child(i)
                        set_tree_item_flags(child, readonly)

                # Apply to all top-level items
                for i in range(self.table.topLevelItemCount()):
                    top_item = self.table.topLevelItem(i)
                    set_tree_item_flags(top_item, readonly)

            # Set detail form fields to readonly/normal
            fields_to_set = [
                "jib_field",
                "naziv_field",
                "adresa_field",
                "grad_field",
                "postanski_broj_field",
                "zemlja_field",
                "telefon_field",
                "email_field",
                "kontakt_field",
                "pdv_field",
                "maticni_field",
                "tarifni_kod_field",
                "naziv_robe_field",
                "sifra_field",
            ]

            for field_name in fields_to_set:
                if hasattr(self, field_name):
                    field = getattr(self, field_name)
                    # Check if field still exists and is valid
                    if field and self._is_valid_widget(field):
                        field.setReadOnly(readonly)

            # Enable/disable edit buttons based on readonly mode
            if hasattr(self, "btn_novi"):
                self.btn_novi.setEnabled(not readonly)

            # Check current selection differently based on widget type
            current_selection_exists = False
            if hasattr(self.table, "currentRow"):  # QTableWidget
                current_selection_exists = self.table.currentRow() >= 0
            elif hasattr(self.table, "selectedItems"):  # QTreeWidget
                selected_items = self.table.selectedItems()
                if selected_items:
                    item = selected_items[0]
                    # Only allow edit/delete if it's a leaf node (customs post), not a parent node (regional center)
                    if item.parent():  # It's a child item (customs post)
                        current_selection_exists = True
                    else:  # It's a parent item (regional center)
                        current_selection_exists = False

            if hasattr(self, "btn_uredi"):
                self.btn_uredi.setEnabled(not readonly and current_selection_exists)
            if hasattr(self, "btn_obrisi"):
                self.btn_obrisi.setEnabled(not readonly and current_selection_exists)

            logger.debug(f"Režim čitanja postavljen na: {readonly}")

        except Exception as e:
            logger.error(f"Greška pri postavljanju readonly režima: {str(e)}")

    def _is_valid_widget(self, widget):
        """Check if widget is still valid (not deleted)"""
        try:
            # Check if widget exists and is valid
            if widget is None:
                return False
            # Try to access some property to see if it's still valid
            widget.isVisible()
            return True
        except RuntimeError:
            # Widget is deleted
            return False

    def format_tarifni_kod(self, kod):
        """Formatira tarifni kod u oblik '0210 19 70 000'"""
        if not kod:
            return ""

        kod_str = str(kod).strip()

        # Ukloni sve razmake i znake koji nisu cifre
        kod_str = "".join(filter(str.isdigit, kod_str))

        # Formatira kod na osnovu dužine
        if len(kod_str) >= 11:
            # Format: 0210 19 70 000 (11 cifara)
            return f"{kod_str[:4]} {kod_str[4:6]} {kod_str[6:8]} {kod_str[8:11]}"
        elif len(kod_str) >= 10:
            # Format: 0210 19 70 00 (10 cifara)
            return f"{kod_str[:4]} {kod_str[4:6]} {kod_str[6:8]} {kod_str[8:10]}"
        elif len(kod_str) >= 8:
            # Format: 0210 19 70 (8 cifara)
            return f"{kod_str[:4]} {kod_str[4:6]} {kod_str[6:8]}"
        elif len(kod_str) >= 6:
            # Format: 0210 19 (6 cifara)
            return f"{kod_str[:4]} {kod_str[4:6]}"
        elif len(kod_str) >= 4:
            # Format: 0210 (4 cifre)
            return f"{kod_str[:4]}"
        else:
            return kod_str

    def _search_trgovacki_nazivi(self, query: str):
        """Pretraga carinskih tarifa — hijerarhijski za brojeve, tekst za opis."""
        try:
            query = query.strip()
            if not query:
                self._load_trgovacki_nazivi_data()
                return

            clean_query = query.replace(" ", "")
            is_code = clean_query.isdigit()

            def _clean(v):
                return _TAIL_RATES_RE.sub('', str(v)).rstrip(' –-').strip() if v else v

            # Ako je pretraga brojčana, koristi hijerarhijski prikaz iz SQLite
            if is_code and len(clean_query) >= 2:
                # Guard: populate_tariff_hierarchy zahtijeva QTableWidget
                if not hasattr(self.table, 'setRowCount'):
                    logger.warning("_search_trgovacki_nazivi: self.table je QTreeWidget — restauriram")
                    self._restore_table_widget()
                populate_tariff_hierarchy(
                    self.table,
                    prefix=clean_query,
                    clean_opis_fn=_clean,
                )
            else:
                # Za tekstualnu pretragu ili kratke brojeve (<2 cifre), koristi običnu pretragu
                if is_code and len(clean_query) < 2:
                    # Za kratke brojeve (<2 cifre) - obična pretraga
                    results = self.service.load_trgovacki_nazivi_data()
                    # Filter lokalno za kratke prefikse
                    results = [r for r in results if r.get('tarifni_kod', '').startswith(clean_query)]
                else:
                    # Tekstualna pretraga
                    results = self.service.search_trgovacki_nazivi(query)

                self._populate_table_from_service(
                    results,
                    columns=["tarifni_kod", "opis"],
                    format_fn=_clean,
                )

            logger.info(f"Uspešno prikazano rezultata za trgovačke nazive")
        except Exception as e:
            logger.error(f"Greška pri pretrazi trgovačkih naziva: {str(e)}")
            QMessageBox.critical(
                self, "Greška", f"Greška pri pretrazi trgovačkih naziva:\n{str(e)}"
            )

    def _search_uvoznici(self, query: str):
        """Search uvoznici using Service layer."""
        try:
            logger.info(f"Pretraga uvoznika sa query-jem: '{query}'")

            results = self.service.search_uvoznici(query)

            self._populate_table_from_service(
                results,
                columns=["jib", "naziv", "adresa", "grad", "drzava"],
            )

            logger.info(f"Uspešno prikazano {len(results)} rezultata za uvoznike")
        except Exception as e:
            logger.error(f"Greška pri pretrazi uvoznika: {str(e)}")
            QMessageBox.critical(
                self, "Greška", f"Greška pri pretrazi uvoznika:\n{str(e)}"
            )

    def _on_novi(self):
        """Handle Novi button click with validation"""
        try:
            logger.info("Kreiranje novog zapisa")

            if self.current_category in ["Pošiljaoci", "Carinske tarife"]:
                self._clear_form()
                self.btn_snimi.setEnabled(True)
                self.is_editing = False
                # Enable editing mode
                self._set_readonly_mode(readonly=False)
                logger.info(
                    f"Forma za novi zapis ({self.current_category}) pripremljena"
                )
            else:
                # Original implementation for other categories
                if hasattr(super(), "_on_novi"):
                    super()._on_novi()

        except Exception as e:
            logger.error(f"Greška pri kreiranju novog zapisa: {str(e)}")
            QMessageBox.critical(
                self, "Greška", f"Greška pri kreiranju novog zapisa:\n{str(e)}"
            )

    def _on_uredi(self, row=None):
        """Handle Uredi button click with validation"""
        try:
            logger.info("Uređivanje zapisa")
            # itemDoubleClicked šalje QTableWidgetItem, a ne int
            from PySide6.QtWidgets import QTableWidgetItem as _QTWI

            if isinstance(row, _QTWI):
                row = row.row()

            if self.current_category == "Pošiljaoci":
                if row is None:
                    current_row = self.table.currentRow()
                    if current_row < 0:
                        QMessageBox.warning(
                            self, "Upozorenje", "Molimo odaberite red za uređivanje."
                        )
                        return
                    row = current_row

                # Load data from selected row to form
                jib_item = self.table.item(row, 0)
                naziv_item = self.table.item(row, 1)
                adresa_item = self.table.item(row, 2)
                grad_item = self.table.item(row, 3)
                drzava_item = self.table.item(row, 4)

                if jib_item:
                    self.jib_field.setText(jib_item.text())
                if naziv_item:
                    self.naziv_field.setText(naziv_item.text())
                if adresa_item:
                    self.adresa_field.setText(adresa_item.text())
                if grad_item:
                    self.grad_field.setText(grad_item.text())
                if drzava_item:
                    self.zemlja_field.setText(drzava_item.text())

                # JIB (13 cifara) = "4" + PDV (12 cifara iz DB)
                jib_val = jib_item.text() if jib_item else ""
                self.pdv_field.setText("4" + jib_val if jib_val else "")
                self.telefon_field.setText("")
                self.email_field.setText("")
                self.kontakt_field.setText("")
                self.maticni_field.setText("")

                self.current_row_index = row
                self.btn_snimi.setEnabled(True)
                self.is_editing = True
                # Enable editing mode
                self._set_readonly_mode(readonly=False)
                logger.info(f"Zapis {row} uspešno učitan za uređivanje")
            elif self.current_category == "Uvoznici":
                if row is None:
                    current_row = self.table.currentRow()
                    if current_row < 0:
                        QMessageBox.warning(
                            self, "Upozorenje", "Molimo odaberite red za uređivanje."
                        )
                        return
                    row = current_row

                # JIB iz tabele (ključ za DB query)
                jib_item = self.table.item(row, 0)
                if not jib_item:
                    return
                jib = jib_item.text()

                # Dohvati podatke iz baze preko Service layer-a
                uvoznici = self.service.load_uvoznici_data(jib)
                db_row = uvoznici[0] if uvoznici else None

                if db_row:
                    jib_val = db_row.get("jib", "")
                    naziv = db_row.get("naziv", "")
                    adresa = db_row.get("adresa", "")
                    grad = db_row.get("grad", "")
                    ptt = db_row.get("postanski_broj", "")
                    drzava = db_row.get("drzava", "")
                    jib_str = str(jib_val) if jib_val else ""
                    # DB čuva 12-cifreni PDV; JIB (13 cifara) = "4" + PDV
                    self.jib_field.setText(jib_str)                     # PDV (12 cifara)
                    self.naziv_field.setText(str(naziv) if naziv else "")
                    self.adresa_field.setText(str(adresa) if adresa else "")
                    self.grad_field.setText(str(grad) if grad else "")
                    self.postanski_broj_field.setText(str(ptt) if ptt else "")
                    self.zemlja_field.setText(str(drzava) if drzava else "")
                    self.pdv_field.setText("4" + jib_str if jib_str else "")  # JIB (13 cifara)
                    self.telefon_field.setText("")
                    self.email_field.setText("")
                    self.kontakt_field.setText("")
                    self.maticni_field.setText("")
                else:
                    # Fallback: popuni iz tabele (col 0 = PDV, 12 cifara)
                    pdv_val = jib
                    self.jib_field.setText(pdv_val or "")  # PDV (12 cifara)
                    for col, field in [
                        (1, self.naziv_field),
                        (2, self.adresa_field),
                        (3, self.grad_field),
                        (4, self.zemlja_field),
                    ]:
                        item = self.table.item(row, col)
                        if item:
                            field.setText(item.text())
                    self.pdv_field.setText(
                        "4" + pdv_val if pdv_val else ""
                    )  # JIB (13 cifara)

                self.current_row_index = row
                self.btn_snimi.setEnabled(True)
                self.is_editing = True
                self._set_readonly_mode(readonly=False)
                logger.info(f"Uvoznik {jib} uspešno učitan za uređivanje")

            elif self.current_category == "Carinske tarife":
                if row is None:
                    current_row = self.table.currentRow()
                    if current_row < 0:
                        QMessageBox.warning(
                            self, "Upozorenje", "Molimo odaberite red za uređivanje."
                        )
                        return
                    row = current_row

                # Load data from selected row to form for Carinske tarife
                kod_item = self.table.item(row, 0)
                opis_item = self.table.item(row, 1)

                if kod_item:
                    # Formatiraj kod za prikaz u formi
                    original_kod = kod_item.text().replace(" ", "")
                    formatted_kod = self.format_tarifni_kod(original_kod)
                    self.tarifni_kod_field.setText(formatted_kod)
                if opis_item:
                    self.naziv_robe_field.setText(opis_item.text())

                self.current_row_index = row
                self.btn_snimi.setEnabled(True)
                self.is_editing = True
                # Enable editing mode
                self._set_readonly_mode(readonly=False)
                logger.info(f"Zapis {row} uspešno učitan za uređivanje")
            elif self.current_category == "Carinarnice":
                # Handle selection differently for tree widget vs regular table
                sifra_value = None
                naziv_value = None
                row_index = -1

                if hasattr(self, "tree_widget") and self.table == self.tree_widget:
                    # For tree widget, get the selected item
                    selected_items = self.tree_widget.selectedItems()
                    if not selected_items:
                        QMessageBox.warning(
                            self,
                            "Upozorenje",
                            "Molimo odaberite ispostavu za uređivanje.",
                        )
                        return

                    item = selected_items[0]
                    # Only allow editing if it's a customs post (child item), not a regional center (parent item)
                    if not item.parent():  # It's a regional center - can't edit
                        QMessageBox.warning(
                            self, "Upozorenje", "Ne možete uređivati regionalni centar."
                        )
                        return

                    sifra_value = item.text(0)
                    naziv_value = item.text(1)
                    # For tree widget, we don't have a row index in the traditional sense
                    # We'll use a different approach to track the current item
                    self.current_tree_item = item
                else:
                    # For regular table
                    if row is None:
                        current_row = self.table.currentRow()
                        if current_row < 0:
                            QMessageBox.warning(
                                self,
                                "Upozorenje",
                                "Molimo odaberite red za uređivanje.",
                            )
                            return
                        row = current_row

                    # Load data from selected row to form
                    sifra_item = self.table.item(row, 0)
                    naziv_item = self.table.item(row, 1)

                    if sifra_item:
                        sifra_value = sifra_item.text()
                    if naziv_item:
                        naziv_value = naziv_item.text()

                    row_index = row

                if sifra_value:
                    self.sifra_field.setText(sifra_value)
                if naziv_value:
                    self.naziv_field.setText(naziv_value)

                self.current_row_index = row_index
                self.btn_snimi.setEnabled(True)
                self.is_editing = True
                # Enable editing mode
                self._set_readonly_mode(readonly=False)
                logger.info(f"Zapis za uređivanje uspešno učitan")
            else:
                # Original implementation for other categories
                if hasattr(super(), "_on_uredi"):
                    super()._on_uredi(row)

        except Exception as e:
            logger.error(f"Greška pri uređivanju zapisa: {str(e)}")
            QMessageBox.critical(
                self, "Greška", f"Greška pri uređivanju zapisa:\n{str(e)}"
            )

    def _on_obrisi(self, row: int = None):
        """Handle Obriši button click"""
        if self.current_category in ["Pošiljaoci", "Uvoznici"]:
            if row is None:
                current_row = self.table.currentRow()
                if current_row < 0:
                    QMessageBox.warning(
                        self, "Upozorenje", "Molimo odaberite red za brisanje."
                    )
                    return
                row = current_row

            jib_item = self.table.item(row, 0)
            if not jib_item:
                return

            entity_name = ""
            table_name = ""
            success_message = ""
            if self.current_category == "Pošiljaoci":
                entity_name = "pošiljaoca"
                table_name = "catalogs.izvoznici"
                success_message = "Pošiljalac uspješno obrisan."
            elif self.current_category == "Uvoznici":
                entity_name = "uvoznika"
                table_name = "catalogs.uvoznici"
                success_message = "Uvoznik uspješno obrisan."
            elif self.current_category == "Carinske tarife":
                entity_name = "carinske tarife"
                table_name = "catalogs.zvanicna_tarifa"
                success_message = "Carinska tarifa uspješno obrisana."
            elif self.current_category == "Carinarnice":
                entity_name = "carinarnice"
                table_name = "catalogs.carinske_ispostave"
                success_message = "Carinarnica uspješno obrisana."
            if not table_name:
                return

            # Determine the identifier field based on category
            identifier_field = "jib"
            if self.current_category in ["Carinske tarife"]:
                identifier_field = "tarifni_kod"
            elif self.current_category == "Carinarnice":
                identifier_field = "sifra"

            # Get the identifier value from the table
            identifier_item = None
            identifier_value = None

            if hasattr(self, "tree_widget") and self.table == self.tree_widget:
                # For tree widget, get the selected item
                selected_items = self.tree_widget.selectedItems()
                if selected_items:
                    item = selected_items[0]
                    # Only allow deletion if it's a customs post (child item), not a regional center (parent item)
                    if item.parent():  # It's a customs post
                        identifier_item = item
                        identifier_value = item.text(0)
                    else:  # It's a regional center - can't delete
                        QMessageBox.warning(
                            self, "Upozorenje", "Ne možete obrisati regionalni centar."
                        )
                        return
            else:
                # For regular table
                identifier_item = self.table.item(row, 0)
                if identifier_item:
                    identifier_value = identifier_item.text()

            if not identifier_value:
                return

            reply = QMessageBox.question(
                self,
                "Potvrda brisanja",
                f"Da li ste sigurni da želite obrisati {entity_name} sa {identifier_field.upper()}-om {identifier_value}?",
                QMessageBox.Yes | QMessageBox.No,
            )

            if reply == QMessageBox.Yes:
                try:
                    # Delete from database using Service layer
                    deleted = False
                    if self.current_category == "Pošiljaoci":
                        deleted = self.service.delete_posiljalac(identifier_value)
                    elif self.current_category == "Uvoznici":
                        deleted = self.service.delete_uvoznik(identifier_value)
                    elif self.current_category == "Carinske tarife":
                        deleted = self.service.delete_trgovacki_naziv(identifier_value)
                    elif self.current_category == "Carinarnice":
                        deleted = self.service.delete_carinarnica(identifier_value)

                    if not deleted:
                        QMessageBox.warning(
                            self, "Upozorenje", f"Neuspešno brisanje {entity_name}."
                        )
                        return

                    # Reload data
                    if self.current_category == "Pošiljaoci":
                        self._load_posiljaoci_data()
                    elif self.current_category == "Uvoznici":
                        self._load_uvoznici_data()
                    elif self.current_category == "Carinske tarife":
                        self._load_trgovacki_nazivi_data()
                    elif self.current_category == "Carinarnice":
                        self._load_carinarnice_data()

                    QMessageBox.information(self, "Uspeh", success_message)

                    # Return to readonly mode after deletion
                    self._set_readonly_mode(readonly=True)
                except Exception as e:
                    QMessageBox.critical(
                        self, "Greška", f"Greška pri brisanju {entity_name}:\n{str(e)}"
                    )
        else:
            # Original implementation for other categories
            if hasattr(super(), "_on_obrisi"):
                super()._on_obrisi(row)

    def _on_snimi(self):
        """Handle Snimi button click"""
        if self.current_category in ["Pošiljaoci", "Uvoznici"]:
            # Prepare and validate data
            form_data = self._prepare_form_data()
            validation_errors = self._validate_form_data(form_data)

            if validation_errors:
                error_msg = "Sledeća polja su obavezna:\n" + "\n".join(
                    validation_errors
                )
                QMessageBox.warning(self, "Upozorenje", error_msg)
                return

            try:
                if self.is_editing:
                    # Update existing record
                    if self.current_category == "Pošiljaoci":
                        success = self.service.update_posiljalac({
                            "jib": form_data["jib"],
                            "naziv": form_data["naziv"],
                            "adresa": form_data["adresa"],
                            "grad": form_data["grad"],
                            "drzava": form_data["zemlja"],
                            "telefon": form_data["telefon"],
                            "email": form_data["email"],
                            "kontakt": form_data["kontakt"],
                            "pdv_broj": form_data["pdv"],
                            "maticni": form_data["maticni"],
                        })
                        if success:
                            self._load_posiljaoci_data()
                    elif self.current_category == "Uvoznici":
                        success = self.service.update_uvoznik({
                            "jib": form_data["jib"],
                            "naziv": form_data["naziv"],
                            "adresa": form_data["adresa"],
                            "grad": form_data["grad"],
                            "drzava": form_data["zemlja"],
                            "telefon": form_data["telefon"],
                            "email": form_data["email"],
                            "kontakt": form_data["kontakt"],
                            "pdv_broj": form_data["pdv"],
                            "maticni": form_data["maticni"],
                        })
                        if success:
                            self._load_uvoznici_data()
                    elif self.current_category == "Carinske tarife":
                        success = self.service.update_trgovacki_naziv(
                            form_data["tarifni_kod"],
                            form_data["naziv_robe"],
                        )
                        if success:
                            self._load_trgovacki_nazivi_data()
                else:
                    # Insert new record
                    if self.current_category == "Pošiljaoci":
                        success = self.service.add_posiljalac({
                            "jib": form_data["jib"],
                            "naziv": form_data["naziv"],
                            "adresa": form_data["adresa"],
                            "grad": form_data["grad"],
                            "drzava": form_data["zemlja"],
                            "telefon": form_data["telefon"],
                            "email": form_data["email"],
                            "kontakt": form_data["kontakt"],
                            "pdv_broj": form_data["pdv"],
                            "maticni": form_data["maticni"],
                        })
                        if success:
                            self._load_posiljaoci_data()
                    elif self.current_category == "Uvoznici":
                        success = self.service.add_uvoznik({
                            "jib": form_data["jib"],
                            "naziv": form_data["naziv"],
                            "adresa": form_data["adresa"],
                            "grad": form_data["grad"],
                            "drzava": form_data["zemlja"],
                            "telefon": form_data["telefon"],
                            "email": form_data["email"],
                            "kontakt": form_data["kontakt"],
                            "pdv_broj": form_data["pdv"],
                            "maticni": form_data["maticni"],
                        })
                        if success:
                            self._load_uvoznici_data()
                    elif self.current_category == "Carinske tarife":
                        success = self.service.add_trgovacki_naziv(
                            form_data["tarifni_kod"],
                            form_data["naziv_robe"],
                        )
                        if success:
                            self._load_trgovacki_nazivi_data()
                    elif self.current_category == "Carinarnice":
                        if (
                            self.is_editing
                            and hasattr(self, "current_tree_item")
                            and self.current_tree_item
                            and self.current_tree_item.parent()
                        ):
                            # Update existing customs post
                            success = self.service.update_carinarnica(
                                form_data["sifra"],
                                form_data["naziv"],
                            )
                        else:
                            # Insert new customs post
                            success = self.service.add_carinarnica(
                                form_data["sifra"],
                                form_data["naziv"],
                            )
                        if success:
                            self._load_carinarnice_data()

                # Clear form
                self._clear_form()

                QMessageBox.information(self, "Uspeh", "Podaci uspješno sačuvani.")

                # Mark as dirty
                if self.on_dirty:
                    self.on_dirty()

                # Return to readonly mode after saving
                self._set_readonly_mode(readonly=True)

            except Exception as e:
                if self.current_category == "Pošiljaoci":
                    error_msg = f"Greška pri čuvanju pošiljaoca:\n{str(e)}"
                elif self.current_category == "Carinske tarife":
                    error_msg = f"Greška pri čuvanju carinske tarife:\n{str(e)}"
                else:
                    error_msg = f"Greška pri čuvanju uvoznika:\n{str(e)}"
                QMessageBox.critical(self, "Greška", error_msg)
        else:
            # Original implementation for other categories
            if hasattr(super(), "_on_snimi"):
                super()._on_snimi()

    def _on_row_selected(self):
        """Row selected → populate detail form + enable buttons"""
        try:
            current_row = self.table.currentRow()

            if current_row < 0:
                self.btn_uredi.setEnabled(False)
                self.btn_obrisi.setEnabled(False)
                logger.debug("Nijedan red nije selektovan")
                return

            # Za Inspekcijska pravila / Inkoterms — read-only, bez CRUD dugmadi
            if self.current_category == "Inspekcijska pravila":
                self._on_inspekcijska_row_selected()
                return
            if self.current_category == "Inkoterms":
                return

            self.btn_uredi.setEnabled(True)
            self.btn_obrisi.setEnabled(True)
            self.current_row_index = current_row

            # Populate fields for Pošiljaoci and Uvoznici
            if self.current_category in ["Pošiljaoci", "Uvoznici"] and hasattr(
                self, "jib_field"
            ):
                try:
                    # Col 0 = PDV (12 cifara); JIB (13 cifara) = "4" + PDV
                    jib_item = self.table.item(current_row, 0)
                    pdv_val = jib_item.text() if jib_item else ""
                    self.jib_field.setText(pdv_val)  # PDV (12 cifara) u headeru

                    for col, field in [
                        (1, self.naziv_field),
                        (2, self.adresa_field),
                        (3, self.grad_field),
                        (4, self.zemlja_field),
                    ]:
                        item = self.table.item(current_row, col)
                        field.setText(item.text() if item else "")

                    # Desni panel JIB = "4" + PDV (13 cifara)
                    if hasattr(self, "pdv_field"):
                        self.pdv_field.setText("4" + pdv_val if pdv_val else "")

                    # Dohvati dodatna polja iz baze preko Service layer-a
                    jib_val = pdv_val
                    if self.current_category == "Pošiljaoci":
                        results = self.service.load_posiljaoci_data(jib_val)
                    else:
                        results = self.service.load_uvoznici_data(jib_val)
                    db_row = results[0] if results else None
                    if db_row:
                        telefon = db_row.get("telefon", "")
                        email = db_row.get("email", "")
                        kontakt = db_row.get("kontakt", "")
                        pdv_broj = db_row.get("pdv_broj", "")
                        maticni = db_row.get("maticni", "")
                        self.telefon_field.setText(str(telefon) if telefon else "")
                        self.email_field.setText(str(email) if email else "")
                        self.kontakt_field.setText(str(kontakt) if kontakt else "")
                        self.pdv_field.setText(str(pdv_broj) if pdv_broj else "")
                        self.maticni_field.setText(str(maticni) if maticni else "")

                    logger.debug(f"Popunjeni vidljivi podaci za red {current_row}")
                except Exception as e:
                    logger.error(f"Greška pri popunjavanju forme: {str(e)}")
            # Populate fields for Carinske tarife
            elif self.current_category == "Carinske tarife" and hasattr(
                self, "tarifni_kod_field"
            ):
                try:
                    kod_item = self.table.item(current_row, 0)
                    naziv_item = self.table.item(current_row, 1)

                    if kod_item:
                        # U originalnom polju sačuvaj neformatiranu vrednost
                        original_kod = (
                            self.table.item(current_row, 0).text().replace(" ", "")
                        )
                        # Formatiraj kod za prikaz u formi
                        formatted_kod = self.format_tarifni_kod(original_kod)
                        self.tarifni_kod_field.setText(formatted_kod)
                    if naziv_item:
                        self.naziv_robe_field.setText(naziv_item.text())

                    logger.debug(
                        f"Popunjeni podaci za carinsku tarifu u redu {current_row}"
                    )
                except Exception as e:
                    logger.error(f"Greška pri popunjavanju forme: {str(e)}")
            # Populate fields for Carinarnice (when using tree widget)
            elif self.current_category == "Carinarnice" and hasattr(
                self, "sifra_field"
            ):
                try:
                    # For tree widget, get the selected item
                    if hasattr(self, "tree_widget") and self.table == self.tree_widget:
                        selected_items = self.tree_widget.selectedItems()
                        if selected_items:
                            item = selected_items[0]
                            # Only populate if it's a customs post (child item), not a regional center (parent item)
                            if item.parent():  # It's a customs post
                                sifra = item.text(0)
                                naziv = item.text(1)

                                self.sifra_field.setText(sifra)
                                self.naziv_field.setText(naziv)

                                logger.debug(
                                    f"Popunjeni podaci za carinsku ispostavu: {sifra} - {naziv}"
                                )
                            else:  # It's a regional center - disable edit buttons
                                logger.debug(
                                    "Selektovan regionalni centar (nema akcija za uređivanje)"
                                )
                                self.btn_uredi.setEnabled(False)
                                self.btn_obrisi.setEnabled(False)
                                return
                    else:
                        # For regular table
                        sifra_item = self.table.item(current_row, 0)
                        naziv_item = self.table.item(current_row, 1)

                        if sifra_item:
                            self.sifra_field.setText(sifra_item.text())
                        if naziv_item:
                            self.naziv_field.setText(naziv_item.text())

                        logger.debug(
                            f"Popunjeni podaci za carinarnicu u redu {current_row}"
                        )
                except Exception as e:
                    logger.error(f"Greška pri popunjavanju forme: {str(e)}")

            # Update pager
            self._update_pager()

        except Exception as e:
            logger.error(f"Greška pri selekciji reda: {str(e)}")

    # ============================================================
    # BaseTabView interface
    # ============================================================

    def get_data(self) -> Dict[str, Any]:
        """Vraća podatke iz view-a (BaseTabView interface)."""
        return {}

    def set_data(self, data: Dict[str, Any]) -> None:
        """Postavlja podatke u view (BaseTabView interface)."""
        pass

    def clear_form(self) -> None:
        """Čisti formu (BaseTabView interface) - delegira na _clear_form."""
        self._clear_form()


# Test standalone
if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)

    window = QMainWindow()
    window.setWindowTitle("Šifrarnici - Deklarant Pro")
    window.setGeometry(50, 50, 1400, 900)

    # Apply global style
    app.setStyle("Fusion")

    tab = SifarniciTab()
    window.setCentralWidget(tab)

    window.show()
    sys.exit(app.exec())
