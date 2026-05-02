"""
Analytics Panel — upotreba AI agenta i status sistema.

Prikazuje informacije koje Database panel ne prikazuje:
AI provider, upotreba tokena danas/sesija, instalirani parseri,
zadnje indeksiranje carinskih dokumenata.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QGridLayout, QScrollArea,
    QProgressBar, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Signal, Qt, QThread
from PySide6.QtGui import QFont
import qtawesome as qta
from gui.utils.safe_message_box import SafeMessageBox as QMessageBox


class _StatsThread(QThread):
    done = Signal(dict)

    def run(self):
        result = {}

        # LLM provider
        try:
            from gui.tabs.agent.widgets.llm_provider import LLMProvider
            result['llm_provider'] = LLMProvider().active_provider()
        except Exception:
            result['llm_provider'] = 'nepoznat'

        # Upotreba danas (audit log)
        try:
            from services.agent.llm_audit_log import get_today_stats, get_session_stats
            today = get_today_stats()
            result['calls_today']   = today.get('calls_today', 0)
            result['tokens_today']  = today.get('tokens_today', 0)
            result['blocked_today'] = today.get('blocked_today', 0)

            sess = get_session_stats()
            result['session_tokens'] = sess.get('session_tokens_used', 0)
            result['session_budget'] = sess.get('session_budget', 0)
            result['session_pct']    = sess.get('session_pct', 0)
        except Exception:
            result['calls_today'] = result['tokens_today'] = result['blocked_today'] = 0
            result['session_tokens'] = result['session_budget'] = result['session_pct'] = 0

        # Parseri
        try:
            from services.plugin_service import PluginService
            result['parseri'] = len(PluginService().get_installed_parsers())
        except Exception:
            result['parseri'] = None

        # Carinski dokumenti — lista i zadnje indeksiranje
        try:
            from database.db import get_db_connection
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT naziv, datum_indeksa
                        FROM catalogs.carinski_dokumenti
                        ORDER BY naziv
                    """)
                    rows = cur.fetchall()
                    result['cd_dokumenti'] = [
                        {'naziv': r['naziv'], 'datum': r['datum_indeksa']}
                        for r in rows
                    ]
                    result['cd_count']  = len(rows)
                    result['cd_zadnje'] = max(
                        (r['datum_indeksa'] for r in rows), default=None
                    )
        except Exception:
            result['cd_count'] = None
            result['cd_zadnje'] = None
            result['cd_dokumenti'] = []

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
        lbl = QLabel("Upotreba AI agenta")
        lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #222; margin-left: 8px;")
        hdr.addWidget(lbl)
        hdr.addStretch()
        layout.addLayout(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        sw = QWidget()
        sl = QVBoxLayout(sw)
        sl.setSpacing(14)
        sl.setContentsMargins(0, 0, 0, 0)

        # ── AI provider ────────────────────────────────────────
        prov_group = QGroupBox("🤖 AI provider")
        prov_lay = QGridLayout(prov_group)
        prov_lay.setSpacing(10)
        prov_lay.setColumnStretch(1, 1)

        prov_lay.addWidget(self._ico('fa5s.robot'), 0, 0)
        prov_lay.addWidget(QLabel("Aktivni provider:"), 0, 1)
        self.lbl_provider = QLabel("—")
        self.lbl_provider.setFont(QFont("Arial", 13, QFont.Bold))
        prov_lay.addWidget(self.lbl_provider, 0, 2)

        prov_lay.addWidget(self._ico('fa5s.puzzle-piece'), 1, 0)
        prov_lay.addWidget(QLabel("Instaliranih parsera:"), 1, 1)
        self.lbl_parseri = QLabel("—")
        self.lbl_parseri.setFont(QFont("Arial", 13, QFont.Bold))
        self.lbl_parseri.setStyleSheet("color: #0078d4;")
        prov_lay.addWidget(self.lbl_parseri, 1, 2)

        sl.addWidget(prov_group)

        # ── Upotreba danas ─────────────────────────────────────
        today_group = QGroupBox("📊 Upotreba danas")
        today_lay = QGridLayout(today_group)
        today_lay.setSpacing(10)
        today_lay.setColumnStretch(1, 1)

        rows_today = [
            ('lbl_calls',   'fa5s.comments',      'Upita agentu:'),
            ('lbl_tokens',  'fa5s.coins',          'Tokena potrošeno:'),
            ('lbl_blocked', 'fa5s.shield-alt',     'Blokiranih poruka:'),
        ]
        for attr, ico_name, tekst in rows_today:
            i = rows_today.index((attr, ico_name, tekst))
            today_lay.addWidget(self._ico(ico_name), i, 0)
            today_lay.addWidget(QLabel(tekst), i, 1)
            lbl = QLabel("—")
            lbl.setFont(QFont("Arial", 13, QFont.Bold))
            lbl.setStyleSheet("color: #0078d4;")
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            today_lay.addWidget(lbl, i, 2)
            setattr(self, attr, lbl)

        sl.addWidget(today_group)

        # ── Token budžet (sesija) ──────────────────────────────
        budget_group = QGroupBox("💰 Token budžet — ova sesija")
        budget_lay = QVBoxLayout(budget_group)
        budget_lay.setSpacing(8)

        info_lay = QHBoxLayout()
        self.lbl_sess_tokens = QLabel("0 / 0 tokena")
        self.lbl_sess_tokens.setFont(QFont("Arial", 12))
        info_lay.addWidget(self.lbl_sess_tokens)
        info_lay.addStretch()
        self.lbl_sess_pct = QLabel("0%")
        self.lbl_sess_pct.setFont(QFont("Arial", 12, QFont.Bold))
        info_lay.addWidget(self.lbl_sess_pct)
        budget_lay.addLayout(info_lay)

        self.progress_budget = QProgressBar()
        self.progress_budget.setRange(0, 100)
        self.progress_budget.setValue(0)
        self.progress_budget.setTextVisible(False)
        self.progress_budget.setFixedHeight(12)
        self.progress_budget.setStyleSheet("""
            QProgressBar { border:none; border-radius:6px; background:#e9ecef; }
            QProgressBar::chunk { border-radius:6px; background:#0078d4; }
        """)
        budget_lay.addWidget(self.progress_budget)

        sl.addWidget(budget_group)

        # ── Carinski dokumenti ─────────────────────────────────
        cd_group = QGroupBox("📋 Carinski propisi u bazi")
        cd_lay = QVBoxLayout(cd_group)
        cd_lay.setSpacing(8)

        # Info red: broj + zadnje indeksiranje
        info_lay = QHBoxLayout()
        self.lbl_cd_count = QLabel("— dokumenata")
        self.lbl_cd_count.setFont(QFont("Arial", 12, QFont.Bold))
        self.lbl_cd_count.setStyleSheet("color: #0078d4;")
        info_lay.addWidget(self.lbl_cd_count)
        info_lay.addStretch()
        self.lbl_cd_zadnje = QLabel("")
        self.lbl_cd_zadnje.setStyleSheet("color: #888; font-size: 11px;")
        info_lay.addWidget(self.lbl_cd_zadnje)
        cd_lay.addLayout(info_lay)

        # Lista dokumenata
        self.cd_lista = QListWidget()
        self.cd_lista.setMinimumHeight(220)
        self.cd_lista.setMaximumHeight(320)
        self.cd_lista.setStyleSheet("""
            QListWidget {
                border: 1px solid #e0e0e0; border-radius: 4px;
                background: #fafafa; font-size: 12px;
            }
            QListWidget::item { padding: 5px 8px; border-bottom: 1px solid #f0f0f0; }
            QListWidget::item:hover { background: #e8f0fe; }
            QListWidget::item:selected { background: #d0e4ff; color: #000; }
        """)
        self.cd_lista.setSelectionMode(QListWidget.NoSelection)
        cd_lay.addWidget(self.cd_lista)

        sl.addWidget(cd_group)
        sl.addStretch()
        scroll.setWidget(sw)
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
        # Provider
        prov = stats.get('llm_provider', '—')
        boje = {'deepseek': '#6f42c1', 'groq': '#fd7e14', 'gemini': '#1a73e8',
                'none': '#dc3545', 'nepoznat': '#999'}
        tekst = prov.capitalize() if prov not in ('none', 'nepoznat') else '⚠️ Nije konfigurisan'
        self.lbl_provider.setText(tekst)
        self.lbl_provider.setStyleSheet(
            f"color: {boje.get(prov, '#333')}; font-size: 13px; font-weight: bold;"
        )

        parseri = stats.get('parseri')
        self.lbl_parseri.setText(str(parseri) if parseri is not None else "—")

        # Danas
        self.lbl_calls.setText(str(stats.get('calls_today', 0)))
        tokens = stats.get('tokens_today', 0)
        self.lbl_tokens.setText(f"{tokens:,}".replace(",", "."))
        blocked = stats.get('blocked_today', 0)
        self.lbl_blocked.setText(str(blocked))
        self.lbl_blocked.setStyleSheet(
            "color: #dc3545; font-weight: bold;" if blocked > 0 else "color: #28a745; font-weight: bold;"
        )

        # Sesija
        used = stats.get('session_tokens', 0)
        budget = stats.get('session_budget', 0)
        pct = int(stats.get('session_pct', 0))
        self.lbl_sess_tokens.setText(
            f"{used:,} / {budget:,} tokena".replace(",", ".")
        )
        self.lbl_sess_pct.setText(f"{pct}%")
        self.progress_budget.setValue(min(pct, 100))
        chunk_color = "#28a745" if pct < 70 else ("#fd7e14" if pct < 90 else "#dc3545")
        self.progress_budget.setStyleSheet(f"""
            QProgressBar {{ border:none; border-radius:6px; background:#e9ecef; }}
            QProgressBar::chunk {{ border-radius:6px; background:{chunk_color}; }}
        """)

        # Carinski dokumenti
        cd_count = stats.get('cd_count') or 0
        self.lbl_cd_count.setText(f"{cd_count} dokumenata")

        zadnje = stats.get('cd_zadnje')
        if zadnje:
            try:
                self.lbl_cd_zadnje.setText(
                    "Ažurirano: " + zadnje.strftime("%d.%m.%Y. %H:%M")
                )
            except Exception:
                self.lbl_cd_zadnje.setText(str(zadnje)[:16])
        else:
            self.lbl_cd_zadnje.setText("Nije indeksirano")

        self.cd_lista.clear()
        dokumenti = stats.get('cd_dokumenti', [])
        if dokumenti:
            for d in dokumenti:
                naziv = d.get('naziv', '')
                datum = d.get('datum')
                datum_str = ""
                if datum:
                    try:
                        datum_str = "  —  " + datum.strftime("%d.%m.%Y.")
                    except Exception:
                        datum_str = ""
                item = QListWidgetItem(f"📄 {naziv}{datum_str}")
                self.cd_lista.addItem(item)
        else:
            item = QListWidgetItem("Nema indeksiranih dokumenata")
            item.setForeground(Qt.gray)
            self.cd_lista.addItem(item)

    def show_error(self, message: str):
        QMessageBox.critical(self, "Greška", message)

    # ── HANDLERS ───────────────────────────────────────────────

    def _on_refresh(self):
        self.btn_refresh.setEnabled(False)
        self.btn_refresh.setText(" Učitavanje...")
        self._thread = _StatsThread(self)
        self._thread.done.connect(self._on_done)
        self._thread.start()
        self.refresh_requested.emit()

    def _on_done(self, stats: dict):
        self.btn_refresh.setEnabled(True)
        self.btn_refresh.setText(" Osvježi")
        self.set_statistics(stats)

    @staticmethod
    def _ico(name: str) -> QLabel:
        lbl = QLabel()
        lbl.setPixmap(qta.icon(name, color='#555').pixmap(16, 16))
        return lbl
