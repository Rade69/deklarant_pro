"""
Learning Panel — GUI za upravljanje učenjem aplikacije iz XML deklaracija.

Omogućava:
- Pregled XML fajlova u docs/NOVA ASIKUDA/
- Dodavanje novih XML fajlova
- Pokretanje reindeksiranja (exporter_xml_index)
- Pregled statusa product_tariff_mapping
"""

from __future__ import annotations

import shutil
from pathlib import Path

import qtawesome as qta
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

XML_FOLDER = Path(__file__).parents[5] / "docs" / "NOVA ASIKUDA"


# ── Worker thread ────────────────────────────────────────────────────────────

class _ReindexWorker(QThread):
    log_line = Signal(str)
    finished = Signal(int, int)   # (dodano, ukupno)
    error = Signal(str)

    def run(self):
        try:
            from services.agent.learning.exporter_xml_indexer import reindex, get_stats
            import logging

            class _QtHandler(logging.Handler):
                def __init__(self, signal): self._s = signal; super().__init__()
                def emit(self, record): self._s.emit(self.format(record))

            handler = _QtHandler(self.log_line)
            handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
            logger = logging.getLogger("deklarant_pro.exporter_indexer")
            logger.addHandler(handler)

            self.log_line.emit("Pokrećem reindeksiranje...")
            dodano = reindex()
            stats = get_stats()
            ukupno = stats.get("total_pairs", 0)

            logger.removeHandler(handler)
            self.finished.emit(dodano, ukupno)
        except Exception as e:
            self.error.emit(str(e))


class _MappingStatsWorker(QThread):
    finished = Signal(int)
    error = Signal(str)

    def run(self):
        try:
            from database.db import get_db_connection
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM catalogs.product_tariff_mapping")
                    count = cur.fetchone()[0]
            self.finished.emit(count)
        except Exception as e:
            self.error.emit(str(e))


# ── Panel ────────────────────────────────────────────────────────────────────

class LearningPanel(QWidget):
    """Admin panel za učenje aplikacije iz XML deklaracija."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._reindex_worker: _ReindexWorker | None = None
        self._setup_ui()
        self._refresh_stats()

    # ── UI ───────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(14)

        # Header
        hdr = QHBoxLayout()
        icon_lbl = QLabel()
        icon_lbl.setPixmap(qta.icon("fa5s.brain", color="#1E3A5F", scale_factor=2).pixmap(32, 32))
        hdr.addWidget(icon_lbl)
        title = QLabel("Učenje iz XML deklaracija")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #1E3A5F; margin-left: 10px;")
        hdr.addWidget(title)
        hdr.addStretch()
        layout.addLayout(hdr)

        layout.addWidget(self._make_xml_group())
        layout.addWidget(self._make_mapping_group())
        layout.addWidget(self._make_log_group())
        layout.addStretch()

    def _make_xml_group(self) -> QGroupBox:
        grp = QGroupBox("📂 XML fajlovi (docs/NOVA ASIKUDA)")
        grp.setStyleSheet(self._grp_style())
        lay = QVBoxLayout(grp)
        lay.setSpacing(10)

        # Info redovi
        info_lay = QHBoxLayout()
        self.lbl_xml_count = self._info_label("XML fajlova: —")
        self.lbl_xml_folder = self._info_label(str(XML_FOLDER))
        self.lbl_xml_folder.setStyleSheet("color: #555; font-size: 12px; font-family: monospace;")
        info_lay.addWidget(self.lbl_xml_count)
        info_lay.addStretch()
        lay.addLayout(info_lay)
        lay.addWidget(self.lbl_xml_folder)

        # Dugmad
        btn_lay = QHBoxLayout()
        btn_lay.setSpacing(10)

        self.btn_add_xml = QPushButton(
            qta.icon("fa5s.file-import", color="white"), "  Dodaj XML fajlove"
        )
        self.btn_add_xml.setMinimumHeight(38)
        self.btn_add_xml.setStyleSheet(self._btn_style("#2563eb"))
        self.btn_add_xml.clicked.connect(self._on_add_xml)
        btn_lay.addWidget(self.btn_add_xml)

        self.btn_reindex = QPushButton(
            qta.icon("fa5s.sync-alt", color="white"), "  Pokreni reindeksiranje"
        )
        self.btn_reindex.setMinimumHeight(38)
        self.btn_reindex.setStyleSheet(self._btn_style("#1E3A5F"))
        self.btn_reindex.clicked.connect(self._on_reindex)
        btn_lay.addWidget(self.btn_reindex)

        self.btn_refresh = QPushButton(
            qta.icon("fa5s.redo", color="#555"), "  Osvježi statistiku"
        )
        self.btn_refresh.setMinimumHeight(38)
        self.btn_refresh.setStyleSheet(self._btn_style_secondary())
        self.btn_refresh.clicked.connect(self._refresh_stats)
        btn_lay.addWidget(self.btn_refresh)

        btn_lay.addStretch()
        lay.addLayout(btn_lay)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setRange(0, 0)   # indeterminate
        self.progress.setFixedHeight(18)
        self.progress.setStyleSheet("""
            QProgressBar { border: 1px solid #ccc; border-radius: 4px; background: #f5f5f5; }
            QProgressBar::chunk { background: #1E3A5F; border-radius: 3px; }
        """)
        lay.addWidget(self.progress)

        return grp

    def _make_mapping_group(self) -> QGroupBox:
        grp = QGroupBox("🧠 Product Tariff Mapping (naučeni mappinzi)")
        grp.setStyleSheet(self._grp_style())
        lay = QHBoxLayout(grp)

        self.lbl_mapping_count = self._info_label("Mappinga u bazi: —")
        self.lbl_mapping_count.setStyleSheet("font-size: 15px; font-weight: bold; color: #1E3A5F;")
        lay.addWidget(self.lbl_mapping_count)
        lay.addStretch()

        return grp

    def _make_log_group(self) -> QGroupBox:
        grp = QGroupBox("📋 Log reindeksiranja")
        grp.setStyleSheet(self._grp_style())
        lay = QVBoxLayout(grp)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFixedHeight(180)
        self.log_output.setFont(QFont("Monospace", 11))
        self.log_output.setStyleSheet(
            "background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; padding: 6px;"
        )
        self.log_output.setPlaceholderText("Ovdje će se prikazivati tok reindeksiranja...")
        lay.addWidget(self.log_output)

        return grp

    # ── Akcije ───────────────────────────────────────────────────────────────

    def _on_add_xml(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Odaberi XML deklaracije", "", "XML fajlovi (*.xml)"
        )
        if not files:
            return

        XML_FOLDER.mkdir(parents=True, exist_ok=True)
        kopirano = 0
        for src in files:
            dst = XML_FOLDER / Path(src).name
            if dst.exists():
                odgovor = QMessageBox.question(
                    self, "Fajl postoji",
                    f"{dst.name} već postoji. Prepiši?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
                )
                if odgovor != QMessageBox.Yes:
                    continue
            shutil.copy2(src, dst)
            kopirano += 1

        self._log(f"✅ Kopirano {kopirano} fajl(ova) u {XML_FOLDER.name}")
        self._refresh_xml_count()

    def _on_reindex(self):
        if self._reindex_worker and self._reindex_worker.isRunning():
            return

        self.log_output.clear()
        self.btn_reindex.setEnabled(False)
        self.progress.setVisible(True)

        self._reindex_worker = _ReindexWorker()
        self._reindex_worker.log_line.connect(self._log)
        self._reindex_worker.finished.connect(self._on_reindex_done)
        self._reindex_worker.error.connect(self._on_reindex_error)
        self._reindex_worker.start()

    def _on_reindex_done(self, dodano: int, ukupno: int):
        self.progress.setVisible(False)
        self.btn_reindex.setEnabled(True)
        self._log(f"✅ Reindeksiranje završeno — {dodano} promjena, ukupno {ukupno} parova u bazi.")
        self._refresh_stats()

    def _on_reindex_error(self, msg: str):
        self.progress.setVisible(False)
        self.btn_reindex.setEnabled(True)
        self._log(f"❌ Greška: {msg}")

    def _refresh_stats(self):
        self._refresh_xml_count()
        w = _MappingStatsWorker()
        w.finished.connect(lambda n: self.lbl_mapping_count.setText(f"Mappinga u bazi: {n:,}"))
        w.error.connect(lambda e: self.lbl_mapping_count.setText("Mappinga u bazi: (greška)"))
        w.start()
        self._mapping_worker = w  # sprečava GC

    def _refresh_xml_count(self):
        if XML_FOLDER.exists():
            count = len(list(XML_FOLDER.glob("*.xml")))
            self.lbl_xml_count.setText(f"XML fajlova: {count}")
        else:
            self.lbl_xml_count.setText("XML fajlova: 0 (folder ne postoji)")

    def _log(self, tekst: str):
        self.log_output.append(tekst)

    # ── Stilovi ──────────────────────────────────────────────────────────────

    @staticmethod
    def _info_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(QFont("Arial", 13))
        return lbl

    @staticmethod
    def _grp_style() -> str:
        return """
            QGroupBox {
                border: 1px solid #ddd; border-radius: 6px;
                margin-top: 12px; padding-top: 10px;
                font-weight: bold; font-size: 13px;
                background: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin; subcontrol-position: top left;
                padding: 0 8px; color: #333;
            }
        """

    @staticmethod
    def _btn_style(color: str) -> str:
        return f"""
            QPushButton {{
                background: {color}; color: white;
                border: none; border-radius: 5px;
                padding: 6px 16px; font-size: 13px; font-weight: 600;
            }}
            QPushButton:hover {{ opacity: 0.9; }}
            QPushButton:disabled {{ background: #9ca3af; }}
        """

    @staticmethod
    def _btn_style_secondary() -> str:
        return """
            QPushButton {
                background: white; color: #374151;
                border: 1px solid #d1d5db; border-radius: 5px;
                padding: 6px 16px; font-size: 13px;
            }
            QPushButton:hover { background: #f3f4f6; }
        """
