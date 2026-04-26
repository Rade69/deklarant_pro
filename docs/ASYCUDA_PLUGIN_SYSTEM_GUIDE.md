# ASYCUDA PRO - PLUGIN SISTEM ZA NOVE PARSERE

**Kako dodati nove parsere u instaliranu aplikaciju BEZ reinstalacije**

---

## PROBLEM

**Scenarij:**
- Deklarant Pro instalirana kod klijenta (Windows .exe)
- Nova firma sa specifičnim formatom fakture
- Treba dodati parser za tu fakturu
- **CILJ:** Update bez reinstalacije cijele aplikacije!

---

## RJEŠENJE: 3 OPCIJE

---

## OPCIJA A: PLUGIN FOLDER SYSTEM ⭐ PREPORUČENO

### Koncept
```
deklarant_pro.exe (instalirana aplikacija)
    ↓
C:/Program Files/Deklarant Pro/
    ├── deklarant_pro.exe
    ├── plugins/                    ← Plugin folder
    │   ├── parsers/                ← Parseri
    │   │   ├── firma_abc_parser.py
    │   │   ├── firma_xyz_parser.py
    │   │   └── nova_firma.py       ← DODAŠ OVDJE!
    │   └── __init__.py
    └── config/
        └── parser_config.json      ← Opciono: config
```

### Kako radi?
1. **Klijent dobije NOVI parser fajl** (email, USB, download)
2. **Kopiraj u plugins/parsers/ folder**
3. **Restart aplikacije** - automatski učita novi parser!
4. **Done!** ✅

---

### IMPLEMENTACIJA

#### 1. Kreiraj Plugin Infrastrukturu

**Lokacija:** `importers/plugin_loader.py`

```python
"""
Plugin Loader - Dinamičko učitavanje parsera iz plugins/ foldera.
"""
import os
import sys
import importlib.util
from pathlib import Path
from typing import List, Type
from importers.base_strategy import ImportStrategy

class PluginLoader:
    """Učitava parsere iz plugins/parsers/ foldera."""
    
    def __init__(self):
        # Plugins folder - LOKALNI ili INSTALLATION
        self.plugins_dir = self._get_plugins_directory()
        self.parsers_dir = self.plugins_dir / "parsers"
        
        # Kreiraj ako ne postoji
        self.parsers_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"📂 Plugins directory: {self.plugins_dir}")
    
    def _get_plugins_directory(self) -> Path:
        """
        Odredi plugins directory - različito za development i production.
        
        Development: {project_root}/plugins/
        Production: {exe_location}/plugins/
        """
        if getattr(sys, 'frozen', False):
            # PRODUCTION - PyInstaller .exe
            # Plugins folder pored .exe fajla
            exe_dir = Path(sys.executable).parent
            return exe_dir / "plugins"
        else:
            # DEVELOPMENT - Python runtime
            # Plugins folder u projektu
            project_root = Path(__file__).parent.parent
            return project_root / "plugins"
    
    def discover_parsers(self) -> List[Type[ImportStrategy]]:
        """
        Pronađi sve parsere u plugins/parsers/ folderu.
        
        Returns:
            Lista ImportStrategy klasa
        """
        parsers = []
        
        if not self.parsers_dir.exists():
            print(f"⚠️  Parsers directory ne postoji: {self.parsers_dir}")
            return parsers
        
        # Pretraži sve .py fajlove
        for filepath in self.parsers_dir.glob("*.py"):
            if filepath.name.startswith("_"):
                continue  # Skip __init__.py i slično
            
            try:
                parser_class = self._load_parser_from_file(filepath)
                if parser_class:
                    parsers.append(parser_class)
                    print(f"✅ Loaded parser: {parser_class.__name__} from {filepath.name}")
            except Exception as e:
                print(f"❌ Failed to load {filepath.name}: {e}")
        
        return parsers
    
    def _load_parser_from_file(self, filepath: Path) -> Type[ImportStrategy]:
        """
        Dinamički učitaj parser iz Python fajla.
        
        Args:
            filepath: Put do .py fajla
            
        Returns:
            ImportStrategy klasa ili None
        """
        # Kreiraj module name
        module_name = f"plugins.parsers.{filepath.stem}"
        
        # Učitaj modul
        spec = importlib.util.spec_from_file_location(module_name, filepath)
        if spec is None or spec.loader is None:
            return None
        
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        
        # Pronađi ImportStrategy klasu u modulu
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            
            # Da li je klasa koja nasljeđuje ImportStrategy?
            if (isinstance(attr, type) and 
                issubclass(attr, ImportStrategy) and 
                attr is not ImportStrategy):
                return attr
        
        return None
    
    def install_plugin(self, source_path: Path) -> bool:
        """
        Instaliraj novi plugin parser.
        
        Args:
            source_path: Put do .py fajla parsera
            
        Returns:
            True ako uspješno, False ako ne
        """
        try:
            import shutil
            destination = self.parsers_dir / source_path.name
            
            shutil.copy2(source_path, destination)
            print(f"✅ Plugin instaliran: {destination}")
            return True
            
        except Exception as e:
            print(f"❌ Plugin instalacija failed: {e}")
            return False
```

---

#### 2. Integriraj sa Strategy Registry

**Lokacija:** `importers/strategy_registry.py` (AŽURIRAJ postojeći)

```python
from importers.plugin_loader import PluginLoader

class StrategyRegistry:
    """Registry sa plugin support."""
    
    def __init__(self):
        self._strategies = []
        self._plugin_loader = PluginLoader()
        
        # Učitaj built-in strategije
        self._load_builtin_strategies()
        
        # Učitaj plugin strategije
        self._load_plugin_strategies()
    
    def _load_builtin_strategies(self):
        """Učitaj ugrađene parsere (PDF, Excel, XML)."""
        from importers.strategies.pdf_strategy import PDFImportStrategy
        from importers.strategies.excel_strategy import ExcelImportStrategy
        from importers.strategies.xml_strategy import XMLImportStrategy
        
        self.register(PDFImportStrategy())
        self.register(ExcelImportStrategy())
        self.register(XMLImportStrategy())
    
    def _load_plugin_strategies(self):
        """Učitaj plugin parsere iz plugins/parsers/ foldera."""
        plugin_classes = self._plugin_loader.discover_parsers()
        
        for plugin_class in plugin_classes:
            try:
                instance = plugin_class()
                self.register(instance)
                print(f"✅ Registered plugin parser: {instance.strategy_name}")
            except Exception as e:
                print(f"❌ Failed to register {plugin_class.__name__}: {e}")
    
    def reload_plugins(self):
        """
        Reload svih plugin parsera.
        Korisno za hot-reload bez restarta aplikacije.
        """
        # Očisti trenutne plugin parsere
        self._strategies = [
            s for s in self._strategies 
            if not hasattr(s, '_is_plugin')
        ]
        
        # Ponovo učitaj
        self._load_plugin_strategies()
        print("🔄 Plugins reloaded!")
    
    # ... ostale metode (register, get_strategy, itd.)
```

---

#### 3. Kreiraj Template za Novi Parser

**Lokacija:** `plugins/parsers/_TEMPLATE_parser.py`

```python
"""
TEMPLATE ZA NOVI PARSER

Kopiraj ovaj fajl i preimenuj u: firma_naziv_parser.py

Zamijeni:
- FirmaNazivParser sa pravim imenom klase
- can_handle logiku sa specifičnim pravilima
- import_file logiku sa parsing logikom
"""

from importers.base_strategy import ImportStrategy
from typing import Dict, Any, List

class FirmaNazivParser(ImportStrategy):
    """
    Parser za faktore firme XYZ.
    
    Format: PDF/Excel sa specifičnom strukturom
    Kreirao: [Ime autora]
    Datum: [Datum kreiranja]
    """
    
    def __init__(self):
        super().__init__()
        self._is_plugin = True  # Označava da je plugin
    
    @property
    def strategy_name(self) -> str:
        """Jedinstveno ime parsera."""
        return "Firma XYZ Parser"
    
    @property
    def priority(self) -> int:
        """
        Prioritet (1-100).
        
        Viši broj = viši prioritet
        Built-in parseri: 10
        Plugin parseri: obično 20-30
        """
        return 20
    
    def can_handle(self, file_path: str) -> bool:
        """
        Provjeri da li ovaj parser može obraditi fajl.
        
        Primjeri:
        - PDF sa specifičnim tekstom u header-u
        - Excel sa određenim nazivom sheet-a
        - Naziv fajla sa određenim pattern-om
        
        Args:
            file_path: Put do fajla
            
        Returns:
            True ako može obraditi, False ako ne
        """
        # PRIMJER: PDF sa "FIRMA XYZ" u header-u
        if file_path.lower().endswith('.pdf'):
            # Brzo čitanje prva 3 reda PDF-a
            # (koristi pdfplumber ili PyPDF2)
            try:
                import pdfplumber
                with pdfplumber.open(file_path) as pdf:
                    first_page = pdf.pages[0]
                    text = first_page.extract_text()
                    
                    # Provjeri keywords
                    if "FIRMA XYZ" in text and "FAKTURA" in text:
                        return True
            except:
                pass
        
        # PRIMJER: Excel sa specifičnim sheet-om
        if file_path.lower().endswith(('.xlsx', '.xls')):
            try:
                import openpyxl
                wb = openpyxl.load_workbook(file_path)
                
                # Provjeri naziv sheet-a
                if "Faktura_XYZ" in wb.sheetnames:
                    return True
            except:
                pass
        
        return False
    
    def import_file(self, file_path: str) -> Dict[str, Any]:
        """
        Parsiraj fajl i vrati strukturirane podatke.
        
        Args:
            file_path: Put do fajla
            
        Returns:
            Dict sa parsiranim podacima:
            {
                'izvoznik': {...},
                'primalac': {...},
                'stavke': [...],
                'valuta': '...',
                'ukupno': 0.00,
                ...
            }
        """
        if file_path.endswith('.pdf'):
            return self._parse_pdf(file_path)
        elif file_path.endswith(('.xlsx', '.xls')):
            return self._parse_excel(file_path)
        else:
            raise ValueError(f"Nepodržan format: {file_path}")
    
    def _parse_pdf(self, file_path: str) -> Dict[str, Any]:
        """
        Parsiraj PDF fakturu.
        
        Implementiraj specifičnu logiku za PDF format ove firme.
        """
        import pdfplumber
        
        data = {
            'izvoznik': {},
            'primalac': {},
            'stavke': [],
            'valuta': 'EUR',
            'ukupno': 0.0
        }
        
        with pdfplumber.open(file_path) as pdf:
            # PRIMJER: Parsing logika
            first_page = pdf.pages[0]
            text = first_page.extract_text()
            lines = text.split('\n')
            
            # TODO: Implementiraj specifičnu logiku
            # Primjer: Pronađi izvoznika
            for i, line in enumerate(lines):
                if "Prodavac:" in line:
                    data['izvoznik']['naziv'] = lines[i + 1]
                    data['izvoznik']['adresa'] = lines[i + 2]
                    break
            
            # Primjer: Pronađi stavke (tabela)
            # ... (specifična logika za tabelu)
        
        return data
    
    def _parse_excel(self, file_path: str) -> Dict[str, Any]:
        """
        Parsiraj Excel fakturu.
        
        Implementiraj specifičnu logiku za Excel format ove firme.
        """
        import openpyxl
        
        data = {
            'izvoznik': {},
            'primalac': {},
            'stavke': [],
            'valuta': 'EUR',
            'ukupno': 0.0
        }
        
        wb = openpyxl.load_workbook(file_path)
        ws = wb.active  # ili wb['Faktura_XYZ']
        
        # TODO: Implementiraj specifičnu logiku
        # Primjer: Izvoznik u ćelijama A1-A3
        data['izvoznik']['naziv'] = ws['A1'].value
        data['izvoznik']['adresa'] = ws['A2'].value
        
        # Primjer: Stavke u tabeli od reda 10
        for row in ws.iter_rows(min_row=10, max_row=50):
            if row[0].value:  # Ako ima naziv artikla
                stavka = {
                    'naziv': row[0].value,
                    'kolicina': row[1].value,
                    'cijena': row[2].value,
                    'ukupno': row[3].value
                }
                data['stavke'].append(stavka)
        
        return data
```

---

#### 4. Admin UI za Plugin Management

**Opciono ali preporučeno:** GUI za instalaciju novih parsera

**Lokacija:** `gui/widgets/plugin_manager_dialog.py`

```python
"""
Plugin Manager Dialog - UI za instalaciju novih parsera.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QListWidget, QLabel, QFileDialog, QMessageBox
)
from importers.plugin_loader import PluginLoader
from importers.strategy_registry import get_registry

class PluginManagerDialog(QDialog):
    """Dialog za upravljanje plugin parserima."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Plugin Manager - Parseri")
        self.setMinimumSize(600, 400)
        
        self.plugin_loader = PluginLoader()
        self.setup_ui()
        self.load_plugins_list()
    
    def setup_ui(self):
        """Setup UI."""
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("Instalirani Plugin Parseri:")
        layout.addWidget(header)
        
        # Lista parsera
        self.plugins_list = QListWidget()
        layout.addWidget(self.plugins_list)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.btn_install = QPushButton("📥 Instaliraj Novi Parser")
        self.btn_install.clicked.connect(self.install_new_parser)
        btn_layout.addWidget(self.btn_install)
        
        self.btn_reload = QPushButton("🔄 Reload Parsera")
        self.btn_reload.clicked.connect(self.reload_parsers)
        btn_layout.addWidget(self.btn_reload)
        
        self.btn_close = QPushButton("Zatvori")
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)
        
        layout.addLayout(btn_layout)
    
    def load_plugins_list(self):
        """Učitaj listu instaliranih parsera."""
        self.plugins_list.clear()
        
        # Parseri folder
        parsers_dir = self.plugin_loader.parsers_dir
        
        if not parsers_dir.exists():
            self.plugins_list.addItem("(Nema instaliranih plugin parsera)")
            return
        
        # Lista .py fajlova
        parser_files = list(parsers_dir.glob("*.py"))
        parser_files = [f for f in parser_files if not f.name.startswith("_")]
        
        if not parser_files:
            self.plugins_list.addItem("(Nema instaliranih plugin parsera)")
            return
        
        for filepath in parser_files:
            self.plugins_list.addItem(f"✅ {filepath.name}")
    
    def install_new_parser(self):
        """Instaliraj novi parser."""
        # File dialog
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Odaberi Parser Fajl",
            "",
            "Python fajlovi (*.py)"
        )
        
        if not filepath:
            return
        
        from pathlib import Path
        source_path = Path(filepath)
        
        # Instalacija
        success = self.plugin_loader.install_plugin(source_path)
        
        if success:
            QMessageBox.information(
                self,
                "Uspjeh",
                f"Parser '{source_path.name}' je uspješno instaliran!\n\n"
                "Restartuj aplikaciju da bi se aktivirao."
            )
            self.load_plugins_list()
        else:
            QMessageBox.critical(
                self,
                "Greška",
                f"Instalacija parsera '{source_path.name}' nije uspjela!"
            )
    
    def reload_parsers(self):
        """Reload parsera bez restarta aplikacije."""
        try:
            registry = get_registry()
            registry.reload_plugins()
            
            QMessageBox.information(
                self,
                "Uspjeh",
                "Parseri su uspješno reload-ovani!"
            )
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Greška",
                f"Reload parsera nije uspio:\n{e}"
            )
```

**Dodaj u MainWindow:**

```python
# gui/main_window.py

def _create_menu_bar(self):
    """Kreiraj menu bar."""
    menubar = self.menuBar()
    
    # ... postojeći meniji
    
    # Admin menu
    admin_menu = menubar.addMenu("Admin")
    
    plugin_action = admin_menu.addAction("Plugin Manager...")
    plugin_action.triggered.connect(self._show_plugin_manager)

def _show_plugin_manager(self):
    """Prikaži plugin manager dialog."""
    from gui.widgets.plugin_manager_dialog import PluginManagerDialog
    
    dialog = PluginManagerDialog(self)
    dialog.exec()
```

---

### DEPLOYMENT PROCES

#### Za Development:
1. **Kreiraj novi parser** u `plugins/parsers/firma_xyz.py`
2. **Restart aplikacije** - automatski se učita
3. **Test** import funkcionalnosti

#### Za Production (Windows):

**A) PyInstaller Build sa Plugins Support:**

```python
# build_windows.spec

a = Analysis(
    ['__main__.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config', 'config'),
        ('plugins', 'plugins'),  # Dodaj plugins folder!
    ],
    hiddenimports=[],
    # ...
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ASYCUDA_Pro',
    # ...
)
```

**B) Instalacija novog parsera kod klijenta:**

**Opcija 1: Manualno**
```
1. Dobij novi parser fajl: nova_firma_parser.py
2. Kopiraj u: C:\Program Files\Deklarant Pro\plugins\parsers\
3. Restart aplikacije
4. Done!
```

**Opcija 2: Kroz GUI**
```
1. Otvori Deklarant Pro
2. Admin → Plugin Manager
3. Klikni "Instaliraj Novi Parser"
4. Odaberi .py fajl
5. Restart aplikacije
6. Done!
```

**Opcija 3: Auto-Update (naprednije)**
```
1. Parser upload na server
2. Aplikacija provjeri za update pri pokretanju
3. Download + install automatski
4. Restart aplikacije
5. Done!
```

---

## OPCIJA B: DATABASE-DRIVEN PARSERS

### Koncept
Umjesto Python kod-a, **konfiguriši parsere kroz bazu podataka**.

**Prednosti:**
- ✅ ZERO programiranje za nova polja
- ✅ Web admin panel
- ✅ Real-time update (bez restarta!)

**Mane:**
- ❌ Limitiran na jednostavne parse scenarije
- ❌ Kompleksna logika teška za izraziti

### Implementacija

**Database schema:**

```sql
CREATE TABLE parser_configs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE,
    firma_name VARCHAR(255),
    file_type VARCHAR(10),  -- 'pdf', 'excel', 'xml'
    priority INT DEFAULT 20,
    config JSON,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Primjer config JSON-a za Excel parser:
{
    "izvoznik": {
        "naziv": {"cell": "A1"},
        "adresa": {"cell": "A2"},
        "jib": {"cell": "A3"}
    },
    "primalac": {
        "naziv": {"cell": "B1"},
        "adresa": {"cell": "B2"}
    },
    "stavke": {
        "start_row": 10,
        "columns": {
            "naziv": "A",
            "kolicina": "B",
            "cijena": "C",
            "ukupno": "D"
        }
    }
}
```

**Parser koji čita iz baze:**

```python
class DatabaseConfiguredParser(ImportStrategy):
    """Parser koji se konfiguriše kroz bazu."""
    
    def __init__(self, config_id: int):
        self.config = self._load_config(config_id)
    
    def _load_config(self, config_id: int) -> dict:
        """Učitaj config iz baze."""
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT config FROM parser_configs WHERE id = %s",
                (config_id,)
            )
            result = cur.fetchone()
            return result['config'] if result else {}
    
    def can_handle(self, file_path: str) -> bool:
        """Provjeri da li može obraditi."""
        # Provjeri file_type iz config-a
        # ...
    
    def import_file(self, file_path: str) -> dict:
        """Parsiraj prema config-u."""
        if self.config.get('file_type') == 'excel':
            return self._parse_excel_by_config(file_path)
        # ...
```

**Web Admin Panel:**
- Flask/Django mini-app
- Form za kreiranje novog parser config-a
- Real-time preview
- Deploy na lokalnom serveru ili cloud

---

## OPCIJA C: AUTO-UPDATE SYSTEM

### Koncept
Aplikacija automatski provjeri i download-uje nove parsere sa central servera.

### Implementacija

**Server side:**
```
https://parsers.asycuda.com/
    ├── parsers/
    │   ├── manifest.json       ← Lista dostupnih parsera
    │   ├── firma_abc_v1.py
    │   ├── firma_xyz_v2.py
    │   └── ...
```

**manifest.json:**
```json
{
    "parsers": [
        {
            "name": "Firma ABC Parser",
            "filename": "firma_abc_v1.py",
            "version": "1.0",
            "hash": "sha256:...",
            "firma": "ABC d.o.o."
        },
        {
            "name": "Firma XYZ Parser",
            "filename": "firma_xyz_v2.py",
            "version": "2.0",
            "hash": "sha256:...",
            "firma": "XYZ d.o.o."
        }
    ]
}
```

**Client side (u aplikaciji):**

```python
class AutoUpdateManager:
    """Auto-update menadžer za parsere."""
    
    UPDATE_URL = "https://parsers.asycuda.com/manifest.json"
    
    def check_for_updates(self) -> List[dict]:
        """Provjeri za nove parsere."""
        import requests
        
        response = requests.get(self.UPDATE_URL, timeout=10)
        manifest = response.json()
        
        # Uporedi sa instaliranim parserima
        installed = self._get_installed_parsers()
        new_parsers = []
        
        for parser in manifest['parsers']:
            if parser['filename'] not in installed:
                new_parsers.append(parser)
        
        return new_parsers
    
    def download_parser(self, parser_info: dict) -> bool:
        """Download i instaliraj parser."""
        import requests
        
        url = f"https://parsers.asycuda.com/parsers/{parser_info['filename']}"
        
        response = requests.get(url, timeout=30)
        
        # Verify hash
        import hashlib
        content_hash = hashlib.sha256(response.content).hexdigest()
        
        if f"sha256:{content_hash}" != parser_info['hash']:
            raise ValueError("Hash mismatch! Corrupt download.")
        
        # Save to plugins folder
        plugin_loader = PluginLoader()
        filepath = plugin_loader.parsers_dir / parser_info['filename']
        
        filepath.write_bytes(response.content)
        return True
```

**UI za auto-update:**

```python
# Pri pokretanju aplikacije
def on_startup(self):
    """Check for updates pri pokretanju."""
    updater = AutoUpdateManager()
    
    try:
        new_parsers = updater.check_for_updates()
        
        if new_parsers:
            # Prikaži notifikaciju
            msg = f"Dostupno {len(new_parsers)} novih parsera!\n\n"
            msg += "\n".join([p['name'] for p in new_parsers])
            msg += "\n\nŽelite li ih instalirati?"
            
            reply = QMessageBox.question(
                self,
                "Novi Parseri Dostupni",
                msg,
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                for parser in new_parsers:
                    updater.download_parser(parser)
                
                QMessageBox.information(
                    self,
                    "Uspjeh",
                    "Parseri instalirani! Restartujte aplikaciju."
                )
    except:
        pass  # Tiho fail ako nema interneta
```

---

## POREĐENJE OPCIJA

| Feature | Plugin Folder | Database Config | Auto-Update |
|---------|--------------|----------------|-------------|
| **Setup kompleksnost** | 🟢 Niska | 🟡 Srednja | 🔴 Visoka |
| **Fleksibilnost** | 🟢 Potpuna | 🟡 Limitirana | 🟢 Potpuna |
| **Zero-code update** | 🟡 Polu | 🟢 Da | 🟢 Da |
| **Offline rad** | 🟢 Da | 🟢 Da | 🔴 Ne |
| **Sigurnost** | 🟡 Srednja | 🟢 Visoka | 🟡 Srednja |
| **Brzina deploy-a** | 🟢 Instant | 🟢 Instant | 🟡 Zavisi od servera |

---

## PREPORUKA: HYBRID PRISTUP

**Kombinuj Opciju A + C:**

1. **Plugin Folder System** (Opcija A) - osnovna infrastruktura
2. **Auto-Update** (Opcija C) - distribucija novih parsera
3. **Manualni install** - backup opcija ako nema interneta

**Workflow:**
```
1. Kreiraš novi parser (Python kod)
2. Upload na server
3. Klijent automatski download pri pokretanju
4. Ili manualno install iz .py fajla
5. Restart - parser aktivan!
```

---

## DEPLOYMENT CHECKLIST

Za svaki novi parser:

- [ ] Kreiraj parser fajl (koristi TEMPLATE)
- [ ] Testiraj lokalno (development)
- [ ] Dokumentuj format fakture (PDF/Excel specifičnosti)
- [ ] Testiraj sa realnim fakturama (min 5 različitih)
- [ ] Code review
- [ ] Version number (npr. firma_abc_v1.py → firma_abc_v2.py)
- [ ] Upload na server (ako koristiš auto-update)
- [ ] ili pošalji klijentu za manualni install
- [ ] Instrukcije za instalaciju
- [ ] Support - phone/email za pomoć

---

## PRIMJER: Dodavanje Parsera za Novu Firmu

**Scenarij:** Firma "Maxi d.o.o." ima Excel fakturu sa specifičnim formatom.

**Koraci:**

### 1. Analiziraj format fakture

```
Excel struktura:
- Sheet name: "Faktura"
- Izvoznik: A1-A4
- Primalac: B1-B4
- Stavke: Tabela od A10 do E50
- Ukupno: E51
```

### 2. Kreiraj parser

```python
# plugins/parsers/maxi_parser.py

from importers.base_strategy import ImportStrategy
import openpyxl

class MaxiParser(ImportStrategy):
    """Parser za Excel faktore firme Maxi d.o.o."""
    
    @property
    def strategy_name(self) -> str:
        return "Maxi d.o.o. Excel Parser"
    
    @property
    def priority(self) -> int:
        return 25
    
    def can_handle(self, file_path: str) -> bool:
        if not file_path.endswith(('.xlsx', '.xls')):
            return False
        
        try:
            wb = openpyxl.load_workbook(file_path)
            
            # Provjeri da li ima "Faktura" sheet
            if "Faktura" not in wb.sheetnames:
                return False
            
            ws = wb["Faktura"]
            
            # Provjeri specifičan marker
            if ws['A1'].value and "MAXI D.O.O." in str(ws['A1'].value).upper():
                return True
        except:
            pass
        
        return False
    
    def import_file(self, file_path: str) -> dict:
        wb = openpyxl.load_workbook(file_path)
        ws = wb["Faktura"]
        
        data = {
            'izvoznik': {
                'naziv': ws['A1'].value,
                'adresa': ws['A2'].value,
                'grad': ws['A3'].value,
                'jib': ws['A4'].value
            },
            'primalac': {
                'naziv': ws['B1'].value,
                'adresa': ws['B2'].value,
                'grad': ws['B3'].value,
                'jib': ws['B4'].value
            },
            'stavke': [],
            'valuta': 'BAM'
        }
        
        # Parsiraj stavke
        for row in range(10, 51):
            naziv = ws[f'A{row}'].value
            if not naziv:
                break  # Kraj tabele
            
            stavka = {
                'naziv': naziv,
                'kolicina': ws[f'B{row}'].value or 0,
                'jedinica': ws[f'C{row}'].value or 'kom',
                'cijena': ws[f'D{row}'].value or 0,
                'ukupno': ws[f'E{row}'].value or 0
            }
            data['stavke'].append(stavka)
        
        # Ukupno
        data['ukupno'] = ws['E51'].value or 0
        
        return data
```

### 3. Test lokalno

```python
python -c "
from plugins.parsers.maxi_parser import MaxiParser

parser = MaxiParser()

# Test
result = parser.import_file('test_files/maxi_faktura.xlsx')
print(result)
"
```

### 4. Deploy kod klijenta

**Opcija A - Manualno:**
- Email `maxi_parser.py` klijentu
- Instrukcije: Kopiraj u `C:\Program Files\Deklarant Pro\plugins\parsers\`
- Restart aplikacije

**Opcija B - Kroz GUI:**
- Email `maxi_parser.py` klijentu
- Otvori Deklarant Pro → Admin → Plugin Manager
- Klikni "Instaliraj Novi Parser"
- Odaberi `maxi_parser.py`
- Restart

**Opcija C - Auto-update:**
- Upload `maxi_parser.py` na server
- Update `manifest.json`
- Klijent automatski download-uje pri sljedećem pokretanju

### 5. Verifikacija

```
✅ Otvori Deklarant Pro
✅ Import faktura → Odaberi Maxi Excel fajl
✅ Provjeri da se podaci automatski popune
✅ Done!
```

---

## ZAKLJUČAK

**Za tvoj use case, PREPORUČUJEM:**

1. **Opcija A (Plugin Folder)** - jednostavno i pouzdano
2. **+ Admin UI** - korisničko-friendly instalacija
3. **+ Opciono Auto-Update** - ako imaš server

**Benefiti:**
- ✅ Zero reinstalacija aplikacije
- ✅ Brz deployment (minuti, ne dani)
- ✅ Klijent može sam instalirati
- ✅ Testiranje u production okruženju
- ✅ Rollback moguć (obriši .py fajl)

**Workflow:**
```
Novi klijent sa novom fakturom
    ↓
Analiziraš format (1-2 sata)
    ↓
Napišeš parser (2-4 sata)
    ↓
Testiraj lokalno (1 sat)
    ↓
Pošalješ .py fajl klijentu (email)
    ↓
Klijent instalira kroz GUI (2 minuta!)
    ↓
Restart aplikacije
    ↓
Done! ✅
```

**UKUPNO VRIJEME: 4-8 sati development → 2 minuta deployment!** 🚀
