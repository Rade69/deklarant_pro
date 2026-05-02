"""
Analytics Panel — pregled statusa sistema i baze znanja.

Prikazuje stvarno korisne informacije za admin špedicije:
status konekcije, veličina baze znanja, carinski dokumenti, LLM status.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QGridLayout, QScrollArea
)
from PySide6.QtCore import Signal, Qt, QThread
from PySide6.QtGui import QFont
import qtawesome as qta
from gui.utils.safe_message_box import SafeMessageBox as QMessageBox


class _SystemStatusThread(QThread):
    done = Signal(dict)

    def run(self):
        result = {}

        # PostgreSQL konekcija
        try:
            from database.db import get_db_connection
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) AS n FROM catalogs.exporter_xml_index")
                    result['xml_deklaracije'] = cur.fetchone()['n']
                    cur.execute("SELECT COUNT(*) AS n FROM catalogs.product_tariff_mapping")
                    result['tarif_mapiranja'] = cur.fetchone()['n']
                    cur.execute("SELECT COUNT(*) AS n FROM catalogs.carinski_dokumenti")
                    result['carinski_dokumenti'] = cur.fetchone()['n']
                    cur.execute("SELECT COUNT(*) AS n FROM catalogs.izvoznici")
                    result['izvoznici'] = cur.fetchone()['n']
                    cur.execute("SELECT COUNT(*) AS n FROM catalogs.uvoznici")
                    result['uvoznici'] = cur.fetchone()['n']
                    cur.execute("SELECT COUNT(*) AS n FROM catalogs.tarifa_nazivi")
                    result['tarifa_nazivi'] = cur.fetchone()['n']
            result['pg_status'] = True
        except Exception as e:
            result['pg_status'] = False
            result['pg_error'] = str(e)

        # LLM provider
        try:
            from gui.tabs.agent.widgets.llm_provider import LLMProvider
            provider = LLMProvider()
            result['llm_provider'] = provider.active_provider()
        except Exception:
            result['llm_provider'] = 'nepoznat'

        # Broj instaliranih parsera
        try:
            from services.plugin_service import PluginService
            ps = PluginService()
            result['parseri'] = len(ps.get_installed_parsers())
        except Exception:
            result['parseri'] = None

        self.done.emit(result)


class AnalyticsPanel(QWidget):
    refresh_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread = None
        self.setup_ui()
        self._apply_styles()

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
        ico.setPixmap(qta.icon('fa5s.tachometer-alt', color='#333').pixmap(28, 28))
        hdr.addWidget(ico)
        lbl = QLabel("Status sistema")
        lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #222; margin-left: 8px;")
        hdr.addWidget(lbl)
        hdr.addStretch()
        layout.addLayout(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll_w = QWidget()
        sl = QVBoxLayout(scroll_w)
        sl.setSpacing(14)
        sl.setContentsMargins(0, 0, 0, 0)

        # ── Konekcija i LLM ────────────────────────────────────
        sys_group = QGroupBox("⚙️ Infrastruktura")
        sys_lay = QGridLayout(sys_group)
        sys_lay.setSpacing(10)
        sys_lay.setColumnStretch(1, 1)

        sys_lay.addWidget(self._ico_lbl('fa5s.server'), 0, 0)
        sys_lay.addWidget(QLabel("PostgreSQL:"), 0, 1)
        self.lbl_pg = QLabel("—")
        self.lbl_pg.setFont(QFont("Arial", 12, QFont.Bold))
        sys_lay.addWidget(self.lbl_pg, 0, 2)

        sys_lay.addWidget(self._ico_lbl('fa5s.robot'), 1, 0)
        sys_lay.addWidget(QLabel("AI provider:"), 1, 1)
        self.lbl_llm = QLabel("—")
        self.lbl_llm.setFont(QFont("Arial", 12, QFont.Bold))
        sys_lay.addWidget(self.lbl_llm, 1, 2)

        sys_lay.addWidget(self._ico_lbl('fa5s.puzzle-piece'), 2, 0)
        sys_lay.addWidget(QLabel("Instaliranih parsera:"), 2, 1)
        self.lbl_parseri = QLabel("—")
        self.lbl_parseri.setFont(QFont("Arial", 12, QFont.Bold))
        sys_lay.addWidget(self.lbl_parseri, 2, 2)

        sl.addWidget(sys_group)

        # ── Baza znanja ────────────────────────────────────────
        kb_group = QGroupBox("🧠 Baza znanja")
        kb_lay = QGridLayout(kb_group)
        kb_lay.setSpacing(10)
        kb_lay.setColumnStretch(1, 1)

        self._kb_rows = [
            ('xml_deklaracije',  'fa5s.file-code',   'XML deklaracije (istorija)',  self),
            ('tarif_mapiranja',  'fa5s.map',          'Tarifna mapiranja',           self),
            ('tarifa_nazivi',    'fa5s.list',         'Nazivi robe → tarifa',        self),
        ]

        self._kb_labels = {}
        for i, (key, ico_name, tekst, _) in enumerate(self._kb_rows):
            kb_lay.addWidget(self._ico_lbl(ico_name), i, 0)
            kb_lay.addWidget(QLabel(tekst + ":"), i, 1)
            val = QLabel("—")
            val.setFont(QFont("Arial", 12, QFont.Bold))
            val.setStyleSheet("color: #0078d4;")
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            kb_lay.addWidget(val, i, 2)
            self._kb_labels[key] = val

        sl.addWidget(kb_group)

        # ── Carinski dokumenti ─────────────────────────────────
        cd_group = QGroupBox("📋 Carinski propisi")
        cd_lay = QGridLayout(cd_group)
        cd_lay.setSpacing(10)
        cd_lay.setColumnStretch(1, 1)

        cd_lay.addWidget(self._ico_lbl('fa5s.book'), 0, 0)
        cd_lay.addWidget(QLabel("Indeksiranih dokumenata:"), 0, 1)
        self.lbl_cd = QLabel("—")
        self.lbl_cd.setFont(QFont("Arial", 12, QFont.Bold))
        self.lbl_cd.setStyleSheet("color: #0078d4;")
        self.lbl_cd.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        cd_lay.addWidget(self.lbl_cd, 0, 2)

        cd_lay.addWidget(self._ico_lbl('fa5s.users'), 1, 0)
        cd_lay.addWidget(QLabel("Izvoznici u bazi:"), 1, 1)
        self.lbl_izvoznici = QLabel("—")
        self.lbl_izvoznici.setFont(QFont("Arial", 12, QFont.Bold))
        self.lbl_izvoznici.setStyleSheet("color: #0078d4;")
        self.lbl_izvoznici.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        cd_lay.addWidget(self.lbl_izvoznici, 1, 2)

        cd_lay.addWidget(self._ico_lbl('fa5s.building'), 2, 0)
        cd_lay.addWidget(QLabel("Uvoznici u bazi:"), 2, 1)
        self.lbl_uvoznici = QLabel("—")
        self.lbl_uvoznici.setFont(QFont("Arial", 12, QFont.Bold))
        self.lbl_uvoznici.setStyleSheet("color: #0078d4;")
        self.lbl_uvoznici.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        cd_lay.addWidget(self.lbl_uvoznici, 2, 2)

        sl.addWidget(cd_group)
        sl.addStretch()
        scroll.setWidget(scroll_w)
        layout.addWidget(scroll)

        # Dugme
        self.btn_refresh = QPushButton(qta.icon('fa5s.sync', color='white'), " Osvježi")
        self.btn_refresh.setStyleSheet("""
            QPushButton { background:#0078d4; color:white; border:none;
                          border-radius:4px; padding:8px 20px; font-size:13px; }
            QPushButton:hover { background:#106ebe; }
            QPushButton:disabled { background:#aaa; }
        """)
        self.btn_refresh.setMinimumHeight(38)
        self.btn_refresh.clicked.connect(self._on_refresh)
        layout.addWidget(self.btn_refresh, alignment=Qt.AlignLeft)

    # ── PUBLIC API ──────────────────────────────────────────────

    def set_statistics(self, stats: dict):
        pg_ok = stats.get('pg_status', False)
        pg_err = stats.get('pg_error', '')

        if pg_ok:
            self.lbl_pg.setText("✅ Spojena")
            self.lbl_pg.setStyleSheet("color: #28a745; font-size: 12px; font-weight: bold;")
        else:
            self.lbl_pg.setText(f"❌ {pg_err[:60]}" if pg_err else "❌ Greška")
            self.lbl_pg.setStyleSheet("color: #dc3545; font-size: 12px; font-weight: bold;")

        llm = stats.get('llm_provider', '—')
        llm_boje = {'deepseek': '#6f42c1', 'groq': '#fd7e14', 'gemini': '#1a73e8', 'none': '#999'}
        self.lbl_llm.setText(llm.capitalize() if llm != 'none' else '⚠️ Nije konfigurisan')
        self.lbl_llm.setStyleSheet(f"color: {llm_boje.get(llm, '#333')}; font-size: 12px; font-weight: bold;")

        parseri = stats.get('parseri')
        self.lbl_parseri.setText(str(parseri) if parseri is not None else "—")

        for key, lbl in self._kb_labels.items():
            v = stats.get(key)
            lbl.setText(f"{v:,}".replace(",", ".") if v is not None else "—")

        self.lbl_cd.setText(str(stats.get('carinski_dokumenti', '—')))
        self.lbl_izvoznici.setText(str(stats.get('izvoznici', '—')))
        self.lbl_uvoznici.setText(str(stats.get('uvoznici', '—')))

    def show_error(self, message: str):
        QMessageBox.critical(self, "Greška", message)

    # ── HANDLERS ───────────────────────────────────────────────

    def _on_refresh(self):
        self.btn_refresh.setEnabled(False)
        self.btn_refresh.setText(" Učitavanje...")
        self._thread = _SystemStatusThread(self)
        self._thread.done.connect(self._on_done)
        self._thread.start()
        self.refresh_requested.emit()

    def _on_done(self, stats: dict):
        self.btn_refresh.setEnabled(True)
        self.btn_refresh.setText(" Osvježi")
        self.set_statistics(stats)

    # ── HELPER ─────────────────────────────────────────────────

    @staticmethod
    def _ico_lbl(name: str) -> QLabel:
        lbl = QLabel()
        lbl.setPixmap(qta.icon(name, color='#555').pixmap(16, 16))
        return lbl
