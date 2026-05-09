"""
Database Panel — status PostgreSQL konekcije i pregled ključnih tabela.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QGridLayout, QScrollArea, QFrame
)
from PySide6.QtCore import Signal, Qt, QThread
from PySide6.QtGui import QFont
from typing import Dict, Any
import qtawesome as qta
from psycopg2 import sql as pg_sql
from gui.utils.safe_message_box import SafeMessageBox as QMessageBox


class _TestConnThread(QThread):
    done = Signal(bool, str)

    def run(self):
        try:
            from database.db import get_db_connection
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT version()")
                    ver = cur.fetchone()['version'].split(',')[0]
            self.done.emit(True, ver)
        except Exception as e:
            self.done.emit(False, str(e))


class _LoadStatsThread(QThread):
    done = Signal(dict)

    def run(self):
        stats = {}
        try:
            from database.db import get_db_connection
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    tabele = [
                        ("Izvoznici",          "catalogs.izvoznici"),
                        ("Uvoznici",           "catalogs.uvoznici"),
                        ("XML deklaracije",    "catalogs.exporter_xml_index"),
                        ("Tarif. mapiranja",   "catalogs.product_tariff_mapping"),
                        ("Carinski dokumenti", "catalogs.carinski_dokumenti"),
                        ("Deklaranti",         "catalogs.deklaranti"),
                    ]
                    for naziv, tabela in tabele:
                        try:
                            schema, tbl = tabela.split(".", 1)
                            q = pg_sql.SQL("SELECT COUNT(*) AS n FROM {}.{}").format(
                                pg_sql.Identifier(schema), pg_sql.Identifier(tbl)
                            )
                            cur.execute(q)
                            stats[naziv] = cur.fetchone()['n']
                        except Exception:
                            stats[naziv] = None
        except Exception as e:
            stats['_error'] = str(e)
        self.done.emit(stats)


class DatabasePanel(QWidget):
    refresh_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._conn_thread = None
        self._stats_thread = None
        self.setup_ui()
        self._apply_styles()

    def closeEvent(self, event):
        for t in (self._conn_thread, self._stats_thread):
            if t and t.isRunning():
                t.quit()
                t.wait(2000)
        super().closeEvent(event)

    def _apply_styles(self):
        self.setStyleSheet("background-color: #f8f9fa;")
        for gb in self.findChildren(QGroupBox):
            gb.setStyleSheet("""
                QGroupBox {
                    border: 1px solid #ddd; border-radius: 6px;
                    margin-top: 12px; padding-top: 10px;
                    font-weight: bold; font-size: 13px;
                    background-color: white;
                }
                QGroupBox::title {
                    subcontrol-origin: margin; subcontrol-position: top left;
                    padding: 0 8px; color: #444;
                }
            """)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # Header
        hdr = QHBoxLayout()
        ico = QLabel()
        ico.setPixmap(qta.icon('fa5s.server', color='#333').pixmap(28, 28))
        hdr.addWidget(ico)
        lbl = QLabel("Baza podataka — PostgreSQL")
        lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #222; margin-left: 8px;")
        hdr.addWidget(lbl)
        hdr.addStretch()
        layout.addLayout(hdr)

        # ── Konekcija ──────────────────────────────────────────
        conn_group = QGroupBox("🔌 Status konekcije")
        conn_lay = QGridLayout(conn_group)
        conn_lay.setSpacing(10)

        conn_lay.addWidget(QLabel("Server:"), 0, 0)
        self.lbl_server = QLabel("—")
        self.lbl_server.setFont(QFont("Courier New", 11))
        self.lbl_server.setTextInteractionFlags(Qt.TextSelectableByMouse)
        conn_lay.addWidget(self.lbl_server, 0, 1)

        conn_lay.addWidget(QLabel("Status:"), 1, 0)
        self.lbl_status = QLabel("Nije provjereno")
        self.lbl_status.setFont(QFont("Arial", 12, QFont.Bold))
        conn_lay.addWidget(self.lbl_status, 1, 1)

        conn_lay.addWidget(QLabel("Verzija:"), 2, 0)
        self.lbl_ver = QLabel("—")
        self.lbl_ver.setStyleSheet("color: #666; font-size: 12px;")
        conn_lay.addWidget(self.lbl_ver, 2, 1)

        self.btn_test = QPushButton(qta.icon('fa5s.plug', color='white'), " Testiraj konekciju")
        self.btn_test.setStyleSheet("""
            QPushButton { background:#0078d4; color:white; border:none;
                          border-radius:4px; padding:7px 16px; font-size:13px; }
            QPushButton:hover { background:#106ebe; }
            QPushButton:disabled { background:#aaa; }
        """)
        self.btn_test.setMinimumHeight(36)
        self.btn_test.clicked.connect(self._on_test_conn)
        conn_lay.addWidget(self.btn_test, 3, 0, 1, 2)

        layout.addWidget(conn_group)

        # ── Tabele ─────────────────────────────────────────────
        tbl_group = QGroupBox("📊 Broj zapisa po tabeli")
        tbl_lay = QGridLayout(tbl_group)
        tbl_lay.setSpacing(8)

        self._stat_labels: Dict[str, QLabel] = {}
        self._red_labels: Dict[str, QLabel] = {}

        redovi = [
            ("Izvoznici",          "fa5s.truck"),
            ("Uvoznici",           "fa5s.building"),
            ("XML deklaracije",    "fa5s.file-code"),
            ("Tarif. mapiranja",   "fa5s.map"),
            ("Carinski dokumenti", "fa5s.book"),
            ("Deklaranti",         "fa5s.id-card"),
        ]

        for i, (naziv, ico_name) in enumerate(redovi):
            ico_lbl = QLabel()
            ico_lbl.setPixmap(qta.icon(ico_name, color='#555').pixmap(16, 16))
            tbl_lay.addWidget(ico_lbl, i, 0)

            tbl_lay.addWidget(QLabel(naziv + ":"), i, 1)

            val = QLabel("—")
            val.setFont(QFont("Arial", 12, QFont.Bold))
            val.setStyleSheet("color: #0078d4;")
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            tbl_lay.addWidget(val, i, 2)
            self._stat_labels[naziv] = val

        tbl_lay.setColumnStretch(1, 1)

        self.btn_refresh = QPushButton(qta.icon('fa5s.sync', color='white'), " Osvježi podatke")
        self.btn_refresh.setStyleSheet("""
            QPushButton { background:#28a745; color:white; border:none;
                          border-radius:4px; padding:7px 16px; font-size:13px; }
            QPushButton:hover { background:#218838; }
            QPushButton:disabled { background:#aaa; }
        """)
        self.btn_refresh.setMinimumHeight(36)
        self.btn_refresh.clicked.connect(self._on_refresh)
        tbl_lay.addWidget(self.btn_refresh, len(redovi), 0, 1, 3)

        layout.addWidget(tbl_group)
        layout.addStretch()

        # Postavi server adresu iz settings-a
        try:
            from config.settings import get_db_settings
            s = get_db_settings()
            self.lbl_server.setText(f"{s.host}:{s.port}/{s.database}")
        except Exception:
            self.lbl_server.setText("(config nije dostupan)")

    # ── PUBLIC API ─────────────────────────────────────────────

    def set_connection_status(self, ok: bool, info: str = ""):
        if ok:
            self.lbl_status.setText("✅ Spojena")
            self.lbl_status.setStyleSheet("color: #28a745; font-size: 13px; font-weight: bold;")
            self.lbl_ver.setText(info)
        else:
            self.lbl_status.setText("❌ Greška")
            self.lbl_status.setStyleSheet("color: #dc3545; font-size: 13px; font-weight: bold;")
            self.lbl_ver.setText(info)

    def set_table_stats(self, stats: Dict[str, Any]):
        for naziv, val_lbl in self._stat_labels.items():
            v = stats.get(naziv)
            if v is None:
                val_lbl.setText("N/A")
                val_lbl.setStyleSheet("color: #999; font-size: 12px;")
            else:
                val_lbl.setText(f"{v:,}".replace(",", "."))
                val_lbl.setStyleSheet("color: #0078d4; font-size: 12px; font-weight: bold;")

    def show_success(self, message: str):
        QMessageBox.information(self, "Uspjeh", message)

    def show_error(self, message: str):
        QMessageBox.critical(self, "Greška", message)

    # ── HANDLERS ───────────────────────────────────────────────

    def _on_test_conn(self):
        self.btn_test.setEnabled(False)
        self.lbl_status.setText("⏳ Testiranje...")
        self.lbl_status.setStyleSheet("color: #888; font-size: 13px;")
        self._conn_thread = _TestConnThread(self)
        self._conn_thread.done.connect(self._on_conn_done)
        self._conn_thread.start()

    def _on_conn_done(self, ok: bool, info: str):
        self.btn_test.setEnabled(True)
        self.set_connection_status(ok, info)

    def _on_refresh(self):
        self.btn_refresh.setEnabled(False)
        self.btn_refresh.setText(" Učitavanje...")
        self._stats_thread = _LoadStatsThread(self)
        self._stats_thread.done.connect(self._on_stats_done)
        self._stats_thread.start()
        self.refresh_requested.emit()

    def _on_stats_done(self, stats: Dict[str, Any]):
        self.btn_refresh.setEnabled(True)
        self.btn_refresh.setText(" Osvježi podatke")
        if '_error' in stats:
            self.set_connection_status(False, stats['_error'])
        else:
            self.set_table_stats(stats)
