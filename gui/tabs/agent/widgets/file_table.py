"""
Tabela sa fajlovima.
"""

from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QWidget, QHBoxLayout, QProgressBar, QLabel
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
import qtawesome as qta
from ..models.file_item import FileItem
from ..constants import (
    COLOR_DANGER, COLOR_INFO, COLOR_PRIMARY, COLOR_SAGE,
    COLOR_SAGE_MID, COLOR_SAGE_PALE, COLOR_SUCCESS, COLOR_TEXT,
    COLOR_TEXT_MUTED, COLOR_WARNING,
    ICON_FILE_EXCEL, ICON_FILE_PDF, ICON_FILE_XML,
)


class FileTable(QTableWidget):
    """Tabela sa upload-ovanim fajlovima."""

    file_selected = Signal(FileItem)
    file_removed = Signal(str)  # filepath

    # Kolone
    COL_ICON = 0
    COL_TIP = 1
    COL_NAZIV = 2
    COL_VELICINA = 3
    COL_STATUS = 4
    COL_PARSER = 5
    COL_POUZDANOST = 6
    COL_AKCIJA = 7
    STATUS_LABELS = {
        "Uploaded": "Dodano",
        "Processing": "Obrada",
        "Completed": "Završeno",
        "Error": "Greška",
        "Skipped": "Preskočeno",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._files = {}  # filepath -> FileItem
        self._setup_ui()

    def _setup_ui(self):
        """Setup table."""
        # Kolone
        self.setColumnCount(8)
        self.setHorizontalHeaderLabels([
            "",
            "Tip",
            "Naziv fajla",
            "Veličina",
            "Status",
            "Parser",
            "Pouzdanost",
            "Akcija"
        ])

        # Column widths
        self.setColumnWidth(self.COL_ICON, 36)
        self.setColumnWidth(self.COL_TIP, 68)
        self.setColumnWidth(self.COL_NAZIV, 250)
        self.setColumnWidth(self.COL_VELICINA, 88)
        self.setColumnWidth(self.COL_STATUS, 106)
        self.setColumnWidth(self.COL_PARSER, 110)
        self.setColumnWidth(self.COL_POUZDANOST, 140)
        self.setColumnWidth(self.COL_AKCIJA, 64)

        # Header
        header = self.horizontalHeader()
        header.setSectionResizeMode(self.COL_NAZIV, QHeaderView.Stretch)
        header.setMinimumHeight(42)

        # Visina redova
        self.verticalHeader().setDefaultSectionSize(44)

        # Font - setFont() zaobilazi globalni QWidget { font-size: 11px }
        table_font = QFont()
        table_font.setPointSize(10)
        self.setFont(table_font)
        header_font = QFont()
        header_font.setPointSize(10)
        header_font.setBold(True)
        self.horizontalHeader().setFont(header_font)

        # Selection
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.setAlternatingRowColors(True)
        self.setShowGrid(True)

        # Click signal
        self.itemClicked.connect(self._on_item_clicked)

        # Styling — botanička zelena tema
        self.setStyleSheet(f"""
            QTableWidget {{
                border: 1px solid {COLOR_SAGE_PALE};
                border-radius: 6px;
                gridline-color: #d6e1e8;
                background-color: white;
                alternate-background-color: #f4f8fa;
            }}
            QTableWidget::item {{
                padding: 5px;
                font-size: 13px;
            }}
            QTableWidget::item:selected {{
                background-color: {COLOR_SAGE};
                color: white;
            }}
            QHeaderView::section {{
                background-color: #dbe7ee;
                padding: 8px;
                border: none;
                border-right: 1px solid #c5d5df;
                border-bottom: 2px solid {COLOR_SAGE_MID};
                font-weight: bold;
                font-size: 13px;
                color: {COLOR_TEXT};
            }}
        """)

    def add_file(self, file_item: FileItem):
        """Dodaj fajl u tabelu."""
        if file_item.filepath in self._files:
            return  # Vec postoji

        self._files[file_item.filepath] = file_item

        row = self.rowCount()
        self.insertRow(row)

        # Icon
        icon_name, icon_color = self._get_file_icon(file_item.file_type)
        icon_item = QTableWidgetItem()
        icon_item.setIcon(qta.icon(icon_name, color=icon_color))
        self.setItem(row, self.COL_ICON, icon_item)

        # Tip
        tip_item = QTableWidgetItem(file_item.file_type)
        tip_item.setTextAlignment(Qt.AlignCenter)
        self.setItem(row, self.COL_TIP, tip_item)

        # Naziv
        naziv_item = QTableWidgetItem(file_item.filename)
        naziv_item.setData(Qt.UserRole, file_item.filepath)
        self.setItem(row, self.COL_NAZIV, naziv_item)

        # Veličina
        size_item = QTableWidgetItem(file_item.size_str)
        size_item.setTextAlignment(Qt.AlignCenter)
        self.setItem(row, self.COL_VELICINA, size_item)

        # Status
        status_item = QTableWidgetItem(f"● {self._status_label(file_item.status)}")
        status_item.setTextAlignment(Qt.AlignCenter)
        status_item.setForeground(self._get_status_color(file_item.status))
        self.setItem(row, self.COL_STATUS, status_item)

        # Parser
        parser_item = QTableWidgetItem(file_item.parser)
        parser_item.setTextAlignment(Qt.AlignCenter)
        self.setItem(row, self.COL_PARSER, parser_item)

        # Pouzdanost (progress bar)
        pouzdanost_widget = self._create_pouzdanost_widget(file_item.confidence_pct)
        self.setCellWidget(row, self.COL_POUZDANOST, pouzdanost_widget)

        # Akcija (remove button)
        akcija_widget = self._create_akcija_widget(file_item.filepath)
        self.setCellWidget(row, self.COL_AKCIJA, akcija_widget)

    def _create_pouzdanost_widget(self, confidence_pct: int) -> QWidget:
        """Kreiraj pouzdanost widget sa progress bar-om."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(5, 2, 5, 2)

        # Progress bar
        progress = QProgressBar()
        progress.setMinimum(0)
        progress.setMaximum(100)
        progress.setValue(confidence_pct)
        progress.setTextVisible(False)
        progress.setFixedHeight(20)

        # Boja prema confidence-u
        if confidence_pct >= 80:
            color = COLOR_SUCCESS
        elif confidence_pct >= 60:
            color = COLOR_WARNING
        else:
            color = COLOR_DANGER

        progress.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {COLOR_SAGE_PALE};
                border-radius: 3px;
                background-color: #e4ebef;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 2px;
            }}
        """)

        # Label sa %
        label = QLabel(f"{confidence_pct}%")
        label.setStyleSheet(f"font-weight: bold; color: {COLOR_TEXT}; font-size: 13px;")
        label.setFixedWidth(40)
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        layout.addWidget(progress)
        layout.addWidget(label)

        return widget

    def _create_akcija_widget(self, filepath: str) -> QWidget:
        """Kreiraj akcija widget sa remove buttonom."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignCenter)

        btn = QPushButton(qta.icon('fa5s.trash-alt', color=COLOR_DANGER), "")
        btn.setFixedSize(28, 28)
        btn.setToolTip("Ukloni fajl")
        btn.clicked.connect(lambda: self._on_remove_file(filepath))
        btn.setStyleSheet("""
            QPushButton {
                border: 1px solid #c7d6df;
                border-radius: 4px;
                background-color: white;
            }
            QPushButton:hover {
                background-color: #f5e3e3;
                border-color: #ad3e3e;
            }
        """)

        layout.addWidget(btn)

        return widget

    def _get_file_icon(self, file_type: str) -> tuple:
        """Vrati ikonu za file type."""
        if file_type == 'PDF':
            return (ICON_FILE_PDF, 'red')
        elif file_type == 'Excel':
            return (ICON_FILE_EXCEL, 'green')
        elif file_type == 'XML':
            return (ICON_FILE_XML, 'blue')
        else:
            return ('fa5s.file', 'gray')

    def _get_status_color(self, status: str) -> QColor:
        """Vrati boju za status."""
        if status == 'Uploaded':
            return QColor(COLOR_INFO)
        elif status == 'Processing':
            return QColor(COLOR_PRIMARY)
        elif status == 'Completed':
            return QColor(COLOR_SUCCESS)
        elif status == 'Error':
            return QColor(COLOR_DANGER)
        elif status == 'Skipped':
            return QColor(COLOR_TEXT_MUTED)
        else:
            return QColor(COLOR_TEXT)

    def _status_label(self, status: str) -> str:
        return self.STATUS_LABELS.get(status, status)

    def _on_item_clicked(self, item):
        """Handle item click."""
        row = item.row()
        naziv_item = self.item(row, self.COL_NAZIV)
        filepath = naziv_item.data(Qt.UserRole)

        if filepath in self._files:
            self.file_selected.emit(self._files[filepath])

    def _on_remove_file(self, filepath: str):
        """Ukloni fajl iz tabele."""
        if filepath not in self._files:
            return

        # Find row
        for row in range(self.rowCount()):
            naziv_item = self.item(row, self.COL_NAZIV)
            if naziv_item.data(Qt.UserRole) == filepath:
                self.removeRow(row)
                break

        # Remove from dict
        del self._files[filepath]

        # Emit signal
        self.file_removed.emit(filepath)

    def update_file_status(self, filepath: str, status: str, confidence: float, parser: str = None):
        """Ažuriraj status, parser i confidence za fajl u tabeli.

        Poziva se iz Qt signala (thread-safe u PySide6).
        """
        for row in range(self.rowCount()):
            naziv_item = self.item(row, self.COL_NAZIV)
            if naziv_item and naziv_item.data(Qt.UserRole) == filepath:
                # Status
                status_item = self.item(row, self.COL_STATUS)
                if status_item:
                    status_item.setText(f"● {self._status_label(status)}")
                    status_item.setForeground(self._get_status_color(status))

                # Parser
                if parser:
                    parser_item = self.item(row, self.COL_PARSER)
                    if parser_item:
                        parser_item.setText(parser)

                # Confidence (progress bar)
                pct = int(confidence * 100)
                pouzdanost_widget = self._create_pouzdanost_widget(pct)
                self.setCellWidget(row, self.COL_POUZDANOST, pouzdanost_widget)

                # Ažuriraj FileItem u internom dictu
                if filepath in self._files:
                    self._files[filepath].status = status
                    self._files[filepath].confidence = confidence
                    if parser:
                        self._files[filepath].detected_parser = parser

                break

    def clear_files(self):
        """Očisti sve fajlove."""
        self.setRowCount(0)
        self._files.clear()

    def get_files(self) -> list:
        """Vrati sve fajlove."""
        return list(self._files.values())
