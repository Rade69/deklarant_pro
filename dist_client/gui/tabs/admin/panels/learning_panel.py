"""
Learning Panel — GUI za upravljanje učenjem aplikacije iz XML deklaracija.
"""

from __future__ import annotations

import shutil
import hashlib
from pathlib import Path

import qtawesome as qta
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
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

from services.agent.learning.exporter_xml_indexer import get_xml_folder
from gui.utils.safe_message_box import SafeMessageBox as QMessageBox

XML_FOLDER = get_xml_folder()


# ── DB helper ────────────────────────────────────────────────────────────────

def _db_connect():
    import psycopg2
    from config.settings import get_db_settings
    s = get_db_settings()
    return psycopg2.connect(
        host=s.host, port=s.port, dbname=s.database,
        user=s.user, password=s.password,
    )


# ── Worker threadovi ─────────────────────────────────────────────────────────

class _ReindexWorker(QThread):
    log_line = Signal(str)
    finished = Signal(int, int, int)  # dodano_parova, ukupno_parova, uvezeno_tarifa
    error    = Signal(str)

    def run(self):
        handler = None
        logger = None
        try:
            from services.agent.learning.exporter_xml_indexer import reindex, get_stats, get_xml_folder
            from services.tariff.tariff_mapping_service import TariffMappingService
            import logging

            class _QtHandler(logging.Handler):
                def __init__(self, sig): self._s = sig; super().__init__()
                def emit(self, record): self._s.emit(self.format(record))

            handler = _QtHandler(self.log_line)
            handler.setFormatter(logging.Formatter("%(message)s"))
            logger = logging.getLogger("deklarant_pro.exporter_indexer")
            logger.addHandler(handler)

            # Korak 1: reindeksiraj parove izvoznik+uvoznik
            self.log_line.emit("Korak 1/2 — Indeksiram parove izvoznik+uvoznik...")
            dodano = reindex()
            stats  = get_stats()
            ukupno = stats.get("total_pairs", 0)

            # Korak 2: ekstrahuj tarifne veze iz svih XML-ova
            self.log_line.emit("Korak 2/2 — Ekstraktujem tarifne veze iz XML-ova...")
            xml_folder = get_xml_folder()
            xml_paths = [str(p) for p in xml_folder.glob("*.xml")]
            if xml_paths:
                tariff_stats = TariffMappingService().import_from_xml_files(xml_paths)
                uvezeno = tariff_stats.get("imported", 0)
                self.log_line.emit(
                    f"   Obrađeno {tariff_stats['total_files']} fajlova, "
                    f"pronađeno {tariff_stats['total_items']} stavki, "
                    f"uvezeno {uvezeno} novih veza."
                )
            else:
                uvezeno = 0

            self.finished.emit(dodano, ukupno, uvezeno)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            if logger is not None and handler is not None:
                logger.removeHandler(handler)


class _StatsWorker(QThread):
    """Učitava sve statistike iz baze u jednom upitu."""
    finished = Signal(dict)
    error    = Signal(str)

    def run(self):
        conn = None
        try:
            from services.agent.learning.exporter_xml_indexer import create_table_if_not_exists

            create_table_if_not_exists()
            conn = _db_connect()
            with conn.cursor() as cur:
                stats = {}
                queries = {
                    "deklaracije": "SELECT COUNT(*) FROM catalogs.exporter_xml_index",
                    "tarife": "SELECT COUNT(*) FROM catalogs.product_tariff_mapping",
                    "uvoznici": "SELECT COUNT(*) FROM catalogs.uvoznici",
                    "izvoznici": "SELECT COUNT(*) FROM catalogs.izvoznici",
                }
                for key, query in queries.items():
                    cur.execute(query)
                    stats[key] = cur.fetchone()[0]
            self.finished.emit(stats)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            if conn is not None:
                conn.close()


# ── Panel ────────────────────────────────────────────────────────────────────

class LearningPanel(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._reindex_worker: _ReindexWorker | None = None
        self._stats_worker:   _StatsWorker   | None = None
        self._setup_ui()
        self._refresh_stats()

    def closeEvent(self, event):
        self._stop_worker(self._stats_worker)
        self._stop_worker(self._reindex_worker)
        super().closeEvent(event)

    @staticmethod
    def _stop_worker(worker: QThread | None):
        if worker and worker.isRunning():
            worker.quit()
            worker.wait(1500)

    # ── Izgradnja UI-a ───────────────────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(14)

        # Zaglavlje
        hdr = QHBoxLayout()
        icon_lbl = QLabel()
        icon_lbl.setPixmap(
            qta.icon("fa5s.brain", color="#1E3A5F", scale_factor=2).pixmap(32, 32)
        )
        hdr.addWidget(icon_lbl)
        title = QLabel("Učenje iz XML deklaracija")
        title.setStyleSheet(
            "font-size: 22px; font-weight: bold; color: #1E3A5F; margin-left: 10px;"
        )
        hdr.addWidget(title)
        hdr.addStretch()
        layout.addLayout(hdr)

        layout.addWidget(self._make_xml_group())
        layout.addWidget(self._make_stats_group())
        layout.addWidget(self._make_log_group())
        layout.addStretch()

    def _make_xml_group(self) -> QGroupBox:
        grp = QGroupBox("📂 XML fajlovi (docs/NOVA ASIKUDA)")
        grp.setStyleSheet(self._grp_style())
        lay = QVBoxLayout(grp)
        lay.setSpacing(10)

        self.lbl_xml_count = self._info_label("Broj XML fajlova: —")
        lay.addWidget(self.lbl_xml_count)

        self.lbl_xml_folder = QLabel(str(XML_FOLDER))
        self.lbl_xml_folder.setStyleSheet(
            "color: #555; font-size: 13px; font-family: monospace;"
        )
        lay.addWidget(self.lbl_xml_folder)

        btn_lay = QHBoxLayout()
        btn_lay.setSpacing(10)

        self.btn_add_xml = QPushButton(
            qta.icon("fa5s.file-import", color="white"), "  Dodaj XML fajlove"
        )
        self.btn_add_xml.setMinimumHeight(42)
        self.btn_add_xml.setStyleSheet(self._btn_style("#2563eb"))
        self.btn_add_xml.clicked.connect(self._on_add_xml)
        btn_lay.addWidget(self.btn_add_xml)

        self.btn_reindex = QPushButton(
            qta.icon("fa5s.sync-alt", color="white"), "  Pokreni reindeksiranje"
        )
        self.btn_reindex.setMinimumHeight(42)
        self.btn_reindex.setStyleSheet(self._btn_style("#1E3A5F"))
        self.btn_reindex.clicked.connect(self._on_reindex)
        btn_lay.addWidget(self.btn_reindex)

        self.btn_refresh = QPushButton(
            qta.icon("fa5s.redo", color="#374151"), "  Osvježi statistiku"
        )
        self.btn_refresh.setMinimumHeight(42)
        self.btn_refresh.setStyleSheet(self._btn_style_secondary())
        self.btn_refresh.clicked.connect(self._refresh_stats)
        btn_lay.addWidget(self.btn_refresh)

        btn_lay.addStretch()
        lay.addLayout(btn_lay)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setRange(0, 0)
        self.progress.setFixedHeight(18)
        self.progress.setStyleSheet("""
            QProgressBar { border: 1px solid #ccc; border-radius: 4px; background: #f5f5f5; }
            QProgressBar::chunk { background: #1E3A5F; border-radius: 3px; }
        """)
        lay.addWidget(self.progress)
        return grp

    def _make_stats_group(self) -> QGroupBox:
        grp = QGroupBox("📊 Naučene deklaracije — stanje baze")
        grp.setStyleSheet(self._grp_style())
        grid = QGridLayout(grp)
        grid.setSpacing(14)
        grid.setContentsMargins(14, 16, 14, 14)

        def stat_pair(row, icon_name, opis, attr):
            ico = QLabel()
            ico.setPixmap(
                qta.icon(icon_name, color="#1E3A5F", scale_factor=1.2).pixmap(22, 22)
            )
            lbl_opis = QLabel(opis)
            lbl_opis.setFont(QFont("Arial", 14))
            lbl_opis.setStyleSheet("color: #374151;")
            lbl_val = QLabel("—")
            lbl_val.setFont(QFont("Arial", 15, QFont.Bold))
            lbl_val.setStyleSheet("color: #1E3A5F;")
            grid.addWidget(ico,      row, 0)
            grid.addWidget(lbl_opis, row, 1)
            grid.addWidget(lbl_val,  row, 2)
            setattr(self, attr, lbl_val)

        stat_pair(0, "fa5s.file-code",   "Naučenih deklaracija (XML indeks):", "lbl_stat_dekl")
        stat_pair(1, "fa5s.tags",         "Tarifnih veza u bazi znanja:",       "lbl_stat_tarife")
        stat_pair(2, "fa5s.building",     "Uvoznika u bazi:",                   "lbl_stat_uvoznici")
        stat_pair(3, "fa5s.truck",        "Izvoznika u bazi:",                  "lbl_stat_izvoznici")

        grid.setColumnStretch(1, 1)
        return grp

    def _make_log_group(self) -> QGroupBox:
        grp = QGroupBox("📋 Tok reindeksiranja")
        grp.setStyleSheet(self._grp_style())
        lay = QVBoxLayout(grp)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFixedHeight(190)
        self.log_output.setFont(QFont("Monospace", 12))
        self.log_output.setStyleSheet(
            "background: #f8f9fa; border: 1px solid #dee2e6;"
            " border-radius: 4px; padding: 6px;"
        )
        self.log_output.setPlaceholderText(
            "Ovdje će se prikazivati tok reindeksiranja..."
        )
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
        preskoceno = 0
        identicni = 0
        apply_to_all: bool | None = None
        for src in files:
            src_path = Path(src)
            if not self._is_valid_learning_xml(src_path):
                preskoceno += 1
                continue

            if self._is_duplicate_xml(src_path):
                self._log(f"⚠️ Preskočen duplikat: {src_path.name}")
                preskoceno += 1
                continue

            dst = XML_FOLDER / src_path.name
            if dst.exists():
                if _file_hash(dst) == _file_hash(src_path):
                    # Isto ime, isti sadržaj — tiho preskoči, nema potrebe pitati
                    identicni += 1
                    continue

                if apply_to_all is not None:
                    prepisi = apply_to_all
                else:
                    odg = QMessageBox.question(
                        self, "Fajl postoji",
                        f"{dst.name} već postoji sa drugačijim sadržajem. Prepiši?",
                        QMessageBox.Yes | QMessageBox.No
                        | QMessageBox.YesToAll | QMessageBox.NoToAll,
                        QMessageBox.No,
                    )
                    if odg == QMessageBox.YesToAll:
                        apply_to_all = True
                    elif odg == QMessageBox.NoToAll:
                        apply_to_all = False
                    prepisi = odg in (QMessageBox.Yes, QMessageBox.YesToAll)

                if not prepisi:
                    preskoceno += 1
                    continue
            shutil.copy2(src, dst)
            kopirano += 1

        self._log(f"✅ Kopirano {kopirano} fajl(ova) u {XML_FOLDER.name}")
        if identicni:
            self._log(f"ℹ️ Već postoji (identičan sadržaj), preskočeno: {identicni}")
        if preskoceno:
            self._log(f"⚠️ Preskočeno {preskoceno} fajl(ova)")
        self._refresh_xml_count()

    def _is_valid_learning_xml(self, xml_path: Path) -> bool:
        try:
            from services.agent.learning.exporter_xml_indexer import extract_parties_from_xml
            exporter, consignee, _jib, _date = extract_parties_from_xml(xml_path)
            if exporter and consignee:
                return True
            self._log(f"⚠️ Preskočen XML bez exportera/consignee-a: {xml_path.name}")
            return False
        except Exception as e:
            self._log(f"⚠️ Nevalidan XML {xml_path.name}: {e}")
            return False

    def _is_duplicate_xml(self, xml_path: Path) -> bool:
        src_hash = _file_hash(xml_path)
        for existing in XML_FOLDER.glob("*.xml"):
            if existing.name == xml_path.name:
                continue
            if _file_hash(existing) == src_hash:
                return True
        return False

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

    def _on_reindex_done(self, dodano: int, ukupno: int, uvezeno_tarifa: int):
        self.progress.setVisible(False)
        self.btn_reindex.setEnabled(True)
        self._log(
            f"✅ Završeno — {dodano} novih parova, ukupno {ukupno} deklaracija, "
            f"{uvezeno_tarifa} novih tarifnih veza."
        )
        self._refresh_stats()

    def _on_reindex_error(self, msg: str):
        self.progress.setVisible(False)
        self.btn_reindex.setEnabled(True)
        self._log(f"❌ Greška: {msg}")

    def _refresh_stats(self):
        self._refresh_xml_count()
        self._stats_worker = _StatsWorker()
        self._stats_worker.finished.connect(self._on_stats_loaded)
        self._stats_worker.error.connect(
            lambda e: self._log(f"⚠️ Statistika nedostupna: {e}")
        )
        self._stats_worker.start()

    def _on_stats_loaded(self, stats: dict):
        self.lbl_stat_dekl.setText(f"{stats['deklaracije']:,}")
        self.lbl_stat_tarife.setText(f"{stats['tarife']:,}")
        self.lbl_stat_uvoznici.setText(f"{stats['uvoznici']:,}")
        self.lbl_stat_izvoznici.setText(f"{stats['izvoznici']:,}")
        self._log("✅ Statistika osvježena")

    def _refresh_xml_count(self):
        if XML_FOLDER.exists():
            count = len(list(XML_FOLDER.glob("*.xml")))
            self.lbl_xml_count.setText(f"Broj XML fajlova: {count}")
        else:
            self.lbl_xml_count.setText("Broj XML fajlova: 0  (folder ne postoji)")

    def _log(self, tekst: str):
        try:
            self.log_output.append(tekst)
        except RuntimeError:
            return

    # ── Stilovi ──────────────────────────────────────────────────────────────

    @staticmethod
    def _info_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(QFont("Arial", 14))
        return lbl

    @staticmethod
    def _grp_style() -> str:
        return """
            QGroupBox {
                border: 1px solid #ddd; border-radius: 6px;
                margin-top: 12px; padding-top: 10px;
                font-weight: bold; font-size: 14px;
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
                padding: 6px 18px; font-size: 14px; font-weight: 600;
            }}
            QPushButton:disabled {{ background: #9ca3af; }}
        """

    @staticmethod
    def _btn_style_secondary() -> str:
        return """
            QPushButton {
                background: white; color: #374151;
                border: 1px solid #d1d5db; border-radius: 5px;
                padding: 6px 18px; font-size: 14px;
            }
            QPushButton:hover { background: #f3f4f6; }
        """


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
