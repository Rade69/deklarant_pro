# gui/tabs/sifarnici_tab.py
import logging
import re

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
from PySide6.QtCore import Qt, Signal, QSize
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
from database.db import (
    get_izvoznik_by_jib,
    search_izvoznike,
    get_partner_by_jib,
    search_partnere,
    get_connection_pool,
)

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


@dataclass
class ValidationRule:
    """Pravila za validaciju"""

    field_name: str
    is_required: bool = True
    min_length: int = 0
    max_length: int = 255


class DatabaseManager:
    """Centralizovani menadžer za database konekcije sa connection pooling-om

    Obezbeđuje:
    - Connection pooling za efikasno korišćenje konekcija
    - Transaction management
    - Error handling
    - Logging
    """

    # Class-level connection pool
    _connection_pool = None

    @classmethod
    def get_pool(cls):
        """Kreira i vraća connection pool (lazy initialization)

        Returns:
            psycopg2.pool.SimpleConnectionPool or None
        """
        if cls._connection_pool is None:
            try:
                cls._connection_pool = get_connection_pool()
                logger.info("Connection pool uspešno kreiran")
            except Exception as e:
                logger.error(f"Greška pri kreiranju connection pool-a: {str(e)}")
                raise
        return cls._connection_pool

    @classmethod
    def get_connection(cls):
        """Kreira i vraća database konekciju iz pool-a

        Returns:
            psycopg2 connection object

        Raises:
            Exception: Ako konekcija ne uspe
        """
        try:
            pool = cls.get_pool()
            if pool:
                conn = pool.getconn()
                logger.debug("Database konekcija dobijena iz pool-a")
                return conn
            # Fallback ako pool nije kreiran — direktna konekcija (bez pooling-a)
            from config.settings import get_db_settings
            import psycopg2
            from psycopg2.extras import RealDictCursor
            s = get_db_settings()
            conn = psycopg2.connect(
                host=s.host, port=s.port, database=s.database,
                user=s.user, password=s.password, cursor_factory=RealDictCursor
            )
            logger.debug("Database konekcija uspostavljena (fallback direktna)")
            return conn
        except Exception as e:
            logger.error(f"Greška pri dobijanju database konekcije: {str(e)}")
            raise Exception(f"Neuspešna database konekcija: {str(e)}")

    @classmethod
    def return_connection(cls, conn):
        """Vraća konekciju nazad u pool

        Args:
            conn: psycopg2 connection object za vraćanje
        """
        try:
            if cls._connection_pool:
                cls._connection_pool.putconn(conn)
                logger.debug("Database konekcija vraćena u pool")
            else:
                conn.close()
                logger.debug("Database konekcija zatvorena (nema pool-a)")
        except Exception as e:
            logger.error(f"Greška pri vraćanju konekcije: {str(e)}")

    @staticmethod
    def execute_query(
        query: str, params: Optional[Tuple] = None, fetch_all: bool = False
    ) -> Union[List[Tuple], Tuple, None]:
        """Izvršava SQL SELECT query i vraća rezultate

        Args:
            query: SQL query string
            params: Parametri za query (opciono)
            fetch_all: Ako je True vraća sve redove, inače samo prvi

        Returns:
            Query rezultati kao TUPLE (indeks pristup)
        """
        conn = None
        try:
            conn = DatabaseManager.get_connection()
            with conn.cursor() as cur:
                cur.execute(query, params or ())
                if fetch_all:
                    result = cur.fetchall()
                    # Convert dict rows to tuples for backward compatibility
                    if result and isinstance(result[0], dict):
                        result = [tuple(row.values()) for row in result]
                    logger.debug(f"Query vraća {len(result)} redova")
                    return result
                result = cur.fetchone()
                # Convert dict row to tuple for backward compatibility
                if result and isinstance(result, dict):
                    result = tuple(result.values())
                logger.debug("Query vraća jedan red")
                return result
        except Exception as e:
            logger.error(f"Database query error: {str(e)}")
            raise Exception(f"Database query error: {str(e)}")
        finally:
            if conn:
                DatabaseManager.return_connection(conn)

    @staticmethod
    def execute_update(query: str, params: Optional[Tuple] = None) -> bool:
        """Izvršava UPDATE/INSERT/DELETE operacije

        Args:
            query: SQL query string
            params: Parametri za query (opciono)

        Returns:
            True ako operacija uspe

        Raises:
            Exception: Ako update ne uspe
        """
        conn = None
        try:
            conn = DatabaseManager.get_connection()
            with conn.cursor() as cur:
                cur.execute(query, params or ())
                conn.commit()
                logger.info("Database update uspešan")
                return True
        except Exception as e:
            logger.error(f"Database update error: {str(e)}")
            raise Exception(f"Database update error: {str(e)}")
        finally:
            if conn:
                DatabaseManager.return_connection(conn)


class FormValidator:
    """Validator za form fields sa fleksibilnim pravilima"""

    @staticmethod
    def validate_required_fields(fields_dict: Dict[str, str]) -> List[str]:
        """Validira obavezna polja

        Args:
            fields_dict: Dictionary gde key je ime polja, value je vrednost

        Returns:
            Lista imena polja koja nedostaju
        """
        missing_fields = []
        for field_name, field_value in fields_dict.items():
            if not field_value or not field_value.strip():
                missing_fields.append(field_name)
        return missing_fields

    @staticmethod
    def validate_with_rules(
        data: Dict[str, str], rules: List[ValidationRule]
    ) -> Dict[str, List[str]]:
        """Validira podatke prema definisanim pravilima

        Args:
            data: Podaci za validaciju
            rules: Lista validacionih pravila

        Returns:
            Dictionary sa greškama po poljima
        """
        errors = {}
        for rule in rules:
            value = data.get(rule.field_name, "")

            field_errors = []

            # Required field check
            if rule.is_required and (not value or not value.strip()):
                field_errors.append(f"{rule.field_name} je obavezno polje")

            # Length checks
            if value:
                if len(value) < rule.min_length:
                    field_errors.append(
                        f"{rule.field_name} mora imati najmanje {rule.min_length} karaktera"
                    )
                if len(value) > rule.max_length:
                    field_errors.append(
                        f"{rule.field_name} može imati najviše {rule.max_length} karaktera"
                    )

            if field_errors:
                errors[rule.field_name] = field_errors

        return errors

    @staticmethod
    def sanitize_input(text: str) -> str:
        """Čisti i sanitizuje input tekst

        Args:
            text: Input tekst za sanitizaciju

        Returns:
            Očišćeni tekst
        """
        if not text:
            return ""
        return text.strip()


class UIHelper:
    """Helper klase za UI komponente sa stilizacijom"""

    # Mapiranje style_class → objectName (unified_color_system.qss paleta)
    BUTTON_OBJECT_NAMES = {
        "primary": "",               # default plava (base QPushButton) → Uredi
        "success": "btnDodaj",       # zelena → Novi
        "danger":  "btnObrisi",      # crvena → Obriši
        "default": "btnSnimi",       # zelena → Snimi
    }

    @classmethod
    def create_styled_button(
        cls, text: str, style_class: str = "default", icon_name: str = ""
    ) -> QPushButton:
        """Kreira stilizovano dugme

        Args:
            text: Tekst na dugmetu
            style_class: Stil klase (primary, success, danger, default)
            icon_name: QtAwesome ime ikone (opcionalno)

        Returns:
            QPushButton instanca
        """
        btn_text = (" " + text) if icon_name else text
        button = QPushButton(btn_text)
        button.setObjectName(cls.BUTTON_OBJECT_NAMES.get(style_class, ""))

        if icon_name and QTAWESOME_AVAILABLE:
            try:
                qta_icon = qta.icon(icon_name, color="#FFFFFF")
                pixmap = qta_icon.pixmap(QSize(16, 16))
                button.setIcon(QIcon(pixmap))
                button.setIconSize(QSize(16, 16))
            except Exception:
                pass

        return button

    @classmethod
    def create_action_buttons(
        cls, parent, edit_callback: Callable, delete_callback: Callable
    ) -> QWidget:
        """Kreira akciona dugmad za tabelu

        Args:
            parent: Parent widget
            edit_callback: Callback za edit akciju
            delete_callback: Callback za delete akciju

        Returns:
            QWidget sa akcionim dugmadima
        """
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
        btn_edit.clicked.connect(edit_callback)

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
        btn_delete.clicked.connect(delete_callback)

        layout.addWidget(btn_edit)
        layout.addWidget(btn_delete)
        layout.addStretch()

        return widget


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
        self._editing_jib = ""  # Čuva stari jib pri editovanju (za WHERE uslov u UPDATE)
        self.db_manager = DatabaseManager()
        self.validator = FormValidator()
        self.ui_helper = UIHelper()

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
            ("fa5s.list-alt",    "Carinske tarife",   "Carinske tarife"),
            ("fa5s.paper-plane", "Pošiljaoci",         "Pošiljaoci"),
            ("fa5s.truck",       "Uvoznici",           "Uvoznici"),
            ("fa5s.id-card",     "Deklaranti",         "Deklaranti"),
            ("fa5s.landmark",    "Carinarnice",        "Carinarnice"),
            ("fa5s.cogs",        "Carinski postupci",  "Carinski postupci"),
            ("fa5s.globe",       "Zemlje",             "Zemlje"),
        ]
        fallback_emojis = ["📦", "📤", "📥", "💼", "🏛", "⚙️", "🌐"]

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

            layout.addWidget(content)

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
                    if hasattr(field, "clear"):
                        field.clear()

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

            # Clear detail panel
            self._clear_detail_panel()

            # VAŽNO: Reset table to QTableWidget before setting up new category
            # (in case we came from Carinarnice which uses QTreeWidget)
            self._restore_table_widget()

            # Setup per category
            setup_methods = {
                "Pošiljaoci": self._setup_posiljaoci,
                "Carinske tarife": self._setup_trgovacki_nazivi,
                "Uvoznici": self._setup_uvoznici,
                "Deklaranti": self._setup_deklaranti,
                "Carinarnice": self._setup_carinarnice,
                "Carinski postupci": self._setup_carinski_postupci,
            }

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

    def _build_partner_form_strip(self, show_jib: bool = False) -> QWidget:
        """
        Kreira kompaktni info-strip za pošiljaoca/uvoznika.

        Layout:
          ┌ Header ──────────────────────────────────────────┐
          │  JIB: [_______]   Naziv: [_____________________] │
          ├──────────────────────────────┬───────────────────┤
          │  Adresa: [________________] │ Telefon: [_______] │
          │  Grad:   [________] PTT:[__] │ Email:   [_______] │
          │  Zemlja: [________________] │ PDV:     [_______] │
          │                             │ Matični: [_______] │
          │                             │ Kontakt: [_______] │
          └─────────────────────────────┴───────────────────┘
        """
        _FIELD = (
            "QLineEdit { background: white; border: 1px solid #c8cdd4; "
            "border-radius: 3px; padding: 4px 7px; font-size: 12px; }"
            "QLineEdit:focus { border: 1px solid #2196F3; }"
            "QLineEdit:read-only { background: #f5f5f5; color: #555; }"
        )
        _LBL = "color: #4a5568; font-size: 12px; font-weight: bold;"

        # Outer strip — bordered card (WA_StyledBackground omogućava rendering)
        strip = QWidget()
        strip.setObjectName("partner_strip")
        strip.setAttribute(Qt.WA_StyledBackground, True)
        strip.setStyleSheet(
            "QWidget#partner_strip { border: 1px solid #c8cdd4; "
            "border-radius: 4px; background: white; }"
        )
        outer = QVBoxLayout(strip)
        outer.setSpacing(0)
        outer.setContentsMargins(1, 1, 1, 1)  # prostor za border

        # ── Header row: Naziv ────────────────────────────────────────────
        header = QWidget()
        header.setObjectName("strip_header")
        header.setStyleSheet(
            "QWidget#strip_header { background: #eef2f7; "
            "border-bottom: 1px solid #d0d5db; }"
        )
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(14, 9, 14, 9)
        h_layout.setSpacing(6)

        self.jib_field = QLineEdit()
        self.jib_field.setFixedWidth(175)
        self.jib_field.setStyleSheet(_FIELD)
        self.jib_field.setPlaceholderText("JIB broj")

        lbl_naziv = QLabel("Naziv:")
        lbl_naziv.setStyleSheet(_LBL)
        lbl_naziv.setFixedWidth(44)
        self.naziv_field = QLineEdit()
        self.naziv_field.setStyleSheet(_FIELD)
        self.naziv_field.setPlaceholderText("Naziv firme")

        if show_jib:
            lbl_jib = QLabel("JIB:")
            lbl_jib.setStyleSheet(_LBL)
            lbl_jib.setFixedWidth(32)
            h_layout.addWidget(lbl_jib)
            h_layout.addWidget(self.jib_field)
            h_layout.addSpacing(18)

        h_layout.addWidget(lbl_naziv)
        h_layout.addWidget(self.naziv_field, 1)
        outer.addWidget(header)

        # ── Body row: Adresa | separator | Kontakt ───────────────────────
        body = QWidget()
        body.setStyleSheet("background: white;")
        b_layout = QHBoxLayout(body)
        b_layout.setSpacing(0)
        b_layout.setContentsMargins(0, 0, 0, 0)

        # Left panel – Adresa
        left = QWidget()
        left.setStyleSheet("QLabel { color: #4a5568; font-size: 12px; }")
        lf = QFormLayout(left)
        lf.setContentsMargins(14, 10, 14, 10)
        lf.setSpacing(9)
        lf.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.adresa_field = QLineEdit()
        self.adresa_field.setStyleSheet(_FIELD)

        grad_row = QWidget()
        gr_lay = QHBoxLayout(grad_row)
        gr_lay.setContentsMargins(0, 0, 0, 0)
        gr_lay.setSpacing(6)
        self.grad_field = QLineEdit()
        self.grad_field.setStyleSheet(_FIELD)
        ptt_lbl = QLabel("PTT:")
        ptt_lbl.setFixedWidth(30)
        ptt_lbl.setStyleSheet("color: #666; font-size: 11px;")
        self.postanski_broj_field = QLineEdit()
        self.postanski_broj_field.setFixedWidth(68)
        self.postanski_broj_field.setStyleSheet(_FIELD)
        gr_lay.addWidget(self.grad_field, 2)
        gr_lay.addWidget(ptt_lbl)
        gr_lay.addWidget(self.postanski_broj_field)

        self.zemlja_field = QLineEdit()
        self.zemlja_field.setStyleSheet(_FIELD)

        lf.addRow("Adresa:", self.adresa_field)
        lf.addRow("Grad:", grad_row)
        lf.addRow("Zemlja:", self.zemlja_field)

        # Vertical separator
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFixedWidth(1)
        sep.setStyleSheet("background: #d0d5db;")

        # Right panel – Kontakt & Ostalo
        right = QWidget()
        right.setStyleSheet("QLabel { color: #4a5568; font-size: 12px; }")
        rf = QFormLayout(right)
        rf.setContentsMargins(14, 10, 14, 10)
        rf.setSpacing(9)
        rf.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.telefon_field = QLineEdit()
        self.telefon_field.setStyleSheet(_FIELD)
        self.email_field = QLineEdit()
        self.email_field.setStyleSheet(_FIELD)
        # pdv_field i maticni_field ostaju kao interni (skriveni) — nisu u layoutu
        self.pdv_field = QLineEdit()
        self.maticni_field = QLineEdit()
        self.kontakt_field = QLineEdit()
        self.kontakt_field.setStyleSheet(_FIELD)

        rf.addRow("Telefon:", self.telefon_field)
        rf.addRow("Email:", self.email_field)
        rf.addRow("Kontakt:", self.kontakt_field)

        b_layout.addWidget(left, 6)
        b_layout.addWidget(sep)
        b_layout.addWidget(right, 4)
        outer.addWidget(body)

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
            strip = self._build_partner_form_strip(show_jib=True)
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
            self.tree_widget.setHeaderLabels(
                ["Šifra", "Naziv"]
            )  # Uklonjena Akcije kolona

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
                self._load_not_implemented("Deklaranti")
            elif self.current_category == "Carinarnice":
                self._load_carinarnice_data()
            elif self.current_category == "Carinski postupci":
                self._load_carinski_postupci_data()
            elif self.current_category == "Zemlje":
                self._load_zemlje_data()
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
        """Load data from catalogs.uvoznici table using generic method"""
        try:
            logger.info("Učitavanje podataka o uvoznicima iz baze")

            self._load_data_generic(
                table_name="catalogs.uvoznici",
                columns=[
                    "jib",
                    "naziv",
                    "adresa",
                    "grad",
                    "drzava",
                    "telefon",
                    "email",
                    "kontakt",
                    "pdv_broj",
                    "maticni",
                ],
                order_by="naziv",
                add_actions=False,
            )

            logger.info("Uspešno učitano uvoznici")
        except Exception as e:
            logger.error(f"Greška pri učitavanju uvoznika: {str(e)}")
            QMessageBox.critical(
                self, "Greška", f"Greška pri učitavanju uvoznika:\n{str(e)}"
            )

    def _load_posiljaoci_data(self):
        """Load data from catalogs.izvoznici table using generic method"""
        try:
            logger.info("Učitavanje podataka o pošiljaocima iz baze")

            self._load_data_generic(
                table_name="catalogs.izvoznici",
                columns=[
                    "jib",
                    "naziv",
                    "adresa",
                    "grad",
                    "drzava",
                    "telefon",
                    "email",
                    "kontakt",
                    "pdv_broj",
                    "maticni",
                ],
                order_by="naziv",
                add_actions=False,
            )

            logger.info("Uspešno učitano pošiljaoci")
        except Exception as e:
            logger.error(f"Greška pri učitavanju pošiljalaca: {str(e)}")
            QMessageBox.critical(
                self, "Greška", f"Greška pri učitavanju pošiljalaca:\n{str(e)}"
            )

    def _load_trgovacki_nazivi_data(self):
        """Load Trgovački nazivi data — hijerarhijski prikaz za brojeve"""
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
                # Hijerarhijski drill-down iz SQLite tarifa_2026
                import sqlite3 as _sqlite3
                import os as _os
                _DB = _os.path.normpath(_os.path.join(
                    _os.path.dirname(__file__), '..', '..', 'database', 'asycuda_sistem.db'
                ))

                prefix = search_text.replace(' ', '').replace('.', '')

                # Dohvati traženi čvor i SVE potomke koji počinju tim prefiksom
                _conn = _sqlite3.connect(_DB)
                _conn.row_factory = _sqlite3.Row

                root_row = _conn.execute(
                    "SELECT kod, naziv, stopa_uvozna, nivo FROM tarifa_2026 WHERE kod = ?",
                    (prefix,)
                ).fetchone()

                # Svi potomci sortirani po kodu (max 300)
                desc_rows = _conn.execute(
                    "SELECT kod, naziv, stopa_uvozna, nivo FROM tarifa_2026 "
                    "WHERE kod LIKE ? AND kod != ? ORDER BY kod LIMIT 300",
                    (prefix + '%', prefix)
                ).fetchall()
                _conn.close()

                # Nivo → oznaka i indentacija po dužini koda
                _nivo_ikona = {
                    'glava': '📂',
                    'podglava': '📁',
                    'tarifni_broj': '📋',
                    'podbroj': '📄',
                }
                prefix_len = len(prefix)

                def _indent(kod):
                    extra = len(kod) - prefix_len
                    # Svaka 2 cifre = jedan nivo dublje
                    return '  ' * max(0, extra // 2)

                rows_to_show = []
                if root_row:
                    rows_to_show.append((root_row['kod'], root_row['naziv'],
                                         root_row['stopa_uvozna'], root_row['nivo'], True))
                for r in desc_rows:
                    rows_to_show.append((r['kod'], r['naziv'],
                                         r['stopa_uvozna'], r['nivo'], False))

                self.table.setRowCount(len(rows_to_show))
                for i, (kod, naziv, stopa, nivo, is_root) in enumerate(rows_to_show):
                    ikona = _nivo_ikona.get(nivo, '•')
                    indent = '' if is_root else _indent(kod)
                    stopa_str = ''
                    if stopa:
                        stopa_str = stopa if str(stopa).endswith('%') else str(stopa) + '%'

                    item_kod = QTableWidgetItem(indent + ikona + ' ' + kod)
                    item_naziv = QTableWidgetItem(naziv or '')
                    if stopa_str:
                        item_naziv.setToolTip(f"Stopa uvozna: {stopa_str}")

                    if is_root:
                        font = item_kod.font()
                        font.setBold(True)
                        item_kod.setFont(font)
                        item_naziv.setFont(font)

                    self.table.setItem(i, 0, item_kod)
                    self.table.setItem(i, 1, item_naziv)
                self.table.setColumnWidth(0, 200)
            else:
                # Obična pretraga — kao prije
                self._load_data_generic(
                    table_name="catalogs.zvanicna_tarifa",
                    columns=["tarifni_kod", "opis"],
                    order_by="tarifni_kod",
                    format_fn=_clean_tariff_opis,
                    max_rows=20000,
                    add_actions=False,
                )

            logger.info("Uspešno učitano trgovački nazivi")
        except Exception as e:
            logger.error(f"Greška pri učitavanju tarifnih naziva robe: {str(e)}")
            raise

    def _load_data_generic(
        self,
        table_name: str,
        columns: List[str],
        order_by: str = "naziv",
        format_fn: Optional[Callable[[str], str]] = None,
        max_rows: int = 5000,
        add_actions: bool = True,
    ):
        """Generičko učitavanje podataka za sve kategorije

        Args:
            table_name: Ime tabele u bazi
            columns: Lista kolona za SELECT
            order_by: Redosled sortiranja
            format_fn: Optional funkcija za formatiranje vrednosti
            max_rows: Maksimalni broj redova za učitavanje
            add_actions: Da li da doda kolonu za akcije (default True)
        """
        try:
            logger.info(f"Učitavanje podataka iz {table_name}")

            results = (
                self.db_manager.execute_query(
                    f"SELECT {', '.join(columns)} FROM {table_name} ORDER BY {order_by}",
                    fetch_all=True,
                )
                or []
            )

            logger.info(f"Pronađeno {len(results)} zapisa za učitavanje")

            # Performance: disable sorting/updates while filling
            self.table.setSortingEnabled(False)
            self.table.setUpdatesEnabled(False)

            # Limit the number of rows to prevent freezing for large datasets
            actual_rows = min(len(results), max_rows)
            self.table.setRowCount(actual_rows)

            # Process all rows efficiently
            for row in range(actual_rows):
                row_data = results[row]
                for col, value in enumerate(row_data):
                    formatted_value = format_fn(value) if format_fn else value
                    self.table.setItem(
                        row, col, QTableWidgetItem(str(formatted_value or ""))
                    )

                # Add action buttons (using text instead of widgets to avoid freezing)
                if add_actions and len(columns) < self.table.columnCount():
                    item_actions = QTableWidgetItem("✏️  🗑️")
                    item_actions.setTextAlignment(Qt.AlignCenter)
                    item_actions.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    self.table.setItem(row, len(columns), item_actions)

            self.table.setUpdatesEnabled(True)
            self.table.setSortingEnabled(True)

            # Final refresh
            self.table.viewport().update()
            QApplication.processEvents()

            logger.info(f"Uspešno učitano {actual_rows} od {len(results)} zapisa")

            try:
                self._update_status()
            except Exception:
                pass
            try:
                self._update_pager()
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Greška pri učitavanju podataka: {str(e)}")
            raise

    def _load_carinarnice_data(self):
        """Load Carinarnice data from catalogs.carinske_ispostave table (hierarchical view)."""
        try:
            logger.info(
                "Učitavanje podataka o carinarnicama iz baze (hijerarhijski prikaz)"
            )

            # Load all regional centers and their customs posts from database
            query = """
                SELECT rc.id as rc_id, rc.sifra as rc_sifra, rc.naziv as rc_naziv,
                       ci.sifra as ci_sifra, ci.naziv as ci_naziv
                FROM catalogs.regionalni_centri rc
                LEFT JOIN catalogs.carinske_ispostave ci ON rc.id = ci.regionalni_centar_id
                ORDER BY rc.sifra, ci.sifra
            """

            result = self.db_manager.execute_query(query, fetch_all=True) or []

            logger.info(f"Pronađeno {len(result)} zapisa za prikaz")

            # Clear existing items
            self.table.clear()

            # Create a dictionary to group customs posts by regional center
            regional_centers = {}
            for row_data in result:
                rc_id = row_data[0]
                rc_sifra = row_data[1]
                rc_naziv = row_data[2]
                ci_sifra = row_data[3]
                ci_naziv = row_data[4]

                if rc_id not in regional_centers:
                    regional_centers[rc_id] = {
                        "sifra": rc_sifra,
                        "naziv": rc_naziv,
                        "ispostave": [],
                    }

                if ci_sifra and ci_naziv:  # Only add if customs post exists
                    regional_centers[rc_id]["ispostave"].append((ci_sifra, ci_naziv))

            # Add regional centers and their customs posts to the tree
            for rc_id, rc_data in regional_centers.items():
                # Create top-level item for regional center
                rc_item = QTreeWidgetItem(self.table)
                rc_item.setText(0, str(rc_data["sifra"] or ""))
                rc_item.setText(1, str(rc_data["naziv"] or ""))
                rc_item.setText(2, "")  # No actions for regional center

                # Make regional center item bold
                font = rc_item.font(0)
                font.setBold(True)
                rc_item.setFont(0, font)
                rc_item.setFont(1, font)

                # Add child items for each customs post under this regional center
                for ci_sifra, ci_naziv in rc_data["ispostave"]:
                    ci_item = QTreeWidgetItem(rc_item)
                    ci_item.setText(0, str(ci_sifra or ""))
                    ci_item.setText(1, str(ci_naziv or ""))

                    # Nema više kolone za akcije - samo prikazujemo podatke

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
        """Load Carinski postupci data from catalogs.carinski_postupci table."""
        try:
            logger.info("Učitavanje carinskih postupaka iz baze")

            # Query from database
            query = """
                SELECT sifra, opis, vrsta, oznaka
                FROM catalogs.carinski_postupci
                ORDER BY sifra
            """

            result = self.db_manager.execute_query(query, fetch_all=True) or []

            logger.info(f"Pronađeno {len(result)} carinskih postupaka")

            # Clear table
            self.table.setRowCount(0)

            # Populate table
            for row_data in result:
                row = self.table.rowCount()
                self.table.insertRow(row)

                # sifra (Šifra)
                sifra_item = QTableWidgetItem(str(row_data[0] or ""))
                sifra_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, 0, sifra_item)

                # opis (Postupak)
                postupak_item = QTableWidgetItem(str(row_data[1] or ""))
                self.table.setItem(row, 1, postupak_item)

                # vrsta (Vrsta)
                vrsta_item = QTableWidgetItem(str(row_data[2] or ""))
                vrsta_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, 2, vrsta_item)

                # oznaka (Oznaka)
                oznaka_item = QTableWidgetItem(str(row_data[3] or ""))
                oznaka_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, 3, oznaka_item)

            # Update status
            try:
                self._update_status()
            except Exception:
                pass
            try:
                self._update_pager()
            except Exception:
                pass

            logger.info(f"Uspešno učitano {len(result)} carinskih postupaka")

        except Exception as e:
            logger.error(f"Greška pri učitavanju carinskih postupaka: {str(e)}")
            raise

    def _load_zemlje_data(self):
        """Load Zemlje data from catalogs.drzave table."""
        try:
            logger.info("Učitavanje zemalja iz baze")

            # Query from database
            query = """
                SELECT sifra, naziv
                FROM catalogs.drzave
                ORDER BY sifra
            """

            result = self.db_manager.execute_query(query, fetch_all=True) or []

            logger.info(f"Pronađeno {len(result)} zemalja")

            # Clear table
            self.table.setRowCount(0)

            # Populate table
            for row_data in result:
                row = self.table.rowCount()
                self.table.insertRow(row)

                # sifra (Šifra)
                sifra_item = QTableWidgetItem(str(row_data[0] or ""))
                sifra_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, 0, sifra_item)

                # naziv (Naziv)
                naziv_item = QTableWidgetItem(str(row_data[1] or ""))
                self.table.setItem(row, 1, naziv_item)

            # Update status
            try:
                self._update_status()
            except Exception:
                pass
            try:
                self._update_pager()
            except Exception:
                pass

            logger.info(f"Uspešno učitano {len(result)} zemalja")

        except Exception as e:
            logger.error(f"Greška pri učitavanju zemalja: {str(e)}")
            raise

    def _search_zemlje(self, query: str):
        """Search zemlje in database using ILIKE - like Pošiljaoci"""
        try:
            logger.info(f"Pretraga zemalja sa query-jem: '{query}'")

            # Sanitize search query
            clean_query = self.validator.sanitize_input(query)

            # Clear existing data
            self.table.setRowCount(0)

            # Query with ILIKE for case-insensitive search
            if clean_query:
                result = self.db_manager.execute_query(
                    """SELECT sifra, naziv 
                       FROM catalogs.drzave 
                       WHERE sifra ILIKE %s OR naziv ILIKE %s
                       ORDER BY sifra""",
                    (f"{clean_query}%", f"{clean_query}%"),
                    fetch_all=True,
                )
                logger.info(f"Pronađeno {len(result)} rezultata za pretragu")
            else:
                # If empty query, load all
                result = self.db_manager.execute_query(
                    "SELECT sifra, naziv FROM catalogs.drzave ORDER BY sifra",
                    fetch_all=True,
                )
                logger.info(f"Učitano svih {len(result)} zemalja")

            result = result or []

            # Populate table
            for row_data in result:
                row = self.table.rowCount()
                self.table.insertRow(row)

                # sifra (Šifra)
                sifra_item = QTableWidgetItem(str(row_data[0] or ""))
                sifra_item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, 0, sifra_item)

                # naziv (Naziv)
                naziv_item = QTableWidgetItem(str(row_data[1] or ""))
                self.table.setItem(row, 1, naziv_item)

            # Update status
            try:
                self._update_status()
            except Exception:
                pass
            try:
                self._update_pager()
            except Exception:
                pass

            logger.info(f"Uspešno učitano {len(result)} zemalja")

        except Exception as e:
            logger.error(f"Greška pri pretrazi zemalja: {str(e)}")
            raise

    def _search_generic(
        self,
        query: str,
        table_name: str,
        columns: List[str],
        search_columns: List[str],
        order_by: str = "naziv",
        format_fn: Optional[Callable[[str], str]] = None,
        add_actions: bool = True,
    ):
        """Generička pretraga za sve kategorije

        Args:
            query: Pretraga tekst
            table_name: Ime tabele u bazi
            columns: Lista kolona za SELECT
            search_columns: Lista kolona za WHERE ILIKE
            order_by: Redosled sortiranja
            format_fn: Optional funkcija za formatiranje vrednosti (npr. format_tarifni_kod)
            add_actions: Da li da doda kolonu za akcije (default True)
        """
        try:
            logger.info(f"Pretraga {table_name} sa query-jem: '{query}'")

            clean_query = self.validator.sanitize_input(query)
            self.table.setRowCount(0)

            # Izgradi WHERE deo query-ja
            if clean_query:
                where_parts = [f"{col} ILIKE %s" for col in search_columns]
                where_clause = " OR ".join(where_parts)
                params = tuple(f"%{clean_query}%" for _ in search_columns)
                query_str = f"SELECT {', '.join(columns)} FROM {table_name} WHERE {where_clause} ORDER BY {order_by}"
            else:
                query_str = (
                    f"SELECT {', '.join(columns)} FROM {table_name} ORDER BY {order_by}"
                )
                params = ()

            results = (
                self.db_manager.execute_query(query_str, params, fetch_all=True) or []
            )
            logger.info(f"Pronađeno {len(results)} rezultata za pretragu")

            if not results:
                logger.info("Nema rezultata za datu pretragu")
                self.table.setRowCount(1)
                self.table.setItem(0, 0, QTableWidgetItem("Nema rezultata"))
                if len(columns) > 1:
                    self.table.setSpan(0, 0, 1, len(columns))
                return

            # Popuni tabelu
            self.table.setSortingEnabled(False)
            self.table.setUpdatesEnabled(False)
            self.table.setRowCount(len(results))

            for row, row_data in enumerate(results):
                for col, value in enumerate(row_data):
                    formatted_value = format_fn(value) if format_fn else value
                    self.table.setItem(
                        row, col, QTableWidgetItem(str(formatted_value or ""))
                    )

                # Dodaj akcije kao tekst (ne widget!) samo ako je add_actions=True
                # i ako tabela ima više kolona od broja podataka
                if add_actions and len(columns) < self.table.columnCount():
                    item_actions = QTableWidgetItem("✏️  🗑️")
                    item_actions.setTextAlignment(Qt.AlignCenter)
                    item_actions.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    self.table.setItem(row, len(columns), item_actions)

            self.table.setUpdatesEnabled(True)
            self.table.setSortingEnabled(True)

            # Osveži UI
            self.table.show()
            self.table.setVisible(True)
            self.table.setEnabled(True)
            self.table.viewport().update()
            self.table.update()
            self.table.repaint()

            logger.info(f"Uspešno prikazano {len(results)} rezultata u GUI")

        except Exception as e:
            logger.error(f"Greška pri pretrazi: {str(e)}")
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
        """Delete record from database"""
        try:
            if self.current_category in ["Pošiljaoci", "Uvoznici"]:
                table_name = (
                    "catalogs.izvoznici"
                    if self.current_category == "Pošiljaoci"
                    else "catalogs.uvoznici"
                )
                jib = data.get("jib")
                if jib:
                    query = f"DELETE FROM {table_name} WHERE jib = %s"
                    self.db_manager.execute_update(query, (jib,))
                    logger.info(f"Zapis sa JIB {jib} obrisan iz {table_name}")
            elif self.current_category == "Carinske tarife":
                table_name = "catalogs.zvanicna_tarifa"
                tarifni_kod = data.get("tarifni_kod")
                if tarifni_kod:
                    query = f"DELETE FROM {table_name} WHERE tarifni_kod = %s"
                    self.db_manager.execute_update(query, (tarifni_kod,))
                    logger.info(
                        f"Zapis sa tarifnim kodom {tarifni_kod} obrisan iz {table_name}"
                    )
            elif self.current_category == "Carinarnice":
                table_name = "catalogs.carinske_ispostave"
                sifra = data.get("sifra")
                if sifra:
                    query = f"DELETE FROM {table_name} WHERE sifra = %s"
                    self.db_manager.execute_update(query, (sifra,))
                    logger.info(f"Zapis sa šifrom {sifra} obrisan iz {table_name}")
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

    def _on_search_text_changed(self, text: str):
        """Live search as user types - immediate filtering"""
        try:
            logger.info(
                f"🔍 PRETRAGA: text='{text}', category='{self.current_category}'"
            )

            # For Zemlje - use database search like Pošiljaoci
            if self.current_category == "Zemlje":
                logger.info(f"▶️ Pozivam _search_zemlje za '{self.current_category}'")
                self._search_zemlje(text)
            # For Carinarnice - use tree widget search
            elif self.current_category == "Carinarnice":
                logger.info(
                    f"▶️ Pozivam _search_carinarnice za '{self.current_category}'"
                )
                self._search_carinarnice(text)
                self._update_status()
            # For Carinski postupci - use read-only filtering
            elif self.current_category == "Carinski postupci":
                logger.info(f"▶️ Pozivam _filter_table za '{self.current_category}'")
                self._filter_table(text)
                self._update_status()
            elif self.current_category in [
                "Pošiljaoci",
                "Uvoznici",
                "Carinske tarife",
                "Primaoci",
                "Deklaranti",
            ]:
                # Za Carinske tarife — direktno iz baze (hijerarhijski za brojeve)
                if self.current_category == "Carinske tarife":
                    logger.info(f"▶️ Pozivam _search_trgovacki_nazivi za '{self.current_category}'")
                    self._search_trgovacki_nazivi(text)
                else:
                    # Za ostale kategorije — filter tabele
                    logger.info(f"▶️ Pozivam _filter_table za '{self.current_category}'")
                    self._filter_table(text)
                self._update_status()
            else:
                logger.info(
                    f"⏭️ Preskačem - kategorija '{self.current_category}' nije u listi"
                )
        except Exception as e:
            logger.error(f"Greška pri live pretrazi: {str(e)}")

    def _search_posiljaoci(self, query: str):
        """Search posiljaoci in database using generic method"""
        try:
            logger.info(f"Pretraga pošiljalaca sa query-jem: '{query}'")

            # Use generic search with text-based actions (no widgets)
            self._search_generic(
                query=query,
                table_name="catalogs.izvoznici",
                columns=[
                    "jib",
                    "naziv",
                    "adresa",
                    "grad",
                    "drzava",
                    "telefon",
                    "email",
                    "kontakt",
                    "pdv_broj",
                    "maticni",
                ],
                search_columns=["jib", "naziv", "grad", "telefon", "email"],
                order_by="naziv",
                add_actions=False,
            )

            logger.info(f"Uspešno prikazano rezultati za pošiljaoce")
        except Exception as e:
            logger.error(f"Greška pri pretrazi pošiljalaca: {str(e)}")
            QMessageBox.critical(
                self, "Greška", f"Greška pri pretrazi pošiljalaca:\n{str(e)}"
            )

    def _filter_table(self, search_text: str):
        """Filter table rows based on search text — contains matching"""
        try:
            search_text = search_text.lower().strip()
            logger.debug(f"Filtriranje tabele sa tekstom: '{search_text}'")

            for row in range(self.table.rowCount()):
                match = False

                if not search_text:
                    # No search text - show all
                    match = True
                else:
                    # Proveri sve kolone — CONTAINS match (ne samo prefix)
                    for col in range(self.table.columnCount()):
                        item = self.table.item(row, col)
                        if item:
                            cell_text = item.text().lower()
                            if search_text in cell_text:
                                match = True
                                break

                self.table.setRowHidden(row, not match)

            logger.debug("Filtriranje tabele završeno")

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

            # For Pošiljaoci, Uvoznici and Carinske tarife, reload all data from database
            if self.current_category == "Pošiljaoci":
                self._load_posiljaoci_data()
            elif self.current_category == "Uvoznici":
                self._load_uvoznici_data()
            elif self.current_category == "Carinske tarife":
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
            total = self.table.rowCount()
            visible = sum(1 for row in range(total) if not self.table.isRowHidden(row))

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
                # For Pošiljaoci, get the actual count from database
                try:
                    count_result = self.db_manager.execute_query(
                        "SELECT COUNT(*) FROM catalogs.izvoznici"
                    )
                    total = count_result[0] if count_result else 0
                    self.lbl_totals.setText(
                        f"Ukupno: {total} pošiljalaca | Prikazano: {total}"
                    )
                    logger.debug(f"Ažuriran status za pošiljaoce: {total} ukupno")
                except Exception as e:
                    # Fallback to table count if database query fails
                    logger.warning(f"Neuspešan query za brojanje pošiljalaca: {e}")
                    # Check if table is QTableWidget or QTreeWidget
                    if hasattr(self.table, "rowCount"):  # QTableWidget
                        total = self.table.rowCount()
                        visible = sum(
                            1 for row in range(total) if not self.table.isRowHidden(row)
                        )
                    elif hasattr(self.table, "topLevelItemCount"):  # QTreeWidget
                        # For QTreeWidget, count all items (both parent and child)
                        total = self._get_tree_widget_count()
                        visible = total  # For now, assume all are visible
                    else:
                        total = 0
                        visible = 0
                    self.lbl_totals.setText(
                        f"Ukupno: {total} pošiljalaca | Prikazano: {visible}"
                    )
            elif self.current_category == "Uvoznici":
                # For Uvoznici, get the actual count from database
                try:
                    count_result = self.db_manager.execute_query(
                        "SELECT COUNT(*) FROM catalogs.uvoznici"
                    )
                    total = count_result[0] if count_result else 0
                    self.lbl_totals.setText(
                        f"Ukupno: {total} uvoznika | Prikazano: {total}"
                    )
                    logger.debug(f"Ažuriran status za uvoznike: {total} ukupno")
                except Exception as e:
                    # Fallback to table count if database query fails
                    logger.warning(f"Neuspešan query za brojanje uvoznika: {e}")
                    total = self.table.rowCount()
                    visible = sum(
                        1 for row in range(total) if not self.table.isRowHidden(row)
                    )
                    self.lbl_totals.setText(
                        f"Ukupno: {total} uvoznika | Prikazano: {visible}"
                    )
            elif self.current_category == "Carinske tarife":
                # For Carinske tarife, get the actual count from database
                try:
                    count_result = self.db_manager.execute_query(
                        "SELECT COUNT(*) FROM catalogs.zvanicna_tarifa"
                    )
                    total = count_result[0] if count_result else 0
                    self.lbl_totals.setText(
                        f"Ukupno: {total} carinskih tarifa | Prikazano: {total}"
                    )
                    logger.debug(f"Ažuriran status za carinske tarife: {total} ukupno")
                except Exception as e:
                    # Fallback to table count if database query fails
                    logger.warning(f"Neuspešan query za brojanje carinskih tarifa: {e}")
                    total = self.table.rowCount()
                    visible = sum(
                        1 for row in range(total) if not self.table.isRowHidden(row)
                    )
                    self.lbl_totals.setText(
                        f"Ukupno: {total} carinskih tarifa | Prikazano: {visible}"
                    )
            elif self.current_category == "Carinarnice":
                # For Carinarnice, get the actual count from database
                try:
                    count_result = self.db_manager.execute_query(
                        "SELECT COUNT(*) FROM catalogs.carinske_ispostave"
                    )
                    total = count_result[0] if count_result else 0
                    self.lbl_totals.setText(
                        f"Ukupno: {total} carinarnica | Prikazano: {total}"
                    )
                    logger.debug(f"Ažuriran status za carinarnice: {total} ukupno")
                except Exception as e:
                    # Fallback to table count if database query fails
                    logger.warning(f"Neuspešan query za brojanje carinarnica: {e}")
                    total = self.table.rowCount()
                    visible = sum(
                        1 for row in range(total) if not self.table.isRowHidden(row)
                    )
                    self.lbl_totals.setText(
                        f"Ukupno: {total} carinarnica | Prikazano: {visible}"
                    )
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
        if not hasattr(self, "tree_widget") or self.table != self.tree_widget:
            return 0

        total = 0

        def count_children(item):
            count = 1  # Count the parent item itself
            for i in range(item.childCount()):
                child = item.child(i)
                count += count_children(child)  # Recursively count children
            return count

        for i in range(self.tree_widget.topLevelItemCount()):
            top_item = self.tree_widget.topLevelItem(i)
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

            # Ako je pretraga brojčana, koristi hijerarhijski prikaz iz SQLite (kao u _load_trgovacki_nazivi_data)
            if is_code and len(clean_query) >= 2:
                # Hijerarhijski drill-down iz SQLite tarifa_2026
                import sqlite3 as _sqlite3
                import os as _os
                _DB = _os.path.normpath(_os.path.join(
                    _os.path.dirname(__file__), '..', '..', 'database', 'asycuda_sistem.db'
                ))

                prefix = clean_query.replace(' ', '').replace('.', '')

                # Dohvati traženi čvor i SVE potomke koji počinju tim prefiksom
                _conn = _sqlite3.connect(_DB)
                _conn.row_factory = _sqlite3.Row

                root_row = _conn.execute(
                    "SELECT kod, naziv, stopa_uvozna, nivo FROM tarifa_2026 WHERE kod = ?",
                    (prefix,)
                ).fetchone()

                # Svi potomci sortirani po kodu (max 300)
                desc_rows = _conn.execute(
                    "SELECT kod, naziv, stopa_uvozna, nivo FROM tarifa_2026 "
                    "WHERE kod LIKE ? AND kod != ? ORDER BY kod LIMIT 300",
                    (prefix + '%', prefix)
                ).fetchall()
                _conn.close()

                # Nivo → oznaka i indentacija po dužini koda
                _nivo_ikona = {
                    'glava': '📂',
                    'podglava': '📁',
                    'tarifni_broj': '📋',
                    'podbroj': '📄',
                }
                prefix_len = len(prefix)

                def _indent(kod):
                    extra = len(kod) - prefix_len
                    # Svaka 2 cifre = jedan nivo dublje
                    return '  ' * max(0, extra // 2)

                rows_to_show = []
                if root_row:
                    rows_to_show.append((root_row['kod'], root_row['naziv'],
                                         root_row['stopa_uvozna'], root_row['nivo'], True))
                for r in desc_rows:
                    rows_to_show.append((r['kod'], r['naziv'],
                                         r['stopa_uvozna'], r['nivo'], False))

                self.table.setRowCount(len(rows_to_show))
                for i, (kod, naziv, stopa, nivo, is_root) in enumerate(rows_to_show):
                    ikona = _nivo_ikona.get(nivo, '•')
                    indent = '' if is_root else _indent(kod)
                    stopa_str = ''
                    if stopa:
                        stopa_str = stopa if str(stopa).endswith('%') else str(stopa) + '%'

                    item_kod = QTableWidgetItem(indent + ikona + ' ' + kod)
                    item_naziv = QTableWidgetItem(naziv or '')
                    if stopa_str:
                        item_naziv.setToolTip(f"Stopa uvozna: {stopa_str}")

                    if is_root:
                        font = item_kod.font()
                        font.setBold(True)
                        item_kod.setFont(font)
                        item_naziv.setFont(font)

                    self.table.setItem(i, 0, item_kod)
                    self.table.setItem(i, 1, item_naziv)
                self.table.setColumnWidth(0, 200)
            else:
                # Za tekstualnu pretragu ili kratke brojeve (<2 cifre), koristi običnu pretragu
                if is_code and len(clean_query) < 2:
                    # Za kratke brojeve (<2 cifre) - obična pretraga
                    sql = "SELECT tarifni_kod, opis FROM catalogs.zvanicna_tarifa WHERE tarifni_kod LIKE %s ORDER BY tarifni_kod"
                    params = (f"{clean_query}%",)
                else:
                    # Tekstualna pretraga
                    sql = "SELECT tarifni_kod, opis FROM catalogs.zvanicna_tarifa WHERE tarifni_kod ILIKE %s OR opis ILIKE %s ORDER BY tarifni_kod"
                    params = (f"%{query}%", f"%{query}%")

                results = self.db_manager.execute_query(sql, params, fetch_all=True)
                if results is None:
                    results = []

                # Ručno punjenje tabele (sigurno za tuple i dict)
                self.table.setRowCount(len(results))
                for i, r in enumerate(results):
                    try:
                        if isinstance(r, tuple):
                            # Proveri da li tuple ima dovoljno elemenata
                            if len(r) >= 2:
                                kod = str(r[0]) if r[0] is not None else ""
                                opis = _clean(r[1]) if r[1] is not None else ""
                            else:
                                kod, opis = "", ""
                        elif isinstance(r, dict):
                            kod = str(r.get('tarifni_kod', ''))
                            opis = _clean(r.get('opis', ''))
                        else:
                            kod, opis = "", ""
                        
                        self.table.setItem(i, 0, QTableWidgetItem(kod))
                        self.table.setItem(i, 1, QTableWidgetItem(opis))
                    except (IndexError, KeyError, TypeError) as e:
                        logger.warning(f"Greška pri obradi reda {i}: {e}")
                        self.table.setItem(i, 0, QTableWidgetItem(""))
                        self.table.setItem(i, 1, QTableWidgetItem(""))
                
                self.table.setColumnWidth(0, 150)
            
            # Osiguraj da su svi redovi vidljivi
            for row in range(self.table.rowCount()):
                self.table.setRowHidden(row, False)

        except Exception as e:
            logger.error(f"Greška pri pretrazi tarifa: {e}")
            QMessageBox.critical(self, "Greška", f"Greška pri pretrazi tarifa:\n{str(e)}")

    def _search_uvoznici(self, query: str):
        """Search uvoznici in database using generic method"""
        try:
            logger.info(f"Pretraga uvoznika sa query-jem: '{query}'")

            # Use generic search with text-based actions (no widgets)
            self._search_generic(
                query=query,
                table_name="catalogs.uvoznici",
                columns=[
                    "jib",
                    "naziv",
                    "adresa",
                    "grad",
                    "drzava",
                    "telefon",
                    "email",
                    "kontakt",
                    "pdv_broj",
                    "maticni",
                ],
                search_columns=["jib", "naziv", "grad", "telefon", "email"],
                order_by="naziv",
                add_actions=False,
            )

            logger.info(f"Uspešno prikazano rezultati za uvoznike")
        except Exception as e:
            logger.error(f"Greška pri pretrazi uvoznika: {str(e)}")
            QMessageBox.critical(
                self, "Greška", f"Greška pri pretrazi uvoznika:\n{str(e)}"
            )

    def _on_novi(self):
        """Handle Novi button click with validation"""
        try:
            logger.info("Kreiranje novog zapisa")

            if self.current_category in ["Pošiljaoci", "Carinske tarife", "Uvoznici"]:
                self._clear_form()
                self.btn_snimi.setEnabled(True)
                self.is_editing = False
                self._editing_jib = ""  # Reset pri novom zapisu
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
                jib_val = jib_item.text() if jib_item else ""

                # Sačuvaj stari jib za WHERE uslov u UPDATE
                self._editing_jib = jib_val

                # Dohvati kompletne podatke iz baze (izvoznici nema postanski_broj)
                db_row = self.db_manager.execute_query(
                    "SELECT jib, naziv, adresa, grad, drzava, "
                    "telefon, email, kontakt, pdv_broj, maticni "
                    "FROM catalogs.izvoznici WHERE jib = %s",
                    (jib_val,),
                )

                if db_row:
                    jib_db, naziv, adresa, grad, drzava, tel, email, kontakt, pdv_broj, maticni = db_row
                    self.jib_field.setText(str(jib_db) if jib_db else "")
                    self.naziv_field.setText(str(naziv) if naziv else "")
                    self.adresa_field.setText(str(adresa) if adresa else "")
                    self.grad_field.setText(str(grad) if grad else "")
                    self.postanski_broj_field.setText("")  # ne postoji u izvoznici
                    self.zemlja_field.setText(str(drzava) if drzava else "")
                    self.telefon_field.setText(str(tel) if tel else "")
                    self.email_field.setText(str(email) if email else "")
                    self.kontakt_field.setText(str(kontakt) if kontakt else "")
                    self.pdv_field.setText(str(pdv_broj) if pdv_broj else "")
                    self.maticni_field.setText(str(maticni) if maticni else "")
                else:
                    # Fallback: popuni iz tabele
                    self.jib_field.setText(jib_val)
                    self.naziv_field.setText(self.table.item(row, 1).text() if self.table.item(row, 1) else "")
                    self.adresa_field.setText(self.table.item(row, 2).text() if self.table.item(row, 2) else "")
                    self.grad_field.setText(self.table.item(row, 3).text() if self.table.item(row, 3) else "")
                    self.zemlja_field.setText(self.table.item(row, 4).text() if self.table.item(row, 4) else "")
                    self.postanski_broj_field.setText("")
                    self.pdv_field.setText("")
                    self.telefon_field.setText("")
                    self.email_field.setText("")
                    self.kontakt_field.setText("")
                    self.maticni_field.setText("")

                self.current_row_index = row
                self.btn_snimi.setEnabled(True)
                self.is_editing = True
                # Enable editing mode
                self._set_readonly_mode(readonly=False)
                logger.info(f"Pošiljalac {jib_val!r} uspješno učitan za uređivanje")
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

                # Sačuvaj stari jib za WHERE uslov u UPDATE
                self._editing_jib = jib

                # Dohvati kompletne podatke iz baze
                db_row = self.db_manager.execute_query(
                    "SELECT jib, naziv, adresa, grad, postanski_broj, drzava, "
                    "telefon, email, kontakt, pdv_broj, maticni "
                    "FROM catalogs.uvoznici WHERE jib = %s",
                    (jib,),
                )

                if db_row:
                    jib_db, naziv, adresa, grad, ptt, drzava, tel, email, kontakt, pdv_broj, maticni = db_row
                    self.jib_field.setText(str(jib_db) if jib_db else "")
                    self.naziv_field.setText(str(naziv) if naziv else "")
                    self.adresa_field.setText(str(adresa) if adresa else "")
                    self.grad_field.setText(str(grad) if grad else "")
                    self.postanski_broj_field.setText(str(ptt) if ptt else "")
                    self.zemlja_field.setText(str(drzava) if drzava else "")
                    self.telefon_field.setText(str(tel) if tel else "")
                    self.email_field.setText(str(email) if email else "")
                    self.kontakt_field.setText(str(kontakt) if kontakt else "")
                    self.pdv_field.setText(str(pdv_broj) if pdv_broj else "")
                    self.maticni_field.setText(str(maticni) if maticni else "")
                else:
                    # Fallback: popuni iz tabele
                    self.jib_field.setText(jib or "")
                    for col, field in [
                        (1, self.naziv_field),
                        (2, self.adresa_field),
                        (3, self.grad_field),
                        (4, self.zemlja_field),
                    ]:
                        item = self.table.item(row, col)
                        if item:
                            field.setText(item.text())
                    self.pdv_field.setText("")

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
                    # Delete from database using centralized manager
                    self.db_manager.execute_update(
                        f"DELETE FROM {table_name} WHERE {identifier_field} = %s",
                        (identifier_value,),
                    )

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
                        # Koristimo _editing_jib (stari JIB) za WHERE, ali ažuriramo i jib polje
                        old_jib = self._editing_jib or form_data["jib"]
                        self.db_manager.execute_update(
                            """
                            UPDATE catalogs.izvoznici
                            SET jib = %s, naziv = %s, adresa = %s, grad = %s,
                                drzava = %s,
                                telefon = %s, email = %s, kontakt = %s,
                                pdv_broj = %s, maticni = %s
                            WHERE jib = %s
                        """,
                            (
                                form_data["jib"],
                                form_data["naziv"],
                                form_data["adresa"],
                                form_data["grad"],
                                form_data["zemlja"],
                                form_data["telefon"],
                                form_data["email"],
                                form_data["kontakt"],
                                form_data["pdv"],
                                form_data["maticni"],
                                old_jib,
                            ),
                        )
                        self._editing_jib = ""
                        # Reload data for Pošiljaoci
                        self._load_posiljaoci_data()
                    elif self.current_category == "Uvoznici":
                        old_jib_uv = self._editing_jib or form_data["jib"]
                        self.db_manager.execute_update(
                            """
                            UPDATE catalogs.uvoznici
                            SET jib = %s, naziv = %s, adresa = %s, grad = %s,
                                postanski_broj = %s, drzava = %s,
                                telefon = %s, email = %s, kontakt = %s,
                                pdv_broj = %s, maticni = %s
                            WHERE jib = %s
                        """,
                            (
                                form_data["jib"],
                                form_data["naziv"],
                                form_data["adresa"],
                                form_data["grad"],
                                form_data["postanski_broj"],
                                form_data["zemlja"],
                                form_data["telefon"],
                                form_data["email"],
                                form_data["kontakt"],
                                form_data["pdv"],
                                form_data["maticni"],
                                old_jib_uv,
                            ),
                        )
                        self._editing_jib = ""
                        # Reload data for Uvoznici
                        self._load_uvoznici_data()
                    elif self.current_category == "Carinske tarife":
                        self.db_manager.execute_update(
                            """
                            UPDATE catalogs.zvanicna_tarifa
                            SET opis = %s
                            WHERE tarifni_kod = %s
                        """,
                            (
                                form_data["naziv_robe"],
                                form_data["tarifni_kod"],
                            ),
                        )
                        # Reload data for Carinske tarife
                        self._load_trgovacki_nazivi_data()
                else:
                    # Insert new record
                    if self.current_category == "Pošiljaoci":
                        self.db_manager.execute_update(
                            """
                            INSERT INTO catalogs.izvoznici
                            (jib, naziv, adresa, grad, drzava,
                             telefon, email, kontakt, pdv_broj, maticni)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                            (
                                form_data["jib"],
                                form_data["naziv"],
                                form_data["adresa"],
                                form_data["grad"],
                                form_data["zemlja"],
                                form_data["telefon"],
                                form_data["email"],
                                form_data["kontakt"],
                                form_data["pdv"],
                                form_data["maticni"],
                            ),
                        )
                        # Reload data for Pošiljaoci
                        self._load_posiljaoci_data()
                    elif self.current_category == "Uvoznici":
                        self.db_manager.execute_update(
                            """
                            INSERT INTO catalogs.uvoznici
                            (jib, naziv, adresa, grad, postanski_broj, drzava,
                             telefon, email, kontakt, pdv_broj, maticni)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                            (
                                form_data["jib"],
                                form_data["naziv"],
                                form_data["adresa"],
                                form_data["grad"],
                                form_data["postanski_broj"],
                                form_data["zemlja"],
                                form_data["telefon"],
                                form_data["email"],
                                form_data["kontakt"],
                                form_data["pdv"],
                                form_data["maticni"],
                            ),
                        )
                        # Reload data for Uvoznici
                        self._load_uvoznici_data()
                    elif self.current_category == "Carinske tarife":
                        self.db_manager.execute_update(
                            """
                            INSERT INTO catalogs.zvanicna_tarifa
                            (tarifni_kod, opis)
                            VALUES (%s, %s)
                        """,
                            (
                                form_data["tarifni_kod"],
                                form_data["naziv_robe"],
                            ),
                        )
                        # Reload data for Carinske tarife
                        self._load_trgovacki_nazivi_data()
                    elif self.current_category == "Carinarnice":
                        if (
                            self.is_editing
                            and hasattr(self, "current_tree_item")
                            and self.current_tree_item
                            and self.current_tree_item.parent()
                        ):
                            # Update existing customs post
                            self.db_manager.execute_update(
                                """
                                UPDATE catalogs.carinske_ispostave
                                SET naziv = %s
                                WHERE sifra = %s
                            """,
                                (
                                    form_data["naziv"],
                                    form_data["sifra"],
                                ),
                            )
                        else:
                            # Insert new customs post
                            self.db_manager.execute_update(
                                """
                                INSERT INTO catalogs.carinske_ispostave
                                (sifra, naziv)
                                VALUES (%s, %s)
                            """,
                                (
                                    form_data["sifra"],
                                    form_data["naziv"],
                                ),
                            )
                        # Reload data for Carinarnice
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

                    # Dohvati dodatna polja iz baze
                    jib_val = (
                        pdv_val if self.current_category == "Uvoznici" else pdv_val
                    )
                    if self.current_category == "Pošiljaoci":
                        db_row = self.db_manager.execute_query(
                            "SELECT telefon, email, kontakt, pdv_broj, maticni "
                            "FROM catalogs.izvoznici WHERE jib = %s",
                            (jib_val,),
                        )
                    else:
                        db_row = self.db_manager.execute_query(
                            "SELECT telefon, email, kontakt, pdv_broj, maticni "
                            "FROM catalogs.uvoznici WHERE jib = %s",
                            (jib_val,),
                        )
                    if db_row:
                        telefon, email, kontakt, pdv_broj, maticni = db_row
                        self.telefon_field.setText(telefon or "")
                        self.email_field.setText(email or "")
                        self.kontakt_field.setText(kontakt or "")
                        self.pdv_field.setText(pdv_broj or "")
                        self.maticni_field.setText(maticni or "")

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
    window.setWindowTitle("Šifrarnici - ASYCUDA Pro")
    window.setGeometry(50, 50, 1400, 900)

    # Apply global style
    app.setStyle("Fusion")

    tab = SifarniciView()
    window.setCentralWidget(tab)

    window.show()
    sys.exit(app.exec())
