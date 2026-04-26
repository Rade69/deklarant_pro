# ASYCUDA PRO - ADMIN TAB DESIGN

**Centralni Admin Panel unutar aplikacije**

---

## KONCEPCIJA

Umjesto rasutih dialoga po menijima, **SVE admin funkcionalnosti** na jednom mjestu!

```
┌─────────────────────────────────────────────────────────┐
│ Faktura │ Naimenovanja │ Zaglavlje │ Šifrarnici │ ADMIN │ ← Novi tab!
└─────────────────────────────────────────────────────────┘
```

---

## UI LAYOUT - Dva Pristupa

### OPCIJA 1: Sidebar Navigation ⭐ PREPORUČENO

```
┌──────────────────────────────────────────────────────────┐
│ ADMIN TAB                                                │
├─────────────┬────────────────────────────────────────────┤
│             │                                            │
│ 📦 Plugins  │  CONTENT AREA                             │
│ ⚙️  Settings│                                            │
│ 💾 Database │  (Dinamički sadržaj zavisno od izbora)   │
│ 📊 Analytics│                                            │
│ 📋 Logs     │                                            │
│ ℹ️  System  │                                            │
│             │                                            │
│             │                                            │
└─────────────┴────────────────────────────────────────────┘
```

**Prednosti:**
- ✅ Čist, moderan izgled
- ✅ Brza navigacija
- ✅ Lako proširiv (dodaj novu sekciju)
- ✅ Familijaran UX (kao VS Code, GitHub Settings)

---

### OPCIJA 2: Sub-Tabs

```
┌──────────────────────────────────────────────────────────┐
│ ADMIN TAB                                                │
├──────────────────────────────────────────────────────────┤
│ Plugins │ Settings │ Database │ Analytics │ Logs │ System│
├──────────────────────────────────────────────────────────┤
│                                                          │
│  CONTENT AREA                                            │
│  (Dinamički sadržaj zavisno od sub-tab-a)               │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

**Prednosti:**
- ✅ Jednostavan (samo nested tabs)
- ✅ Familijaran (kao Excel ribbon)

**Mane:**
- ❌ Horizontalni prostor ograničen
- ❌ Teže proširiv (mnogo sub-tabs = clutter)

---

## SEKCIJE ADMIN TAB-a

### 1. 📦 PLUGIN MANAGER

**Funkcionalnosti:**

```
┌────────────────────────────────────────────────────────┐
│ PLUGIN MANAGER                                         │
├────────────────────────────────────────────────────────┤
│                                                        │
│ Instalirani Parseri:                                   │
│ ┌────────────────────────────────────────────────────┐ │
│ │ ✅ Špediter ABC - Maxi Parser v1.2                 │ │
│ │    Client: Špediter ABC │ Firma: Maxi d.o.o.      │ │
│ │    Status: Aktivan │ Priority: 25                  │ │
│ │    [Deaktiviraj] [Info] [Ukloni]                   │ │
│ ├────────────────────────────────────────────────────┤ │
│ │ ✅ Špediter XYZ - Metro Parser v2.0                │ │
│ │    Client: Špediter XYZ │ Firma: Metro            │ │
│ │    Status: Aktivan │ Priority: 20                  │ │
│ │    [Deaktiviraj] [Info] [Ukloni]                   │ │
│ ├────────────────────────────────────────────────────┤ │
│ │ ⚠️  Test Parser v0.1                               │ │
│ │    Client: Development │ Status: Inaktivan        │ │
│ │    [Aktiviraj] [Info] [Ukloni]                     │ │
│ └────────────────────────────────────────────────────┘ │
│                                                        │
│ [📥 Instaliraj Novi Parser]  [🔄 Reload Parsera]      │
│                                                        │
│ ─────────────────────────────────────────────────────  │
│                                                        │
│ Parser Info Panel:                                     │
│ ┌────────────────────────────────────────────────────┐ │
│ │ Ime: Maxi Parser                                   │ │
│ │ Verzija: 1.2                                       │ │
│ │ Klijent: Špediter ABC d.o.o.                       │ │
│ │ Firma: Maxi d.o.o.                                 │ │
│ │ Format: Excel (.xlsx)                              │ │
│ │ Autor: Radovan                                     │ │
│ │ Datum: 2026-03-01                                  │ │
│ │ Changelog:                                         │ │
│ │   v1.2 - Fixed multi-page support                 │ │
│ │   v1.1 - Added VAT calculation                    │ │
│ │   v1.0 - Initial release                          │ │
│ └────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────┘
```

**Features:**
- ✅ Lista svih parsera (sa status: aktivan/inaktivan)
- ✅ Install button (QFileDialog za .py fajl)
- ✅ Activate/Deactivate button (bez brisanja fajla)
- ✅ Remove button (briše .py fajl)
- ✅ Info panel (metadata, changelog)
- ✅ Reload button (hot-reload bez restarta)
- ✅ Search/Filter (po klijentu, firmi, formatu)
- ✅ Sort (po priority, datum, naziv)

---

### 2. ⚙️ SETTINGS / CONFIGURATION

**Funkcionalnosti:**

```
┌────────────────────────────────────────────────────────┐
│ SETTINGS                                               │
├────────────────────────────────────────────────────────┤
│                                                        │
│ Database Connection:                                   │
│ ┌────────────────────────────────────────────────────┐ │
│ │ Host: localhost                   Port: 5432       │ │
│ │ Database: deklarant_pro                              │ │
│ │ User: postgres                                     │ │
│ │ Password: ********                                 │ │
│ │                                                    │ │
│ │ [Test Connection] ✅ Connected                     │ │
│ └────────────────────────────────────────────────────┘ │
│                                                        │
│ Paths:                                                 │
│ ┌────────────────────────────────────────────────────┐ │
│ │ Plugins:  C:\...\Deklarant Pro\plugins   [Browse]   │ │
│ │ Exports:  C:\Users\...\ASYCUDA\exports [Browse]   │ │
│ │ Imports:  C:\Users\...\ASYCUDA\imports [Browse]   │ │
│ │ Logs:     C:\...\Deklarant Pro\logs      [Browse]   │ │
│ └────────────────────────────────────────────────────┘ │
│                                                        │
│ Application Settings:                                  │
│ ┌────────────────────────────────────────────────────┐ │
│ │ ☑ Auto-check for parser updates on startup        │ │
│ │ ☑ Enable debug logging                            │ │
│ │ ☑ Create backup before database operations        │ │
│ │ ☐ Enable analytics tracking                       │ │
│ │                                                    │ │
│ │ Import Settings:                                   │ │
│ │   Default currency: EUR ▼                         │ │
│ │   Date format: DD.MM.YYYY ▼                       │ │
│ │   Auto-save after import: ☑                       │ │
│ └────────────────────────────────────────────────────┘ │
│                                                        │
│ [💾 Sačuvaj Izmjene]  [↺ Reset na Default]            │
│                                                        │
└────────────────────────────────────────────────────────┘
```

**Features:**
- ✅ Database config (host, port, credentials)
- ✅ Test connection button
- ✅ Paths configuration (plugins, exports, imports, logs)
- ✅ App preferences (checkboxes, dropdowns)
- ✅ Import default settings
- ✅ Save/Reset buttons
- ✅ .env file sync

---

### 3. 💾 DATABASE MANAGEMENT

**Funkcionalnosti:**

```
┌────────────────────────────────────────────────────────┐
│ DATABASE MANAGEMENT                                    │
├────────────────────────────────────────────────────────┤
│                                                        │
│ Database Info:                                         │
│ ┌────────────────────────────────────────────────────┐ │
│ │ Database: deklarant_pro                              │ │
│ │ Size: 156 MB                                       │ │
│ │ Tables: 24                                         │ │
│ │ Total Records: 15,342                              │ │
│ │ Last Backup: 2026-03-10 14:30                     │ │
│ │ Status: ✅ Healthy                                 │ │
│ └────────────────────────────────────────────────────┘ │
│                                                        │
│ Backup & Restore:                                      │
│ ┌────────────────────────────────────────────────────┐ │
│ │ [💾 Create Backup]                                 │ │
│ │                                                    │ │
│ │ Backup Location:                                   │ │
│ │ C:\Users\...\ASYCUDA\backups\  [Browse]           │ │
│ │                                                    │ │
│ │ Available Backups:                                 │ │
│ │ ┌──────────────────────────────────────────────┐  │ │
│ │ │ 📁 asycuda_2026-03-10_14-30.sql  156 MB      │  │ │
│ │ │ 📁 asycuda_2026-03-09_18-15.sql  154 MB      │  │ │
│ │ │ 📁 asycuda_2026-03-08_10-00.sql  152 MB      │  │ │
│ │ └──────────────────────────────────────────────┘  │ │
│ │                                                    │ │
│ │ [⬆️ Restore from Backup]  [🗑️ Delete Backup]      │ │
│ └────────────────────────────────────────────────────┘ │
│                                                        │
│ Maintenance:                                           │
│ ┌────────────────────────────────────────────────────┐ │
│ │ [🔧 Vacuum Database]  - Optimize & reclaim space  │ │
│ │ [📊 Analyze Tables]   - Update statistics         │ │
│ │ [🔍 Check Integrity]  - Verify database health    │ │
│ │ [🗑️ Clear Old Data]   - Remove data older than... │ │
│ └────────────────────────────────────────────────────┘ │
│                                                        │
│ Migrations:                                            │
│ ┌────────────────────────────────────────────────────┐ │
│ │ Current Schema Version: 3.2                        │ │
│ │                                                    │ │
│ │ ☑ Migration 001: Initial schema                   │ │
│ │ ☑ Migration 002: Add parsers metadata             │ │
│ │ ☑ Migration 003: Add analytics tables             │ │
│ │ ☐ Migration 004: Add user roles (pending)         │ │
│ │                                                    │ │
│ │ [▶️ Run Pending Migrations]                        │ │
│ └────────────────────────────────────────────────────┘ │
│                                                        │
└────────────────────────────────────────────────────────┘
```

**Features:**
- ✅ Database info (size, tables count, status)
- ✅ Create backup (pg_dump)
- ✅ Restore from backup
- ✅ List available backups (sa datumom, size)
- ✅ Delete old backups
- ✅ Maintenance operations (vacuum, analyze, integrity check)
- ✅ Schema migrations status
- ✅ Run pending migrations

---

### 4. 📊 ANALYTICS / STATISTICS

**Funkcionalnosti:**

```
┌────────────────────────────────────────────────────────┐
│ ANALYTICS                                              │
├────────────────────────────────────────────────────────┤
│                                                        │
│ Overview (Last 30 Days):                               │
│ ┌────────────────────────────────────────────────────┐ │
│ │ Total Imports: 342                                 │ │
│ │ Total Exports: 298                                 │ │
│ │ Success Rate: 97.4%                                │ │
│ │ Avg Import Time: 2.3s                              │ │
│ └────────────────────────────────────────────────────┘ │
│                                                        │
│ Imports by Parser:                                     │
│ ┌────────────────────────────────────────────────────┐ │
│ │ ██████████████████████ Maxi Parser    156 (45%)   │ │
│ │ ███████████████        Metro Parser   89  (26%)   │ │
│ │ ██████████             Excel Generic  67  (20%)   │ │
│ │ ████                   PDF Generic    30  (9%)    │ │
│ └────────────────────────────────────────────────────┘ │
│                                                        │
│ Import Trends (Line Chart):                           │
│ ┌────────────────────────────────────────────────────┐ │
│ │ 40 │                                        ╱╲     │ │
│ │    │                              ╱╲       ╱  ╲    │ │
│ │ 30 │                    ╱╲       ╱  ╲     ╱    ╲   │ │
│ │    │          ╱╲       ╱  ╲     ╱    ╲   ╱      ╲  │ │
│ │ 20 │  ╱╲     ╱  ╲     ╱    ╲   ╱      ╲ ╱        │ │
│ │    │╱    ╲ ╱      ╲ ╱        ╲╱                   │ │
│ │ 10 ┴───────────────────────────────────────────── │ │
│ │    Mon Tue Wed Thu Fri Sat Sun                    │ │
│ └────────────────────────────────────────────────────┘ │
│                                                        │
│ Error Log (Recent):                                    │
│ ┌────────────────────────────────────────────────────┐ │
│ │ 2026-03-10 15:23 │ Maxi Parser │ Failed to parse  │ │
│ │ 2026-03-09 12:10 │ PDF Import  │ Invalid format   │ │
│ │ 2026-03-08 09:45 │ Database    │ Connection lost  │ │
│ └────────────────────────────────────────────────────┘ │
│                                                        │
│ [📥 Export Report (Excel)]  [📊 Advanced Analytics]   │
│                                                        │
└────────────────────────────────────────────────────────┘
```

**Features:**
- ✅ Import/Export statistics
- ✅ Success rate tracking
- ✅ Parser usage breakdown (chart)
- ✅ Timeline trends (line chart)
- ✅ Recent errors log
- ✅ Export to Excel report
- ✅ Date range filter

---

### 5. 📋 LOGS VIEWER

**Funkcionalnosti:**

```
┌────────────────────────────────────────────────────────┐
│ LOGS                                                   │
├────────────────────────────────────────────────────────┤
│                                                        │
│ Filters:                                               │
│ Level: [All ▼]  Date: [Last 7 Days ▼]  Search: [___]  │
│                                                        │
│ ┌────────────────────────────────────────────────────┐ │
│ │ Time        Level    Module          Message       │ │
│ ├────────────────────────────────────────────────────┤ │
│ │ 15:42:13    INFO     ImportService   Imported PDF │ │
│ │ 15:41:55    DEBUG    PluginLoader    Loaded Maxi  │ │
│ │ 15:41:32    WARNING  Database        Slow query   │ │
│ │ 15:40:12    ERROR    MaxiParser      Parse failed │ │
│ │             ├─ File: invoice_123.xlsx               │ │
│ │             ├─ Error: KeyError: 'total'            │ │
│ │             └─ Stack: [Show Stack Trace]           │ │
│ │ 15:35:08    INFO     MainWindow      App started  │ │
│ │ ...                                                │ │
│ └────────────────────────────────────────────────────┘ │
│                                                        │
│ [🔄 Refresh]  [🗑️ Clear Logs]  [💾 Export Logs]       │
│                                                        │
│ Log File Location:                                     │
│ C:\...\Deklarant Pro\logs\asycuda_2026-03-10.log       │
│ [📂 Open Log Folder]                                  │
│                                                        │
└────────────────────────────────────────────────────────┘
```

**Features:**
- ✅ Real-time log viewer
- ✅ Filter by level (INFO, DEBUG, WARNING, ERROR)
- ✅ Filter by date range
- ✅ Search functionality
- ✅ Expandable error details (stack trace)
- ✅ Export logs to file
- ✅ Clear logs
- ✅ Open log folder

---

### 6. ℹ️ SYSTEM INFO

**Funkcionalnosti:**

```
┌────────────────────────────────────────────────────────┐
│ SYSTEM INFORMATION                                     │
├────────────────────────────────────────────────────────┤
│                                                        │
│ Application:                                           │
│ ┌────────────────────────────────────────────────────┐ │
│ │ Name: Deklarant Pro                                  │ │
│ │ Version: 2.0.1                                     │ │
│ │ Build: 20260310                                    │ │
│ │ License: Špediter ABC d.o.o. (Active)              │ │
│ │ Installed: 2025-11-15                              │ │
│ └────────────────────────────────────────────────────┘ │
│                                                        │
│ System:                                                │
│ ┌────────────────────────────────────────────────────┐ │
│ │ OS: Windows 11 Pro (Build 22000)                   │ │
│ │ Python: 3.11.5                                     │ │
│ │ Qt: PySide6 6.6.0                                  │ │
│ │ Memory: 8 GB (4.2 GB available)                    │ │
│ │ CPU: Intel Core i7-11700 @ 2.5GHz (8 cores)       │ │
│ └────────────────────────────────────────────────────┘ │
│                                                        │
│ Database:                                              │
│ ┌────────────────────────────────────────────────────┐ │
│ │ Engine: PostgreSQL 15.3                            │ │
│ │ Host: localhost:5432                               │ │
│ │ Database: deklarant_pro                              │ │
│ │ Schema Version: 3.2                                │ │
│ │ Size: 156 MB                                       │ │
│ └────────────────────────────────────────────────────┘ │
│                                                        │
│ Installed Parsers:                                     │
│ ┌────────────────────────────────────────────────────┐ │
│ │ 5 active parsers, 1 inactive                       │ │
│ │ Built-in: PDF (v2.0), Excel (v2.1), XML (v1.5)    │ │
│ │ Plugins: Maxi Parser, Metro Parser, Test Parser   │ │
│ └────────────────────────────────────────────────────┘ │
│                                                        │
│ Paths:                                                 │
│ ┌────────────────────────────────────────────────────┐ │
│ │ Installation: C:\Program Files\Deklarant Pro\        │ │
│ │ Data: C:\Users\User\AppData\Local\ASYCUDA\         │ │
│ │ Plugins: C:\Program Files\Deklarant Pro\plugins\     │ │
│ │ Logs: C:\Program Files\Deklarant Pro\logs\           │ │
│ └────────────────────────────────────────────────────┘ │
│                                                        │
│ [📋 Copy System Info]  [📧 Email Support]             │
│                                                        │
└────────────────────────────────────────────────────────┘
```

**Features:**
- ✅ App version & build info
- ✅ License information
- ✅ System specs (OS, Python, Qt, CPU, RAM)
- ✅ Database info
- ✅ Installed parsers summary
- ✅ Paths display
- ✅ Copy system info (za support tickets)
- ✅ Email support button (pre-populated sa system info)

---

## IMPLEMENTACIJA - CODE STRUKTURA

```
gui/tabs/
├── admin_tab.py              # Main Admin Tab wrapper
├── admin/
│   ├── __init__.py
│   ├── admin_view.py         # Glavni UI (sidebar + content area)
│   ├── admin_controller.py   # Orchestration
│   └── panels/               # Sekcije
│       ├── __init__.py
│       ├── plugin_panel.py   # Plugin Manager UI
│       ├── settings_panel.py # Settings UI
│       ├── database_panel.py # Database Management UI
│       ├── analytics_panel.py# Analytics UI
│       ├── logs_panel.py     # Logs Viewer UI
│       └── system_panel.py   # System Info UI
│
services/
├── admin_service.py          # Admin business logic
├── plugin_service.py         # Plugin operations
├── backup_service.py         # Database backup/restore
├── analytics_service.py      # Statistics gathering
└── log_service.py            # Log reading/filtering
```

---

## IMPLEMENTACIJA - STEP BY STEP

### KORAK 1: Admin Tab Wrapper

```python
# gui/tabs/admin_tab.py

from PySide6.QtWidgets import QWidget, QVBoxLayout
from gui.tabs.admin.admin_view import AdminView
from gui.tabs.admin.admin_controller import AdminController
from services.admin_service import AdminService

class AdminTab(QWidget):
    """Admin Tab - centralni control panel."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Layers
        self.service = AdminService()
        self.view = AdminView(parent=self)
        self.controller = AdminController(self.view, self.service)
        
        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
```

---

### KORAK 2: Admin View (Sidebar + Content)

```python
# gui/tabs/admin/admin_view.py

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, 
    QListWidget, QStackedWidget, QPushButton
)
from gui.tabs.admin.panels.plugin_panel import PluginPanel
from gui.tabs.admin.panels.settings_panel import SettingsPanel
# ... ostali paneli

class AdminView(QWidget):
    """Admin View sa sidebar navigation."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """Setup glavnog UI-a."""
        layout = QHBoxLayout(self)
        
        # SIDEBAR (lijevo)
        self.sidebar = self._create_sidebar()
        layout.addWidget(self.sidebar, stretch=1)
        
        # CONTENT AREA (desno)
        self.content_stack = QStackedWidget()
        layout.addWidget(self.content_stack, stretch=4)
        
        # Paneli
        self._create_panels()
        
        # Select prvi panel
        self.sidebar.setCurrentRow(0)
    
    def _create_sidebar(self) -> QListWidget:
        """Kreiraj sidebar sa navigacijom."""
        sidebar = QListWidget()
        sidebar.setMaximumWidth(200)
        
        # Items
        sidebar.addItem("📦 Plugin Manager")
        sidebar.addItem("⚙️  Settings")
        sidebar.addItem("💾 Database")
        sidebar.addItem("📊 Analytics")
        sidebar.addItem("📋 Logs")
        sidebar.addItem("ℹ️  System Info")
        
        # Connect
        sidebar.currentRowChanged.connect(
            self.content_stack.setCurrentIndex
        )
        
        return sidebar
    
    def _create_panels(self):
        """Kreiraj sve content panele."""
        # Plugin panel
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
        
        # System panel
        self.system_panel = SystemPanel()
        self.content_stack.addWidget(self.system_panel)
```

---

### KORAK 3: Plugin Panel (Primjer)

```python
# gui/tabs/admin/panels/plugin_panel.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QGroupBox, QPushButton,
    QLabel, QTextEdit, QFileDialog, QMessageBox
)
from importers.plugin_loader import PluginLoader

class PluginPanel(QWidget):
    """Plugin Manager panel."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.plugin_loader = PluginLoader()
        self.setup_ui()
        self.load_parsers()
    
    def setup_ui(self):
        """Setup UI."""
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("<h2>Plugin Manager</h2>")
        layout.addWidget(header)
        
        # Content area
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
        info_layout.addWidget(self.info_text)
        
        content_layout.addWidget(info_group, stretch=1)
        
        layout.addLayout(content_layout)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.btn_install = QPushButton("📥 Instaliraj Novi Parser")
        self.btn_install.clicked.connect(self._install_parser)
        btn_layout.addWidget(self.btn_install)
        
        self.btn_reload = QPushButton("🔄 Reload Parsera")
        self.btn_reload.clicked.connect(self._reload_parsers)
        btn_layout.addWidget(self.btn_reload)
        
        self.btn_remove = QPushButton("🗑️ Ukloni")
        self.btn_remove.clicked.connect(self._remove_parser)
        btn_layout.addWidget(self.btn_remove)
        
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
    
    def load_parsers(self):
        """Učitaj listu parsera."""
        self.parsers_list.clear()
        
        parsers_dir = self.plugin_loader.parsers_dir
        
        if not parsers_dir.exists():
            self.parsers_list.addItem("(Nema parsera)")
            return
        
        for filepath in parsers_dir.glob("*.py"):
            if filepath.name.startswith("_"):
                continue
            
            # Load parser info
            parser = self.plugin_loader._load_parser_from_file(filepath)
            
            if parser:
                instance = parser()
                display_name = f"✅ {instance.strategy_name}"
                
                item = QListWidgetItem(display_name)
                item.setData(Qt.UserRole, {
                    'filepath': filepath,
                    'parser': instance
                })
                
                self.parsers_list.addItem(item)
    
    def _on_parser_selected(self, current, previous):
        """Parser selected - prikaži info."""
        if not current:
            self.info_text.clear()
            return
        
        data = current.data(Qt.UserRole)
        parser = data['parser']
        
        # Format info
        info = f"""
<b>Ime:</b> {parser.strategy_name}<br>
<b>Prioritet:</b> {parser.priority}<br>
<b>Klijent:</b> {parser.metadata.get('client', 'N/A')}<br>
<b>Firma:</b> {parser.metadata.get('firma', 'N/A')}<br>
<b>Verzija:</b> {parser.metadata.get('version', 'N/A')}<br>
<b>Autor:</b> {parser.metadata.get('author', 'N/A')}<br>
<br>
<b>Fajl:</b> {data['filepath'].name}
        """
        
        self.info_text.setHtml(info)
    
    def _install_parser(self):
        """Instaliraj novi parser."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Odaberi Parser Fajl",
            "",
            "Python fajlovi (*.py)"
        )
        
        if not filepath:
            return
        
        from pathlib import Path
        success = self.plugin_loader.install_plugin(Path(filepath))
        
        if success:
            QMessageBox.information(
                self,
                "Uspjeh",
                "Parser uspješno instaliran!\nRestartuj aplikaciju."
            )
            self.load_parsers()
        else:
            QMessageBox.critical(
                self,
                "Greška",
                "Instalacija nije uspjela!"
            )
    
    def _reload_parsers(self):
        """Reload parsera bez restarta."""
        # TODO: Implement registry.reload_plugins()
        self.load_parsers()
        QMessageBox.information(
            self,
            "Reload",
            "Parseri reload-ovani!"
        )
    
    def _remove_parser(self):
        """Ukloni parser."""
        current = self.parsers_list.currentItem()
        if not current:
            return
        
        data = current.data(Qt.UserRole)
        filepath = data['filepath']
        
        reply = QMessageBox.question(
            self,
            "Potvrda",
            f"Obrisati parser '{filepath.name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                filepath.unlink()
                self.load_parsers()
                QMessageBox.information(
                    self,
                    "Uspjeh",
                    "Parser obrisan!"
                )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Greška",
                    f"Brisanje nije uspjelo:\n{e}"
                )
```

---

### KORAK 4: Dodaj u MainWindow

```python
# gui/main_window.py

def _create_tabs(self):
    """Kreiraj tabove."""
    tabs = QTabWidget()
    
    # Postojeći tabovi
    self.faktura_tab = FakturaTab(...)
    tabs.addTab(self.faktura_tab, "Faktura")
    
    self.naimenovanja_tab = NaimenovanjaTab(...)
    tabs.addTab(self.naimenovanja_tab, "Naimenovanja")
    
    self.zaglavlje_tab = ZaglavljeTab(...)
    tabs.addTab(self.zaglavlje_tab, "Zaglavlje")
    
    self.sifarnici_tab = SifarniciTab(...)
    tabs.addTab(self.sifarnici_tab, "Šifrarnici")
    
    # NOVI - Admin Tab
    self.admin_tab = AdminTab(self)
    tabs.addTab(self.admin_tab, "⚙️ Admin")
    
    return tabs
```

---

## PREDNOSTI ADMIN TAB-a

### 1. User Experience
✅ Sve na jednom mjestu (no more hunting through menus!)  
✅ Consistent UX (isti pattern kao VS Code, GitHub)  
✅ Professional izgled  
✅ Brza navigacija (sidebar ili tabs)

### 2. Developer Experience
✅ Modularno (svaki panel poseban fajl)  
✅ Lako proširiv (dodaj novi panel = 1 fajl)  
✅ Testabilan (paneli nezavisni)  
✅ Reusable (panel može biti i dialog)

### 3. Maintenance
✅ Centralizovano (sve admin funkcije u jednom tab-u)  
✅ Jasna struktura (admin/ folder)  
✅ Lako za debug  
✅ Verzionisanje (admin features zajedno)

### 4. Future Features
✅ User management (multi-user support)  
✅ Audit log (ko je šta radio)  
✅ Remote monitoring (server status)  
✅ License management  
✅ Update checker  
✅ Plugin marketplace

---

## PRIORITET IMPLEMENTACIJE

### Faza 1: MVP (1-2 dana)
- ✅ Admin Tab wrapper
- ✅ Sidebar navigation
- ✅ Plugin Manager panel
- ✅ Settings panel (basic)
- ✅ System Info panel

### Faza 2: Essential Features (2-3 dana)
- ✅ Database backup/restore
- ✅ Logs viewer
- ✅ Analytics (basic stats)

### Faza 3: Advanced Features (opciono)
- ✅ Advanced analytics (charts)
- ✅ Remote parser install
- ✅ Auto-update check
- ✅ User management

---

## ZAKLJUČAK

**Admin Tab je BRILJANTNA ideja jer:**

1. **UX**: Sve na jednom mjestu - no more scattered dialogs! 🎯
2. **Professional**: Moderni SaaS-style admin panel 💼
3. **Extensible**: Lako dodati nove sekcije/features 🔧
4. **Maintainable**: Čista struktura, modularno 📦

**Implementacija:**
- Start sa Plugin Manager + Settings + System Info (MVP)
- Dodaj Database i Logs kasnije
- Analytics kao cherry on top 🍒

**Javi mi da li želiš da krenem sa implementacijom!** 🚀

Mogu ti dati detaljne Claude Code prompte za svaki panel! 📝
