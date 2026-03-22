import os
from pathlib import Path
from PySide6.QtWidgets import QMainWindow, QTabWidget, QApplication, QMessageBox
from PySide6.QtCore import QFile, QTextStream, QIODevice, QSettings

from config.settings import get_path_settings

from core.draft import DeclarationDraft
from gui.tabs.tab_factory import get_tab_factory
from gui.tabs.admin_tab import AdminTab
from gui.tabs.agent_tab import AgentTab


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ASYCUDA Pro")

        # Set default size (80% of Full HD 1920x1080)
        self.resize(1536, 823)

        # Set maximum size to prevent window manager from making it too wide
        self.setMaximumWidth(1650)

        # Restore window geometry from previous session
        self._restore_window_state()

        # 1. Ucitaj stilove
        self.load_stylesheet()

        # 2. Inicijalizacija draft-a
        self.draft = DeclarationDraft()
        self.draft.ensure_min_items(1)

        # 3. Kreiranje tabova (redoslijed: Faktura, Zaglavlje, Naimenovanja, Šifrarnici)
        tabs = QTabWidget()

        # Enable responsive resizing for tab widget
        from PySide6.QtWidgets import QSizePolicy
        tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Font za tab kartice (stilovi su u main_tabs.qss — bez inline setStyleSheet koji bi kreirao QSS bubble)
        from PySide6.QtGui import QFont
        tabs.setFont(QFont("Arial", 16, QFont.Bold))

        self.setCentralWidget(tabs)

        # Kreiranje tabova koristeći TabFactory
        tab_factory = get_tab_factory()
        
        # Faktura tab (Refaktorisan - 3-layer arhitektura)
        self.faktura_tab = tab_factory.create_tab('faktura', self.draft, self._on_dirty, tabs)
        tabs.addTab(self.faktura_tab, "📄 Faktura")

        # Naimenovanja tab (rubrike 31-46)
        self.naimenovanje_tab = tab_factory.create_tab('naimenovanja', self.draft, self._on_dirty, tabs)
        tabs.addTab(self.naimenovanje_tab, "📦 Naimenovanja")

        # Zaglavlje tab (rubrike 1-49)
        self.zaglavlje_tab = tab_factory.create_tab('zaglavlje', self.draft, self._on_dirty, tabs)
        tabs.addTab(self.zaglavlje_tab, "🗂️ Zaglavlje")

        # Šifrarnici tab
        self.sifarnici_tab = tab_factory.create_tab('sifarnici', self.draft, self._on_dirty, tabs)
        tabs.addTab(self.sifarnici_tab, "📋 Šifrarnici")

        # Admin tab (novi - plugin manager, settings, database, analytics, logs, system info)
        self.admin_tab = AdminTab(self)
        tabs.addTab(self.admin_tab, "⚙️ Admin")

        # Agent tab (novi - AI agent za automatsko procesiranje faktura)
        self.agent_tab = AgentTab(
            self,
            draft=self.draft,
            faktura_tab=self.faktura_tab,
            naimenovanje_tab=self.naimenovanje_tab,
            zaglavlje_tab=self.zaglavlje_tab,
        )
        tabs.addTab(self.agent_tab, "🤖 Agent")

        # Set Admin Tab as current tab for testing (opciono - za development)
        # tabs.setCurrentWidget(self.admin_tab)

        # Register callback to update all tabs when draft data changes
        self.draft.register_data_change_callback(self._on_draft_data_changed)

    def load_stylesheet(self):
        """
        Load all QSS stylesheets in correct order.
        Order matters: later styles can override earlier ones.
        """
        # Style files in loading order
        style_files = [
            "asycuda_modern_material.qss",  # Base styles
            "typography.qss",  # Text styles
            "spacing_system.qss",  # Spacing
            "main_tabs.qss",  # Main tab widget styling
            "zone_styling.qss",  # Zone hierarchy
            "naimenovanja_components.qss",  # Naimenovanja tab components
            "button_system.qss",  # Button categories
            "faktura_tab_v2.qss",  # Faktura tab base styles
            "QSS_header_toolbar_sistem.qss",  # Inputi, scrollbari, tabela, kombo
            "unified_color_system.qss",  # Unificirana paleta boja (najviši prioritet)
        ]

        combined_style = ""
        settings = get_path_settings()
        styles_dir = settings.styles_dir

        for style_file in style_files:
            style_path = styles_dir / style_file  # Path object

            if style_path.exists():
                file = QFile(str(style_path))
                if file.open(QIODevice.ReadOnly | QIODevice.Text):
                    stream = QTextStream(file)
                    content = stream.readAll()
                    combined_style += f"\n/* ========== {style_file} ========== */\n"
                    combined_style += content
                    file.close()

        if combined_style:
            QApplication.instance().setStyleSheet(combined_style)

    def _on_dirty(self) -> None:
        current_title = self.windowTitle()
        if not current_title.endswith("*"):
            self.setWindowTitle(current_title + " *")

    def _on_draft_data_changed(self) -> None:
        """Called when draft data changes - update all tabs that need refreshing."""
        # Update the zaglavlje tab to reflect any changes in the draft
        self.zaglavlje_tab.load_from_draft(self.draft)

        # Optionally update other tabs if needed
        # For now, we'll just update the zaglavlje tab since that's what we're focusing on

        # Refresh the UI to ensure all changes are displayed
        self.zaglavlje_tab.update()

    def _restore_window_state(self) -> None:
        """Restore window geometry and position from previous session."""
        settings = QSettings("AsycudaPro", "MainWindow")

        # Restore geometry (position + size)
        geometry = settings.value("geometry")
        if geometry:
            # Try to restore, but validate size
            success = self.restoreGeometry(geometry)

            # Check if restored size is too wide or wrong height (reject old settings)
            MAX_WIDTH = 1650  # Maximum acceptable width
            CORRECT_HEIGHT = 823  # Correct height
            if self.width() > MAX_WIDTH or self.height() != CORRECT_HEIGHT:
                self.resize(1536, 823)  # Force correct size
                self._center_on_primary_screen()
            elif not success:
                self._center_on_primary_screen()
        else:
            # First run - center the window on primary screen
            self._center_on_primary_screen()

    def _center_on_primary_screen(self) -> None:
        """Center window on primary screen."""
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def showEvent(self, event) -> None:
        """Save geometry when window is shown (backup to closeEvent)."""
        super().showEvent(event)

        # FORCE size after window is shown (in case window manager overrode it)
        MAX_WIDTH = 1650
        CORRECT_HEIGHT = 823
        if self.width() > MAX_WIDTH or self.height() != CORRECT_HEIGHT:
            self.resize(1536, 823)
            self._center_on_primary_screen()

        # Save initial position after first show
        settings = QSettings("AsycudaPro", "MainWindow")
        if not settings.value("geometry"):
            settings.setValue("geometry", self.saveGeometry())
            settings.sync()  # Force immediate write

    def closeEvent(self, event) -> None:
        """Save window state before closing."""
        settings = QSettings("AsycudaPro", "MainWindow")
        settings.setValue("geometry", self.saveGeometry())
        settings.sync()  # Force immediate write to disk
        super().closeEvent(event)
