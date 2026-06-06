import logging
logger = logging.getLogger(__name__)
"""
Tariff Search Dialog

Dialog za ručnu pretragu tarifnih stavova iz zvanične tarife.
"""

import re
from typing import Optional

# Skida sufiks sa tarifnim stopama: "– 10 0 0 10 0 0 0 0" ili "kd 10 0 0 8 0 0 0 0"
_TAIL_RATES_RE = re.compile(r'(?:\s+\w{1,3})?(?:\s+\d+){4,}\s*$')

from database.db import get_db_connection

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QFrame,
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont

_INITIAL_LIMIT = 200
_SEARCH_LIMIT = 300


class TariffSearchDialog(QDialog):
    """
    Dialog za ručnu pretragu tarifnih stavova.

    Pretražuje tabelu `zvanicna_tarifa` po kodu ili opisu.
    Vraća odabrani tarifni broj putem get_selected_code().
    """

    tariff_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pretraga tarifnih stavova")
        self.setMinimumSize(720, 520)
        self.resize(820, 580)
        self.setModal(True)

        self._selected_code: Optional[str] = None
        self._total_count = self._get_total_count()

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._do_search)

        self._setup_ui()
        self._do_search()  # inicijalno učitavanje

    # ------------------------------------------------------------------ #
    #  UI setup                                                            #
    # ------------------------------------------------------------------ #

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        # --- Search row ---
        search_row = QHBoxLayout()
        search_icon = QLabel("🔍")
        search_icon.setFixedWidth(22)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Unesite tarifni broj ili opis…")
        self.search_input.setFixedHeight(34)
        self.search_input.setStyleSheet(
            "QLineEdit { border: 1px solid #bbb; border-radius: 4px; "
            "padding: 4px 8px; font-size: 13px; }"
            "QLineEdit:focus { border: 1px solid #2196F3; }"
        )
        self.search_input.textChanged.connect(lambda: self._search_timer.start())

        search_row.addWidget(search_icon)
        search_row.addWidget(self.search_input, 1)
        layout.addLayout(search_row)

        # --- Count label ---
        self.lbl_count = QLabel()
        self.lbl_count.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(self.lbl_count)

        # --- Separator ---
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #ddd;")
        layout.addWidget(sep)

        # --- Table ---
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Tarifni broj", "Opis"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(
            "QTableWidget { border: 1px solid #ddd; font-size: 13px; background: #ffffff; alternate-background-color: #f7f9fc; color: #1e3820; }"
            "QTableWidget::item { color: #1e3820; }"
            "QTableWidget::item:selected { background-color: #1976D2; color: white; }"
        )
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.table, 1)

        # --- Buttons ---
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_apply = QPushButton("PRIMIJENI")
        self.btn_apply.setEnabled(False)
        self.btn_apply.setFixedHeight(36)
        self.btn_apply.setMinimumWidth(120)
        self.btn_apply.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; border: none; "
            "border-radius: 4px; padding: 6px 16px; font-size: 13px; font-weight: bold; }"
            "QPushButton:hover { background-color: #43A047; }"
            "QPushButton:pressed { background-color: #388E3C; }"
            "QPushButton:disabled { background-color: #ccc; color: #888; }"
        )
        self.btn_apply.clicked.connect(self._on_apply)

        btn_cancel = QPushButton("OTKAŽI")
        btn_cancel.setFixedHeight(36)
        btn_cancel.setMinimumWidth(90)
        btn_cancel.setStyleSheet(
            "QPushButton { background-color: #9E9E9E; color: white; border: none; "
            "border-radius: 4px; padding: 6px 16px; font-size: 13px; }"
            "QPushButton:hover { background-color: #757575; }"
            "QPushButton:pressed { background-color: #616161; }"
        )
        btn_cancel.clicked.connect(self.reject)

        btn_row.addWidget(self.btn_apply)
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------ #
    #  Database                                                            #
    # ------------------------------------------------------------------ #

    def _get_total_count(self) -> int:
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM catalogs.zvanicna_tarifa")
                    return cur.fetchone()[0]
        except Exception:
            return 0

    def _do_search(self):
        query = self.search_input.text().strip()
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    if query:
                        if query.isdigit():
                            cur.execute(
                                "SELECT tarifni_kod, opis FROM catalogs.zvanicna_tarifa "
                                "WHERE tarifni_kod LIKE %s "
                                "ORDER BY LENGTH(tarifni_kod), tarifni_kod LIMIT %s",
                                (f"{query}%", _SEARCH_LIMIT),
                            )
                        else:
                            cur.execute(
                                "SELECT tarifni_kod, opis FROM catalogs.zvanicna_tarifa "
                                "WHERE opis ILIKE %s OR tarifni_kod LIKE %s "
                                "ORDER BY LENGTH(tarifni_kod), tarifni_kod LIMIT %s",
                                (f"%{query}%", f"%{query}%", _SEARCH_LIMIT),
                            )
                    else:
                        cur.execute(
                            "SELECT tarifni_kod, opis FROM catalogs.zvanicna_tarifa "
                            "ORDER BY LENGTH(tarifni_kod), tarifni_kod LIMIT %s",
                            (_INITIAL_LIMIT,),
                        )
                    rows = cur.fetchall()
        except Exception as e:
            logger.warning(f"⚠️  TariffSearchDialog DB greška: {e}")
            rows = []

        self._populate_table(rows, query)

    # ------------------------------------------------------------------ #
    #  Table population                                                    #
    # ------------------------------------------------------------------ #

    def _populate_table(self, rows: list, query: str):
        self.table.setRowCount(0)
        limit = _SEARCH_LIMIT if query else _INITIAL_LIMIT
        shown = len(rows)

        if query:
            self.lbl_count.setText(
                f"Pronađeno: {shown}"
                + (" (prikaz prvih 300)" if shown == _SEARCH_LIMIT else "")
            )
        else:
            self.lbl_count.setText(
                f"Prikazano: {shown} od {self._total_count} — pretražite za više"
            )

        bold_font = QFont()
        bold_font.setBold(True)

        self.table.setRowCount(len(rows))
        for row_idx, (kod, opis) in enumerate(rows):
            # Kod — bold za potpune kodove (8+ cifara)
            item_kod = QTableWidgetItem(kod or "")
            if kod and len(kod) >= 8 and kod.isdigit():
                item_kod.setFont(bold_font)
            else:
                item_kod.setForeground(Qt.gray)

            # Opis — ukloni višestruke razmake i sufiks s tarifnim stopama
            opis_clean = " ".join((opis or "").split())
            opis_clean = _TAIL_RATES_RE.sub('', opis_clean).rstrip(' –-').strip()
            item_opis = QTableWidgetItem(opis_clean)

            self.table.setItem(row_idx, 0, item_kod)
            self.table.setItem(row_idx, 1, item_opis)

        self.table.resizeRowsToContents()
        self.btn_apply.setEnabled(False)

    # ------------------------------------------------------------------ #
    #  Signal handlers                                                     #
    # ------------------------------------------------------------------ #

    def _on_selection_changed(self):
        selected = self.table.selectedItems()
        self.btn_apply.setEnabled(bool(selected))
        if selected:
            self._selected_code = self.table.item(
                self.table.currentRow(), 0
            ).text()

    def _on_double_click(self, item):
        self._selected_code = self.table.item(item.row(), 0).text()
        self.accept()

    def _on_apply(self):
        row = self.table.currentRow()
        if row >= 0:
            self._selected_code = self.table.item(row, 0).text()
            self.accept()

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def get_selected_code(self) -> Optional[str]:
        """Vraća odabrani tarifni broj ili None."""
        return self._selected_code
