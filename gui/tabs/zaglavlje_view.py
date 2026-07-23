# gui/tabs/zaglavlje_view.py

"""
Zaglavlje View - UI Layer

Samo UI konstrukcija i signal emission.
Nema business logike.

GUI je identičan originalu (zaglavlje_tab_original.py):
- 3 kolone u QHBoxLayout unutar jednog QScrollArea
- Lijeva (580px): Izvoznik, Primalac, Deklarant, Transport, Aktivno, Vid25-27, Izlaz29-30
- Srednja (580px): Deklaracija(1), Obrasci(3-4), Stavke(5-7), Odg.zemlja(9),
                   Zemlje(10-13), Drzave(15-17), Uslovi(20), Valuta(22-24),
                   Troskovi, Odgodjeno(48-49)
- Desna (auto): Tabela Priložene isprave sa IspravaDelegate i _ColRatioFilter
"""

import sys
import os
import logging
from pathlib import Path
from datetime import date

logger = logging.getLogger(__name__)

# Strelica za QComboBox dropdown — cross-platform SVG
_ARROW_SVG = str(
    Path(__file__).parent.parent.parent / "assets" / "icons" / "chevron-down.svg"
).replace("\\", "/")
_DOWN_ARROW_CSS = f"image: url({_ARROW_SVG});" if Path(_ARROW_SVG).exists() else ""
from database.db import get_db_connection
from gui.tabs.base_view import BaseTabView

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QPushButton,
    QLineEdit,
    QLabel,
    QFrame,
    QComboBox,
    QCheckBox,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox,
    QFileDialog,
    QMenu,
    QSizePolicy,
    QScrollArea,
    QCompleter,
    QStyledItemDelegate,
    QHeaderView,
)
from PySide6.QtCore import Qt, Signal, QSize, QObject, QEvent, QPoint
from PySide6.QtGui import QFont, QIcon, QRegularExpressionValidator, QPainter, QColor, QPolygon
from PySide6.QtCore import QRegularExpression
from typing import Dict, Any, Optional, List
from gui.utils.safe_message_box import SafeMessageBox as QMessageBox
from gui.utils.safe_message_box import capture_window_geometry, restore_window_geometry_queued

try:
    import qtawesome as qta

    _QTA = True
except ImportError:
    _QTA = False


# ============================================================
# DB HELPER FUNCTIONS (module-level, kao u originalu)
# ============================================================


def _load_vrste_deklaracija_from_db() -> dict:
    result: dict = {}
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT sifra, oznaka, opis "
                    "FROM catalogs.vrste_deklaracija ORDER BY sifra, oznaka"
                )
                for row in cur.fetchall():
                    sifra = row["sifra"]
                    if sifra not in result:
                        result[sifra] = []
                    result[sifra].append((row["oznaka"], row["opis"]))
    except Exception as e:
        logger.warning("⚠️ [ZaglavljeView] vrste_deklaracija DB greška: %s", e)
    return result


def _load_tipovi_deklaracija_from_db() -> list:
    result = []
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT sifra, opis FROM catalogs.tipovi_deklaracija ORDER BY sifra"
                )
                result = [(r["sifra"], r["opis"]) for r in cur.fetchall()]
    except Exception as e:
        logger.warning("⚠️ [ZaglavljeView] tipovi_deklaracija DB greška: %s", e)
    return result


def _load_vrste_prijevoza_from_db() -> list:
    result = []
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT sifra, opis FROM catalogs.vrste_prijevoza ORDER BY sifra"
                )
                result = [(r["sifra"], r["opis"]) for r in cur.fetchall()]
    except Exception as e:
        logger.warning("⚠️ [ZaglavljeView] vrste_prijevoza DB greška: %s", e)
    return result


def _load_ured_odredista_from_db() -> tuple[str, str]:
    """Učitaj default carinsku ispostavu (BA097012 - Bijeljina).
    
    Returns:
        Tuple (sifra, cleaned_naziv) npr. ("BA097012", "CI Bijeljina")
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT sifra, naziv FROM catalogs.carinske_ispostave "
                    "WHERE sifra = 'BA097012'"
                )
                row = cur.fetchone()
                if row:
                    naziv = row["naziv"]
                    # "1. Carinska ispostava Banja Luka" → "CI Banja Luka"
                    if ". Carinska ispostava" in naziv:
                        clean = "CI " + naziv.split(". Carinska ispostava ")[-1]
                    elif "Carinski referat" in naziv:
                        clean = "CR " + naziv.split("Carinski referat ")[-1]
                    else:
                        clean = naziv
                    return (row['sifra'], clean)
    except Exception as e:
        logger.warning("⚠️ [ZaglavljeView] ured_odredista DB greška: %s", e)
    return ("", "")


def _load_isprave_from_db() -> dict:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT sifra, opis FROM catalogs.prilozeni_dokumenti_sifre ORDER BY sifra"
                )
                rows = cur.fetchall()
        return {r["sifra"]: r["opis"] for r in rows}
    except Exception as e:
        logger.warning("⚠️ [ZaglavljeView] isprave DB greška: %s", e)
        return {}


# ============================================================
# HELPER KLASE
# ============================================================


class _ArrowComboBox(QComboBox):
    """QComboBox sa ručno iscrtanom strelicom (otporno na QSS hijerarhiju)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            """
            QComboBox::drop-down {
                width: 18px;
                border: none;
                background: transparent;
            }
            QComboBox::down-arrow {
                image: none;
                width: 0px;
                height: 0px;
                border: none;
            }
            """
        )

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = self.rect()
        cx = r.right() - 9
        cy = r.center().y() + 1
        tri = QPolygon(
            [
                QPoint(cx - 5, cy - 3),
                QPoint(cx + 5, cy - 3),
                QPoint(cx, cy + 4),
            ]
        )
        painter.setPen(QColor(74, 74, 74))
        painter.setBrush(QColor(74, 74, 74))
        painter.drawPolygon(tri)


class IspravaDelegate(QStyledItemDelegate):
    """Delegate za kolonu Šifra – autocomplete sa prikazom koda i naziva."""

    def __init__(self, isprave: dict, table: QTableWidget, parent=None):
        super().__init__(parent)
        self._isprave = isprave
        self._table = table
        self._display_map = {f"{k} — {v}": k for k, v in isprave.items()}
        self._display_list = sorted(self._display_map.keys())

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setPlaceholderText("npr. N380")
        font = editor.font()
        font.setPointSize(13)
        editor.setFont(font)

        completer = QCompleter(self._display_list, editor)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)

        popup = completer.popup()
        pfont = popup.font()
        pfont.setPointSize(15)
        popup.setFont(pfont)
        popup.setMinimumWidth(520)
        popup.setStyleSheet(
            "QListView { font-size: 15pt; background-color: #ffffff; color: #1e3820; }"
            "QListView::item { padding: 6px 10px; min-height: 28px; color: #1e3820; }"
            "QListView::item:selected { background-color: #c8dcc8; color: #1e3820; }"
        )

        completer.activated.connect(
            lambda display_text: self._on_selected(display_text, index.row(), editor)
        )
        editor.textEdited.connect(
            lambda text: self._on_text_edited(text, index.row(), completer)
        )

        # Enter tipka — potvrdi označenu stavku, ili prvu u popupu ako nema označene
        def _on_enter():
            popup = completer.popup()
            if popup.isVisible():
                idx = popup.currentIndex()
                if not idx.isValid():
                    # Nema označene strelicama — uzmi prvu stavku
                    idx = popup.model().index(0, 0)
                if idx.isValid():
                    completer.activated.emit(idx.data())
                    popup.hide()

        editor.returnPressed.connect(_on_enter)
        editor.setCompleter(completer)
        return editor

    def _on_selected(self, display_text: str, row: int, editor: QLineEdit):
        kod = self._display_map.get(display_text, display_text.split(" — ")[0].strip())
        editor.setText(kod)
        self._set_document_name(row, kod)

    def _on_text_edited(self, text: str, row: int, completer: QCompleter):
        text = text.strip()
        completer.setCompletionPrefix(text)
        completer.complete()
        kod = text.upper()
        if kod in self._isprave:
            self._set_document_name(row, kod)

    def _set_document_name(self, row: int, kod: str):
        naziv = self._isprave.get(kod, "")
        if naziv:
            item = self._table.item(row, 1)
            if item is None:
                item = QTableWidgetItem()
                self._table.setItem(row, 1, item)
            item.setText(naziv)

    def setModelData(self, editor, model, index):
        text = editor.text().strip()
        if " — " in text:
            text = text.split(" — ")[0].strip()
        model.setData(index, text)


class _ColRatioFilter(QObject):
    """Event filter koji drži Referencu na 40% slobodnog prostora."""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Resize:
            avail = obj.viewport().width() - obj.columnWidth(0) - obj.columnWidth(3)
            if avail > 10:
                obj.setColumnWidth(2, int(avail * 0.45))
        return False


# ============================================================
# ZAGLAVLJE VIEW
# ============================================================


class ZaglavljeView(BaseTabView):
    """
    View layer za Zaglavlje tab.

    Odgovornosti:
    - Konstrukcija widgeta (identičan GUI kao original)
    - Layout management
    - Signal emission
    - Data display

    Nema business logike.
    """

    _PRESERVE_REFS = frozenset({"DIS", "N380", "OST", "PE1", "PE2", "PE3"})

    # ============================================================
    # SIGNALS
    # ============================================================

    save_requested = Signal()
    load_requested = Signal(str)
    delete_requested = Signal()
    import_xml_requested = Signal(str)
    export_xml_requested = Signal()
    new_requested = Signal()
    validation_requested = Signal()
    search_company_requested = Signal(str)
    add_company_requested = Signal(str)
    deklaracija_sifra_changed = Signal(str)
    valuta_changed = Signal(str)
    # data_changed naslijeđen iz BaseTabView

    # ============================================================
    # INIT
    # ============================================================

    def __init__(self):
        super().__init__()
        self.setObjectName("ZaglavljeTab")

        # Widget references
        self.field_widgets: Dict[str, QWidget] = {}

        # Buttons
        self.btn_novi: Optional[QPushButton] = None
        self.btn_import: Optional[QPushButton] = None
        self.btn_snimi: Optional[QPushButton] = None
        self.btn_brisi: Optional[QPushButton] = None
        self.btn_izvezi: Optional[QPushButton] = None

        # Table for attached documents
        self.table: Optional[QTableWidget] = None

        # Snapshot priloženih dokumenata iz zadnjeg XML import-a
        # Koristi se za detekciju promjena — export blokiran ako se ništa nije promijenilo
        self._import_attached_docs: List[Dict[str, Any]] = []

        # Setup UI
        self._setup_ui()
        self._auto_fill_deklarant()
        self._apply_styles()
        self._connect_signals()

    def paintEvent(self, event):
        """Botanički dekorativni krugovi u uglovima — isti stil kao Agent tab."""
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()

        painter.setPen(Qt.NoPen)

        # Donji desni ugao — botanički listovi
        painter.setBrush(QColor("#a0c4a0"))
        painter.setOpacity(0.55)
        painter.drawEllipse(w - 200, h - 200, 260, 260)

        painter.setBrush(QColor("#7aa080"))
        painter.setOpacity(0.35)
        painter.drawEllipse(w - 140, h - 140, 190, 190)

        painter.setBrush(QColor("#5a8060"))
        painter.setOpacity(0.15)
        painter.drawEllipse(w - 90, h - 90, 130, 130)

        # Donji lijevi ugao
        painter.setBrush(QColor("#a0c4a0"))
        painter.setOpacity(0.40)
        painter.drawEllipse(-80, h - 160, 210, 210)

        painter.setBrush(QColor("#7aa080"))
        painter.setOpacity(0.25)
        painter.drawEllipse(-40, h - 110, 150, 150)

        painter.end()

    # ============================================================
    # UI CONSTRUCTION
    # ============================================================

    def _create_icon_button(self, text: str, icon_name: str) -> QPushButton:
        """Kreiraj dugme sa ikonom iz QtAwesome."""
        btn = QPushButton(" " + text)
        if sys.platform.startswith("win"):
            btn.setFixedHeight(30)
        if _QTA:
            try:
                btn.setIcon(qta.icon(icon_name, color="#FFFFFF"))
                btn.setIconSize(QSize(20, 20))
            except Exception:
                pass
        return btn

    def _setup_ui(self):
        """Konstruiši UI layout — identičan originalu."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # TOOLBAR
        toolbar = self._create_toolbar()
        main_layout.addWidget(toolbar)

        # MAIN GRID (3 kolone) - bez ScrollArea
        grid_widget = self._create_main_grid()
        grid_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        main_layout.addWidget(grid_widget)

    def _create_toolbar(self) -> QFrame:
        """Kreiraj toolbar sa dugmadima."""
        toolbar = QFrame()
        toolbar.setFixedHeight(50)
        toolbar.setObjectName("toolbar")

        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(8, 5, 8, 9)
        layout.setSpacing(10)

        self.btn_novi = self._create_icon_button("Novi", "fa5s.plus-square")
        self.btn_novi.setObjectName("btnNovi")

        self.btn_import = self._create_icon_button("Uvezi XML", "fa5s.file-import")
        self.btn_import.setObjectName("btnUveziXML")

        self.btn_snimi = self._create_icon_button("Završna provjera", "fa5s.check-circle")
        self.btn_snimi.setObjectName("btnSnimi")

        self.btn_brisi = self._create_icon_button("Briši", "fa5s.trash-alt")
        self.btn_brisi.setObjectName("btnBrisi")

        self.btn_izvezi = self._create_icon_button("Izvezi XML", "fa5s.file-export")
        self.btn_izvezi.setObjectName("btnIzveziXML")

        layout.addWidget(self.btn_novi)
        layout.addWidget(self.btn_import)
        layout.addWidget(self.btn_snimi)
        layout.addWidget(self.btn_brisi)
        layout.addWidget(self.btn_izvezi)

        return toolbar

    def _create_main_grid(self) -> QWidget:
        """Kreiraj glavni widget sa 3 kolone (QHBoxLayout)."""
        grid_widget = QWidget()
        grid_widget.setAttribute(Qt.WA_StyledBackground, True)
        grid_widget.setStyleSheet("QWidget { background-color: #e8f2ed; }")
        grid_layout = QHBoxLayout(grid_widget)
        grid_layout.setContentsMargins(6, 6, 6, 6)
        grid_layout.setSpacing(4)

        left_column = self._create_left_column()
        middle_column = self._create_middle_column()
        right_column = self._create_right_column()

        field_state_style = """
            QLineEdit, QComboBox {
                background-color: #ffffff;
                border: 1px solid #a8b9ae;
                color: #18354a;
            }
            QLineEdit:hover, QComboBox:hover {
                background-color: #fbfefc;
                border-color: #8fa9ba;
            }
            QLineEdit:focus, QComboBox:focus {
                background-color: #ffffff;
                border: 2px solid #3f7898;
            }
            QLineEdit:read-only {
                background-color: #f2f5f3;
                border-color: #bcc8c0;
                color: #526159;
            }
            QLineEdit:disabled, QComboBox:disabled {
                background-color: #edf1ef;
                border-color: #c7d0ca;
                color: #7d8982;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                border: 1px solid #a8b9ae;
                selection-background-color: #dfeaf1;
                selection-color: #18354a;
            }
        """
        for column in (left_column, middle_column, right_column):
            column.setStyleSheet(column.styleSheet() + field_state_style)

        if sys.platform.startswith("win"):
            for column in (left_column, middle_column, right_column):
                self._apply_windows_control_metrics(column)

        grid_layout.addWidget(left_column, 0)
        grid_layout.addWidget(middle_column, 0)
        grid_layout.addWidget(right_column, 1)

        return grid_widget

    def _apply_windows_control_metrics(self, widget: QWidget) -> None:
        field_height = 22 if widget.objectName() == "left_column" else 27
        for field in widget.findChildren(QLineEdit):
            if field.objectName() == "company_address_field":
                continue
            field.setFixedHeight(field_height)
        for combo in widget.findChildren(QComboBox):
            combo.setFixedHeight(field_height)

    # ============================================================
    # LIJEVA KOLONA
    # ============================================================

    def _create_left_column(self) -> QFrame:
        """Lijeva kolona: Izvoznik(2), Primalac(8), Deklarant(14),
        Transport(18-19), Aktivno(21), Vid(25-27), Izlaz(29-30)."""
        column = QFrame()
        column.setFrameShape(QFrame.Shape.Box)
        column.setFrameShadow(QFrame.Shadow.Plain)
        column.setLineWidth(2)
        column.setFixedWidth(470)
        column.setObjectName("left_column")
        column.setAttribute(Qt.WA_StyledBackground, True)
        column.setStyleSheet(("QFrame#left_column { background-color: #eef5f1; }" + """
    QLineEdit {
        background: #fafcfa;
        border: 1px solid #a0c4a0;
        border-radius: 3px;
        padding: 1px 6px;
        min-height: 22px;
        font-size: 14px;
        color: #1e3820;
    }
    QLineEdit:hover   { background: #eef6ec; border-color: #7aa080; }
    QLineEdit:focus   { background: #e8f2e8; border-color: #5a8060; border-width: 2px; }
    QLineEdit:read-only { background: #eef4ee; border-color: #c8dcc8; color: #4a6a4a; }
    QComboBox {
        background: #fafcfa;
        border: 1px solid #a0c4a0;
        border-radius: 3px;
        padding: 1px 6px;
        min-height: 22px;
        font-size: 14px;
        color: #1e3820;
    }
    QComboBox:hover { background: #eef6ec; border-color: #7aa080; }
    QComboBox:focus { background: #e8f2e8; border-color: #5a8060; }
    QComboBox::drop-down { border: none; width: 20px; }
    QComboBox::down-arrow {
        __ARROW_CSS__
        width: 14px;
        height: 14px;
        margin-right: 5px;
    }
    QComboBox QAbstractItemView {
        background: #fafcfa;
        border: 1px solid #a0c4a0;
        font-size: 13px;
        selection-background-color: #d4e8d4;
        color: #1e3820;
    }
    QComboBox QAbstractItemView::item {
        padding: 5px 10px;
        min-height: 24px;
    }
""").replace("__ARROW_CSS__", _DOWN_ARROW_CSS))
        layout = QVBoxLayout(column)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(1)

        layout.addWidget(
            self._create_company_group(
                "2. Izvoznik / Pošiljalac", "izvoznik", with_search=True
            ), 3
        )
        layout.addWidget(self._create_hline(), 0)

        layout.addWidget(
            self._create_company_group("8. Primalac", "primalac", with_search=True)
        , 3)
        layout.addWidget(self._create_hline(), 0)

        layout.addWidget(
            self._create_company_group(
                "14. Deklarant / Zastupnik", "deklarant", with_search=False, auto=True
            ), 2
        )
        layout.addWidget(self._create_hline(), 0)

        layout.addWidget(self._create_transport_group(), 2)
        layout.addWidget(self._create_hline(), 0)

        layout.addWidget(self._create_vid_group(), 0)
        layout.addWidget(self._create_hline(), 0)

        layout.addWidget(self._create_izlaz_group(), 0)

        return column

    def _auto_fill_deklarant(self):
        """Popuni polje 14. Deklarant/Zastupnik iz baze (catalogs.deklaranti)."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT jib, naziv, adresa, grad
                        FROM catalogs.deklaranti
                        ORDER BY naziv
                        LIMIT 1
                    """)
                    row = cur.fetchone()

            if not row:
                return

            jib = (row.get("jib") or "").strip()
            naziv = (row.get("naziv") or "").strip()
            adresa = (row.get("adresa") or "").strip()
            grad = (row.get("grad") or "").strip()

            id_field = self.field_widgets.get("deklarant_id")
            if id_field and jib:
                id_field.setText(jib)

            r1 = self.field_widgets.get("deklarant_r1")
            if r1 and naziv:
                r1.setText(naziv)

            r2 = self.field_widgets.get("deklarant_r2")
            if r2 and adresa:
                r2.setText(adresa)

            r3 = self.field_widgets.get("deklarant_r3")
            if r3 and grad:
                r3.setText(grad)

        except Exception as e:
            logger.warning("auto_fill_deklarant: %s", e)

    def _create_company_group(
        self, title: str, prefix: str, with_search: bool = False, auto: bool = False
    ) -> QWidget:
        """Kreiraj grupu za kompaniju: ID + 5 adresnih polja."""
        group = QWidget()
        if sys.platform.startswith("win"):
            group.setMinimumHeight(160)
            group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2 if sys.platform.startswith("win") else 0)

        # Naslov red
        title_row = QWidget()
        title_row.setObjectName(f"party_header_{prefix}")
        party_header_styles = {
            "izvoznik": (
                "QWidget#party_header_izvoznik { background-color: #cfe4d8; "
                "border-left: 5px solid #2f7d5a; border-bottom: 1px solid #7faf91; "
                "border-radius: 4px; }"
            ),
            "primalac": (
                "QWidget#party_header_primalac { background-color: #d3e2ec; "
                "border-left: 5px solid #2f6f9f; border-bottom: 1px solid #8aabbe; "
                "border-radius: 4px; }"
            ),
        }
        party_field_styles = {
            "izvoznik": (
                "QLineEdit { background-color: #f1f8f4; border: 1px solid #8fbea3; "
                "border-radius: 3px; color: #173d2b; }"
                "QLineEdit:hover { background-color: #e9f4ed; border-color: #5f9a79; }"
                "QLineEdit:focus { background-color: #ffffff; border: 2px solid #2f7d5a; }"
            ),
            "primalac": (
                "QLineEdit { background-color: #f1f6fa; border: 1px solid #91b4ca; "
                "border-radius: 3px; color: #193d56; }"
                "QLineEdit:hover { background-color: #e8f1f7; border-color: #5f8fad; }"
                "QLineEdit:focus { background-color: #ffffff; border: 2px solid #2f6f9f; }"
            ),
            "deklarant": (
                "QLineEdit { background-color: #f0f2f4; border: 1px solid #b8c0c8; "
                "border-radius: 3px; color: #5d6670; }"
                "QLineEdit:hover { background-color: #eceff2; border-color: #9da7b1; }"
                "QLineEdit:focus { background-color: #f7f8f9; border: 1px solid #8f99a3; }"
            ),
        }
        if prefix in party_header_styles:
            title_row.setStyleSheet(party_header_styles[prefix])
        if sys.platform.startswith("win"):
            title_row.setFixedHeight(31)
        title_layout = QHBoxLayout(title_row)
        title_layout.setContentsMargins(0, 2, 0, 2)
        title_layout.setSpacing(5)

        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        title_label.setObjectName("section_title")
        if prefix == "izvoznik":
            title_label.setStyleSheet(
                "color: #194a32; border: none; padding-left: 7px;"
            )
        elif prefix == "primalac":
            title_label.setStyleSheet(
                "color: #1f4f70; border: none; padding-left: 7px;"
            )
        if sys.platform.startswith("win"):
            title_label.setFixedHeight(24)
            title_label.setMinimumWidth(title_label.fontMetrics().horizontalAdvance(title) + 12)
            title_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        title_layout.addWidget(title_label, 0, Qt.AlignmentFlag.AlignVCenter)

        if with_search:
            search_btn = QPushButton()
            if sys.platform.startswith("win"):
                search_btn.setFixedSize(34, 28)
                search_btn.setStyleSheet(
                    "QPushButton { background: #f0f7f0; border: 1px solid #6a9d6a; "
                    "border-radius: 3px; padding: 0px; margin: 0px; }"
                    "QPushButton:hover { background: #e0eee0; }"
                )
            if _QTA:
                try:
                    search_btn.setIcon(qta.icon("fa5s.search", color="#333333"))
                    search_btn.setIconSize(QSize(16, 16))
                except Exception:
                    pass
            search_btn.setToolTip("Pretraži")
            search_btn.clicked.connect(
                lambda checked=False, p=prefix: self.search_company_requested.emit(p)
            )
            title_layout.addWidget(search_btn, 0, Qt.AlignmentFlag.AlignVCenter)

            add_btn = QPushButton()
            if sys.platform.startswith("win"):
                add_btn.setFixedSize(44, 28)
            if _QTA:
                try:
                    add_btn.setIcon(qta.icon("fa5s.plus", color="#333333"))
                    add_btn.setIconSize(QSize(17, 17))
                except Exception:
                    pass
            add_btn.setToolTip("Dodaj novi")
            add_btn.setStyleSheet(
                "QPushButton { background: #5cb85c; color: white; border: 1px solid #449d44; "
                "border-radius: 3px; padding: 0px; margin: 0px; }"
                "QPushButton:hover { background: #53a653; }"
            )
            add_btn.clicked.connect(
                lambda checked=False, p=prefix: self.add_company_requested.emit(p)
            )
            title_layout.addWidget(add_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        if auto:
            auto_label = QLabel("AUTO")
            auto_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            if sys.platform.startswith("win"):
                auto_label.setFixedHeight(26)
                auto_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            auto_label.setStyleSheet(
                "background: #5cb85c; color: white; padding: 2px 5px; border-radius: 2px;"
            )
            title_layout.addWidget(auto_label)

        # ID polje
        id_field = QLineEdit()
        id_field.setPlaceholderText(
            "Šifra"
            if prefix == "izvoznik"
            else "JIB" if prefix == "primalac" else "Šifra"
        )
        id_field.setFixedWidth(150)
        id_field.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        if sys.platform.startswith("win"):
            id_field.setFixedHeight(24)
        if auto:
            id_field.setReadOnly(True)
        if prefix in party_field_styles:
            id_field.setStyleSheet(party_field_styles[prefix])
        title_layout.addStretch()
        title_layout.addWidget(id_field)
        title_layout.setAlignment(id_field, Qt.AlignmentFlag.AlignVCenter)
        self.field_widgets[f"{prefix}_id"] = id_field

        layout.addWidget(title_row)

        if sys.platform.startswith("win"):
            header_sep = QFrame()
            header_sep.setFixedHeight(1)
            party_separator_styles = {
                "izvoznik": "background-color: #7faf91;",
                "primalac": "background-color: #8aabbe;",
            }
            header_sep.setStyleSheet(
                party_separator_styles.get(prefix, "background-color: #b8ccb8;")
            )
            layout.addWidget(header_sep)

        # 5 adresnih polja — na Windowsu rastu sa sekcijom (min/max umjesto fixed)
        placeholders = ["Naziv firme", "Adresa", "Grad", "Poštanski broj", "Država"]
        for i, placeholder in enumerate(placeholders, 1):
            field = QLineEdit()
            field.setPlaceholderText(placeholder)
            field.setObjectName("company_address_field")
            if sys.platform.startswith("win"):
                field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                field.setMinimumHeight(24)
                field.setMaximumHeight(42)
                field.setFont(QFont("Segoe UI", 11))
            else:
                field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            if auto:
                field.setReadOnly(True)
            if prefix in party_field_styles:
                field.setStyleSheet(party_field_styles[prefix])
            layout.addWidget(field)
            self.field_widgets[f"{prefix}_r{i}"] = field

        group.setAttribute(Qt.WA_StyledBackground, True)
        group.setProperty("section_card", True)
        return group

    def _create_transport_group(self) -> QWidget:
        """
        Rb.18 / Rb.19 / Rb.21 — transport blok.

        Layout:
          [18. Registracija (polazak)]  [Nacionalnost vozila]
          [registracija field]          [BA/RS/DE field]

          [21. Registracija (granica)]  [Nacionalnost vozila]
          [registracija field]          [BA/RS/DE field]

          [19. Kontejner □]  (ako čekirano → polje za broj kontejnera)
        """
        group = QWidget()
        if sys.platform.startswith("win"):
            group.setMinimumHeight(118)
            group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        bold = QFont("Segoe UI", 10, QFont.Weight.DemiBold)

        # ── Rb.18 red ────────────────────────────────────────────────
        lbl_row18 = QWidget()
        lbl_row18_layout = QHBoxLayout(lbl_row18)
        lbl_row18_layout.setContentsMargins(0, 0, 0, 0)
        lbl_row18_layout.setSpacing(6)
        lbl18 = QLabel("18. Registracija (polazak)")
        lbl18.setFont(bold)
        lbl_row18_layout.addWidget(lbl18, 3)
        lbl_nat18 = QLabel("Nacionalnost vozila")
        lbl_nat18.setFont(bold)
        lbl_row18_layout.addWidget(lbl_nat18, 2)
        layout.addWidget(lbl_row18)

        field_row18 = QWidget()
        if sys.platform.startswith("win"):
            field_row18.setMinimumHeight(24)
            field_row18.setMaximumHeight(42)
            field_row18.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        field_row18_layout = QHBoxLayout(field_row18)
        field_row18_layout.setContentsMargins(0, 0, 0, 0)
        field_row18_layout.setSpacing(6)
        transport_id = QLineEdit()
        transport_id.setPlaceholderText("npr. E25A456")
        transport_id.textEdited.connect(lambda t, w=transport_id: w.setText(t.upper()))
        field_row18_layout.addWidget(transport_id, 3)
        self.field_widgets["transport_id"] = transport_id
        nat18 = QLineEdit()
        nat18.setPlaceholderText("BA / RS / DE...")
        nat18.setMaxLength(3)
        nat18.textEdited.connect(lambda t, w=nat18: w.setText(t.upper()))
        field_row18_layout.addWidget(nat18, 2)
        self.field_widgets["transport_nacionalnost"] = nat18
        layout.addWidget(field_row18)

        # ── Rb.21 red ────────────────────────────────────────────────
        lbl_row21 = QWidget()
        lbl_row21_layout = QHBoxLayout(lbl_row21)
        lbl_row21_layout.setContentsMargins(0, 0, 0, 0)
        lbl_row21_layout.setSpacing(6)
        lbl21 = QLabel("21. Registracija (granica)")
        lbl21.setFont(bold)
        lbl_row21_layout.addWidget(lbl21, 3)
        lbl_nat21 = QLabel("Nacionalnost vozila")
        lbl_nat21.setFont(bold)
        lbl_row21_layout.addWidget(lbl_nat21, 2)
        layout.addWidget(lbl_row21)

        field_row21 = QWidget()
        if sys.platform.startswith("win"):
            field_row21.setMinimumHeight(24)
            field_row21.setMaximumHeight(42)
            field_row21.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        field_row21_layout = QHBoxLayout(field_row21)
        field_row21_layout.setContentsMargins(0, 0, 0, 0)
        field_row21_layout.setSpacing(6)
        aktivno = QLineEdit()
        aktivno.setPlaceholderText("npr. E25A456")
        aktivno.textEdited.connect(lambda t, w=aktivno: w.setText(t.upper()))
        field_row21_layout.addWidget(aktivno, 3)
        self.field_widgets["aktivno_transport"] = aktivno
        nat21 = QLineEdit()
        nat21.setPlaceholderText("BA / RS / DE...")
        nat21.setMaxLength(3)
        nat21.textEdited.connect(lambda t, w=nat21: w.setText(t.upper()))
        field_row21_layout.addWidget(nat21, 2)
        self.field_widgets["aktivno_transport_nat"] = nat21
        layout.addWidget(field_row21)

        # ── Rb.19 red — kontejner checkbox + uvjetno polje ───────────
        kt_row = QWidget()
        if sys.platform.startswith("win"):
            kt_row.setMinimumHeight(26)
        kt_layout = QHBoxLayout(kt_row)
        kt_layout.setContentsMargins(0, 1, 0, 0)
        kt_layout.setSpacing(6)

        lbl19 = QLabel("19. Kontejner")
        lbl19.setFont(bold)
        kt_layout.addWidget(lbl19)

        kontejner = QCheckBox()
        if sys.platform.startswith("win"):
            kontejner.setFixedSize(18, 18)
        kt_layout.addWidget(kontejner)
        self.field_widgets["kontejner"] = kontejner

        lbl_br = QLabel("Broj kontejnera:")
        lbl_br.setFont(QFont("Segoe UI", 10))
        lbl_br.setVisible(False)
        kt_layout.addWidget(lbl_br)

        kontejner_broj = QLineEdit()
        kontejner_broj.setPlaceholderText("npr. TCKU3953473")
        kontejner_broj.setMinimumWidth(160)
        kontejner_broj.setVisible(False)
        kt_layout.addWidget(kontejner_broj, 1)
        self.field_widgets["kontejner_broj"] = kontejner_broj

        kt_layout.addStretch()
        layout.addWidget(kt_row)

        # Prikaži/sakrij polje za broj kontejnera
        def _on_kontejner_toggled(checked: bool):
            lbl_br.setVisible(checked)
            kontejner_broj.setVisible(checked)

        kontejner.toggled.connect(_on_kontejner_toggled)

        group.setAttribute(Qt.WA_StyledBackground, True)
        group.setProperty("section_card", True)
        return group

    def _create_simple_field(self, title: str, field_name: str, placeholder: str = "") -> QWidget:
        """Helper: label iznad QLineEdit."""
        group = QWidget()
        layout = QVBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        label = QLabel(title)
        label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        layout.addWidget(label)

        field = QLineEdit()
        if placeholder:
            field.setPlaceholderText(placeholder)
        layout.addWidget(field)
        self.field_widgets[field_name] = field

        group.setAttribute(Qt.WA_StyledBackground, True)
        group.setProperty("section_card", True)
        return group

    def _create_vid_group(self) -> QWidget:
        """Rb.25-26-27 Vid unutra / Vid granica / Mjesto razduženja — 3 polja u jednom redu."""
        group = QWidget()
        if sys.platform.startswith("win"):
            group.setFixedHeight(56)
            group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

        label = QLabel("25. Vid unutra / 26. Vid granica / 27. Mjesto razduženja")
        label.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        layout.addWidget(label)

        row = QWidget()
        if sys.platform.startswith("win"):
            row.setFixedHeight(27)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(3)

        # Rb.25/26 — helper: popuni combo (dropdown "30 — Cestovni prevoz", u polju samo "30")
        def _make_vid_combo(tooltip: str) -> QComboBox:
            cb = _ArrowComboBox()
            cb.setEditable(True)
            cb.lineEdit().setReadOnly(True)
            for sifra, opis in self._vrste_prijevoza:
                cb.addItem(f"{sifra} — {opis}", sifra)
            # Nakon odabira — u polju prikaži samo šifru
            cb.activated.connect(lambda idx, _cb=cb: _cb.lineEdit().setText(_cb.itemData(idx) or ""))
            cb.setFixedWidth(160)
            cb.setToolTip(tooltip)
            return cb

        self._vrste_prijevoza = _load_vrste_prijevoza_from_db()

        cb_25 = _make_vid_combo("Vid prevoza unutar zemlje (Rb.25)")
        row_layout.addWidget(cb_25)
        self.field_widgets["vid_25"] = cb_25

        cb_26 = _make_vid_combo("Vid prevoza na granici — npr. 30=cestovni, 31=prikolica (Rb.26)")
        row_layout.addWidget(cb_26)
        self.field_widgets["vid_26"] = cb_26

        # Rb.27 — QLineEdit
        field_27 = QLineEdit()
        field_27.setPlaceholderText("27")
        row_layout.addWidget(field_27)
        self.field_widgets["vid_27"] = field_27

        layout.addWidget(row)
        group.setAttribute(Qt.WA_StyledBackground, True)
        group.setProperty("section_card", True)
        return group

    def _create_izlaz_group(self) -> QWidget:
        """Rb.29-30 Izlazna carinarnica + Lokacija robe — side-by-side (QHBoxLayout)."""
        group = QWidget()
        if sys.platform.startswith("win"):
            group.setFixedHeight(56)
            group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 29
        col29 = QWidget()
        col29_layout = QVBoxLayout(col29)
        col29_layout.setContentsMargins(0, 0, 0, 0)
        col29_layout.setSpacing(3)
        label29 = QLabel("29. Izlazna carinarnica")
        label29.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        col29_layout.addWidget(label29)
        field29 = QLineEdit()
        field29.setPlaceholderText("Kod")
        col29_layout.addWidget(field29)
        self.field_widgets["izlazna_carinarnica"] = field29
        layout.addWidget(col29)

        # 30
        col30 = QWidget()
        col30_layout = QVBoxLayout(col30)
        col30_layout.setContentsMargins(0, 0, 0, 0)
        col30_layout.setSpacing(3)
        label30 = QLabel("30. Lokacija robe")
        label30.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        col30_layout.addWidget(label30)
        field30 = QLineEdit()
        field30.setPlaceholderText("Lokacija")
        col30_layout.addWidget(field30)
        self.field_widgets["lokacija_robe"] = field30
        layout.addWidget(col30)

        group.setAttribute(Qt.WA_StyledBackground, True)
        group.setProperty("section_card", True)
        return group

    # ============================================================
    # SREDNJA KOLONA
    # ============================================================

    def _create_middle_column(self) -> QFrame:
        """Srednja kolona: Deklaracija(1), Obrasci(3-4), Stavke(5-7),
        OdgZemlja(9), Zemlje(10-13), Drzave(15-17), Uslovi(20),
        Valuta(22-24), Troskovi, Odgodjeno(48-49)."""
        column = QFrame()
        column.setFrameShape(QFrame.Shape.Box)
        column.setFrameShadow(QFrame.Shadow.Plain)
        column.setLineWidth(2)
        column.setFixedWidth(560)
        column.setObjectName("middle_column")
        column.setAttribute(Qt.WA_StyledBackground, True)
        _win_label_css = (
            "\n    QLabel { font-size: 10pt; color: #102814; font-weight: 600; }"
            if sys.platform.startswith("win") else ""
        )
        column.setStyleSheet(("QFrame#middle_column { background-color: #f2f7f4; }" + _win_label_css + """
    QLineEdit {
        background: #fafcfa;
        border: 1px solid #a0c4a0;
        border-radius: 3px;
        padding: 3px 8px;
        min-height: 22px;
        font-size: 11pt;
        color: #102814;
    }
    QLineEdit:hover   { background: #eef6ec; border-color: #7aa080; }
    QLineEdit:focus   { background: #e8f2e8; border-color: #5a8060; border-width: 2px; }
    QLineEdit:read-only { background: #eef4ee; border-color: #c8dcc8; color: #4a6a4a; }
    QComboBox {
        background: #fafcfa;
        border: 1px solid #a0c4a0;
        border-radius: 3px;
        padding: 3px 8px;
        min-height: 22px;
        font-size: 11pt;
        color: #102814;
    }
    QComboBox:hover { background: #eef6ec; border-color: #7aa080; }
    QComboBox:focus { background: #e8f2e8; border-color: #5a8060; }
    QComboBox::drop-down { border: none; width: 20px; }
    QComboBox::down-arrow {
        __ARROW_CSS__
        width: 14px;
        height: 14px;
        margin-right: 5px;
    }
    QComboBox QAbstractItemView {
        background: #fafcfa;
        border: 1px solid #a0c4a0;
        font-size: 13px;
        selection-background-color: #d4e8d4;
        color: #1e3820;
    }
    QComboBox QAbstractItemView::item {
        padding: 5px 10px;
        min-height: 24px;
    }
""").replace("__ARROW_CSS__", _DOWN_ARROW_CSS))
        layout = QVBoxLayout(column)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2 if sys.platform.startswith("win") else 5)

        layout.addWidget(self._create_deklaracija_group())
        layout.addWidget(self._create_hline())

        layout.addWidget(self._create_obrasci_group())
        layout.addWidget(self._create_hline())

        layout.addWidget(self._create_stavke_group())
        layout.addWidget(self._create_hline())

        layout.addWidget(self._create_odgovorna_zemlja_group())
        layout.addWidget(self._create_hline())

        layout.addWidget(self._create_zem_group())
        layout.addWidget(self._create_hline())

        layout.addWidget(self._create_drzava_izvoza_group())
        layout.addWidget(self._create_hline())

        layout.addWidget(self._create_drzava_porijekla_group())
        layout.addWidget(self._create_hline())

        layout.addWidget(self._create_uslovi_group())
        layout.addWidget(self._create_hline())

        layout.addWidget(self._create_valuta_group())
        layout.addWidget(self._create_hline())

        layout.addWidget(self._create_troski_group())
        layout.addWidget(self._create_hline())

        layout.addWidget(self._create_odgodjeno_group())

        return column

    def _create_deklaracija_group(self) -> QWidget:
        """Rb.1 Deklaracija — dva combo iz baze + ured odredišta (read-only)."""
        self._vrste_dek_map = _load_vrste_deklaracija_from_db()
        ured_sifra, ured_naziv = _load_ured_odredista_from_db()

        group = QWidget()
        layout = QVBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        label = QLabel("1. Deklaracija")
        label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        layout.addWidget(label)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(10, 0, 10, 0)
        row_layout.setSpacing(10)

        # Combo 1: Vrsta deklaracije (IM/EX) — usko polje, širok dropdown
        cb_sifra = _ArrowComboBox()
        cb_sifra.setEditable(True)
        cb_sifra.lineEdit().setReadOnly(True)
        cb_sifra.setFixedWidth(120)
        cb_sifra.view().setMinimumWidth(500)

        for sifra in sorted(self._vrste_dek_map.keys()):
            for oznaka, opis in self._vrste_dek_map[sifra]:
                if oznaka:
                    cb_sifra.addItem(f"{sifra}-{oznaka}: {opis}", sifra)

        def _on_sifra_activated(idx, _cb=cb_sifra):
            sifra = _cb.itemData(idx)
            if sifra:
                self.deklaracija_sifra_changed.emit(sifra)
                _cb.lineEdit().setText(sifra)
                self._populate_oznaka_combo(sifra)

        cb_sifra.activated.connect(_on_sifra_activated)
        cb_sifra.setToolTip("Vrsta deklaracije: IM (uvoz) ili EX (izvoz)")
        row_layout.addWidget(cb_sifra)
        self.field_widgets["deklaracija_1"] = cb_sifra

        # Combo 2: Oznaka (A/Z/B)
        cb_oznaka = _ArrowComboBox()
        cb_oznaka.setEditable(True)
        cb_oznaka.lineEdit().setReadOnly(True)
        cb_oznaka.setFixedWidth(75)
        cb_oznaka.view().setMinimumWidth(500)

        def _on_oznaka_activated(idx, _cb=cb_oznaka):
            _cb.lineEdit().setText(_cb.itemData(idx) or "")

        cb_oznaka.activated.connect(_on_oznaka_activated)
        cb_oznaka.setToolTip("Tip deklaracije: A (potpuna), Z (pojednostavljena), B (periodična)")
        row_layout.addWidget(cb_oznaka)
        self.field_widgets["deklaracija_oznaka"] = cb_oznaka

        # Popuni drugi combo tek nakon što je dodan u field_widgets
        if cb_sifra.count() > 0:
            first_sifra = cb_sifra.itemData(0)
            if first_sifra:
                cb_sifra.lineEdit().setText(first_sifra)
                self._populate_oznaka_combo(first_sifra)

        sep1 = QLabel("|")
        sep1.setStyleSheet("color: #aaa; font-weight: bold; padding: 0 8px;")
        row_layout.addWidget(sep1)

        # Šifra carinske ispostave
        ured_sifra_cb = _ArrowComboBox()
        ured_sifra_cb.setEditable(True)
        ured_sifra_cb.setFixedWidth(115)
        ured_sifra_cb.view().setMinimumWidth(200)
        if ured_sifra:
            ured_sifra_cb.addItem(ured_sifra)
            ured_sifra_cb.setCurrentText(ured_sifra)
        ured_sifra_cb.setToolTip(
            "Šifra carinske ispostave (default: BA097012).\n"
            "Možeš upisati drugu šifru ili odabrati iz padajućeg menija."
        )
        row_layout.addWidget(ured_sifra_cb)
        self.field_widgets["ured_odredista_sifra"] = ured_sifra_cb

        sep2 = QLabel("|")
        sep2.setStyleSheet("color: #aaa; padding: 0 6px;")
        row_layout.addWidget(sep2)

        # Naziv carinske ispostave
        ured_naziv_cb = _ArrowComboBox()
        ured_naziv_cb.setEditable(True)
        ured_naziv_cb.setFixedWidth(140 if sys.platform.startswith("win") else 175)
        ured_naziv_cb.view().setMinimumWidth(300)
        if ured_naziv:
            ured_naziv_cb.addItem(ured_naziv)
            ured_naziv_cb.setCurrentText(ured_naziv)
        ured_naziv_cb.setToolTip(
            "Naziv carinske ispostave (default: CI Bijeljina).\n"
            "Možeš upisati drugi naziv ili odabrati iz padajućeg menija."
        )
        row_layout.addWidget(ured_naziv_cb)
        self.field_widgets["ured_odredista_naziv"] = ured_naziv_cb

        row_layout.addStretch()

        layout.addWidget(row)

        group.setAttribute(Qt.WA_StyledBackground, True)
        group.setProperty("section_card", True)
        return group

    def _populate_oznaka_combo(self, sifra: str):
        """Popuni combo za tip potpunosti deklaracije (A/Z/B), isti za IM i EX."""
        cb = self.field_widgets.get("deklaracija_oznaka")
        if not cb:
            return

        cb.blockSignals(True)
        cb.clear()

        tipovi = _load_tipovi_deklaracija_from_db()
        for sifra_tipa, opis in tipovi:
            cb.addItem(f"{sifra_tipa} — {opis}", sifra_tipa)

        # Default: uvijek A (potpuna deklaracija)
        idx = cb.findData("A")
        if idx >= 0:
            cb.setCurrentIndex(idx)
            cb.lineEdit().setText("A")
        elif cb.count() > 0:
            cb.setCurrentIndex(0)
            cb.lineEdit().setText(cb.itemData(0) or "")

        cb.blockSignals(False)

    def _create_obrasci_group(self) -> QWidget:
        """Rb.3 Obrasci + Rb.4 Tovarni listovi — side-by-side."""
        group = QWidget()
        layout = QHBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # 3. Obrasci
        col3 = QWidget()
        col3_layout = QVBoxLayout(col3)
        col3_layout.setContentsMargins(0, 0, 0, 0)
        col3_layout.setSpacing(3)
        label3 = QLabel("3. Obrasci")
        label3.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        col3_layout.addWidget(label3)

        row3 = QWidget()
        row3_layout = QHBoxLayout(row3)
        row3_layout.setContentsMargins(0, 0, 0, 0)
        row3_layout.setSpacing(5)
        for i in [1, 2]:
            field = QLineEdit()
            field.setPlaceholderText(str(i))
            field.setFixedWidth(40)
            row3_layout.addWidget(field)
            self.field_widgets[f"obrazac_{i}"] = field
        row3_layout.addStretch()
        col3_layout.addWidget(row3)
        layout.addWidget(col3)

        # 4. Tovarni listovi
        col4 = QWidget()
        col4_layout = QVBoxLayout(col4)
        col4_layout.setContentsMargins(0, 0, 0, 0)
        col4_layout.setSpacing(3)
        label4 = QLabel("4. Tovarni listovi")
        label4.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        col4_layout.addWidget(label4)
        field4 = QLineEdit()
        field4.setPlaceholderText("Broj")
        field4.setFixedWidth(40)
        col4_layout.addWidget(field4)
        self.field_widgets["tovarni_listovi"] = field4
        layout.addWidget(col4)

        group.setAttribute(Qt.WA_StyledBackground, True)
        group.setProperty("section_card", True)
        return group

    def _create_stavke_group(self) -> QWidget:
        """Rb.5 Naim. / Rb.6 Uk.paketa / Rb.7 Ref.br — side-by-side."""
        group = QWidget()
        layout = QHBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)

        # 5. Naim.
        col5 = QWidget()
        col5_l = QVBoxLayout(col5)
        col5_l.setContentsMargins(0, 0, 0, 0)
        col5_l.setSpacing(3)
        lbl5 = QLabel("5. Naim.")
        lbl5.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        col5_l.addWidget(lbl5)
        field5 = QLineEdit()
        field5.setFixedWidth(80)
        col5_l.addWidget(field5)
        self.field_widgets["stavke"] = field5
        layout.addWidget(col5)

        # 6. Uk. paketa
        col6 = QWidget()
        col6_l = QVBoxLayout(col6)
        col6_l.setContentsMargins(0, 0, 0, 0)
        col6_l.setSpacing(3)
        lbl6 = QLabel("6. Uk. paketa")
        lbl6.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        col6_l.addWidget(lbl6)
        field6 = QLineEdit()
        field6.setFixedWidth(110)
        col6_l.addWidget(field6)
        self.field_widgets["uk_paketa"] = field6
        layout.addWidget(col6)

        # 7. Ref.br — godina (auto) + broj (editabilno)
        col7 = QWidget()
        col7_l = QVBoxLayout(col7)
        col7_l.setContentsMargins(0, 0, 0, 0)
        col7_l.setSpacing(3)
        lbl7 = QLabel("7. Ref.br")
        lbl7.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        col7_l.addWidget(lbl7)

        ref_row = QWidget()
        ref_row_l = QHBoxLayout(ref_row)
        ref_row_l.setContentsMargins(0, 0, 0, 0)
        ref_row_l.setSpacing(6)

        field7_godina = QLineEdit(str(date.today().year))
        field7_godina.setFixedWidth(65)
        field7_godina.setReadOnly(True)
        field7_godina.setStyleSheet("color: #666; background: #f5f5f5;")
        field7_godina.setToolTip("Godina (automatski)")
        ref_row_l.addWidget(field7_godina)
        self.field_widgets["ref_br_godina"] = field7_godina

        field7 = QLineEdit()
        field7.setFixedWidth(140)
        field7.setToolTip("Referentni broj deklaracije")
        ref_row_l.addWidget(field7)

        col7_l.addWidget(ref_row)
        self.field_widgets["ref_br"] = field7
        layout.addWidget(col7)

        group.setAttribute(Qt.WA_StyledBackground, True)
        group.setProperty("section_card", True)
        return group

    def _create_odgovorna_zemlja_group(self) -> QWidget:
        """Rb.9 Odgovorna zemlja — 4 polja u jednom redu."""
        group = QWidget()
        layout = QVBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        label = QLabel("9. Odgovorna zemlja / Podaci")
        label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        layout.addWidget(label)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(3)

        field1 = QLineEdit()
        field1.setFixedWidth(40)
        row_layout.addWidget(field1)
        self.field_widgets["odg_zemlja_1"] = field1

        for i in range(2, 5):
            field = QLineEdit()
            row_layout.addWidget(field)
            self.field_widgets[f"odg_zemlja_{i}"] = field

        layout.addWidget(row)
        group.setAttribute(Qt.WA_StyledBackground, True)
        group.setProperty("section_card", True)
        return group

    def _create_zem_group(self) -> QWidget:
        """Rb.10-13 Zemlje — 4 kolone side-by-side."""
        group = QWidget()
        layout = QHBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        for num, lbl in [
            (10, "Zem.otp."),
            (11, "Trgov.zem."),
            (12, "Vrijednost"),
            (13, "CAP"),
        ]:
            col = QWidget()
            col_layout = QVBoxLayout(col)
            col_layout.setContentsMargins(0, 0, 0, 0)
            col_layout.setSpacing(3)
            label = QLabel(f"{num}. {lbl}")
            label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            col_layout.addWidget(label)
            field = QLineEdit()
            field.setPlaceholderText(str(num))
            col_layout.addWidget(field)
            self.field_widgets[f"zem_{num}"] = field
            layout.addWidget(col)

        group.setAttribute(Qt.WA_StyledBackground, True)
        group.setProperty("section_card", True)
        return group

    def _create_drzava_izvoza_group(self) -> QWidget:
        """Rb.15 Država izvoza (naziv + šifra) + Rb.17 šifra odredišta — side-by-side."""
        group = QWidget()
        layout = QVBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(5)

        # 15 naziv
        col15 = QWidget()
        col15_layout = QVBoxLayout(col15)
        col15_layout.setContentsMargins(0, 0, 0, 0)
        col15_layout.setSpacing(3)
        label15 = QLabel("15. Država izvoza")
        label15.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        col15_layout.addWidget(label15)
        field15 = QLineEdit()
        field15.setPlaceholderText("Naziv")
        field15.setMinimumWidth(160)
        field15.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        col15_layout.addWidget(field15)
        self.field_widgets["drzava_izvoza_naziv"] = field15
        row_layout.addWidget(col15, stretch=1)

        # 15 šifra
        col15s = QWidget()
        col15s_layout = QVBoxLayout(col15s)
        col15s_layout.setContentsMargins(0, 0, 0, 0)
        col15s_layout.setSpacing(3)
        label15s = QLabel("15. Šifra")
        label15s.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        col15s_layout.addWidget(label15s)
        field15s = QLineEdit()
        field15s.setPlaceholderText("RS")
        field15s.setFixedWidth(55)
        col15s_layout.addWidget(field15s)
        self.field_widgets["drzava_izvoza_sifra"] = field15s
        row_layout.addWidget(col15s)

        # 17 šifra odredišta
        col17s = QWidget()
        col17s_layout = QVBoxLayout(col17s)
        col17s_layout.setContentsMargins(0, 0, 0, 0)
        col17s_layout.setSpacing(3)
        label17s = QLabel("17. Šifra")
        label17s.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        col17s_layout.addWidget(label17s)
        field17s = QLineEdit()
        field17s.setPlaceholderText("BA")
        field17s.setFixedWidth(55)
        col17s_layout.addWidget(field17s)
        self.field_widgets["drzava_odredista_sifra"] = field17s
        row_layout.addWidget(col17s)

        layout.addWidget(row)
        group.setAttribute(Qt.WA_StyledBackground, True)
        group.setProperty("section_card", True)
        return group

    def _create_drzava_porijekla_group(self) -> QWidget:
        """Rb.16 Država porijekla + Rb.17 Država odredišta naziv — side-by-side."""
        group = QWidget()
        layout = QHBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 16
        col16 = QWidget()
        col16_layout = QVBoxLayout(col16)
        col16_layout.setContentsMargins(0, 0, 0, 0)
        col16_layout.setSpacing(3)
        label16 = QLabel("16. Država porijekla")
        label16.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        col16_layout.addWidget(label16)
        field16 = QLineEdit()
        field16.setPlaceholderText("Naziv")
        col16_layout.addWidget(field16)
        self.field_widgets["drzava_porijekla"] = field16
        layout.addWidget(col16)

        # 17 naziv odredišta
        col17 = QWidget()
        col17_layout = QVBoxLayout(col17)
        col17_layout.setContentsMargins(0, 0, 0, 0)
        col17_layout.setSpacing(3)
        label17 = QLabel("17. Država odredišta")
        label17.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        col17_layout.addWidget(label17)
        field17 = QLineEdit()
        field17.setPlaceholderText("Naziv")
        col17_layout.addWidget(field17)
        self.field_widgets["drzava_odredista_naziv"] = field17
        layout.addWidget(col17)

        group.setAttribute(Qt.WA_StyledBackground, True)
        group.setProperty("section_card", True)
        return group

    def _create_uslovi_group(self) -> QWidget:
        """Rb.20 Uslovi isporuke — kod fixedW50 + mjesto u jednom redu."""
        group = QWidget()
        layout = QVBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        label = QLabel("20. Uslovi isporuke")
        label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        layout.addWidget(label)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(5)

        field1 = QLineEdit()
        field1.setPlaceholderText("CPT")
        field1.setFixedWidth(70)
        row_layout.addWidget(field1)
        self.field_widgets["uslovi_kod"] = field1

        field2 = QLineEdit()
        field2.setPlaceholderText("Mjesto")
        row_layout.addWidget(field2)
        self.field_widgets["uslovi_mjesto"] = field2

        layout.addWidget(row)
        group.setAttribute(Qt.WA_StyledBackground, True)
        group.setProperty("section_card", True)
        return group

    def _create_valuta_group(self) -> QWidget:
        """Rb.22-24 Valuta, Iznos, Kurs, Vrsta transakcije — side-by-side."""
        group = QWidget()
        layout = QVBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(5)

        # 22 Valuta (QLineEdit sa regex validatorom)
        col22v = QWidget()
        col22v_layout = QVBoxLayout(col22v)
        col22v_layout.setContentsMargins(0, 0, 0, 0)
        col22v_layout.setSpacing(3)
        label22v = QLabel("22. Valuta")
        label22v.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        col22v_layout.addWidget(label22v)
        field22v = QLineEdit()
        field22v.setPlaceholderText("EUR")
        field22v.setFixedWidth(70)
        if not sys.platform.startswith("win"):
            field22v.setMinimumHeight(32)
        validator = QRegularExpressionValidator(QRegularExpression("^[A-Z]{3}$"))
        field22v.setValidator(validator)
        col22v_layout.addWidget(field22v)
        self.field_widgets["valuta"] = field22v
        field22v.editingFinished.connect(
            lambda: self.valuta_changed.emit(field22v.text().strip().upper())
        )
        row_layout.addWidget(col22v)

        # 22 Ukupan Iznos
        col22i = QWidget()
        col22i_layout = QVBoxLayout(col22i)
        col22i_layout.setContentsMargins(0, 0, 0, 0)
        col22i_layout.setSpacing(3)
        label22i = QLabel("22. Ukupan iznos fakture")
        label22i.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        col22i_layout.addWidget(label22i)
        field22i = QLineEdit()
        field22i.setPlaceholderText("0.00")
        field22i.setMinimumWidth(140)
        if not sys.platform.startswith("win"):
            field22i.setMinimumHeight(32)
        field22i.setAlignment(Qt.AlignmentFlag.AlignRight)
        col22i_layout.addWidget(field22i)
        self.field_widgets["iznos"] = field22i
        row_layout.addWidget(col22i, 1)

        # 23 Kurs
        col23 = QWidget()
        col23_layout = QVBoxLayout(col23)
        col23_layout.setContentsMargins(0, 0, 0, 0)
        col23_layout.setSpacing(3)
        label23 = QLabel("23. Kurs")
        label23.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        col23_layout.addWidget(label23)
        field23 = QLineEdit()
        field23.setPlaceholderText("1.00")
        field23.setFixedWidth(80)
        col23_layout.addWidget(field23)
        self.field_widgets["kurs"] = field23
        row_layout.addWidget(col23)

        # 24 Vrsta transakcije (2 mala polja)
        col24 = QWidget()
        col24_layout = QVBoxLayout(col24)
        col24_layout.setContentsMargins(0, 0, 0, 0)
        col24_layout.setSpacing(3)
        label24 = QLabel("24. Vrsta trans.")
        label24.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        col24_layout.addWidget(label24)
        row24 = QWidget()
        row24_layout = QHBoxLayout(row24)
        row24_layout.setContentsMargins(0, 0, 0, 0)
        row24_layout.setSpacing(5)
        for i in [1, 2]:
            field = QLineEdit()
            field.setPlaceholderText(str(i))
            field.setFixedWidth(30)
            row24_layout.addWidget(field)
            self.field_widgets[f"vrsta_trans_{i}"] = field
        col24_layout.addWidget(row24)
        row_layout.addWidget(col24)

        layout.addWidget(row)
        group.setAttribute(Qt.WA_StyledBackground, True)
        group.setProperty("section_card", True)
        return group

    def _create_troski_group(self) -> QWidget:
        """Troškovi transporta — 5 redova sa specifičnim nazivima."""
        group = QWidget()
        group.setObjectName("troski_group")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        troskovi = [
            "prevoz do granice",
            "osiguranje",
            "ostali troškovi / dodaci",
            "unutrašnji zavisni troškovi",
            "popusti",
        ]

        for i, naziv in enumerate(troskovi, 1):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(10)

            field_val = QLineEdit("0,00")
            field_val.setFixedWidth(80)
            field_val.setAlignment(Qt.AlignmentFlag.AlignRight)
            field_val.setObjectName(f"trosak_{i}")
            row_layout.addWidget(field_val)
            self.field_widgets[f"trosak_{i}"] = field_val

            # Valuta dropdown — samo za trosak_1 (prevoz do granice)
            if i == 1:
                cb_valuta = _ArrowComboBox()
                cb_valuta.addItems(["BAM", "EUR"])
                cb_valuta.setFixedWidth(60)
                cb_valuta.setObjectName("trosak_1_valuta")
                cb_valuta.setToolTip("Valuta prevoza do granice")
                row_layout.addWidget(cb_valuta)
                self.field_widgets["trosak_1_valuta"] = cb_valuta

            label_naziv = QLabel(naziv)
            label_naziv.setStyleSheet("font-size: 10pt; color: #333333;")
            row_layout.addWidget(label_naziv)
            row_layout.addStretch()

            layout.addWidget(row)

        group.setAttribute(Qt.WA_StyledBackground, True)
        group.setProperty("section_card", True)
        return group

    def _create_odgodjeno_group(self) -> QWidget:
        """Rb.48-49 Odgođeno plaćanje + Skladište — side-by-side, oba QLineEdit."""
        group = QWidget()
        layout = QHBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 48
        col48 = QWidget()
        col48_layout = QVBoxLayout(col48)
        col48_layout.setContentsMargins(0, 0, 0, 0)
        col48_layout.setSpacing(3)
        label48 = QLabel("48. odgođeno plaćanje")
        label48.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        col48_layout.addWidget(label48)
        field48 = QLineEdit()
        field48.setPlaceholderText("Odgođeno")
        col48_layout.addWidget(field48)
        self.field_widgets["odgodjeno_placanje"] = field48
        layout.addWidget(col48)

        # 49
        col49 = QWidget()
        col49_layout = QVBoxLayout(col49)
        col49_layout.setContentsMargins(0, 0, 0, 0)
        col49_layout.setSpacing(3)
        label49 = QLabel("49. identifikacija skladišta")
        label49.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        col49_layout.addWidget(label49)
        field49 = QLineEdit()
        field49.setPlaceholderText("Skladište")
        col49_layout.addWidget(field49)
        self.field_widgets["identifikacija_skladista"] = field49
        layout.addWidget(col49)

        group.setAttribute(Qt.WA_StyledBackground, True)
        group.setProperty("section_card", True)
        return group

    # ============================================================
    # DESNA KOLONA
    # ============================================================

    def _create_right_column(self) -> QFrame:
        """Desna kolona: samo tabela Priložene isprave (Rub.44)."""
        column = QFrame()
        column.setFrameShape(QFrame.Shape.Box)
        column.setFrameShadow(QFrame.Shadow.Plain)
        column.setLineWidth(2)
        column.setObjectName("right_column")
        column.setAttribute(Qt.WA_StyledBackground, True)
        column.setMinimumWidth(420)
        column.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        column.setStyleSheet(("QFrame#right_column { background-color: #eef5f1; }" + """
    QLineEdit {
        background: #fafcfa;
        border: 1px solid #a0c4a0;
        border-radius: 3px;
        padding: 3px 8px;
        min-height: 28px;
        color: #1e3820;
    }
    QLineEdit:hover   { background: #eef6ec; border-color: #7aa080; }
    QLineEdit:focus   { background: #e8f2e8; border-color: #5a8060; border-width: 2px; }
    QLineEdit:read-only { background: #eef4ee; border-color: #c8dcc8; color: #4a6a4a; }
    QComboBox {
        background: #fafcfa;
        border: 1px solid #a0c4a0;
        border-radius: 3px;
        padding: 3px 8px;
        min-height: 28px;
        font-size: 13px;
        color: #1e3820;
    }
    QComboBox:hover { background: #eef6ec; border-color: #7aa080; }
    QComboBox:focus { background: #e8f2e8; border-color: #5a8060; }
    QComboBox::drop-down { border: none; width: 20px; }
    QComboBox::down-arrow {
        __ARROW_CSS__
        width: 14px;
        height: 14px;
        margin-right: 5px;
    }
    QComboBox QAbstractItemView {
        background: #fafcfa;
        border: 1px solid #a0c4a0;
        font-size: 13px;
        selection-background-color: #d4e8d4;
        color: #1e3820;
    }
    QComboBox QAbstractItemView::item {
        padding: 5px 10px;
        min-height: 24px;
    }
""").replace("__ARROW_CSS__", _DOWN_ARROW_CSS))
        layout = QVBoxLayout(column)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        # QTableWidget(20, 4)
        self.table = QTableWidget(20, 3)
        self.table.setHorizontalHeaderLabels(
            ["Šifra", "Naziv dokumenta", "Referenca"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(
            """
            QTableWidget {
                font-size: 13pt;
                color: #18354a;
                background-color: #ffffff;
                alternate-background-color: #eef4f7;
                gridline-color: #c9d5de;
                border: 1px solid #9fb2c1;
                border-radius: 4px;
            }
            QTableWidget::item {
                color: #18354a;
                padding: 3px 6px;
            }
            QTableWidget::item:hover {
                background-color: #dfeaf1;
            }
            QTableWidget::item:selected {
                background-color: #2c668f;
                color: #ffffff;
            }
            QHeaderView::section {
                font-size: 13pt;
                font-weight: bold;
                color: #18354a;
                background-color: #dfeaf1;
                border: none;
                border-right: 1px solid #c8d7e2;
                border-bottom: 2px solid #7892a5;
                padding: 4px;
            }
            """
        )

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 65)

        self._col_ratio_filter = _ColRatioFilter(self)
        self.table.installEventFilter(self._col_ratio_filter)

        for i in range(20):
            self.table.setRowHeight(i, 32)

        # Minimalna visina — spriječava skupljanje prozora pri setRowCount(0),
        # ali dozvoljava rast kad je prozor maksimiziran.
        self.table.setMinimumHeight(20 * 32 + self.table.horizontalHeader().height())
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Tipkovnica: bilo koji znak otvara editor, Tab prelazi na sljedeću ćeliju
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.DoubleClicked |
            QTableWidget.EditTrigger.AnyKeyPressed |
            QTableWidget.EditTrigger.SelectedClicked
        )
        self.table.setTabKeyNavigation(True)

        # IspravaDelegate na koloni 0
        self._isprave = _load_isprave_from_db()
        if self._isprave:
            self.table.setItemDelegateForColumn(
                0, IspravaDelegate(self._isprave, self.table)
            )

        # Delete tipka i desni klik — brisanje reda
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_docs_table_context_menu)
        self.table.installEventFilter(self)

        layout.addWidget(self.table)

        return column

    # ============================================================
    # HELPER
    # ============================================================

    def eventFilter(self, obj, event):
        """Delete tipka na tabeli priloženih dokumenata briše sadržaj reda."""
        if obj is self.table and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Delete:
                self._clear_selected_doc_rows()
                return True
        return super().eventFilter(obj, event)

    def _on_docs_table_context_menu(self, pos):
        """Desni klik na tabeli priloženih dokumenata — kontekstni meni."""
        menu = QMenu(self)
        act_clear = menu.addAction("Obriši red")
        act_clear_all = menu.addAction("Obriši sve redove")
        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action == act_clear:
            self._clear_selected_doc_rows()
        elif action == act_clear_all:
            self._clear_all_doc_rows()

    def _clear_selected_doc_rows(self):
        """Obriši sadržaj odabranih redova u tabeli priloženih dokumenata."""
        rows = {idx.row() for idx in self.table.selectedIndexes()}
        for row in rows:
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item:
                    item.setText("")
            self.table.setRowHeight(row, 32)

    def _clear_all_doc_rows(self):
        """Obriši sadržaj svih redova u tabeli priloženih dokumenata."""
        for row in range(self.table.rowCount()):
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item:
                    item.setText("")

    def _create_hline(self) -> QFrame:
        """Horizontalna linija separator."""
        line = QFrame()
        if sys.platform.startswith("win"):
            line.setFixedHeight(3)
            line.setStyleSheet("background-color: #b8ccb8;")
        else:
            line.setFrameShape(QFrame.Shape.HLine)
            line.setFrameShadow(QFrame.Shadow.Plain)
            line.setLineWidth(1)
            line.setFixedHeight(6)
        return line

    # ============================================================
    # SIGNALS CONNECTIONS
    # ============================================================

    def _connect_signals(self):
        """Poveži signale dugmadi."""
        self.btn_novi.clicked.connect(self.new_requested.emit)
        self.btn_import.clicked.connect(self._on_import_clicked)
        self.btn_snimi.clicked.connect(self.validation_requested.emit)
        self.btn_brisi.clicked.connect(self.delete_requested.emit)
        self.btn_izvezi.clicked.connect(self.export_xml_requested.emit)

    def _on_import_clicked(self):
        geometry_state = capture_window_geometry(self)
        try:
            filename, _ = QFileDialog.getOpenFileName(
                self, "Uvezi XML datoteku", "", "XML Files (*.xml);;All Files (*)"
            )
            if filename:
                self.import_xml_requested.emit(filename)
        finally:
            restore_window_geometry_queued(geometry_state)

    # ============================================================
    # STYLES
    # ============================================================

    def _apply_styles(self):
        """Primijeni Qt stylesheet — identičan originalu."""
        self.setStyleSheet(
            """
            /* POZADINA */
            #ZaglavljeTab {
                background-color: #e8f2ed;
            }

            /* KOLONE — bijela pozadina sa sage zelenim okvirom */
            #left_column, #middle_column, #right_column {
                border: 1px solid #a7c5b5;
                border-radius: 5px;
            }

            /* SEKCIJA KARTICE — bijele kartice sa zaobljenim uglovima */
            QWidget[section_card="true"] {
                background-color: #f8fffb;
                border: 1px solid #bed2c7;
                border-radius: 6px;
                padding: 2px 4px;
            }
            #left_column QWidget[section_card="true"] {
                padding: 0px 2px;
                border-radius: 4px;
            }
            #middle_column QWidget[section_card="true"] {
                padding: 0px 1px;
                border-radius: 3px;
                background-color: #fbfefc;
            }

            /* HORIZONTALNI SEPARATORI — tanka sage linija između sekcija */
            QFrame[frameShape="4"] {
                background-color: #b8cec1;
                border: none;
                max-height: 1px;
                min-height: 1px;
                margin-top: 0px;
                margin-bottom: 0px;
            }

            /* TOOLBAR */
            QFrame#toolbar {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #f4f7fa, stop:1 #e7eef4);
                border-top: 1px solid #c8d5df;
                border-bottom: 2px solid #7892a5;
            }

            /* BUTTONS */
            QPushButton#btnNovi {
                background-color: #2f6f9f;
                border: 1px solid #285f88;
                border-radius: 5px;
                padding: 0px 14px;
                color: white; font-weight: 600; font-size: 13px;
            }
            QPushButton#btnNovi:hover {
                background-color: #3d82b7;
            }
            QPushButton#btnNovi:pressed {
                background-color: #245779;
            }
            QPushButton#btnUveziXML {
                background-color: #6a55a3;
                border: 1px solid #59468c;
                border-radius: 5px;
                padding: 0px 14px;
                color: white; font-weight: 600; font-size: 13px;
            }
            QPushButton#btnUveziXML:hover {
                background-color: #7b65b5;
            }
            QPushButton#btnUveziXML:pressed {
                background-color: #493875;
            }
            QPushButton#btnSnimi {
                background-color: #2f7d5a;
                border: 1px solid #28694c;
                border-radius: 5px;
                padding: 0px 14px;
                color: white; font-weight: 700; font-size: 13px;
            }
            QPushButton#btnSnimi:hover {
                background-color: #3c936c;
            }
            QPushButton#btnSnimi:pressed {
                background-color: #245f45;
            }
            QPushButton#btnBrisi {
                background-color: #a6403d;
                border: 1px solid #8e3432;
                border-radius: 5px;
                padding: 0px 14px;
                color: white; font-weight: 600; font-size: 13px;
            }
            QPushButton#btnBrisi:hover {
                background-color: #b9514d;
            }
            QPushButton#btnBrisi:pressed {
                background-color: #85322f;
            }
            QPushButton#btnIzveziXML {
                background-color: #2f6f6a;
                border: 1px solid #285f5b;
                border-radius: 5px;
                padding: 0px 14px;
                color: white; font-weight: 600; font-size: 13px;
            }
            QPushButton#btnIzveziXML:hover {
                background-color: #3d8780;
            }
            QPushButton#btnIzveziXML:pressed {
                background-color: #245753;
            }
            QPushButton#btnIzlaz {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #fafafa, stop:1 #e0e0e0);
                border: 1px solid #999;
                border-bottom: 3px solid #666;
                border-radius: 3px;
                padding: 0px 14px;
                color: black; font-weight: 600; font-size: 12px;
            }
            QPushButton#btnIzlaz:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffffff, stop:1 #eeeeee);
                border: 1px solid #777;
                border-bottom: 3px solid #444;
            }
            QPushButton#btnIzlaz:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #bdbdbd, stop:1 #9e9e9e);
                border: 1px solid #666;
                border-top: 3px solid #444;
                border-bottom: 1px solid #666;
                color: white;
            }

            /* INPUT FIELDS — krem pozadina za lako uočavanje */
            QLineEdit {
                background: #fafcfa;
                border: 1px solid #a0c4a0;
                border-radius: 3px;
                padding: 1px 6px;
                font-size: 11pt;
                min-height: 22px;
                color: #102814;
            }
            QLineEdit:hover { border-color: #7aa080; background: #eef6ec; }
            QLineEdit:focus { background: #e8f2e8; border-color: #5a8060; border-width: 2px; }
            QLineEdit:read-only { background: #eef4ee; border-color: #c8dcc8; color: #4a6a4a; }

            QComboBox {
                background: #fafcfa;
                border: 1px solid #a0c4a0;
                border-radius: 3px;
                padding: 1px 6px;
                font-size: 11pt;
                min-height: 22px;
                color: #102814;
            }
            QComboBox:hover { border-color: #7aa080; background: #eef6ec; }
            QComboBox:focus { background: #e8f2e8; border-color: #5a8060; }
            QComboBox::drop-down { border: none; width: 20px; }
            QComboBox::down-arrow {
                __ARROW_CSS__
                width: 14px;
                height: 14px;
                margin-right: 5px;
            }
            QComboBox QAbstractItemView {
                background: #fafcfa;
                border: 1px solid #a0c4a0;
                selection-background-color: #d4e8d4;
                color: #1e3820;
            }

            /* LABELE */
            QLabel {
                color: #102814;
                font-size: 10pt;
                background: transparent;
            }
            QLabel#section_title {
                color: #245f45;
                font-size: 10pt;
                font-weight: 700;
                padding-bottom: 1px;
                border-bottom: 2px solid #6f9a7d;
            }
            #left_column QLabel#section_title {
                font-size: 10pt;
                padding-top: 0px;
                padding-bottom: 0px;
                min-height: 21px;
                max-height: 23px;
            }
            #left_column QLineEdit {
                font-size: 10pt;
                min-height: 19px;
                padding: 0px 6px;
            }
            #left_column QLineEdit#company_address_field {
                font-size: 10pt;
                min-height: 23px;
                padding: 0px 6px;
            }
            #left_column QComboBox {
                font-size: 10pt;
                min-height: 19px;
                padding: 0px 6px;
            }
            #left_column QCheckBox {
                font-size: 10pt;
            }
            QCheckBox {
                color: #102814;
                font-size: 11pt;
                background: transparent;
            }
            QCheckBox::indicator {
                width: 16px; height: 16px;
                border: 1px solid #a0c4a0;
                border-radius: 3px;
                background: white;
            }
            QCheckBox::indicator:checked {
                background: #5a8060;
                border-color: #3d6040;
            }

            /* SCROLLBARS */
            QScrollBar:vertical {
                background: #f0f7f0;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #a0c4a0;
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover { background: #7aa080; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar:horizontal {
                background: #f0f7f0;
                height: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal {
                background: #a0c4a0;
                border-radius: 4px;
                min-width: 20px;
            }
            QScrollBar::handle:horizontal:hover { background: #7aa080; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

            /* TABLE */
            QTableWidget {
                background: #ffffff;
                alternate-background-color: #eef4f7;
                border: 1px solid #9fb2c1;
                gridline-color: #c9d5de;
                color: #18354a;
            }
            QTableWidget::item { padding: 4px; color: #18354a; }
            QTableWidget::item:hover { background: #dfeaf1; }
            QTableWidget::item:selected {
                background: #2c668f;
                color: #ffffff;
            }
            QHeaderView::section {
                background: #dfeaf1;
                border: none;
                border-right: 1px solid #c8d7e2;
                border-bottom: 2px solid #7892a5;
                padding: 4px;
                font-weight: bold;
                font-size: 9pt;
                color: #18354a;
            }
            """.replace("__ARROW_CSS__", _DOWN_ARROW_CSS)
        )

    # ============================================================
    # HELPER METHODS
    # ============================================================

    def _with_line_edit_writable(self, widget: QLineEdit, action) -> None:
        was_readonly = widget.isReadOnly()
        if was_readonly:
            widget.setReadOnly(False)
        try:
            action()
        finally:
            if was_readonly:
                widget.setReadOnly(True)

    def _set_line_edit_text(self, widget: QLineEdit, value: Any) -> None:
        self._with_line_edit_writable(
            widget,
            lambda: widget.setText(str(value) if value is not None else ""),
        )

    def _clear_line_edit(self, widget: QLineEdit) -> None:
        self._with_line_edit_writable(widget, widget.clear)

    # ============================================================
    # DATA METHODS
    # ============================================================

    def get_data(self) -> Dict[str, Any]:
        """Ekstraktuj podatke iz widgeta."""
        data = {}
        for key, widget in self.field_widgets.items():
            if isinstance(widget, QLineEdit):
                data[key] = widget.text()
            elif isinstance(widget, QComboBox):
                # Za editable combo-e, currentText() može biti prazan —
                # koristi currentData() ako postoji, pa currentText() kao fallback
                item_data = widget.currentData()
                item_text = widget.currentText()
                data[key] = item_data if item_data is not None else item_text
                data[f"{key}_data"] = item_data
            elif isinstance(widget, QCheckBox):
                data[key] = widget.isChecked()

        # Tabela priloženih dokumenata — čitaj redove sa podacima
        if self.table:
            attached_docs = []
            for row in range(self.table.rowCount()):
                code_item = self.table.item(row, 0)
                name_item = self.table.item(row, 1)
                ref_item = self.table.item(row, 2)
                code = code_item.text() if code_item else ""
                name = name_item.text() if name_item else ""
                number = ref_item.text() if ref_item else ""
                if code:  # Samo redovi sa šifrom
                    attached_docs.append({
                        "code": code,
                        "name": name,
                        "number": number,
                        "from_rule": False,
                    })
            data["attached_documents"] = attached_docs

        return data

    def set_data(self, data: Dict[str, Any], _from_import: bool = False):
        """Popuni widgete podacima."""
        for key, value in data.items():
            if key == 'attached_documents':
                # Priložene isprave — popuni tabelu i sačuvaj snapshot iz importa
                self._import_attached_docs = [dict(d) for d in value] if value else []
                self._populate_attached_table(value, clear_refs_on_import=_from_import)
                continue
            widget = self.field_widgets.get(key)
            if widget is None:
                continue
            if isinstance(widget, QLineEdit):
                self._set_line_edit_text(widget, value)
            elif isinstance(widget, QComboBox):
                idx = widget.findData(value)
                if idx >= 0:
                    widget.setCurrentIndex(idx)
                else:
                    idx = widget.findText(str(value))
                    if idx >= 0:
                        widget.setCurrentIndex(idx)
                    elif widget.isEditable():
                        widget.setEditText(str(value) if value is not None else "")
                # Rb.1 combo 1 — prikaži samo šifru (IM/EX) i popuni combo 2
                if key == 'deklaracija_1' and widget.isEditable():
                    widget.lineEdit().setText(str(value) if value is not None else "")
                    self._populate_oznaka_combo(str(value) if value is not None else "")
                # Rb.1 combo 2 — prikaži samo oznaku (A/Z/B) u lineedit-u
                elif key == 'deklaracija_oznaka' and widget.isEditable():
                    oznaka_idx = widget.findData(value)
                    if oznaka_idx >= 0:
                        widget.setCurrentIndex(oznaka_idx)
                    widget.lineEdit().setText(str(value) if value is not None else "")
                # Rb.25/26 — u polju prikaži samo šifru, ne cijeli dropdown tekst
                elif key in ('vid_25', 'vid_26') and widget.isEditable():
                    code = widget.currentData()
                    if code:
                        widget.lineEdit().setText(str(code))
            elif isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))

    def get_import_attached_docs(self) -> List[Dict[str, Any]]:
        """Vrati snapshot priloženih dokumenata iz zadnjeg XML import-a."""
        return list(self._import_attached_docs)

    def _populate_attached_table(self, attached_docs: list, clear_refs_on_import: bool = False):
        """Popuni tabelu priloženih dokumenata.

        Args:
            attached_docs: Lista dokumenata
            clear_refs_on_import: True samo pri uvozu XML-a — briše stare reference
                                  za sve osim DIS/N380/OST/PE. Pri load_from_draft
                                  uvijek False — čuvaju se sve reference.
        """
        if not self.table:
            return
        if not attached_docs:
            return

        # Osiguraj dovoljno redova — bez toga setItem na nepostojećem redu tiho propada
        needed = min(max(len(attached_docs), self.table.rowCount()), 20)
        if self.table.rowCount() < needed:
            self.table.setRowCount(needed)

        # Očisti sadržaj bez mijenjanja broja redova — sprečava skupljanje prozora
        for row in range(self.table.rowCount()):
            for col in range(self.table.columnCount()):
                self.table.setItem(row, col, QTableWidgetItem(""))
            self.table.setRowHeight(row, 32)

        for idx, doc in enumerate(attached_docs):
            if idx >= 20:
                break  # Maksimalno 20 redova
            code = doc.get('code', '')
            name = doc.get('name', '')
            number = doc.get('number', '')
            user_entered = doc.get('_user_entered', False)

            # Kolona 0 — Šifra
            code_item = QTableWidgetItem(code)
            self.table.setItem(idx, 0, code_item)

            # Kolona 1 — Naziv dokumenta
            name_item = QTableWidgetItem(name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(idx, 1, name_item)

            # Kolona 2 — Referenca
            # Pri XML uvozu: brišemo stale ref-ove osim za DIS/N380/OST/PE i korisničkih unosa
            # Pri load_from_draft: uvijek čuvamo što je u draftu
            if clear_refs_on_import and code not in self._PRESERVE_REFS and not user_entered:
                ref_item = QTableWidgetItem("")
            else:
                ref_item = QTableWidgetItem(number)

            self.table.setItem(idx, 2, ref_item)

    def clear_data(self):
        """Očisti sve podatke iz widgeta."""
        for widget in self.field_widgets.values():
            if isinstance(widget, QLineEdit):
                self._clear_line_edit(widget)
            elif isinstance(widget, QComboBox):
                widget.setCurrentIndex(0)
            elif isinstance(widget, QCheckBox):
                widget.setChecked(False)

        if self.table:
            self.table.clearContents()

        self.data_changed.emit()

    def clear_form(self):
        """Implementacija BaseTabView.clear_form() - delegira na clear_data()."""
        self.clear_data()
