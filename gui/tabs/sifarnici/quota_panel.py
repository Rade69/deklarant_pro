"""
QuotaPanel — panel za pregled tarifnih kvota (UINO).

Lokacija: Šifrarnici → Tarifne kvote

Dokumentacija: scripts/quota_module_2026-04-26.md
"""

import logging
from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from gui.utils.safe_message_box import SafeMessageBox as QMessageBox

logger = logging.getLogger("deklarant_pro.quota_panel")

# Status pragovi
_RISK_HIGH   = 0.10   # < 10%
_RISK_MEDIUM = 0.50   # 10–50%


def _risk_color(remaining: Optional[float], approved: Optional[float]) -> Optional[QColor]:
    if approved is None or approved == 0 or remaining is None:
        return None
    pct = remaining / approved
    if remaining == 0:
        return QColor("#fecaca")   # crvena — potrošeno
    if pct < _RISK_HIGH:
        return QColor("#fed7aa")   # narandžasta — visok rizik
    if pct < _RISK_MEDIUM:
        return QColor("#fef08a")   # žuta — srednji rizik
    return QColor("#bbf7d0")       # zelena — nizak rizik


def _risk_label(remaining: Optional[float], approved: Optional[float]) -> str:
    if approved is None or approved == 0 or remaining is None:
        return "—"
    if remaining == 0:
        return "Potrošeno"
    pct = remaining / approved
    if pct < _RISK_HIGH:
        return "Visok rizik"
    if pct < _RISK_MEDIUM:
        return "Srednji rizik"
    return "Nizak rizik"


def _risk_icon(remaining: Optional[float], approved: Optional[float]) -> Optional[QIcon]:
    if approved is None or approved == 0 or remaining is None:
        return None
    if remaining == 0:
        color = "#ef4444"   # crvena
    else:
        pct = remaining / approved
        if pct < _RISK_HIGH:
            color = "#f97316"   # narandžasta
        elif pct < _RISK_MEDIUM:
            color = "#eab308"   # žuta
        else:
            color = "#22c55e"   # zelena

    px = QPixmap(14, 14)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.NoPen)
    p.drawEllipse(1, 1, 12, 12)
    p.end()
    return QIcon(px)


def _fmt_qty(val: Optional[float]) -> str:
    if val is None:
        return "—"
    return f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_pct(remaining: Optional[float], approved: Optional[float]) -> str:
    if approved is None or approved == 0 or remaining is None:
        return "—"
    return f"{remaining / approved * 100:.1f}%"


# =========================================================
# WORKER THREAD
# =========================================================

class _RefreshWorker(QThread):
    success = Signal(int, str)   # (snapshot_id, status)
    error   = Signal(str)

    def run(self):
        try:
            from services.quota_service import refresh_quota_data
            sid, status = refresh_quota_data()
            self.success.emit(sid, status)
        except Exception as e:
            logger.error(f"Refresh greška: {e}")
            self.error.emit(str(e))


# =========================================================
# PANEL WIDGET
# =========================================================

class QuotaPanel(QWidget):
    """
    Panel za prikaz informativnog stanja tarifnih kvota prema UINO PDF izvještaju.
    """

    COLUMNS = [
        ("Tarifni broj", 145),
        ("Opis",         320),
        ("JM",            50),
        ("Odobreno",     100),
        ("Iskorište.",   100),
        ("Preostalo",    100),
        ("% prest.",      80),
        ("Status",       110),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._snapshot_id: Optional[int] = None
        self._worker: Optional[_RefreshWorker] = None
        self._all_rows: list[dict] = []
        self._init_ui()
        self._load_from_db()

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(2000)
        super().closeEvent(event)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # ── Toolbar ──────────────────────────────────────────
        toolbar = QHBoxLayout()

        self.btn_refresh = QPushButton("Osvježi stanje sa UINO")
        self.btn_refresh.setFixedHeight(32)
        self.btn_refresh.setStyleSheet(
            "QPushButton { background:#2563eb; color:white; border-radius:4px;"
            " padding:0 16px; font-weight:bold; }"
            "QPushButton:hover { background:#1d4ed8; }"
            "QPushButton:disabled { background:#93c5fd; }"
        )
        self.btn_refresh.clicked.connect(self._on_refresh_clicked)
        toolbar.addWidget(self.btn_refresh)

        toolbar.addSpacing(16)
        self.lbl_status = QLabel("Učitavam podatke iz baze…")
        self.lbl_status.setStyleSheet("color: #6b7280; font-size: 12px;")
        toolbar.addWidget(self.lbl_status)
        toolbar.addStretch()

        # Pretraga
        self.le_search = QLineEdit()
        self.le_search.setPlaceholderText("Pretraži po tarifnom broju ili opisu…")
        self.le_search.setFixedWidth(280)
        self.le_search.textChanged.connect(self._apply_filter)
        toolbar.addWidget(self.le_search)

        layout.addLayout(toolbar)

        # ── Info bar ─────────────────────────────────────────
        self.info_bar = QFrame()
        self.info_bar.setFrameShape(QFrame.StyledPanel)
        self.info_bar.setStyleSheet(
            "QFrame { background:#eff6ff; border:1px solid #bfdbfe;"
            " border-radius:4px; padding:4px 8px; }"
        )
        info_layout = QHBoxLayout(self.info_bar)
        info_layout.setContentsMargins(8, 4, 8, 4)

        self.lbl_source      = QLabel("Izvor: UINO")
        self.lbl_report_dt   = QLabel("Zadnje objavljeno stanje: —")
        self.lbl_download_dt = QLabel("Preuzeto u aplikaciju: —")
        self.lbl_napomena    = QLabel(
            "Napomena: Informativno stanje prema javno objavljenom PDF izvještaju."
        )
        self.lbl_napomena.setStyleSheet("color:#92400e; font-style:italic;")

        for lbl in (self.lbl_source, self.lbl_report_dt, self.lbl_download_dt):
            lbl.setStyleSheet("font-size:12px; color:#1e40af;")
            info_layout.addWidget(lbl)
            info_layout.addWidget(self._separator())

        info_layout.addWidget(self.lbl_napomena)
        info_layout.addStretch()
        layout.addWidget(self.info_bar)

        # ── Tabela ───────────────────────────────────────────
        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels([c[0] for c in self.COLUMNS])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setWordWrap(True)
        self.table.setStyleSheet(
            "QTableWidget { font-size: 12pt; background: #ffffff; alternate-background-color: #f0f7f0; color: #1e3820; }"
            "QTableWidget::item { color: #1e3820; }"
            "QTableWidget::item:selected { background-color: #d4e8d4; color: #1e3820; }"
            "QHeaderView::section { font-size: 12pt; font-weight: bold; padding: 6px 8px; }"
        )

        hh = self.table.horizontalHeader()
        hh.setStretchLastSection(True)
        for i, (name, w) in enumerate(self.COLUMNS):
            if name == "Opis":
                hh.setSectionResizeMode(i, QHeaderView.ResizeToContents)
            else:
                hh.setSectionResizeMode(i, QHeaderView.Fixed)
                self.table.setColumnWidth(i, w)

        layout.addWidget(self.table)

    @staticmethod
    def _separator() -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #bfdbfe;")
        return sep

    # ── Punjenje podataka ─────────────────────────────────────

    def _load_from_db(self):
        """Učitaj posljednji snapshot iz baze (ako postoji)."""
        try:
            from services.quota_service import ensure_tables, get_latest_snapshot_meta, get_snapshot_items
            ensure_tables()
            meta = get_latest_snapshot_meta()
            if not meta:
                self.lbl_status.setText("Nema preuzetih podataka. Kliknite 'Osvježi stanje sa UINO'.")
                return
            self._snapshot_id = meta["id"]
            self._update_info_bar(meta)
            rows = get_snapshot_items(self._snapshot_id)
            self._all_rows = [dict(r) for r in rows]
            self._populate_table(self._all_rows)
            self.lbl_status.setText(f"{len(self._all_rows)} kvota učitano iz baze.")
        except Exception as e:
            logger.warning(f"DB učitavanje neuspješno: {e}")
            self.lbl_status.setText("Nije moguće učitati podatke iz baze.")

    def _update_info_bar(self, meta: dict):
        rdt = meta.get("report_datetime")
        ddt = meta.get("downloaded_at")
        self.lbl_report_dt.setText(
            f"Zadnje objavljeno stanje: "
            f"{rdt.strftime('%d.%m.%Y %H:%M') if isinstance(rdt, datetime) else '—'}"
        )
        self.lbl_download_dt.setText(
            f"Preuzeto u aplikaciju: "
            f"{ddt.strftime('%d.%m.%Y %H:%M') if isinstance(ddt, datetime) else '—'}"
        )

    def _populate_table(self, rows: list[dict]):
        self.table.setRowCount(0)
        self.table.setRowCount(len(rows))
        self.table.verticalHeader().setDefaultSectionSize(28)

        for r, item in enumerate(rows):
            app = item.get("approved_qty")
            used = item.get("used_qty")
            rem = item.get("remaining_qty")
            color = _risk_color(rem, app)

            values = [
                item.get("tariff_code", ""),
                item.get("description", ""),
                item.get("unit", ""),
                _fmt_qty(app),
                _fmt_qty(used),
                _fmt_qty(rem),
                _fmt_pct(rem, app),
                _risk_label(rem, app),
            ]

            for c, val in enumerate(values):
                cell = QTableWidgetItem(str(val))
                cell.setTextAlignment(Qt.AlignVCenter | (Qt.AlignRight if c >= 3 else Qt.AlignLeft))
                if c == 7:  # Status kolona
                    icon = _risk_icon(rem, app)
                    if icon:
                        cell.setIcon(icon)
                if color:
                    cell.setBackground(color)
                self.table.setItem(r, c, cell)

    # ── Pretraga ──────────────────────────────────────────────

    def _apply_filter(self, text: str):
        q = text.strip().lower()
        if not q:
            self._populate_table(self._all_rows)
            return
        filtered = [
            row for row in self._all_rows
            if q in (row.get("tariff_code") or "").lower()
            or q in (row.get("description") or "").lower()
        ]
        self._populate_table(filtered)

    # ── Osvježi ───────────────────────────────────────────────

    def _on_refresh_clicked(self):
        if self._worker and self._worker.isRunning():
            return
        self.btn_refresh.setEnabled(False)
        self.lbl_status.setText("Preuzimanje UINO PDF izvještaja…")

        self._worker = _RefreshWorker(parent=self)
        self._worker.success.connect(self._on_refresh_success)
        self._worker.error.connect(self._on_refresh_error)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.start()

    def _on_refresh_success(self, snapshot_id: int, status: str):
        self.btn_refresh.setEnabled(True)
        self._snapshot_id = snapshot_id

        if status == "duplicate":
            self.lbl_status.setText(
                "Ovaj izvještaj je već preuzet. Prikazano je posljednje dostupno stanje."
            )
        else:
            try:
                from services.quota_service import get_latest_snapshot_meta, get_snapshot_items
                meta = get_latest_snapshot_meta()
                if meta:
                    self._update_info_bar(meta)
                rows = get_snapshot_items(snapshot_id)
                self._all_rows = [dict(r) for r in rows]
                self._populate_table(self._all_rows)
                self.lbl_status.setText(f"Osvježeno: {len(self._all_rows)} kvota učitano.")
            except Exception as e:
                self.lbl_status.setText(f"Greška pri prikazu: {e}")

    def _on_refresh_error(self, msg: str):
        self.btn_refresh.setEnabled(True)
        self.lbl_status.setText("Greška pri preuzimanju.")

        if "preuzeti" in msg.lower() or "internet" in msg.lower() or "connect" in msg.lower():
            user_msg = "Nije moguće preuzeti UINO PDF. Provjerite internet konekciju."
        elif "parser" in msg.lower() or "format" in msg.lower():
            user_msg = (
                "PDF je preuzet, ali parser nije mogao pročitati podatke.\n"
                "Moguće je da je UINO promijenio format izvještaja."
            )
        else:
            user_msg = f"UINO PDF trenutno nije dostupan.\n\n{msg}"

        QMessageBox.warning(self, "Greška pri preuzimanju kvota", user_msg)

