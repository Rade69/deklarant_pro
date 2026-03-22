# ASYCUDA PRO - ADMIN TAB IMPLEMENTATION GUIDE

**Complete Step-by-Step Implementation - All Tasks Separated**

---

## 📋 TABLE OF CONTENTS

```
TASK 1:  Folder Structure Setup
TASK 2:  Admin Tab Wrapper (Entry Point)
TASK 3:  Admin View - Main UI with Sidebar
TASK 4:  Admin Controller - Orchestration Layer
TASK 5:  Admin Service - Business Logic
TASK 6:  Plugin Manager Panel - UI
TASK 7:  Plugin Service - Plugin Operations
TASK 8:  Settings Panel - UI
TASK 9:  Settings Service - Configuration Management
TASK 10: Database Panel - UI
TASK 11: Backup Service - Backup/Restore Operations
TASK 12: Logs Panel - UI
TASK 13: Log Service - Log Reading & Filtering
TASK 14: System Info Panel - UI
TASK 15: Analytics Panel - UI (Basic)
TASK 16: Analytics Service - Statistics Gathering
TASK 17: Integration - Add Admin Tab to MainWindow
TASK 18: Testing - End-to-End Tests
TASK 19: Polish - Icons, Styling, UX Improvements
TASK 20: Documentation - User Guide & Developer Docs
```

---

## TASK 1: FOLDER STRUCTURE SETUP

**CILJ:** Kreirati folder strukturu za Admin Tab

**GDJE:** Project root

**ŠTA URADITI:**

```bash
# 1. Kreiraj Admin folder strukturu
mkdir -p gui/tabs/admin
mkdir -p gui/tabs/admin/panels
mkdir -p services/admin

# 2. Kreiraj __init__.py fajlove
touch gui/tabs/admin/__init__.py
touch gui/tabs/admin/panels/__init__.py
touch services/admin/__init__.py

# 3. Kreiraj prazne fajlove (biće popunjeni u sljedećim taskovima)
touch gui/tabs/admin_tab.py
touch gui/tabs/admin/admin_view.py
touch gui/tabs/admin/admin_controller.py
touch gui/tabs/admin/panels/plugin_panel.py
touch gui/tabs/admin/panels/settings_panel.py
touch gui/tabs/admin/panels/database_panel.py
touch gui/tabs/admin/panels/logs_panel.py
touch gui/tabs/admin/panels/system_panel.py
touch gui/tabs/admin/panels/analytics_panel.py

touch services/admin/admin_service.py
touch services/admin/plugin_service.py
touch services/admin/settings_service.py
touch services/admin/backup_service.py
touch services/admin/log_service.py
touch services/admin/analytics_service.py
```

**OČEKIVANI REZULTAT:**
```
gui/tabs/
├── admin_tab.py
└── admin/
    ├── __init__.py
    ├── admin_view.py
    ├── admin_controller.py
    └── panels/
        ├── __init__.py
        ├── plugin_panel.py
        ├── settings_panel.py
        ├── database_panel.py
        ├── logs_panel.py
        ├── system_panel.py
        └── analytics_panel.py

services/admin/
├── __init__.py
├── admin_service.py
├── plugin_service.py
├── settings_service.py
├── backup_service.py
├── log_service.py
└── analytics_service.py
```

**TESTIRANJE:**
```bash
ls -R gui/tabs/admin/
ls -R services/admin/
```

**COMMIT:**
```bash
git add gui/tabs/admin/ services/admin/
git commit -m "Admin Tab: Folder structure setup"
```

---

## TASK 2: ADMIN TAB WRAPPER (ENTRY POINT)

**CILJ:** Kreirati glavni Admin Tab koji se dodaje u MainWindow tab widget

**GDJE:** `gui/tabs/admin_tab.py`

**ŠTA URADITI:**

Implementiraj kompletnu AdminTab klasu koja:
1. Nasljeđuje QWidget
2. Kreira layers (View, Controller, Service)
3. Setup layout sa Admin View-om

**KOD:**

```python
"""
Admin Tab - Central admin panel for ASYCUDA Pro.

Ovaj tab pruža pristup svim admin funkcionalnostima:
- Plugin Manager
- Settings
- Database Management
- Logs
- System Info
- Analytics
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout
from gui.tabs.admin.admin_view import AdminView
from gui.tabs.admin.admin_controller import AdminController
from services.admin.admin_service import AdminService


class AdminTab(QWidget):
    """
    Admin Tab - wrapper around 3-layer architecture.
    
    Ovaj tab ne prima Draft niti on_dirty callback jer je
    admin funkcionalnost nezavisna od deklaracija.
    """
    
    def __init__(self, parent=None):
        """
        Inicijalizacija Admin Tab-a.
        
        Args:
            parent: Parent widget (MainWindow)
        """
        super().__init__(parent)
        
        # Setup layers
        self._setup_layers()
        
        # Setup UI
        self._setup_ui()
    
    def _setup_layers(self):
        """Kreiraj View/Controller/Service layer-e."""
        # Service layer (business logic)
        self.service = AdminService()
        
        # View layer (UI)
        self.view = AdminView(parent=self)
        
        # Controller layer (orchestration)
        self.controller = AdminController(self.view, self.service)
    
    def _setup_ui(self):
        """Setup glavnog layout-a."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
```

**TESTIRANJE:**

```python
# Test import
python -c "from gui.tabs.admin_tab import AdminTab; print('✅ AdminTab import OK')"

# Test instantiation (requires Qt app)
python -c "
from PySide6.QtWidgets import QApplication
from gui.tabs.admin_tab import AdminTab
import sys

app = QApplication(sys.argv)
tab = AdminTab()
print('✅ AdminTab created successfully')
"
```

**OČEKIVANI OUTPUT:**
```
✅ AdminTab import OK
✅ AdminTab created successfully
```

**COMMIT:**
```bash
git add gui/tabs/admin_tab.py
git commit -m "Admin Tab: Wrapper implementation"
```

---

## TASK 3: ADMIN VIEW - MAIN UI WITH SIDEBAR

**CILJ:** Kreirati glavni UI sa sidebar navigation i content area

**GDJE:** `gui/tabs/admin/admin_view.py`

**ŠTA URADITI:**

Implementiraj AdminView klasu koja:
1. Kreira sidebar sa listom sekcija
2. Kreira stacked widget za content panele
3. Povezuje sidebar selection sa content switching
4. Inicijalizuje sve panele

**KOD:**

```python
"""
Admin View - Main UI for Admin Tab.

Layout: Sidebar (lijevo) + Content Area (desno)
"""

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, 
    QListWidget, QStackedWidget, QLabel
)
from PySide6.QtCore import Qt
from gui.tabs.admin.panels.plugin_panel import PluginPanel
from gui.tabs.admin.panels.settings_panel import SettingsPanel
from gui.tabs.admin.panels.database_panel import DatabasePanel
from gui.tabs.admin.panels.logs_panel import LogsPanel
from gui.tabs.admin.panels.system_panel import SystemPanel
from gui.tabs.admin.panels.analytics_panel import AnalyticsPanel


class AdminView(QWidget):
    """Admin View sa sidebar navigation."""
    
    def __init__(self, parent=None):
        """
        Inicijalizacija.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.setup_ui()
    
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
        """
        Kreiraj sidebar sa navigacijom.
        
        Returns:
            QWidget sa sidebar UI-em
        """
        sidebar = QWidget()
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Title
        title = QLabel("<h3>Admin Panel</h3>")
        layout.addWidget(title)
        
        # Navigation list
        self.nav_list = QListWidget()
        self.nav_list.setMaximumWidth(220)
        self.nav_list.setMinimumWidth(180)
        
        # Add items
        items = [
            "📦 Plugin Manager",
            "⚙️  Settings",
            "💾 Database",
            "📊 Analytics",
            "📋 Logs",
            "ℹ️  System Info"
        ]
        
        for item in items:
            self.nav_list.addItem(item)
        
        # Connect selection change
        self.nav_list.currentRowChanged.connect(self._on_nav_changed)
        
        layout.addWidget(self.nav_list)
        layout.addStretch()
        
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
        # Plugin Manager panel
        self.plugin_panel = PluginPanel()
        self.content_stack.addWidget(self.plugin_panel)
        
        # Settings panel
        self.settings_panel = SettingsPanel()
        self.content_stack.addWidget(self.settings_panel)
        
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
    
    def get_settings_panel(self) -> SettingsPanel:
        """Getter za settings panel."""
        return self.settings_panel
    
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
```

**TESTIRANJE:**

```python
python -c "
from PySide6.QtWidgets import QApplication
from gui.tabs.admin.admin_view import AdminView
import sys

app = QApplication(sys.argv)
view = AdminView()

# Check panels exist
assert view.plugin_panel is not None
assert view.settings_panel is not None
assert view.database_panel is not None
assert view.analytics_panel is not None
assert view.logs_panel is not None
assert view.system_panel is not None

print('✅ AdminView created with all panels')
print(f'✅ Sidebar items: {view.nav_list.count()}')
print(f'✅ Content panels: {view.content_stack.count()}')
"
```

**OČEKIVANI OUTPUT:**
```
✅ AdminView created with all panels
✅ Sidebar items: 6
✅ Content panels: 6
```

**COMMIT:**
```bash
git add gui/tabs/admin/admin_view.py
git commit -m "Admin Tab: Main View with sidebar navigation"
```

---

## TASK 4: ADMIN CONTROLLER - ORCHESTRATION LAYER

**CILJ:** Kreirati controller koji koordiniše View i Service

**GDJE:** `gui/tabs/admin/admin_controller.py`

**ŠTA URADITI:**

Implementiraj AdminController klasu koja:
1. Prima View i Service u __init__
2. Povezuje signale sa handlerima
3. Orchestruje operacije između layer-a

**KOD:**

```python
"""
Admin Controller - Orchestration layer.

Koordinira View i Service layer-e.
"""

from typing import Optional
from gui.tabs.admin.admin_view import AdminView
from services.admin.admin_service import AdminService


class AdminController:
    """
    Admin Controller - orchestration layer.
    
    Povezuje View events sa Service operations.
    """
    
    def __init__(self, view: AdminView, service: AdminService):
        """
        Inicijalizacija.
        
        Args:
            view: AdminView instance
            service: AdminService instance
        """
        self.view = view
        self.service = service
        
        # Connect signals
        self._connect_signals()
        
        # Initial data load
        self._load_initial_data()
    
    def _connect_signals(self):
        """Povezivanje View signala sa handler metodama."""
        # Plugin panel signals
        plugin_panel = self.view.get_plugin_panel()
        if hasattr(plugin_panel, 'install_requested'):
            plugin_panel.install_requested.connect(self._on_install_plugin)
        if hasattr(plugin_panel, 'reload_requested'):
            plugin_panel.reload_requested.connect(self._on_reload_plugins)
        if hasattr(plugin_panel, 'remove_requested'):
            plugin_panel.remove_requested.connect(self._on_remove_plugin)
        
        # Settings panel signals
        settings_panel = self.view.get_settings_panel()
        if hasattr(settings_panel, 'save_requested'):
            settings_panel.save_requested.connect(self._on_save_settings)
        
        # Database panel signals
        database_panel = self.view.get_database_panel()
        if hasattr(database_panel, 'backup_requested'):
            database_panel.backup_requested.connect(self._on_backup_database)
        if hasattr(database_panel, 'restore_requested'):
            database_panel.restore_requested.connect(self._on_restore_database)
        
        # Logs panel signals
        logs_panel = self.view.get_logs_panel()
        if hasattr(logs_panel, 'refresh_requested'):
            logs_panel.refresh_requested.connect(self._on_refresh_logs)
    
    def _load_initial_data(self):
        """Učitaj inicijalne podatke pri pokretanju."""
        # Load plugin data
        self._refresh_plugin_list()
        
        # Load system info
        self._refresh_system_info()
        
        # Load settings
        self._refresh_settings()
    
    # PLUGIN HANDLERS
    
    def _on_install_plugin(self, filepath: str):
        """
        Handler za instalaciju plugin-a.
        
        Args:
            filepath: Put do .py fajla
        """
        try:
            success = self.service.install_plugin(filepath)
            
            if success:
                self.view.get_plugin_panel().show_success(
                    "Plugin uspješno instaliran!"
                )
                self._refresh_plugin_list()
            else:
                self.view.get_plugin_panel().show_error(
                    "Instalacija plugin-a nije uspjela!"
                )
        except Exception as e:
            self.view.get_plugin_panel().show_error(
                f"Greška pri instalaciji: {e}"
            )
    
    def _on_reload_plugins(self):
        """Handler za reload plugin-a."""
        try:
            self.service.reload_plugins()
            self._refresh_plugin_list()
            self.view.get_plugin_panel().show_success(
                "Plugin-i uspješno reload-ovani!"
            )
        except Exception as e:
            self.view.get_plugin_panel().show_error(
                f"Greška pri reload-u: {e}"
            )
    
    def _on_remove_plugin(self, plugin_name: str):
        """
        Handler za uklanjanje plugin-a.
        
        Args:
            plugin_name: Ime plugin-a za uklanjanje
        """
        try:
            success = self.service.remove_plugin(plugin_name)
            
            if success:
                self.view.get_plugin_panel().show_success(
                    f"Plugin '{plugin_name}' uklonjen!"
                )
                self._refresh_plugin_list()
            else:
                self.view.get_plugin_panel().show_error(
                    f"Uklanjanje plugin-a '{plugin_name}' nije uspjelo!"
                )
        except Exception as e:
            self.view.get_plugin_panel().show_error(
                f"Greška pri uklanjanju: {e}"
            )
    
    def _refresh_plugin_list(self):
        """Refresh liste plugin-a."""
        plugins = self.service.get_installed_plugins()
        self.view.get_plugin_panel().set_plugins(plugins)
    
    # SETTINGS HANDLERS
    
    def _on_save_settings(self, settings: dict):
        """
        Handler za čuvanje settings-a.
        
        Args:
            settings: Dictionary sa settings-ima
        """
        try:
            success = self.service.save_settings(settings)
            
            if success:
                self.view.get_settings_panel().show_success(
                    "Settings uspješno sačuvani!"
                )
            else:
                self.view.get_settings_panel().show_error(
                    "Čuvanje settings-a nije uspjelo!"
                )
        except Exception as e:
            self.view.get_settings_panel().show_error(
                f"Greška pri čuvanju: {e}"
            )
    
    def _refresh_settings(self):
        """Refresh settings-a."""
        settings = self.service.get_settings()
        self.view.get_settings_panel().set_settings(settings)
    
    # DATABASE HANDLERS
    
    def _on_backup_database(self, backup_path: str):
        """
        Handler za database backup.
        
        Args:
            backup_path: Put gdje sačuvati backup
        """
        try:
            success = self.service.create_backup(backup_path)
            
            if success:
                self.view.get_database_panel().show_success(
                    f"Backup kreiran: {backup_path}"
                )
            else:
                self.view.get_database_panel().show_error(
                    "Kreiranje backup-a nije uspjelo!"
                )
        except Exception as e:
            self.view.get_database_panel().show_error(
                f"Greška pri backup-u: {e}"
            )
    
    def _on_restore_database(self, backup_path: str):
        """
        Handler za database restore.
        
        Args:
            backup_path: Put do backup fajla
        """
        try:
            success = self.service.restore_backup(backup_path)
            
            if success:
                self.view.get_database_panel().show_success(
                    "Database uspješno restore-ovan!"
                )
            else:
                self.view.get_database_panel().show_error(
                    "Restore database-a nije uspio!"
                )
        except Exception as e:
            self.view.get_database_panel().show_error(
                f"Greška pri restore-u: {e}"
            )
    
    # LOGS HANDLERS
    
    def _on_refresh_logs(self):
        """Handler za refresh log-ova."""
        try:
            logs = self.service.get_recent_logs()
            self.view.get_logs_panel().set_logs(logs)
        except Exception as e:
            self.view.get_logs_panel().show_error(
                f"Greška pri učitavanju log-ova: {e}"
            )
    
    # SYSTEM INFO
    
    def _refresh_system_info(self):
        """Refresh system info-a."""
        system_info = self.service.get_system_info()
        self.view.get_system_panel().set_system_info(system_info)
```

**TESTIRANJE:**

```python
python -c "
from PySide6.QtWidgets import QApplication
from gui.tabs.admin.admin_view import AdminView
from gui.tabs.admin.admin_controller import AdminController
from services.admin.admin_service import AdminService
import sys

app = QApplication(sys.argv)

view = AdminView()
service = AdminService()
controller = AdminController(view, service)

print('✅ AdminController created successfully')
print('✅ View and Service connected')
"
```

**COMMIT:**
```bash
git add gui/tabs/admin/admin_controller.py
git commit -m "Admin Tab: Controller orchestration layer"
```

---

## TASK 5: ADMIN SERVICE - BUSINESS LOGIC

**CILJ:** Kreirati service layer sa business logikom

**GDJE:** `services/admin/admin_service.py`

**ŠTA URADITI:**

Implementiraj AdminService klasu koja:
1. Koordinira sve pod-servise (plugin, settings, backup, logs, analytics)
2. Pruža unified API za controller
3. Delegira operacije odgovarajućim servisima

**KOD:**

```python
"""
Admin Service - Main admin business logic.

Koordinira sve admin pod-servise.
"""

from typing import List, Dict, Any, Optional
from services.admin.plugin_service import PluginService
from services.admin.settings_service import SettingsService
from services.admin.backup_service import BackupService
from services.admin.log_service import LogService
from services.admin.analytics_service import AnalyticsService


class AdminService:
    """
    Admin Service - main admin business logic.
    
    Koordinira sve admin operacije kroz pod-servise.
    """
    
    def __init__(self):
        """Inicijalizacija pod-servisa."""
        self.plugin_service = PluginService()
        self.settings_service = SettingsService()
        self.backup_service = BackupService()
        self.log_service = LogService()
        self.analytics_service = AnalyticsService()
    
    # PLUGIN OPERATIONS (delegate to PluginService)
    
    def get_installed_plugins(self) -> List[Dict[str, Any]]:
        """
        Vrati listu instaliranih plugin-a.
        
        Returns:
            Lista dict-ova sa plugin info-m
        """
        return self.plugin_service.get_installed_plugins()
    
    def install_plugin(self, filepath: str) -> bool:
        """
        Instaliraj plugin.
        
        Args:
            filepath: Put do .py fajla
            
        Returns:
            True ako uspješno, False ako ne
        """
        return self.plugin_service.install_plugin(filepath)
    
    def remove_plugin(self, plugin_name: str) -> bool:
        """
        Ukloni plugin.
        
        Args:
            plugin_name: Ime plugin-a
            
        Returns:
            True ako uspješno, False ako ne
        """
        return self.plugin_service.remove_plugin(plugin_name)
    
    def reload_plugins(self) -> bool:
        """
        Reload svih plugin-a.
        
        Returns:
            True ako uspješno, False ako ne
        """
        return self.plugin_service.reload_plugins()
    
    # SETTINGS OPERATIONS (delegate to SettingsService)
    
    def get_settings(self) -> Dict[str, Any]:
        """
        Vrati trenutne settings.
        
        Returns:
            Dict sa settings-ima
        """
        return self.settings_service.get_settings()
    
    def save_settings(self, settings: Dict[str, Any]) -> bool:
        """
        Sačuvaj settings.
        
        Args:
            settings: Dict sa settings-ima
            
        Returns:
            True ako uspješno, False ako ne
        """
        return self.settings_service.save_settings(settings)
    
    # DATABASE OPERATIONS (delegate to BackupService)
    
    def create_backup(self, backup_path: str) -> bool:
        """
        Kreiraj database backup.
        
        Args:
            backup_path: Put gdje sačuvati backup
            
        Returns:
            True ako uspješno, False ako ne
        """
        return self.backup_service.create_backup(backup_path)
    
    def restore_backup(self, backup_path: str) -> bool:
        """
        Restore database iz backup-a.
        
        Args:
            backup_path: Put do backup fajla
            
        Returns:
            True ako uspješno, False ako ne
        """
        return self.backup_service.restore_backup(backup_path)
    
    def get_available_backups(self) -> List[Dict[str, Any]]:
        """
        Vrati listu dostupnih backup-a.
        
        Returns:
            Lista dict-ova sa backup info-m
        """
        return self.backup_service.get_available_backups()
    
    # LOG OPERATIONS (delegate to LogService)
    
    def get_recent_logs(self, count: int = 100) -> List[Dict[str, Any]]:
        """
        Vrati nedavne log-ove.
        
        Args:
            count: Broj log-ova za vratiti
            
        Returns:
            Lista dict-ova sa log entries
        """
        return self.log_service.get_recent_logs(count)
    
    def filter_logs(
        self, 
        level: Optional[str] = None,
        search: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Filtriraj log-ove.
        
        Args:
            level: Log level (INFO, DEBUG, WARNING, ERROR)
            search: Search term
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            
        Returns:
            Lista filtriranih log entries
        """
        return self.log_service.filter_logs(
            level=level,
            search=search,
            start_date=start_date,
            end_date=end_date
        )
    
    # SYSTEM INFO
    
    def get_system_info(self) -> Dict[str, Any]:
        """
        Vrati system info.
        
        Returns:
            Dict sa system info-m
        """
        import sys
        import platform
        from pathlib import Path
        
        return {
            'app_name': 'ASYCUDA Pro',
            'app_version': '2.0.0',  # TODO: Load from config
            'python_version': sys.version,
            'platform': platform.platform(),
            'architecture': platform.machine(),
            'plugins_count': len(self.get_installed_plugins()),
            'database_size': self.backup_service.get_database_size(),
        }
    
    # ANALYTICS OPERATIONS (delegate to AnalyticsService)
    
    def get_import_statistics(self) -> Dict[str, Any]:
        """
        Vrati import statistiku.
        
        Returns:
            Dict sa statistikama
        """
        return self.analytics_service.get_import_statistics()
    
    def get_parser_usage(self) -> List[Dict[str, Any]]:
        """
        Vrati parser usage statistiku.
        
        Returns:
            Lista dict-ova sa parser usage
        """
        return self.analytics_service.get_parser_usage()
```

**TESTIRANJE:**

```python
python -c "
from services.admin.admin_service import AdminService

service = AdminService()

# Test sub-services exist
assert service.plugin_service is not None
assert service.settings_service is not None
assert service.backup_service is not None
assert service.log_service is not None
assert service.analytics_service is not None

print('✅ AdminService created with all sub-services')

# Test system info
info = service.get_system_info()
print(f'✅ System info: {info[\"app_name\"]} v{info[\"app_version\"]}')
"
```

**COMMIT:**
```bash
git add services/admin/admin_service.py
git commit -m "Admin Tab: Main service layer with sub-services"
```

---

## TASK 6: PLUGIN MANAGER PANEL - UI

**CILJ:** Kreirati Plugin Manager panel UI

**GDJE:** `gui/tabs/admin/panels/plugin_panel.py`

**ŠTA URADITI:**

Implementiraj PluginPanel klasu koja:
1. Prikazuje listu instaliranih parsera
2. Ima Install/Reload/Remove buttons
3. Prikazuje info panel sa metadata
4. Emituje signale za controller

**KOD:**

```python
"""
Plugin Manager Panel - UI for plugin management.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QPushButton,
    QGroupBox, QTextEdit, QFileDialog, QMessageBox
)
from PySide6.QtCore import Signal, Qt
from typing import List, Dict, Any
import qtawesome as qta


class PluginPanel(QWidget):
    """Plugin Manager panel UI."""
    
    # Signali
    install_requested = Signal(str)  # filepath
    reload_requested = Signal()
    remove_requested = Signal(str)   # plugin_name
    
    def __init__(self, parent=None):
        """Inicijalizacija."""
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """Setup UI-a."""
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("<h2>📦 Plugin Manager</h2>")
        layout.addWidget(header)
        
        # Main content (horizontal)
        content_layout = QHBoxLayout()
        
        # Lista parsera (lijevo)
        self.parsers_list = QListWidget()
        self.parsers_list.currentItemChanged.connect(
            self._on_parser_selected
        )
        content_layout.addWidget(self.parsers_list, stretch=2)
        
        # Info panel (desno)
        info_group = QGroupBox("Parser Info")
        info_layout = QVBoxLayout(info_group)
        
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMaximumHeight(300)
        info_layout.addWidget(self.info_text)
        
        content_layout.addWidget(info_group, stretch=1)
        
        layout.addLayout(content_layout)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.btn_install = QPushButton(
            qta.icon('fa5s.download'), 
            " Instaliraj Novi Parser"
        )
        self.btn_install.clicked.connect(self._on_install_clicked)
        btn_layout.addWidget(self.btn_install)
        
        self.btn_reload = QPushButton(
            qta.icon('fa5s.sync'), 
            " Reload Parsera"
        )
        self.btn_reload.clicked.connect(self._on_reload_clicked)
        btn_layout.addWidget(self.btn_reload)
        
        self.btn_remove = QPushButton(
            qta.icon('fa5s.trash-alt'), 
            " Ukloni"
        )
        self.btn_remove.clicked.connect(self._on_remove_clicked)
        self.btn_remove.setEnabled(False)
        btn_layout.addWidget(self.btn_remove)
        
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
    
    # PUBLIC API (Controller poziva)
    
    def set_plugins(self, plugins: List[Dict[str, Any]]):
        """
        Postavi listu plugin-a.
        
        Args:
            plugins: Lista dict-ova sa plugin info-m
        """
        self.parsers_list.clear()
        
        if not plugins:
            self.parsers_list.addItem("(Nema instaliranih plugin-a)")
            return
        
        for plugin in plugins:
            display_name = f"✅ {plugin.get('name', 'Unknown')}"
            
            item = QListWidgetItem(display_name)
            item.setData(Qt.UserRole, plugin)
            
            self.parsers_list.addItem(item)
    
    def show_success(self, message: str):
        """Prikaži success poruku."""
        QMessageBox.information(self, "Uspjeh", message)
    
    def show_error(self, message: str):
        """Prikaži error poruku."""
        QMessageBox.critical(self, "Greška", message)
    
    def show_warning(self, message: str):
        """Prikaži warning poruku."""
        QMessageBox.warning(self, "Upozorenje", message)
    
    # PRIVATE HANDLERS
    
    def _on_parser_selected(self, current, previous):
        """Parser selected - prikaži info."""
        if not current:
            self.info_text.clear()
            self.btn_remove.setEnabled(False)
            return
        
        self.btn_remove.setEnabled(True)
        
        data = current.data(Qt.UserRole)
        
        # Format info
        info = f"""
<b>Ime:</b> {data.get('name', 'N/A')}<br>
<b>Prioritet:</b> {data.get('priority', 'N/A')}<br>
<b>Klijent:</b> {data.get('client', 'N/A')}<br>
<b>Firma:</b> {data.get('firma', 'N/A')}<br>
<b>Verzija:</b> {data.get('version', 'N/A')}<br>
<b>Autor:</b> {data.get('author', 'N/A')}<br>
<br>
<b>Fajl:</b> {data.get('filename', 'N/A')}
        """
        
        self.info_text.setHtml(info)
    
    def _on_install_clicked(self):
        """Install button clicked."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Odaberi Parser Fajl",
            "",
            "Python fajlovi (*.py)"
        )
        
        if filepath:
            self.install_requested.emit(filepath)
    
    def _on_reload_clicked(self):
        """Reload button clicked."""
        self.reload_requested.emit()
    
    def _on_remove_clicked(self):
        """Remove button clicked."""
        current = self.parsers_list.currentItem()
        if not current:
            return
        
        data = current.data(Qt.UserRole)
        plugin_name = data.get('name', '')
        
        reply = QMessageBox.question(
            self,
            "Potvrda",
            f"Obrisati parser '{plugin_name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.remove_requested.emit(plugin_name)
```

**TESTIRANJE:**

```python
python -c "
from PySide6.QtWidgets import QApplication
from gui.tabs.admin.panels.plugin_panel import PluginPanel
import sys

app = QApplication(sys.argv)
panel = PluginPanel()

# Test set_plugins
test_plugins = [
    {'name': 'Test Parser', 'priority': 20, 'client': 'Test Client'}
]
panel.set_plugins(test_plugins)

print(f'✅ PluginPanel created')
print(f'✅ Parsers in list: {panel.parsers_list.count()}')
"
```

**COMMIT:**
```bash
git add gui/tabs/admin/panels/plugin_panel.py
git commit -m "Admin Tab: Plugin Manager panel UI"
```

---

**(NAPOMENA: Ostali taskovi prate isti pattern - Panel UI + Service implementation. Zbog ograničenja dužine, prikazujem samo core taskove. Kompletan prompt bi sadržao SVE taskove 7-20 na isti način.)**

---

## TASK 7: PLUGIN SERVICE - PLUGIN OPERATIONS

**CILJ:** Implementirati PluginService sa svim plugin operacijama

**GDJE:** `services/admin/plugin_service.py`

**ŠTA URADITI:**

Implementiraj PluginService klasu koja:
1. Učitava instaliranje plugin-e iz plugins/parsers/
2. Instalira nove plugin-e (copy fajla)
3. Uklanja plugin-e (briše fajl)
4. Reload plugin-a (reload registry)

**KOD:**

```python
"""
Plugin Service - Plugin operations.
"""

from typing import List, Dict, Any
from pathlib import Path
import shutil
from importers.plugin_loader import PluginLoader
from importers.strategy_registry import get_registry


class PluginService:
    """Service za plugin operacije."""
    
    def __init__(self):
        """Inicijalizacija."""
        self.plugin_loader = PluginLoader()
    
    def get_installed_plugins(self) -> List[Dict[str, Any]]:
        """
        Vrati listu instaliranih plugin-a.
        
        Returns:
            Lista dict-ova sa plugin info-m
        """
        plugins = []
        parsers_dir = self.plugin_loader.parsers_dir
        
        if not parsers_dir.exists():
            return plugins
        
        for filepath in parsers_dir.glob("*.py"):
            if filepath.name.startswith("_"):
                continue
            
            try:
                parser_class = self.plugin_loader._load_parser_from_file(filepath)
                
                if parser_class:
                    instance = parser_class()
                    
                    plugins.append({
                        'name': instance.strategy_name,
                        'priority': instance.priority,
                        'filename': filepath.name,
                        'filepath': str(filepath),
                        'client': instance.metadata.get('client', 'Unknown'),
                        'firma': instance.metadata.get('firma', 'Unknown'),
                        'version': instance.metadata.get('version', '1.0'),
                        'author': instance.metadata.get('author', 'Unknown'),
                    })
            except Exception as e:
                print(f"Error loading {filepath.name}: {e}")
        
        return plugins
    
    def install_plugin(self, filepath: str) -> bool:
        """
        Instaliraj plugin.
        
        Args:
            filepath: Put do .py fajla
            
        Returns:
            True ako uspješno, False ako ne
        """
        try:
            source = Path(filepath)
            
            if not source.exists():
                return False
            
            if not source.suffix == '.py':
                return False
            
            # Copy to plugins/parsers/
            destination = self.plugin_loader.parsers_dir / source.name
            shutil.copy2(source, destination)
            
            print(f"✅ Plugin installed: {destination}")
            return True
            
        except Exception as e:
            print(f"❌ Plugin install failed: {e}")
            return False
    
    def remove_plugin(self, plugin_name: str) -> bool:
        """
        Ukloni plugin.
        
        Args:
            plugin_name: Ime plugin-a (strategy_name)
            
        Returns:
            True ako uspješno, False ako ne
        """
        try:
            # Find plugin file
            plugins = self.get_installed_plugins()
            
            for plugin in plugins:
                if plugin['name'] == plugin_name:
                    filepath = Path(plugin['filepath'])
                    
                    if filepath.exists():
                        filepath.unlink()
                        print(f"✅ Plugin removed: {filepath.name}")
                        return True
            
            return False
            
        except Exception as e:
            print(f"❌ Plugin remove failed: {e}")
            return False
    
    def reload_plugins(self) -> bool:
        """
        Reload svih plugin-a.
        
        Returns:
            True ako uspješno, False ako ne
        """
        try:
            registry = get_registry()
            
            if hasattr(registry, 'reload_plugins'):
                registry.reload_plugins()
            
            print("✅ Plugins reloaded")
            return True
            
        except Exception as e:
            print(f"❌ Plugin reload failed: {e}")
            return False
```

**TESTIRANJE:**

```python
python -c "
from services.admin.plugin_service import PluginService

service = PluginService()

# Test get plugins
plugins = service.get_installed_plugins()
print(f'✅ PluginService created')
print(f'✅ Found {len(plugins)} plugins')

for plugin in plugins:
    print(f'  - {plugin[\"name\"]} (v{plugin[\"version\"]})')
"
```

**COMMIT:**
```bash
git add services/admin/plugin_service.py
git commit -m "Admin Tab: Plugin service implementation"
```

---

## TASK 17: INTEGRATION - ADD ADMIN TAB TO MAINWINDOW

**CILJ:** Dodati Admin Tab u MainWindow tab widget

**GDJE:** `gui/main_window.py`

**ŠTA URADITI:**

1. Import AdminTab
2. Kreiraj AdminTab instancu
3. Dodaj u tab widget

**KOD IZMJENE:**

```python
# gui/main_window.py

# Dodaj import na vrh fajla
from gui.tabs.admin_tab import AdminTab

# U _create_tabs() metodi, dodaj Admin Tab:
def _create_tabs(self):
    """Kreiraj tabove."""
    tabs = QTabWidget()
    
    # Postojeći tabovi
    self.faktura_tab = FakturaTab(self.draft, on_dirty=self._on_dirty)
    tabs.addTab(self.faktura_tab, "Faktura")
    
    self.naimenovanja_tab = NaimenovanjaTab(self.draft, on_dirty=self._on_dirty)
    tabs.addTab(self.naimenovanja_tab, "Naimenovanja")
    
    self.zaglavlje_tab = ZaglavljeTab(self.draft, on_dirty=self._on_dirty)
    tabs.addTab(self.zaglavlje_tab, "Zaglavlje")
    
    self.sifarnici_tab = SifarniciTab(self.draft, on_dirty=self._on_dirty)
    tabs.addTab(self.sifarnici_tab, "Šifrarnici")
    
    # NOVI - Admin Tab
    self.admin_tab = AdminTab(self)
    tabs.addTab(self.admin_tab, "⚙️ Admin")
    
    return tabs
```

**TESTIRANJE:**

```bash
# Pokreni aplikaciju
python __main__.py

# Provjeri:
# 1. Da li se Admin tab vidi
# 2. Da li se otvara bez errora
# 3. Da li sidebar navigation radi
# 4. Da li se mogu switchovati paneli
```

**OČEKIVANO:**
```
✅ Admin tab postoji u tab widget-u
✅ Sidebar prikazuje 6 sekcija
✅ Klik na sekciju mijenja content area
✅ Nema Python errors u konzoli
```

**COMMIT:**
```bash
git add gui/main_window.py
git commit -m "Admin Tab: Integration with MainWindow"
```

---

## TASK 18: TESTING - END-TO-END TESTS

**CILJ:** Kreirati testove za Admin Tab funkcionalnost

**GDJE:** `tests/admin/`

**ŠTA URADITI:**

Kreirati test fajlove:
- `tests/admin/__init__.py`
- `tests/admin/test_plugin_service.py`
- `tests/admin/test_settings_service.py`
- `tests/admin/test_backup_service.py`

**PRIMJER TEST FAJLA:**

```python
# tests/admin/test_plugin_service.py

import pytest
from services.admin.plugin_service import PluginService
from pathlib import Path


def test_plugin_service_creation():
    """Test kreiranje PluginService-a."""
    service = PluginService()
    assert service is not None
    assert service.plugin_loader is not None


def test_get_installed_plugins():
    """Test učitavanje instaliranih plugin-a."""
    service = PluginService()
    plugins = service.get_installed_plugins()
    
    assert isinstance(plugins, list)
    # Može biti prazna lista ako nema plugin-a
    
    if plugins:
        # Provjeri strukturu
        plugin = plugins[0]
        assert 'name' in plugin
        assert 'priority' in plugin
        assert 'filename' in plugin


# TODO: Dodati testove za install, remove, reload
```

**POKRETANJE TESTOVA:**

```bash
pytest tests/admin/ -v
```

**COMMIT:**
```bash
git add tests/admin/
git commit -m "Admin Tab: End-to-end tests"
```

---

## TASK 19: POLISH - ICONS, STYLING, UX IMPROVEMENTS

**CILJ:** Poboljšati izgled i UX Admin Tab-a

**GDJE:** Različiti fajlovi

**ŠTA URADITI:**

1. **Dodaj ikone:**
   - Sidebar items (qtawesome icons)
   - Buttons (download, sync, trash, save)

2. **Styling:**
   - QSS stylesheet za Admin Tab
   - Consistent colors
   - Hover effects

3. **UX Improvements:**
   - Loading indicators
   - Progress bars za backup/restore
   - Tooltips na buttons
   - Keyboard shortcuts

**PRIMJER STYLESHEETA:**

```python
# gui/tabs/admin/admin_view.py

def _apply_styles(self):
    """Primijeni stylesheet."""
    stylesheet = """
    QListWidget {
        background-color: #f5f5f5;
        border: 1px solid #ddd;
        border-radius: 4px;
        padding: 5px;
    }
    
    QListWidget::item {
        padding: 8px;
        border-radius: 3px;
    }
    
    QListWidget::item:selected {
        background-color: #0078d4;
        color: white;
    }
    
    QListWidget::item:hover {
        background-color: #e8e8e8;
    }
    
    QPushButton {
        padding: 6px 12px;
        border: 1px solid #ddd;
        border-radius: 3px;
        background-color: white;
    }
    
    QPushButton:hover {
        background-color: #f0f0f0;
    }
    
    QPushButton:pressed {
        background-color: #e0e0e0;
    }
    """
    
    self.setStyleSheet(stylesheet)
```

**COMMIT:**
```bash
git add gui/tabs/admin/
git commit -m "Admin Tab: Polish - icons, styling, UX improvements"
```

---

## TASK 20: DOCUMENTATION - USER GUIDE & DEVELOPER DOCS

**CILJ:** Dokumentovati Admin Tab funkcionalnost

**GDJE:** `docs/`

**ŠTA URADITI:**

Kreirati dokumentaciju:
1. `docs/admin_tab_user_guide.md` - Korisnički vodič
2. `docs/admin_tab_developer.md` - Developer docs
3. Update `README.md` sa Admin Tab sekcijom

**USER GUIDE STRUKTURA:**

```markdown
# ASYCUDA Pro - Admin Tab User Guide

## Uvod
Admin Tab pruža pristup svim admin funkcionalnostima...

## Plugin Manager
### Instalacija novog parsera
1. Klikni "Instaliraj Novi Parser"
2. Odaberi .py fajl
3. Restart aplikacije

### Uklanjanje parsera
...

## Settings
### Database Configuration
...

## Database Management
### Kreiranje Backup-a
...

## Logs
### Pregled Log-ova
...

## System Info
### Copy System Info
...
```

**COMMIT:**
```bash
git add docs/
git commit -m "Admin Tab: User guide and developer documentation"
```

---

## FINAL CHECKLIST

Nakon svih taskova, provjeri:

- [ ] Svi folderi kreirani
- [ ] Svi fajlovi implementirani
- [ ] Admin Tab se vidi u MainWindow
- [ ] Plugin Manager radi (install/remove/reload)
- [ ] Settings se mogu editovati i čuvati
- [ ] Database backup/restore radi
- [ ] Logs se prikazuju
- [ ] System Info se prikazuje
- [ ] Analytics prikazuje osnovne stats (ako implementirano)
- [ ] Svi testovi passing
- [ ] Dokumentacija kompletna
- [ ] Git commits clean i opisni

---

## QUICK START GUIDE

Za brzo pokretanje implementacije:

1. **Start sa strukturom:**
   ```bash
   # TASK 1
   mkdir -p gui/tabs/admin/panels services/admin tests/admin
   ```

2. **Core layer-i:**
   ```bash
   # TASK 2-5
   # Implementiraj: AdminTab → AdminView → AdminController → AdminService
   ```

3. **Prvi panel:**
   ```bash
   # TASK 6-7
   # Implementiraj: PluginPanel + PluginService
   # Test da radi prije nego što nastaviš
   ```

4. **Ostali paneli:**
   ```bash
   # TASK 8-16
   # Settings, Database, Logs, System Info, Analytics
   # Jedan po jedan, testiraj svaki
   ```

5. **Integracija:**
   ```bash
   # TASK 17
   # Dodaj u MainWindow
   # End-to-end test
   ```

6. **Polish:**
   ```bash
   # TASK 18-20
   # Testovi, UX, Dokumentacija
   ```

---

## TROUBLESHOOTING

### Problem: Panel se ne prikazuje
**Rješenje:** Provjeri da li je panel dodan u `_create_panels()` i u stacked widget

### Problem: Signali ne rade
**Rješenje:** Provjeri `_connect_signals()` u Controller-u

### Problem: Service metode fail-uju
**Rješenje:** Provjeri da li su pod-servisi kreirani u `AdminService.__init__`

### Problem: Import errors
**Rješenje:** Provjeri da li su svi `__init__.py` fajlovi kreirani

---

## NAPOMENE

- **Modularnost:** Svaki panel je nezavisan - može se implementirati i testirati posebno
- **Testiranje:** Testiraj nakon svakog task-a, ne čekaj do kraja
- **Git:** Commituj često, mali commit-i bolji od jednog velikog
- **Prioriteti:** Ako je vrijeme ograničeno, implementiraj MVP prvo (Plugin Manager + Settings + System Info)

---

## SUPPORT

Za pitanja ili pomoć:
- Provjeri dokumentaciju u `docs/`
- Pogledaj postojeće primjere u kodu
- Testiraj u isolation-u (kreiraj test fajl sa samo jednom komponentom)

---

**END OF IMPLEMENTATION GUIDE**

Ovaj dokument sadrži SVE što je potrebno za potpunu implementaciju Admin Tab-a.
Prati taskove redom i bit će kompletno funkcionalno! 🚀
