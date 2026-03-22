# ASYCUDA Pro - Admin Tab Developer Documentation

## 📋 Pregled

Admin Tab je implementiran koristeći **3-layer arhitekturu**:

```
┌─────────────────────────────────────────────────────────┐
│                    AdminTab (Wrapper)                    │
├─────────────────────────────────────────────────────────┤
│  AdminView  │  AdminController  │  AdminService         │
│   (UI)      │   (Orchestration) │   (Business Logic)    │
├─────────────┴───────────────────┴───────────────────────┤
│                    Panel Components                      │
│  PluginPanel │ SettingsPanel │ DatabasePanel │ ...      │
├─────────────────────────────────────────────────────────┤
│                    Service Components                    │
│  PluginService │ SettingsService │ BackupService │ ...  │
└─────────────────────────────────────────────────────────┘
```

---

## 🏗️ Arhitektura

### Layer-i

1. **Wrapper Layer** (`gui/tabs/admin_tab.py`)
   - Ulazna tačka za MainWindow
   - Kreira i povezuje sve layer-e

2. **View Layer** (`gui/tabs/admin/`)
   - `admin_view.py` - Glavni UI sa sidebar navigacijom
   - `panels/` - Komponente za svaki panel

3. **Controller Layer** (`gui/tabs/admin/admin_controller.py`)
   - Orkestracija između View i Service
   - Handleri za user akcije

4. **Service Layer** (`services/admin/`)
   - Business logika
   - Delegira na specijalizovane servise

---

## 📁 Struktura fajlova

```
gui/tabs/admin/
├── __init__.py
├── admin_view.py          # Main UI sa sidebar
├── admin_controller.py    # Orchestration layer
└── panels/
    ├── __init__.py
    ├── plugin_panel.py    # Plugin Manager UI
    ├── settings_panel.py  # Settings UI
    ├── database_panel.py  # Database Management UI
    ├── logs_panel.py      # Logs Viewer UI
    ├── system_panel.py    # System Info UI
    └── analytics_panel.py # Analytics UI

services/admin/
├── __init__.py
├── admin_service.py       # Main service (koordinator)
├── plugin_service.py      # Plugin operacije
├── settings_service.py    # Settings operacije
├── backup_service.py      # Backup/Restore operacije
├── log_service.py         # Log operacije
└── analytics_service.py   # Analytics operacije

tests/admin/
├── __init__.py
├── test_admin_service.py
├── test_plugin_service.py
├── test_settings_service.py
├── test_backup_service.py
├── test_log_service.py
└── test_analytics_service.py

gui/styles/
└── admin_tab.qss          # Stylesheet za Admin Tab
```

---

## 🔌 Integration sa MainWindow

Admin Tab se dodaje u MainWindow na sljedeći način:

```python
# gui/main_window.py
from gui.tabs.admin_tab import AdminTab

# U _create_tabs() metodi:
self.admin_tab = AdminTab(self)
tabs.addTab(self.admin_tab, "⚙️ Admin")
```

---

## 🎨 Styling

### Stylesheet

Admin Tab koristi poseban QSS stylesheet:

```python
# gui/tabs/admin/admin_view.py
def _apply_styles(self):
    styles_dir = Path(__file__).parent.parent.parent / "styles"
    stylesheet_path = styles_dir / "admin_tab.qss"
    
    if stylesheet_path.exists():
        with open(stylesheet_path, 'r', encoding='utf-8') as f:
            stylesheet = f.read()
        self.setStyleSheet(stylesheet)
```

### CSS klase

- `AdminView` - Glavni container
- `PluginPanel`, `SettingsPanel`, itd. - Panel specifični stilovi
- `QPushButton#primaryButton` - Primarni buttoni
- `QPushButton#dangerButton` - Danger buttoni (crveni)

---

## 📡 Signal/Slot komunikacija

### Panel → Controller

Svaki panel emituje signale koje Controller prima:

```python
# PluginPanel
install_requested = Signal(str)
reload_requested = Signal()
remove_requested = Signal(str)

# SettingsPanel
save_requested = Signal(dict)

# DatabasePanel
backup_requested = Signal(str)
restore_requested = Signal(str)

# LogsPanel
refresh_requested = Signal()
```

### Controller → Service

Controller direktno poziva Service metode:

```python
def _on_install_plugin(self, filepath: str):
    success = self.service.install_plugin(filepath)
    if success:
        self.view.get_plugin_panel().show_success("Plugin instaliran!")
```

### Service → Controller (kroz return vrijednosti)

Service vraća rezultate koje Controller koristi za update UI-a:

```python
def install_plugin(self, filepath: str) -> bool:
    return self.plugin_service.install_plugin(filepath)
```

---

## 🧪 Testiranje

### Pokretanje testova

```bash
# Svi Admin Tab testovi
pytest tests/admin/ -v

# Specifičan service
pytest tests/admin/test_plugin_service.py -v

# Sa coverage-om
pytest tests/admin/ --cov=services/admin --cov=gui/tabs/admin
```

### Test coverage

```
============================== 35 passed in 0.16s ==============================
tests/admin/test_admin_service.py::TestAdminService::test_admin_service_creation PASSED
tests/admin/test_admin_service.py::TestAdminService::test_get_system_info PASSED
...
```

---

## 🔧 Service Implementacije

### PluginService

```python
class PluginService:
    def get_installed_plugins() -> List[Dict]
    def install_plugin(filepath: str) -> bool
    def remove_plugin(plugin_name: str) -> bool
    def reload_plugins() -> bool
```

**Napomene:**
- Koristi `PluginLoader` za učitavanje parsera
- Parseri se čuvaju u `plugins/parsers/`
- Metadata se čita iz `strategy_name`, `priority`, `metadata` atributa

### SettingsService

```python
class SettingsService:
    def get_settings() -> Dict
    def save_settings(settings: Dict) -> bool
```

**Napomene:**
- Settings se čuvaju u JSON formatu
- Lokacija: `~/.asycuda_pro/settings.json`
- Default vrijednosti su definisane u `_get_default_settings()`

### BackupService

```python
class BackupService:
    def create_backup(backup_path: str) -> bool
    def restore_backup(backup_path: str) -> bool
    def get_available_backups() -> List[Dict]
    def get_database_size() -> int
```

**Napomene:**
- Koristi `shutil.copy2()` za kopiranje database fajla
- Backup-ovi se čuvaju u `~/.asycuda_pro/backups/`
- Automatsko generisanje timestamp-a za backup fajlove

### LogService

```python
class LogService:
    def get_recent_logs(count: int) -> List[Dict]
    def filter_logs(level, search, start_date, end_date) -> List[Dict]
    def _parse_log_line(line: str) -> Dict
```

**Napomene:**
- Logovi se čitaju iz `~/.asycuda_pro/logs/asycuda.log`
- Format: `YYYY-MM-DD HH:MM:SS - LEVEL - Message`

### AnalyticsService

```python
class AnalyticsService:
    def get_import_statistics() -> Dict
    def get_parser_usage() -> List[Dict]
    def get_declaration_statistics() -> Dict
```

**Napomene:**
- Čita podatke direktno iz SQLite baze
- Zahtijeva `declarations` i `import_log` tabele

---

## 🎯 Extension Points

### Dodavanje novog panela

1. **Kreiraj Panel UI:**
   ```python
   # gui/tabs/admin/panels/new_panel.py
   class NewPanel(QWidget):
       def __init__(self):
           super().__init__()
           self.setup_ui()
   ```

2. **Kreiraj Service:**
   ```python
   # services/admin/new_service.py
   class NewService:
       def do_something(self):
           pass
   ```

3. **Dodaj u AdminView:**
   ```python
   def _create_panels(self):
       self.new_panel = NewPanel()
       self.content_stack.addWidget(self.new_panel)
   ```

4. **Dodaj u AdminService:**
   ```python
   def __init__(self):
       self.new_service = NewService()
   ```

5. **Dodaj handler u Controller:**
   ```python
   def _on_new_action(self):
       result = self.service.new_operation()
   ```

---

## 🐛 Debugging

### Logovanje

```python
import logging
logger = logging.getLogger('asycuda_pro.admin')

logger.info("Admin tab initialized")
logger.debug("Plugin loaded: %s", plugin_name)
logger.error("Backup failed: %s", error)
```

### Common Issues

| Problem | Rješenje |
|---------|----------|
| Panel se ne prikazuje | Provjeri da li je dodan u `_create_panels()` i `content_stack` |
| Signali ne rade | Provjeri `_connect_signals()` u Controller-u |
| Stylesheet se ne primjenjuje | Provjeri putanju do `admin_tab.qss` |
| Import error | Provjeri da li su svi `__init__.py` fajlovi prisutni |

---

## 📊 Metrike

| Metrika | Vrijednost |
|---------|------------|
| Ukupno linija koda | ~2,500 |
| Broj testova | 35 |
| Test coverage | ~85% |
| Broj panela | 6 |
| Broj servisa | 6 |

---

## 🚀 Roadmap

### Planirane funkcionalnosti

- [ ] **Plugin Marketplace** - Online repository parsera
- [ ] **Advanced Analytics** - Grafikon i trendovi
- [ ] **User Management** - Više korisnika sa različitim dozvolama
- [ ] **Audit Log** - Detaljan log svih akcija
- [ ] **Export/Import Settings** - Backup konfiguracije
- [ ] **Scheduled Backups** - Automatski backup po rasporedu

---

## 📚 Reference

- [Qt Widgets Documentation](https://doc.qt.io/qt-6/qwidget.html)
- [PySide6 Documentation](https://doc.qt.io/qtforpython-6/)
- [Qt Style Sheets Reference](https://doc.qt.io/qt-6/stylesheet-reference.html)

---

## 🔍 Troubleshooting Guide

### Problem: Panel se ne prikazuje

**Simptomi:**
- Klik na sidebar item
- Content area ostaje prazan
- Nema errora u konzoli

**Rješenja:**

1. **Provjeri da je panel dodan u stacked widget:**
```python
# gui/tabs/admin/admin_view.py
def _create_panels(self):
    self.plugin_panel = PluginPanel()
    self.content_stack.addWidget(self.plugin_panel)  # ← KRITIČNO!
```

2. **Provjeri redoslijed panela:**
```python
# Redoslijed u _create_panels() MORA odgovarati redoslijedu u sidebar-u!
# Sidebar:
# 0: Plugin Manager
# 1: Settings
# 2: Database
# ...

# Panels (ISTI redoslijed!):
self.content_stack.addWidget(self.plugin_panel)    # 0
self.content_stack.addWidget(self.settings_panel)  # 1
self.content_stack.addWidget(self.database_panel)  # 2
```

3. **Provjeri da panel ima getter u View:**
```python
def get_plugin_panel(self) -> PluginPanel:
    return self.plugin_panel
```

---

### Problem: Signali ne rade

**Simptomi:**
- Klik na button
- Handler se ne poziva
- Nema akcije

**Rješenja:**

1. **Provjeri da je signal definisan u Panel-u:**
```python
# gui/tabs/admin/panels/plugin_panel.py
class PluginPanel(QWidget):
    install_requested = Signal(str)  # ← MORA postojati!
```

2. **Provjeri da je signal connect-ovan u Controller-u:**
```python
# gui/tabs/admin/admin_controller.py
def _connect_signals(self):
    plugin_panel = self.view.get_plugin_panel()
    # OVO MORA BITI:
    plugin_panel.install_requested.connect(self._on_install_plugin)
```

3. **Provjeri da signal emit-uje u Panel-u:**
```python
def _on_install_clicked(self):
    filepath = "..."
    self.install_requested.emit(filepath)  # ← KRITIČNO!
```

4. **Debug sa print statements:**
```python
def _on_install_clicked(self):
    print("DEBUG: Install button clicked!")  # ← Dodaj ovo
    self.install_requested.emit(filepath)

def _on_install_plugin(self, filepath):
    print(f"DEBUG: Handler called with: {filepath}")  # ← I ovo
```

---

### Problem: Service metoda fail-uje

**Simptomi:**
- `AttributeError: 'NoneType' object has no attribute 'get_plugins'`
- Service operacija ne radi

**Rješenja:**

1. **Provjeri da je pod-servis kreiran u AdminService:**
```python
# services/admin/admin_service.py
class AdminService:
    def __init__(self):
        self.plugin_service = PluginService()  # ← MORA biti!
        self.settings_service = SettingsService()
        # ...
```

2. **Provjeri da metoda postoji u pod-servisu:**
```python
# services/admin/plugin_service.py
class PluginService:
    def get_installed_plugins(self):  # ← MORA postojati!
        # ...
```

3. **Provjeri delegation u AdminService:**
```python
def get_installed_plugins(self):
    return self.plugin_service.get_installed_plugins()  # ← Delegira!
```

---

### Problem: Import errors

**Simptomi:**
- `ModuleNotFoundError: No module named 'gui.tabs.admin'`
- `ImportError: cannot import name 'PluginPanel'`

**Rješenja:**

1. **Provjeri da su svi `__init__.py` fajlovi kreirani:**
```bash
touch gui/tabs/admin/__init__.py
touch gui/tabs/admin/panels/__init__.py
touch services/admin/__init__.py
```

2. **Provjeri import paths:**
```python
# POGREŠNO:
from admin.panels.plugin_panel import PluginPanel

# TAČNO:
from gui.tabs.admin.panels.plugin_panel import PluginPanel
```

3. **Provjeri da fajl postoji:**
```bash
ls gui/tabs/admin/panels/plugin_panel.py
```

---

### Problem: Stylesheet se ne primjenjuje

**Simptomi:**
- Default Qt styling
- Nema custom colors/borders

**Rješenja:**

1. **Provjeri da fajl postoji:**
```bash
ls gui/styles/admin_tab.qss
```

2. **Provjeri putanju:**
```python
# gui/tabs/admin/admin_view.py
from pathlib import Path

def _load_stylesheet(self):
    # PROVJERI putanju!
    styles_path = Path(__file__).parent.parent.parent / "styles" / "admin_tab.qss"
    print(f"DEBUG: Loading stylesheet from: {styles_path}")  # ← Dodaj
    
    if styles_path.exists():
        print("DEBUG: Stylesheet file exists!")  # ← I ovo
    else:
        print("DEBUG: Stylesheet NOT FOUND!")  # ← Debug
```

3. **Provjeri da je metoda pozvana:**
```python
def setup_ui(self):
    # ... UI setup
    self._load_stylesheet()  # ← MORA biti!
```

---

### Problem: Data se ne prikazuje u Panel-u

**Simptomi:**
- Panel je prazan
- Nema podataka

**Rješenja:**

1. **Provjeri da Controller poziva refresh:**
```python
def _load_initial_data(self):
    self._refresh_plugin_list()  # ← MORA biti!
```

2. **Provjeri da Service vraća podatke:**
```python
def _refresh_plugin_list(self):
    plugins = self.service.get_installed_plugins()
    print(f"DEBUG: Got {len(plugins)} plugins")  # ← Debug
    self.view.get_plugin_panel().set_plugins(plugins)
```

3. **Provjeri da Panel postavlja podatke:**
```python
def set_plugins(self, plugins: List[Dict]):
    print(f"DEBUG: Setting {len(plugins)} plugins in UI")  # ← Debug
    self.parsers_list.clear()
    
    for plugin in plugins:
        print(f"DEBUG: Adding plugin: {plugin['name']}")  # ← Debug
        # ... dodaj u listu
```

---

## 🛠️ Development Workflow

### 1. Kreiranje novog panel-a

```bash
# 1. Kreiraj Panel UI fajl
touch gui/tabs/admin/panels/my_panel.py

# 2. Kreiraj Service fajl
touch services/admin/my_service.py

# 3. Implementiraj Panel (UI only)
# 4. Implementiraj Service (business logic)
# 5. Dodaj u AdminView (_create_panels)
# 6. Dodaj u AdminService (__init__)
# 7. Connect signals u Controller
# 8. Test!
```

### 2. Debugging workflow

```bash
# 1. Check console za errors
python __main__.py

# 2. Add debug prints
# U kod dodaj: print("DEBUG: ...")

# 3. Use pdb debugger
import pdb; pdb.set_trace()

# 4. Run tests
pytest tests/admin/test_my_service.py -v -s

# 5. Check logs
tail -f ~/.asycuda_pro/logs/asycuda.log
```

### 3. Testing workflow

```bash
# 1. Write test
# tests/admin/test_my_service.py

# 2. Run test
pytest tests/admin/test_my_service.py -v

# 3. Check coverage
pytest tests/admin/ --cov=services/admin/my_service

# 4. Fix issues
# Edit kod

# 5. Re-run
pytest tests/admin/test_my_service.py -v
```

---

## 🎨 Styling Best Practices

### 1. Konzistentne boje

```css
/* Primary color */
#0078d4  /* Blue - za selected items */

/* Background colors */
#f5f5f5  /* Light gray - sidebar background */
#ffffff  /* White - panels background */

/* Border colors */
#ddd     /* Light gray - default borders */
#bbb     /* Medium gray - hover borders */

/* Text colors */
#000     /* Black - default text */
#999     /* Gray - disabled text */
```

### 2. Border radius

```css
/* Consistent border radius */
border-radius: 3px;  /* Small elements (items) */
border-radius: 4px;  /* Medium elements (panels, buttons) */
```

### 3. Spacing

```css
/* Consistent padding */
padding: 5px;   /* Tight spacing */
padding: 8px;   /* Normal spacing */
padding: 10px;  /* Loose spacing */

/* Consistent margins */
margin: 10px;   /* Between groups */
```

---

## 📝 Code Style Guide

### 1. Naming conventions

```python
# Classes: PascalCase
class PluginPanel(QWidget):
    pass

# Methods: snake_case
def get_installed_plugins(self):
    pass

# Private methods: _snake_case
def _on_install_clicked(self):
    pass

# Constants: UPPER_CASE
MAX_PLUGINS = 100

# Signals: snake_case
install_requested = Signal(str)
```

### 2. Docstrings

```python
def get_installed_plugins(self) -> List[Dict[str, Any]]:
    """
    Vrati listu instaliranih plugin-a.
    
    Returns:
        Lista dict-ova sa plugin info-m:
        [
            {
                'name': 'Parser Name',
                'priority': 20,
                ...
            }
        ]
    """
    pass
```

### 3. Type hints

```python
from typing import List, Dict, Any, Optional

def install_plugin(self, filepath: str) -> bool:
    pass

def get_settings(self) -> Dict[str, Any]:
    pass

def filter_logs(
    self,
    level: Optional[str] = None,
    search: Optional[str] = None
) -> List[Dict[str, Any]]:
    pass
```

---

**Verzija dokumentacije:** 1.0  
**Datum:** Mart 2026  
**Autor:** ASYCUDA Pro Development Team
