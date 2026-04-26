"""
Document panel — lijevi panel sa upload area, mode karticama i tabelom.
Botanički Sage Green dizajn.

📄 Popravka dugmeta: memory/project_agent_button_fix.md
   scripts/CHANGES_2026-04-26.md
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Signal, Qt
import qtawesome as qta
from .upload_area import UploadArea
from .file_table import FileTable
from .results_viewer import ResultsViewer
from ..models.file_item import FileItem
from ..constants import *


class DocumentPanel(QWidget):
    """Lijevi panel sa dokumentima."""

    files_added = Signal(list)
    analyze_requested = Signal()
    clear_requested = Signal()
    file_selected = Signal(FileItem)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(f"DocumentPanel {{ background-color: {COLOR_SAGE_BG}; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 0)
        layout.setSpacing(14)

        # ── Header ────────────────────────────────────────────────────────────
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)

        header_label = QLabel("Dokumenti")
        header_label.setStyleSheet(f"""
            font-size: 15px;
            font-weight: bold;
            color: {COLOR_TEXT};
            background: transparent;
            padding-bottom: 4px;
            border-bottom: 2px solid {COLOR_SAGE};
        """)
        header_row.addWidget(header_label)
        header_row.addStretch()

        gear_btn = QPushButton(qta.icon(ICON_COG, color=COLOR_SAGE_DARK), "")
        gear_btn.setFixedSize(30, 30)
        gear_btn.setToolTip("Podešavanja agenta")
        gear_btn.setStyleSheet(f"""
            QPushButton {{
                border: 1px solid {COLOR_SAGE_PALE};
                border-radius: 6px;
                background-color: white;
            }}
            QPushButton:hover {{
                background-color: {COLOR_SAGE_PANEL};
                border-color: {COLOR_SAGE_MID};
            }}
        """)
        header_row.addWidget(gear_btn)

        layout.addLayout(header_row)

        # ── Upload area (uključuje mode kartice) ──────────────────────────────
        self.upload_area = UploadArea()
        self.upload_area.files_dropped.connect(self._on_files_dropped)
        layout.addWidget(self.upload_area)

        # ── Tabela fajlova ────────────────────────────────────────────────────
        self.file_table = FileTable()
        self.file_table.file_selected.connect(self.file_selected.emit)
        self.file_table.file_removed.connect(self._on_file_removed)
        layout.addWidget(self.file_table, 1)

        # ── Rezultati ─────────────────────────────────────────────────────────
        self.results_viewer = ResultsViewer()
        layout.addWidget(self.results_viewer)

        # Connect
        self.upload_area.btn_analyze.clicked.connect(self.analyze_requested.emit)
        self.upload_area.btn_clear.clicked.connect(self._on_clear)
        self.file_table.file_selected.connect(self.results_viewer.show_results)

    def _on_files_dropped(self, filepaths: list):
        for filepath in filepaths:
            file_item = FileItem.from_filepath(filepath)
            self.file_table.add_file(file_item)
        # ⭐ Resetuj loading state — poništava zaostali stylesheet i tekst
        self.upload_area.set_loading(False)
        self.upload_area.btn_analyze.setEnabled(True)
        self.files_added.emit(filepaths)

    def _on_file_removed(self, filepath: str):
        if len(self.file_table.get_files()) == 0:
            self.upload_area.set_loading(False)
            self.upload_area.btn_analyze.setEnabled(False)
            self.results_viewer.clear()

    def _on_clear(self):
        self.file_table.clear_files()
        self.results_viewer.clear()
        # ⭐ Prvo resetuj loading state (vraća normalan stylesheet i tekst)
        self.upload_area.set_loading(False)
        self.upload_area.btn_analyze.setEnabled(False)
        self.clear_requested.emit()

    def get_files(self) -> list:
        return self.file_table.get_files()
