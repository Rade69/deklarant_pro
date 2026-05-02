"""
Logs Panel — pregled aplikacijskih logova.

Korisno na Windows instalaciji gdje nema terminala —
deklarant može pročitati grešku i proslijediti razvojnom timu.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QPushButton, QComboBox, QGroupBox, QSizePolicy
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont
from pathlib import Path
import qtawesome as qta


LOG_COLORS = {
    'ERROR':    '#f28b82',
    'CRITICAL': '#f28b82',
    'WARNING':  '#fdd663',
    'INFO':     '#d4d4d4',
    'DEBUG':    '#888888',
}


class LogsPanel(QWidget):
    refresh_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_logs: list = []
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        hdr = QHBoxLayout()
        ico = QLabel()
        ico.setPixmap(qta.icon('fa5s.file-alt', color='#333').pixmap(28, 28))
        hdr.addWidget(ico)
        lbl = QLabel("Logovi aplikacije")
        lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #222; margin-left: 8px;")
        hdr.addWidget(lbl)
        hdr.addStretch()
        layout.addLayout(hdr)

        # Toolbar — filter + refresh
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        toolbar.addWidget(QLabel("Prikaži:"))
        self.level_combo = QComboBox()
        self.level_combo.addItems(["Sve", "ERROR", "WARNING", "INFO", "DEBUG"])
        self.level_combo.setFixedWidth(120)
        self.level_combo.setStyleSheet("""
            QComboBox { border: 1px solid #ccc; border-radius: 4px;
                        padding: 5px 10px; font-size: 13px; background: white; }
            QComboBox::drop-down { border: none; width: 24px; }
        """)
        self.level_combo.currentTextChanged.connect(self._apply_filter)
        toolbar.addWidget(self.level_combo)

        toolbar.addStretch()

        self.lbl_fajl = QLabel("")
        self.lbl_fajl.setStyleSheet("color: #888; font-size: 11px;")
        toolbar.addWidget(self.lbl_fajl)

        self.btn_refresh = QPushButton(qta.icon('fa5s.sync', color='white'), " Osvježi")
        self.btn_refresh.setStyleSheet("""
            QPushButton { background:#0078d4; color:white; border:none;
                          border-radius:4px; padding:7px 18px; font-size:13px; }
            QPushButton:hover { background:#106ebe; }
        """)
        self.btn_refresh.setMinimumHeight(36)
        self.btn_refresh.clicked.connect(self._on_refresh)
        toolbar.addWidget(self.btn_refresh)

        layout.addLayout(toolbar)

        # Log prikaz
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Courier New", 11))
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e; color: #d4d4d4;
                border: 1px solid #444; border-radius: 4px;
                padding: 10px; line-height: 1.5;
            }
        """)
        self.log_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.log_text)

        # Info na dnu
        info = QLabel("Tekst možeš selektovati i kopirati (Ctrl+C) da pošalješ razvojnom timu.")
        info.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(info)

        self._load_from_file()

    # ── PUBLIC API ──────────────────────────────────────────────

    def set_logs(self, logs: list):
        self._all_logs = logs
        self._apply_filter(self.level_combo.currentText())

    def show_error(self, message: str):
        self.log_text.setPlainText(f"Greška pri učitavanju logova:\n{message}")

    # ── PRIVATE ─────────────────────────────────────────────────

    def _load_from_file(self):
        log_file = Path.home() / ".deklarant_pro" / "logs" / "deklarant_pro.log"
        # Fallback na staro ime ako novi još ne postoji
        if not log_file.exists():
            log_file = Path.home() / ".deklarant_pro" / "logs" / "asycuda.log"

        if log_file.exists():
            self.lbl_fajl.setText(str(log_file))
            try:
                lines = log_file.read_text(encoding='utf-8', errors='replace').splitlines()
                self._all_logs = self._parse_lines(lines)
                self._apply_filter(self.level_combo.currentText())
            except Exception as e:
                self.log_text.setPlainText(f"Greška pri čitanju fajla:\n{e}")
        else:
            self.lbl_fajl.setText("Log fajl još ne postoji")
            self.log_text.setPlainText("(Nema logova — aplikacija još nije pisala u log fajl)")

    def _parse_lines(self, lines: list) -> list:
        import re
        pattern = re.compile(
            r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s*-\s*(DEBUG|INFO|WARNING|ERROR|CRITICAL)\s*-\s*(.+)$',
            re.IGNORECASE
        )
        result = []
        for line in lines:
            m = pattern.match(line.strip())
            if m:
                result.append({'timestamp': m.group(1), 'level': m.group(2).upper(), 'message': m.group(3)})
            elif line.strip():
                result.append({'timestamp': '', 'level': 'DEBUG', 'message': line.strip()})
        return result

    def _apply_filter(self, level: str):
        self.log_text.clear()
        logs = self._all_logs
        if level != "Sve":
            logs = [l for l in logs if l.get('level') == level]

        if not logs:
            self.log_text.setHtml('<span style="color:#888;">(Nema logova za odabrani filter)</span>')
            return

        # Prikaži samo zadnjih 500 linija da ne bude presporo
        html_parts = []
        for entry in logs[-500:]:
            ts = entry.get('timestamp', '')
            lvl = entry.get('level', '')
            msg = entry.get('message', '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            color = LOG_COLORS.get(lvl, '#d4d4d4')
            ts_html = f'<span style="color:#666;">[{ts}]</span> ' if ts else ''
            html_parts.append(
                f'{ts_html}<span style="color:{color};font-weight:bold;">{lvl:8}</span> '
                f'<span style="color:#d4d4d4;">{msg}</span>'
            )

        self.log_text.setHtml('<br>'.join(html_parts))
        # Scroll na dno
        sb = self.log_text.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_refresh(self):
        self._load_from_file()
        self.refresh_requested.emit()
