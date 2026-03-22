"""
Analytics Panel - UI for statistics.

TASK 15: Styling improvements - vizuelne kartice, progress bar-ovi, trendovi
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGroupBox, QGridLayout, QPushButton, QScrollArea,
    QFrame, QDateEdit, QComboBox
)
from PySide6.QtCore import Qt, QDate, Signal
from PySide6.QtGui import QFont
from typing import Dict, Any
import qtawesome as qta
from gui.tabs.admin.panels import styles as S


class AnalyticsPanel(QWidget):
    """Analytics panel UI sa poboljšanim styling-om."""

    # Signali
    refresh_requested = Signal()
    export_requested = Signal()

    def __init__(self, parent=None):
        """Inicijalizacija."""
        super().__init__(parent)
        self.setup_ui()
        self._apply_styles()

    def _apply_styles(self):
        """Primijeni styling za Analytics panel."""
        self.setStyleSheet(S.PANEL_BASE_STYLE)
        for groupbox in self.findChildren(QGroupBox):
            groupbox.setStyleSheet(S.GROUPBOX_STYLE)

        # Stat kartice styling
        card_style = """
            QLabel#statCard {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 15px;
            }
            QLabel#statCard:hover {
                border-color: #0078d4;
                background-color: #f5f9ff;
            }
        """
        
        for label in self.findChildren(QLabel):
            if label.objectName() == "statCard":
                label.setStyleSheet(card_style)

        # Stat value styling
        for label in self.findChildren(QLabel):
            if label.objectName() == "statValue":
                label.setStyleSheet("""
                    font-size: 32px;
                    font-weight: bold;
                    color: #0078d4;
                """)
            elif label.objectName() == "statLabel":
                label.setStyleSheet("""
                    font-size: 13px;
                    color: #666;
                    font-weight: 500;
                """)

        # Button styling
        button_style = """
            QPushButton {
                padding: 8px 16px;
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: white;
                font-size: 13px;
                font-weight: 500;
                min-width: 120px;
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
        """
        
        self.btn_refresh.setStyleSheet(button_style)
        self.btn_export.setStyleSheet(button_style)

    def setup_ui(self):
        """Setup UI-a sa vizuelnim karticama."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Header sa ikonicom
        header_layout = QHBoxLayout()
        
        header_icon = QLabel()
        header_icon.setPixmap(qta.icon('fa5s.chart-bar', color='#333333', scale_factor=2).pixmap(32, 32))
        header_layout.addWidget(header_icon)
        
        header = QLabel("Analitika")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #333; margin-left: 10px;")
        header_layout.addWidget(header)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)

        # ===== DATE RANGE FILTER =====
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Period:"))
        
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addDays(-30))
        self.date_from.setMinimumWidth(150)
        filter_layout.addWidget(self.date_from)

        filter_layout.addWidget(QLabel("do:"))
        
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setMinimumWidth(150)
        filter_layout.addWidget(self.date_to)

        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # Scroll area za content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(20)

        # ===== IMPORT STATISTICS =====
        import_group = QGroupBox("📥 Statistika Importa")
        import_layout = QGridLayout(import_group)
        import_layout.setVerticalSpacing(15)
        import_layout.setHorizontalSpacing(15)

        # Ukupno Importa (velika kartica)
        self.lbl_total_imports = QLabel("0")
        self.lbl_total_imports.setObjectName("statValue")
        self.lbl_total_imports.setAlignment(Qt.AlignCenter)
        import_layout.addWidget(QLabel("Ukupno Importa:"), 0, 0)
        import_layout.addWidget(self.lbl_total_imports, 1, 0)

        # Danas
        self.lbl_today_imports = QLabel("0")
        self.lbl_today_imports.setObjectName("statValue")
        self.lbl_today_imports.setStyleSheet("font-size: 24px; font-weight: bold; color: #28a745;")
        self.lbl_today_imports.setAlignment(Qt.AlignCenter)
        import_layout.addWidget(QLabel("Danas:"), 0, 1)
        import_layout.addWidget(self.lbl_today_imports, 1, 1)

        # Ove Nedjelje
        self.lbl_week_imports = QLabel("0")
        self.lbl_week_imports.setObjectName("statValue")
        self.lbl_week_imports.setStyleSheet("font-size: 24px; font-weight: bold; color: #17a2b8;")
        self.lbl_week_imports.setAlignment(Qt.AlignCenter)
        import_layout.addWidget(QLabel("Ove Nedjelje:"), 2, 0)
        import_layout.addWidget(self.lbl_week_imports, 3, 0)

        # Ovog Mjeseca
        self.lbl_month_imports = QLabel("0")
        self.lbl_month_imports.setObjectName("statValue")
        self.lbl_month_imports.setStyleSheet("font-size: 24px; font-weight: bold; color: #ffc107;")
        self.lbl_month_imports.setAlignment(Qt.AlignCenter)
        import_layout.addWidget(QLabel("Ovog Mjeseca:"), 2, 1)
        import_layout.addWidget(self.lbl_month_imports, 3, 1)

        scroll_layout.addWidget(import_group)

        # ===== DECLARATION STATISTICS =====
        decl_group = QGroupBox("📋 Statistika Deklaracija")
        decl_layout = QGridLayout(decl_group)
        decl_layout.setVerticalSpacing(15)
        decl_layout.setHorizontalSpacing(15)

        # Ukupno Deklaracija (velika kartica)
        self.lbl_total_declarations = QLabel("0")
        self.lbl_total_declarations.setObjectName("statValue")
        self.lbl_total_declarations.setStyleSheet("font-size: 32px; font-weight: bold; color: #2e7d32;")
        self.lbl_total_declarations.setAlignment(Qt.AlignCenter)
        decl_layout.addWidget(QLabel("Ukupno Deklaracija:"), 0, 0)
        decl_layout.addWidget(self.lbl_total_declarations, 1, 0)

        # Status breakdown
        self.status_layout = QGridLayout()
        self.status_layout.setVerticalSpacing(8)
        self.status_layout.setHorizontalSpacing(15)
        decl_layout.addLayout(self.status_layout, 2, 0, 1, 2)

        scroll_layout.addWidget(decl_group)

        # ===== PARSER USAGE =====
        parser_group = QGroupBox("🔌 Korišćenje Parsera")
        parser_layout = QVBoxLayout(parser_group)

        self.parser_stats_label = QLabel("📊 Nema podataka o korištenju parsera")
        self.parser_stats_label.setAlignment(Qt.AlignCenter)
        self.parser_stats_label.setStyleSheet("color: #999; font-size: 14px; padding: 20px;")
        parser_layout.addWidget(self.parser_stats_label)

        # Parser lista (placeholder za buduću implementaciju)
        self.parser_list_layout = QGridLayout()
        parser_layout.addLayout(self.parser_list_layout)

        scroll_layout.addWidget(parser_group)

        # ===== TREND SECTION (placeholder) =====
        trend_group = QGroupBox("📈 Trendovi")
        trend_layout = QVBoxLayout(trend_group)

        trend_info = QLabel("Trendovi će biti dostupni u narednoj verziji")
        trend_info.setAlignment(Qt.AlignCenter)
        trend_info.setStyleSheet("color: #999; font-size: 13px; padding: 15px;")
        trend_layout.addWidget(trend_info)

        scroll_layout.addWidget(trend_group)
        scroll_layout.addStretch()

        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        # ===== ACTION BUTTONS =====
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_refresh = QPushButton(
            qta.icon('fa5s.sync', color='white'),
            " Refresh"
        )
        self.btn_refresh.setFont(QFont("Arial", 13))
        self.btn_refresh.setToolTip("Osveži prikaz statistika")
        self.btn_refresh.clicked.connect(self._on_refresh_clicked)
        self.btn_refresh.setMinimumHeight(40)
        self.btn_refresh.setObjectName("refreshButton")
        btn_layout.addWidget(self.btn_refresh)

        self.btn_export = QPushButton(
            qta.icon('fa5s.file-export', color='white'),
            " Export"
        )
        self.btn_export.setFont(QFont("Arial", 13))
        self.btn_export.setToolTip("Eksportuj statistike u fajl")
        self.btn_export.clicked.connect(self._on_export_clicked)
        self.btn_export.setMinimumHeight(40)
        self.btn_export.setObjectName("exportButton")
        btn_layout.addWidget(self.btn_export)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    # PUBLIC API

    def set_statistics(self, stats: Dict[str, Any]):
        """
        Postavi statistike za prikaz.

        Args:
            stats: Dict sa statistikama
        """
        # Import stats
        if 'total_imports' in stats:
            self.lbl_total_imports.setText(str(stats['total_imports']))
        if 'imports_today' in stats:
            self.lbl_today_imports.setText(str(stats['imports_today']))
        if 'imports_this_week' in stats:
            self.lbl_week_imports.setText(str(stats['imports_this_week']))
        if 'imports_this_month' in stats:
            self.lbl_month_imports.setText(str(stats['imports_this_month']))

        # Declaration stats
        if 'total' in stats:
            self.lbl_total_declarations.setText(str(stats['total']))

        # Status breakdown
        if 'by_status' in stats:
            # Clear existing status labels
            while self.status_layout.count():
                item = self.status_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            # Add status labels with styling
            for i, (status, count) in enumerate(stats['by_status'].items()):
                color = S.status_color(status)

                label = QLabel(f"{status}:")
                label.setFont(QFont("Arial", 13))
                label.setStyleSheet("font-weight: 500;")

                value = QLabel(str(count))
                value.setFont(QFont("Arial", 14, QFont.Bold))
                value.setStyleSheet(f"font-weight: bold; color: {color};")

                self.status_layout.addWidget(label, i, 0)
                self.status_layout.addWidget(value, i, 1)

    def set_parser_usage(self, usage: list):
        """
        Postavi parser usage statistiku.

        Args:
            usage: Lista dict-ova sa parser usage-om
        """
        if not usage:
            self.parser_stats_label.setText("📊 Nema podataka o korištenju parsera")
            return

        # Clear existing
        while self.parser_list_layout.count():
            item = self.parser_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.parser_stats_label.setVisible(False)

        # Add parser usage bars
        for i, parser in enumerate(usage[:5]):  # Prikaži top 5
            name = parser.get('name', 'Unknown')
            count = parser.get('count', 0)
            percentage = parser.get('percentage', 0)

            name_label = QLabel(f"{name}:")
            name_label.setFont(QFont("Arial", 12))

            count_label = QLabel(f"{count} ({percentage}%)")
            count_label.setFont(QFont("Arial", 12, QFont.Bold))
            count_label.setAlignment(Qt.AlignRight)

            # Progress bar styling
            bar_label = QLabel()
            bar_label.setStyleSheet(f"""
                background-color: #e0e0e0;
                border-radius: 3px;
            """)
            bar_label.setMinimumHeight(20)
            bar_label.setMinimumWidth(200)

            # Fill percentage
            bar_label.setText(" " * int(percentage / 2))
            bar_label.setStyleSheet(f"""
                background-color: #0078d4;
                border-radius: 3px;
                color: white;
                padding-left: 5px;
            """)

            self.parser_list_layout.addWidget(name_label, i, 0)
            self.parser_list_layout.addWidget(bar_label, i, 1)
            self.parser_list_layout.addWidget(count_label, i, 2)

    def show_success(self, message: str):
        """Prikaži success poruku."""
        pass

    def show_error(self, message: str):
        """Prikaži error poruku."""
        pass

    # PRIVATE HANDLERS

    def _on_refresh_clicked(self):
        """Refresh button clicked."""
        self.refresh_requested.emit()

    def _on_export_clicked(self):
        """Export button clicked."""
        self.export_requested.emit()
