"""
Admin View - Main UI for Admin Tab.

Layout: Sidebar (lijevo) + Content Area (desno)
"""

from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout,
    QListWidget, QListWidgetItem, QStackedWidget, QLabel, QSizePolicy, QWidget
)
from PySide6.QtCore import Qt, Signal
from pathlib import Path
from gui.tabs.base_view import BaseTabView
from gui.tabs.admin.panels.plugin_panel import PluginPanel
from gui.tabs.admin.panels.database_panel import DatabasePanel
from gui.tabs.admin.panels.logs_panel import LogsPanel
from gui.tabs.admin.panels.system_panel import SystemPanel
from gui.tabs.admin.panels.analytics_panel import AnalyticsPanel
from gui.tabs.admin.panels.license_panel import LicensePanel
from gui.tabs.admin.panels.learning_panel import LearningPanel
import qtawesome as qta


class AdminView(BaseTabView):
    """Admin View sa sidebar navigation."""

    def __init__(self, parent=None):
        """
        Inicijalizacija.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.setup_ui()
        self._apply_styles()

    def _apply_styles(self):
        """Primijeni stylesheet za Admin Tab."""
        styles_dir = Path(__file__).parent.parent.parent / "styles"
        stylesheet_path = styles_dir / "admin_tab.qss"

        if stylesheet_path.exists():
            with open(stylesheet_path, 'r', encoding='utf-8') as f:
                stylesheet = f.read()
            self.setStyleSheet(stylesheet)

    def setup_ui(self):
        """Setup kompletnog UI-a."""
        # Main layout (horizontal)
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # SIDEBAR (lijevo)
        sidebar_widget = self._create_sidebar()
        main_layout.addWidget(sidebar_widget, stretch=1)

        # CONTENT AREA (desno)
        content_widget = self._create_content_area()
        main_layout.addWidget(content_widget, stretch=4)

    def _create_sidebar(self) -> QWidget:
        """Kreiraj sidebar sa navigacijom — isti vizuelni stil kao Šifrarnici tab."""
        sidebar = QFrame()
        sidebar.setFrameShape(QFrame.NoFrame)
        sidebar.setMaximumWidth(220)
        sidebar.setMinimumWidth(180)
        sidebar.setStyleSheet(
            "QFrame { background-color: #e8f2e8; border-right: 1px solid #c8dcc8; }"
        )

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header — sage green stil
        title = QLabel("<h3>Admin Panel</h3>")
        title.setStyleSheet(
            "padding: 12px 16px; font-size: 14px; font-weight: bold;"
            " color: #1e3820; background-color: #e8f2e8;"
            " border-bottom: 1px solid #c8dcc8;"
        )
        layout.addWidget(title)

        # Navigation list — sage green nav
        self.nav_list = QListWidget()
        self.nav_list.setFrameShape(QFrame.NoFrame)
        self.nav_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.nav_list.setStyleSheet(
            """
            QListWidget {
                background-color: #e8f2e8;
                border: none;
                outline: none;
                font-size: 13px;
                padding: 8px;
            }
            QListWidget::item {
                padding: 10px 8px;
                border-radius: 4px;
                margin: 2px 0;
                color: #1e3820;
            }
            QListWidget::item:hover {
                background-color: #c8dcc8;
            }
            QListWidget::item:selected {
                background-color: #5a8060;
                color: white;
                font-weight: bold;
            }
            """
        )

        items = [
            ("fa5s.box",          "Upravljanje Parserima",  "Instaliraj, ukloni, ponovo učitaj parsere"),
            ("fa5s.database",     "Baza Podataka",          "Status PostgreSQL baze i broj zapisa"),
            ("fa5s.chart-bar",    "Analitika",              "Statistika import-a i korišćenje parsera"),
            ("fa5s.file-alt",     "Logovi",                 "Pregled i filtriranje logova"),
            ("fa5s.info-circle",  "Sistemske Informacije",  "Informacije o sistemu i aplikaciji"),
            ("fa5s.key",          "Licenca",                "Machine ID, status licence, uvoz licence"),
            ("fa5s.brain",        "Učenje iz XML-ova",      "Reindeksiranje XML deklaracija i pregled stanja baze znanja"),
        ]

        for icon_name, item_text, tooltip in items:
            icon = qta.icon(
                icon_name,
                color="#3d6040",
                color_active="white",
                color_selected="white",
                scale_factor=1.0,
            )
            list_item = QListWidgetItem(icon, f"  {item_text}")
            list_item.setToolTip(tooltip)
            self.nav_list.addItem(list_item)

        self.nav_list.currentRowChanged.connect(self._on_nav_changed)

        layout.addWidget(self.nav_list)

        return sidebar

    def _create_content_area(self) -> QWidget:
        """
        Kreiraj content area sa stacked widget za panele.

        Returns:
            QWidget sa content area
        """
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)

        # Stacked widget za panele
        self.content_stack = QStackedWidget()

        # Kreiraj sve panele i dodaj u stack
        self._create_panels()

        layout.addWidget(self.content_stack)

        return content

    def _create_panels(self):
        """Kreiraj sve content panele."""
        # Upravljanje dodatcima panel
        self.plugin_panel = PluginPanel()
        self.content_stack.addWidget(self.plugin_panel)

        # Database panel
        self.database_panel = DatabasePanel()
        self.content_stack.addWidget(self.database_panel)

        # Analytics panel
        self.analytics_panel = AnalyticsPanel()
        self.content_stack.addWidget(self.analytics_panel)

        # Logs panel
        self.logs_panel = LogsPanel()
        self.content_stack.addWidget(self.logs_panel)

        # System Info panel
        self.system_panel = SystemPanel()
        self.content_stack.addWidget(self.system_panel)

        # License panel
        self.license_panel = LicensePanel()
        self.content_stack.addWidget(self.license_panel)

        # Learning panel
        self.learning_panel = LearningPanel()
        self.content_stack.addWidget(self.learning_panel)

    def _on_nav_changed(self, index: int):
        """
        Handler za promjenu navigation selection.

        Args:
            index: Index odabrane stavke
        """
        self.content_stack.setCurrentIndex(index)

    # PUBLIC API za controller

    def get_plugin_panel(self) -> PluginPanel:
        """Getter za plugin panel."""
        return self.plugin_panel

    def get_database_panel(self) -> DatabasePanel:
        """Getter za database panel."""
        return self.database_panel

    def get_analytics_panel(self) -> AnalyticsPanel:
        """Getter za analytics panel."""
        return self.analytics_panel

    def get_logs_panel(self) -> LogsPanel:
        """Getter za logs panel."""
        return self.logs_panel

    def get_system_panel(self) -> SystemPanel:
        """Getter za system panel."""
        return self.system_panel

    def get_settings_panel(self) -> SystemPanel:
        """Backward-compatible alias za stari naziv panela."""
        return self.system_panel

    def get_license_panel(self) -> LicensePanel:
        """Getter za license panel."""
        return self.license_panel

    def get_learning_panel(self) -> LearningPanel:
        """Getter za learning panel."""
        return self.learning_panel

    def get_data(self) -> dict:
        return {}

    def set_data(self, data: dict) -> None:
        pass

    def clear_form(self) -> None:
        pass
