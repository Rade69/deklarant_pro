"""
Logs Panel - UI for log viewing.

TASK 11: Styling improvements - bolji filteri, statistics, export
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QPushButton, QComboBox, QLineEdit,
    QDateEdit, QMessageBox, QGroupBox, QCheckBox,
    QGridLayout, QFrame
)
from PySide6.QtCore import Signal, QDate
from PySide6.QtGui import QFont
from typing import List, Dict, Any
import qtawesome as qta
from gui.tabs.admin.panels import styles as S


class LogsPanel(QWidget):
    """Logs panel UI sa poboljšanim styling-om."""

    # Signali
    refresh_requested = Signal()
    filter_requested = Signal(dict)
    export_requested = Signal()
    clear_requested = Signal()

    def __init__(self, parent=None):
        """Inicijalizacija."""
        super().__init__(parent)
        self.setup_ui()
        self._apply_styles()

    def _apply_styles(self):
        """Primijeni styling za Logs panel."""
        self.setStyleSheet(S.PANEL_BASE_STYLE)
        for groupbox in self.findChildren(QGroupBox):
            groupbox.setStyleSheet(S.GROUPBOX_STYLE)

        # Log display styling
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #333;
                border-radius: 4px;
                padding: 10px;
                font-family: 'Courier New', 'Consolas', monospace;
                font-size: 12px;
                line-height: 1.5;
            }
            QTextEdit:focus {
                border-color: #0078d4;
            }
        """)

        # Input fields styling
        input_style = """
            QComboBox, QLineEdit, QDateEdit {
                border: 1px solid #ddd;
                border-radius: 3px;
                padding: 6px 10px;
                background-color: white;
                font-size: 13px;
                min-width: 120px;
            }
            QComboBox:hover, QLineEdit:hover, QDateEdit:hover {
                border-color: #bbb;
            }
            QComboBox:focus, QLineEdit:focus, QDateEdit:focus {
                border-color: #0078d4;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
        """
        
        for widget in self.findChildren(QComboBox):
            widget.setStyleSheet(input_style)
        for widget in self.findChildren(QLineEdit):
            widget.setStyleSheet(input_style)
        for widget in self.findChildren(QDateEdit):
            widget.setStyleSheet(input_style)

        # Button styling
        button_style = """
            QPushButton {
                padding: 8px 16px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: white;
                font-size: 13px;
                font-weight: 500;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
                border-color: #bbb;
            }
            QPushButton:pressed {
                background-color: #e0e0e0;
            }
            QPushButton#refreshButton {
                background-color: #0078d4;
                color: white;
                border-color: #0078d4;
            }
            QPushButton#refreshButton:hover {
                background-color: #106ebe;
            }
            QPushButton#exportButton {
                background-color: #28a745;
                color: white;
                border-color: #28a745;
            }
            QPushButton#exportButton:hover {
                background-color: #218838;
            }
            QPushButton#clearButton {
                background-color: #dc3545;
                color: white;
                border-color: #dc3545;
            }
            QPushButton#clearButton:hover {
                background-color: #c82333;
            }
        """
        
        self.btn_refresh.setStyleSheet(button_style)
        self.btn_export.setStyleSheet(button_style)
        self.btn_clear.setStyleSheet(button_style)

        # Statistics labels styling
        for label in self.findChildren(QLabel):
            if label.objectName() == "stat_label":
                label.setStyleSheet("font-weight: bold; color: #333;")
            elif label.objectName() == "stat_value":
                label.setStyleSheet("font-weight: bold; color: #0078d4; font-size: 14px;")

    def setup_ui(self):
        """Setup UI-a sa statistics i boljim filterima."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Header sa ikonicom
        header_layout = QHBoxLayout()
        
        header_icon = QLabel()
        header_icon.setPixmap(qta.icon('fa5s.file-alt', color='#333333', scale_factor=2).pixmap(32, 32))
        header_layout.addWidget(header_icon)
        
        header = QLabel("Logovi")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #333; margin-left: 10px;")
        header_layout.addWidget(header)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)

        # ===== STATISTICS GROUP =====
        stats_group = QGroupBox("📊 Statistika Logova")
        stats_layout = QGridLayout(stats_group)
        stats_layout.setVerticalSpacing(10)
        stats_layout.setHorizontalSpacing(20)

        # Ukupno logova
        self.lbl_total = QLabel("Ukupno:")
        self.lbl_total.setObjectName("stat_label")
        self.lbl_total.setFont(QFont("Arial", 13))
        stats_layout.addWidget(self.lbl_total, 0, 0)

        self.val_total = QLabel("0")
        self.val_total.setObjectName("stat_value")
        self.val_total.setFont(QFont("Arial", 14, QFont.Bold))
        stats_layout.addWidget(self.val_total, 0, 1)

        # ERROR count
        self.lbl_error = QLabel("ERROR:")
        self.lbl_error.setObjectName("stat_label")
        self.lbl_error.setStyleSheet("color: #d32f2f;")
        stats_layout.addWidget(self.lbl_error, 0, 2)

        self.val_error = QLabel("0")
        self.val_error.setObjectName("stat_value")
        self.val_error.setStyleSheet("color: #d32f2f;")
        stats_layout.addWidget(self.val_error, 0, 3)

        # WARNING count
        self.lbl_warning = QLabel("WARNING:")
        self.lbl_warning.setObjectName("stat_label")
        self.lbl_warning.setStyleSheet("color: #f57c00;")
        stats_layout.addWidget(self.lbl_warning, 1, 0)

        self.val_warning = QLabel("0")
        self.val_warning.setObjectName("stat_value")
        self.val_warning.setStyleSheet("color: #f57c00;")
        stats_layout.addWidget(self.val_warning, 1, 1)

        # INFO count
        self.lbl_info = QLabel("INFO:")
        self.lbl_info.setObjectName("stat_label")
        self.lbl_info.setStyleSheet("color: #1976d2;")
        stats_layout.addWidget(self.lbl_info, 1, 2)

        self.val_info = QLabel("0")
        self.val_info.setObjectName("stat_value")
        self.val_info.setStyleSheet("color: #1976d2;")
        stats_layout.addWidget(self.val_info, 1, 3)

        # DEBUG count
        self.lbl_debug = QLabel("DEBUG:")
        self.lbl_debug.setObjectName("stat_label")
        self.lbl_debug.setStyleSheet("color: #757575;")
        stats_layout.addWidget(self.lbl_debug, 2, 0)

        self.val_debug = QLabel("0")
        self.val_debug.setObjectName("stat_value")
        self.val_debug.setStyleSheet("color: #757575;")
        stats_layout.addWidget(self.val_debug, 2, 1)

        layout.addWidget(stats_group)

        # ===== FILTER GROUP =====
        filter_group = QGroupBox("🔍 Filteri")
        filter_layout = QGridLayout(filter_group)
        filter_layout.setVerticalSpacing(10)
        filter_layout.setHorizontalSpacing(15)

        # Row 0: Level i Search
        filter_layout.addWidget(QLabel("Level:"), 0, 0)
        self.level_combo = QComboBox()
        self.level_combo.addItem("Svi", None)
        self.level_combo.addItem("INFO", "INFO")
        self.level_combo.addItem("DEBUG", "DEBUG")
        self.level_combo.addItem("WARNING", "WARNING")
        self.level_combo.addItem("ERROR", "ERROR")
        filter_layout.addWidget(self.level_combo, 0, 1)

        filter_layout.addWidget(QLabel("Search:"), 0, 2)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Pretraga po tekstu...")
        self.search_input.returnPressed.connect(self._on_search)
        filter_layout.addWidget(self.search_input, 0, 3)

        # Row 1: Date range
        filter_layout.addWidget(QLabel("Od:"), 1, 0)
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addDays(-7))
        filter_layout.addWidget(self.date_from, 1, 1)

        filter_layout.addWidget(QLabel("Do:"), 1, 2)
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        filter_layout.addWidget(self.date_to, 1, 3)

        # Row 2: Options
        self.auto_scroll_check = QCheckBox("Auto-scroll (novi logovi na dno)")
        self.auto_scroll_check.setChecked(True)
        self.auto_scroll_check.setFont(QFont("Arial", 13))
        filter_layout.addWidget(self.auto_scroll_check, 2, 0, 1, 2)

        self.include_timestamp_check = QCheckBox("Prikaži timestamp")
        self.include_timestamp_check.setChecked(True)
        self.include_timestamp_check.setFont(QFont("Arial", 13))
        filter_layout.addWidget(self.include_timestamp_check, 2, 2, 1, 2)

        filter_layout.setColumnStretch(4, 1)
        layout.addWidget(filter_group)

        # ===== ACTION BUTTONS =====
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_refresh = QPushButton(
            qta.icon('fa5s.sync', color='white'),
            " Refresh"
        )
        self.btn_refresh.setFont(QFont("Arial", 13))
        self.btn_refresh.setToolTip("Osveži prikaz log-ova")
        self.btn_refresh.clicked.connect(self._on_refresh_clicked)
        self.btn_refresh.setMinimumHeight(38)
        self.btn_refresh.setObjectName("refreshButton")
        btn_layout.addWidget(self.btn_refresh)

        self.btn_export = QPushButton(
            qta.icon('fa5s.file-export', color='white'),
            " Export"
        )
        self.btn_export.setFont(QFont("Arial", 13))
        self.btn_export.setToolTip("Eksportuj log-ove u fajl")
        self.btn_export.clicked.connect(self._on_export_clicked)
        self.btn_export.setMinimumHeight(38)
        self.btn_export.setObjectName("exportButton")
        btn_layout.addWidget(self.btn_export)

        self.btn_clear = QPushButton(
            qta.icon('fa5s.trash', color='white'),
            " Clear"
        )
        self.btn_clear.setFont(QFont("Arial", 13))
        self.btn_clear.setToolTip("Obriši sve log-ove iz prikaza")
        self.btn_clear.clicked.connect(self._on_clear_clicked)
        self.btn_clear.setMinimumHeight(38)
        self.btn_clear.setObjectName("clearButton")
        btn_layout.addWidget(self.btn_clear)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("color: #ddd; background-color: #ddd;")
        layout.addWidget(separator)

        # Log display
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Courier New", 12))
        self.log_text.setMinimumHeight(400)
        layout.addWidget(self.log_text)

    # PUBLIC API

    def set_logs(self, logs: List[Dict[str, Any]]):
        """
        Postavi log-ove za prikaz.

        Args:
            logs: Lista dict-ova sa log entries
        """
        self.log_text.clear()

        if not logs:
            self.log_text.append(f'<span style="color: {S.TEXT_MUTED};">(Nema log-ova za prikaz)</span>')
            self._update_statistics([])
            return

        show_timestamp = self.include_timestamp_check.isChecked()
        for log in logs:
            self.log_text.append(self._format_log_entry(log, show_timestamp))

        if self.auto_scroll_check.isChecked():
            scrollbar = self.log_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

        self._update_statistics(logs)

    def append_log(self, log: Dict[str, Any]):
        """
        Dodaj jedan log na kraj.

        Args:
            log: Dict sa log informacijama
        """
        show_timestamp = self.include_timestamp_check.isChecked()
        self.log_text.append(self._format_log_entry(log, show_timestamp))

        if self.auto_scroll_check.isChecked():
            scrollbar = self.log_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    def clear_logs(self):
        """Obriši sve log-ove iz prikaza."""
        self.log_text.clear()
        self._update_statistics([])

    def show_success(self, message: str):
        """Prikaži success poruku."""
        QMessageBox.information(self, "Uspjeh", message)

    def show_error(self, message: str):
        """Prikaži error poruku."""
        QMessageBox.critical(self, "Greška", message)

    # PRIVATE HELPERS

    def _format_log_entry(self, log: Dict[str, Any], show_timestamp: bool) -> str:
        """Formatiraj jedan log zapis u HTML string."""
        timestamp = log.get('timestamp', '')
        level = log.get('level', '')
        message = log.get('message', '')
        color = S.log_color(level)

        if show_timestamp and timestamp:
            return (
                f'<span style="color: {S.LOG_TIMESTAMP};">[{timestamp}]</span> '
                f'<span style="color: {color}; font-weight: bold;">{level:8}</span> '
                f'<span style="color: {S.LOG_DEFAULT};">{message}</span>'
            )
        return (
            f'<span style="color: {color}; font-weight: bold;">{level:8}</span> '
            f'<span style="color: {S.LOG_DEFAULT};">{message}</span>'
        )

    def _update_statistics(self, logs: List[Dict[str, Any]]):
        """Ažuriraj statistiku logova."""
        total = len(logs)
        error_count = sum(1 for log in logs if log.get('level') == 'ERROR')
        warning_count = sum(1 for log in logs if log.get('level') == 'WARNING')
        info_count = sum(1 for log in logs if log.get('level') == 'INFO')
        debug_count = sum(1 for log in logs if log.get('level') == 'DEBUG')

        self.val_total.setText(str(total))
        self.val_error.setText(str(error_count))
        self.val_warning.setText(str(warning_count))
        self.val_info.setText(str(info_count))
        self.val_debug.setText(str(debug_count))

    def _on_refresh_clicked(self):
        """Refresh button clicked."""
        self.refresh_requested.emit()

    def _on_search(self):
        """Search triggered."""
        filters = {
            'level': self.level_combo.currentData(),
            'search': self.search_input.text(),
            'from_date': self.date_from.date().toString('yyyy-MM-dd'),
            'to_date': self.date_to.date().toString('yyyy-MM-dd'),
        }
        self.filter_requested.emit(filters)

    def _on_export_clicked(self):
        """Export button clicked."""
        self.export_requested.emit()

    def _on_clear_clicked(self):
        """Clear button clicked."""
        reply = QMessageBox.question(
            self,
            "Potvrda",
            "Da li želiš da obrišeš sve log-ove iz prikaza?\n\n"
            "Ovo ne briše log fajl, samo trenutni prikaz.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.clear_requested.emit()
            self.clear_logs()
