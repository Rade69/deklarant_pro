# ASYCUDA PRO - KOMPLETNA REFAKTORISANJE APLIKACIJE

**MASTER PLAN ZA 3-LAYER ARHITEKTURU (VIEW/CONTROLLER/SERVICE)**

---

## 1. KONTEKST I TRENUTNO STANJE

### PROJEKAT: Deklarant Pro
- Python/PySide6 desktop aplikacija
- Upravljanje carinskim deklaracijama za BiH
- 34,180 linija koda, 120 fajlova
- 4 glavna taba (god objects):
  * **ZaglavljeTab**: 2,545 linija ✅ REFAKTORISAN
  * **FakturaTab**: ~3,000 linija ⏳ PENDING
  * **NaimenovanjaTab**: ~2,760 linija ⏳ PENDING
  * **SifarniciTab**: ~3,900 linija ⏳ PENDING

### PROBLEMI SA TRENUTNIM KODOM:
- ❌ God object anti-pattern (svi tabovi 2,500-4,000 linija)
- ❌ Business logika miješana sa UI kodom
- ❌ Teško testiranje (UI i logika spojeni)
- ❌ Nemogućnost reusability (sve zavisi od Qt)
- ❌ Hardcoded database credentials
- ❌ Spregnutost između importera (PDF/Excel/XML)

### ZAVRŠENO (Phases 0-3):
- ✅ Phase 0: Cleanup & Infrastructure
- ✅ Phase 1: Config & Security (centralizovan config, .env)
- ✅ Phase 2: Import Strategy Pattern (refaktorisan import sistem)
- ✅ Phase 3: ZaglavljeTab 100% refaktorisan (View/Controller/Service)

---

## 2. CILJ REFAKTORISANJA

### ARHITEKTONSKI CILJ:
Transformisati 4 god-object taba u čistu 3-layer arhitekturu:

```
[MainWindow]
    ↓
[Tab Wrapper] ← backward compatible API
    ↓
┌─────────────┬──────────────┬─────────────┐
│    VIEW     │  CONTROLLER  │   SERVICE   │
│  (UI Only)  │ (Orchestra)  │  (Logic)    │
└─────────────┴──────────────┴─────────────┘
```

### KVANTITATIVNI CILJEVI:
- **Redukcija koda**: ~35% (12,220 → ~8,000 linija)
- **Testabilnost**: 0% → 100% (Service layer potpuno testabilan)
- **Reusability**: Service layer Qt-independent
- **Maintainability**: 1 fajl 2,545 linija → 3 fajla ~800 linija svaki

---

## 3. ARHITEKTONSKI PATTERN - 3 LAYER SISTEM

### LAYER 1: VIEW (gui/tabs/X_view.py)

**ODGOVORNOST:**
- SAMO UI konstrukcija i prikaz
- Kreiranje widgeta (QLineEdit, QComboBox, QPushButton, itd.)
- Layout management (QVBoxLayout, QGridLayout, QFormLayout)
- Stilizacija i UI helpers

**ŠTA VIEW NE RADI:**
- ❌ Business logika
- ❌ Database pristup
- ❌ Validacija podataka
- ❌ Decision making
- ❌ File I/O

**JAVNI API:**
```python
class XView(QWidget):
    # Signali
    data_changed = Signal()
    save_requested = Signal()
    load_requested = Signal()
    
    def __init__(self, parent=None):
        # Kreiranje UI
        self._setup_ui()
    
    def get_data(self) -> Dict[str, Any]:
        """Prikupi podatke iz svih UI widgeta."""
        
    def set_data(self, data: Dict[str, Any]):
        """Popuni UI widgete sa podacima."""
        
    def clear_form(self):
        """Očisti sve UI widgete."""
        
    def show_error(self, message: str):
        """Prikaži error poruku korisniku."""
        
    def show_success(self, message: str):
        """Prikaži success poruku."""
        
    def show_warning(self, message: str):
        """Prikaži warning poruku."""
```

**PRIVATNE METODE (_create_* pattern):**
```python
def _create_izvoznik_group(self) -> QGroupBox:
    """Kreiranje UI grupe za izvoznika."""
    
def _create_valuta_group(self) -> QGroupBox:
    """Kreiranje UI grupe za valutu."""
    
# ... itd za sve UI sekcije
```

---

### LAYER 2: CONTROLLER (gui/tabs/X_controller.py)

**ODGOVORNOST:**
- Orchestration (koordinacija View ↔ Service)
- Event handling (button clicks, signal handling)
- User interaction flow
- Error handling i poruke korisniku
- Progress indicators

**ŠTA CONTROLLER NE RADI:**
- ❌ Direct UI manipulation (to radi View)
- ❌ Business logika (to radi Service)
- ❌ Database queries (to radi Service)

**JAVNI API:**
```python
class XController:
    def __init__(self, view: XView, service: XService):
        self.view = view
        self.service = service
        self._connect_signals()
    
    def load_data(self, draft: DeclarationDraft):
        """
        Orchestrate učitavanje podataka.
        1. Pozovi Service da konvertuje Draft → data dict
        2. Pozovi View da prikaže podatke
        3. Handle errors
        """
        
    def save_data(self) -> DeclarationDraft:
        """
        Orchestrate čuvanje podataka.
        1. Pozovi View da prikupi podatke
        2. Pozovi Service da validira i konvertuje
        3. Return Draft
        4. Handle errors
        """
        
    def handle_error(self, error: Exception, context: str):
        """Centralizovano error handling."""
        
    def handle_success(self, message: str):
        """Centralizovano success handling."""
```

**PRIVATNE METODE (_on_* pattern):**
```python
def _connect_signals(self):
    """Povezivanje View signala sa handler metodama."""
    
def _on_save_clicked(self):
    """Handler za Save button."""
    
def _on_search_company(self, company_type: str):
    """Handler za pretragu kompanije."""
```

---

### LAYER 3: SERVICE (services/X_service.py)

**ODGOVORNOST:**
- Business logika (validacija, kalkulacije, transformacije)
- Database pristup (CRUD operacije)
- Data conversion (Draft ↔ View data ↔ XML ↔ Database)
- File I/O operacije
- **POTPUNO Qt-independent!**

**ŠTA SERVICE NE RADI:**
- ❌ UI kreiranje
- ❌ User interaction
- ❌ Signal/Slot mehanizam

**JAVNI API:**
```python
class XService:
    def __init__(self):
        """Initialization bez Qt dependency."""
    
    def load_from_draft(self, draft: DeclarationDraft) -> Dict[str, Any]:
        """
        Konvertuj DeclarationDraft → View data format.
        
        Returns:
            Dict sa podacima spremnim za View.set_data()
        """
        
    def save_to_draft(self, draft: DeclarationDraft, 
                      data: Dict[str, Any]) -> DeclarationDraft:
        """
        Konvertuj View data → DeclarationDraft.
        
        Returns:
            Ažurirani Draft objekat
        """
        
    def validate_data(self, data: Dict[str, Any]) -> List[str]:
        """
        Validacija podataka.
        
        Returns:
            Lista error poruka (prazan ako nema errora)
        """
        
    def load_dropdown_data(self, dropdown_type: str) -> List[Dict]:
        """Učitaj podatke za dropdown iz baze."""
        
    def calculate_totals(self, items: List[Dict]) -> Dict[str, float]:
        """Kalkulacija totala (business logic)."""
```

**PRIVATNE HELPER METODE:**
```python
def _validate_required(self, value: Any, field_name: str) -> Optional[str]:
    """Helper za validaciju required polja."""
    
def _normalize_string(self, value: str) -> str:
    """Helper za normalizaciju stringova."""
    
def _log_operation(self, operation: str, success: bool):
    """Helper za logging."""
```

---

### WRAPPER PATTERN (gui/tabs/X_tab.py)

**ODGOVORNOST:**
- Backward compatibility sa postojećim kodom
- Adapter između starog API-ja i novih layer-a
- **MainWindow ne mijenja NI LINIJU koda!**

```python
class XTab(QWidget):
    """
    Wrapper - backward compatible API.
    MainWindow ne mijenja ni liniju koda!
    """
    
    data_changed = Signal()  # MainWindow očekuje ovaj signal
    
    def __init__(
        self,
        draft: Optional[DeclarationDraft] = None,
        on_dirty: Optional[Callable] = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        
        # STARI API - zadržan za backward compatibility
        self.draft = draft if draft else DeclarationDraft()
        self.on_dirty = on_dirty
        
        # NOVI LAYER-I - interno koriste
        self.service = XService()
        self.view = XView(parent=self)
        self.controller = XController(self.view, self.service)
        
        # Layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.view)
        
        # Signals
        self.view.data_changed.connect(self.data_changed.emit)
        self.view.data_changed.connect(self._on_dirty_triggered)
    
    def load_from_draft(self, draft):
        """STARI API - delegiraj novim layer-ima."""
        data = self.service.load_from_draft(draft)
        self.view.set_data(data)
    
    def save_to_draft(self):
        """STARI API - delegiraj novim layer-ima."""
        data = self.view.get_data()
        return self.service.save_to_draft(self.draft, data)
```

---

## 4. STEP-BY-STEP PROCEDURA ZA SVAKI TAB

### ZAGLAVLJE TAB ✅ ZAVRŠEN - Koristi kao TEMPLATE!

Za svaki preostali tab (Faktura, Naimenovanja, Šifrarnici):

---

### STEP 1: BACKUP & BRANCH

1. **Kreiraj feature branch:**
   ```bash
   git checkout -b refactor/X_tab
   ```

2. **Backup original:**
   ```bash
   cp gui/tabs/X_tab.py gui/tabs/X_tab_original.py
   git add gui/tabs/X_tab_original.py
   git commit -m "Backup original XTab before refactor"
   ```

3. **Kreiraj prazne fajlove:**
   ```bash
   touch gui/tabs/X_view.py
   touch gui/tabs/X_controller.py
   touch services/X_service.py
   ```

---

### STEP 2: SERVICE LAYER (Prvi!)

**Zašto prvi?** Jer je Qt-independent i najlakše testirati.

#### 2.1 ANALIZA ORIGINAL:
- Otvori `gui/tabs/X_tab_original.py`
- Identifikuj SVE metode koje rade business logiku
- Identifikuj SVE database queries
- Identifikuj SVE data transformacije

#### 2.2 KREIRANJE services/X_service.py:

```python
from typing import Dict, Any, List, Optional
from database.db import get_db_connection
from core.draft.draft import DeclarationDraft

class XService:
    """Service layer za X tab - Qt independent!"""
    
    def __init__(self):
        """Inicijalizacija bez Qt dependency."""
        pass
    
    # KRITIČNE METODE (OBAVEZNO!)
    def load_from_draft(self, draft: DeclarationDraft) -> Dict[str, Any]:
        """Draft → View data conversion."""
        data = {}
        # Mapiraj SVA polja iz draft-a
        data['field1'] = draft.field1
        data['field2'] = draft.field2
        # ... sve (40-50 polja tipično)
        return data
    
    def save_to_draft(self, draft: DeclarationDraft, 
                      data: Dict[str, Any]) -> DeclarationDraft:
        """View data → Draft conversion."""
        draft.field1 = data.get('field1', '')
        draft.field2 = data.get('field2', '')
        # ... sve polja
        return draft
    
    # DATABASE METODE
    def load_dropdown_X(self) -> List[Dict[str, Any]]:
        """Učitaj podatke za dropdown X iz baze."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT ...")
                    return cur.fetchall()
        except Exception as e:
            self._log_error("load_dropdown_X", e)
            return []
    
    # BUSINESS LOGIC METODE
    def validate_data(self, data: Dict[str, Any]) -> List[str]:
        """Validacija podataka."""
        errors = []
        # Validacija logika
        return errors
    
    def calculate_totals(self, items: List) -> Dict:
        """Kalkulacija totala."""
        # Business logic
        return {}
    
    # PRIVATE HELPERS
    def _log_operation(self, op: str, success: bool):
        """Logging helper."""
        print(f"{'✅' if success else '❌'} {op}")
    
    def _log_error(self, op: str, error: Exception):
        """Error logging."""
        print(f"❌ {op}: {error}")
```

#### 2.3 TESTIRANJE SERVICE:

```python
# tests/unit/test_X_service.py
import pytest
from services.X_service import XService
from core.draft.draft import DeclarationDraft

def test_load_from_draft():
    service = XService()
    draft = DeclarationDraft()
    draft.field1 = "TEST"
    
    data = service.load_from_draft(draft)
    
    assert data['field1'] == "TEST"

def test_save_to_draft():
    service = XService()
    draft = DeclarationDraft()
    data = {'field1': 'NEW'}
    
    updated = service.save_to_draft(draft, data)
    
    assert updated.field1 == "NEW"

# Run: pytest tests/unit/test_X_service.py -v
```

---

### STEP 3: VIEW LAYER

#### 3.1 ANALIZA ORIGINAL UI:
- Otvori `gui/tabs/X_tab_original.py`
- Identifikuj SVE UI grupe (_create_* metode)
- Dokumentuj TAČAN redoslijed grupa u UI
- Dokumentuj layout tip (QVBoxLayout, QGridLayout, QFormLayout)
- **Screenshot original UI kao referenca!**

#### 3.2 KREIRANJE gui/tabs/X_view.py:

```python
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QLineEdit, 
    QComboBox, QFormLayout, QPushButton
)
from PySide6.QtCore import Signal
from typing import Dict, Any
import qtawesome as qta

class XView(QWidget):
    """View layer - SAMO UI, BEZ logike!"""
    
    # Signali
    data_changed = Signal()
    save_requested = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.widgets = {}  # Dictionary svih widgeta
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup kompletan UI - TAČAN redoslijed kao original!"""
        main_layout = QVBoxLayout(self)
        
        # KRITIČNO: Isti redoslijed grupa kao u original!
        # (Kopiraj iz original __init__ metode)
        main_layout.addWidget(self._create_grupa1())
        main_layout.addWidget(self._create_hline())
        main_layout.addWidget(self._create_grupa2())
        # ... sve grupe
        
        main_layout.addStretch()
    
    # PUBLIC API
    def get_data(self) -> Dict[str, Any]:
        """Prikupi podatke iz UI."""
        return {
            'field1': self.widgets['field1'].text(),
            'field2': self.widgets['field2'].currentText(),
            # ... sve widgete
        }
    
    def set_data(self, data: Dict[str, Any]):
        """Popuni UI sa podacima."""
        self.widgets['field1'].setText(data.get('field1', ''))
        self.widgets['field2'].setCurrentText(data.get('field2', ''))
        # ... sve widgete
    
    def clear_form(self):
        """Očisti UI."""
        for widget in self.widgets.values():
            if isinstance(widget, QLineEdit):
                widget.clear()
            elif isinstance(widget, QComboBox):
                widget.setCurrentIndex(0)
    
    def show_error(self, msg: str):
        """Error message."""
        # QMessageBox ili status bar
        pass
    
    # PRIVATE UI CONSTRUCTION
    def _create_grupa1(self) -> QGroupBox:
        """Kreiranje UI grupe 1."""
        group = QGroupBox("Grupa 1")
        layout = QFormLayout()
        
        self.widgets['field1'] = QLineEdit()
        layout.addRow("Polje 1:", self.widgets['field1'])
        
        # Connect signal
        self.widgets['field1'].textChanged.connect(
            self.data_changed.emit
        )
        
        group.setLayout(layout)
        return group
    
    def _create_hline(self) -> QFrame:
        """Horizontal separator."""
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        return line
```

#### 3.3 TESTIRANJE VIEW:

```python
python -c "
from PySide6.QtWidgets import QApplication
from gui.tabs.X_view import XView
import sys

app = QApplication(sys.argv)
view = XView()

# Test get/set
data = {'field1': 'TEST'}
view.set_data(data)
result = view.get_data()

assert result['field1'] == 'TEST'
print('✅ View radi!')
"
```

---

### STEP 4: CONTROLLER LAYER

#### 4.1 KREIRANJE gui/tabs/X_controller.py:

```python
from typing import Optional
from gui.tabs.X_view import XView
from services.X_service import XService
from core.draft.draft import DeclarationDraft

class XController:
    """Controller - orchestration layer."""
    
    def __init__(self, view: XView, service: XService):
        self.view = view
        self.service = service
        self._connect_signals()
    
    def _connect_signals(self):
        """Povezivanje signala."""
        self.view.save_requested.connect(self._on_save)
        # ... ostali signali
    
    def load_data(self, draft: DeclarationDraft):
        """Orchestrate load."""
        try:
            data = self.service.load_from_draft(draft)
            self.view.set_data(data)
            self.handle_success("Podaci učitani")
        except Exception as e:
            self.handle_error(e, "load_data")
    
    def save_data(self) -> Optional[DeclarationDraft]:
        """Orchestrate save."""
        try:
            data = self.view.get_data()
            errors = self.service.validate_data(data)
            if errors:
                self.view.show_error("\n".join(errors))
                return None
            return self.service.save_to_draft(
                DeclarationDraft(), data
            )
        except Exception as e:
            self.handle_error(e, "save_data")
            return None
    
    def handle_error(self, error: Exception, context: str):
        """Central error handling."""
        msg = f"Greška ({context}): {str(error)}"
        self.view.show_error(msg)
    
    def handle_success(self, msg: str):
        """Success handling."""
        self.view.show_success(msg)
    
    # EVENT HANDLERS
    def _on_save(self):
        """Save button click."""
        self.save_data()
```

---

### STEP 5: WRAPPER (Backward Compatibility)

#### 5.1 KREIRAJ NOVI gui/tabs/X_tab.py:

```python
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Signal
from typing import Optional, Callable

from core.draft.draft import DeclarationDraft
from gui.tabs.X_view import XView
from gui.tabs.X_controller import XController
from services.X_service import XService

class XTab(QWidget):
    """
    Wrapper - backward compatible API.
    MainWindow ne mijenja ni liniju koda!
    """
    
    data_changed = Signal()
    
    def __init__(
        self,
        draft: Optional[DeclarationDraft] = None,
        on_dirty: Optional[Callable] = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        
        # STARI API
        self.draft = draft if draft else DeclarationDraft()
        self.on_dirty = on_dirty
        
        # NOVI LAYER-I
        self.service = XService()
        self.view = XView(parent=self)
        self.controller = XController(self.view, self.service)
        
        # UI
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        
        # SIGNALI
        self.view.data_changed.connect(self.data_changed.emit)
        self.view.data_changed.connect(self._on_dirty_triggered)
        
        # INITIAL LOAD
        if self.draft:
            self.load_from_draft(self.draft)
    
    # PUBLIC API (MainWindow poziva ove metode!)
    def load_from_draft(self, draft: DeclarationDraft):
        """STARI API - delegiraj Controller-u."""
        self.draft = draft
        self.controller.load_data(draft)
    
    def save_to_draft(self) -> DeclarationDraft:
        """STARI API - delegiraj Controller-u."""
        saved = self.controller.save_data()
        if saved:
            self.draft = saved
        return self.draft
    
    def clear_form(self):
        """STARI API - delegiraj View-u."""
        self.view.clear_form()
    
    def _on_dirty_triggered(self):
        """on_dirty callback."""
        if self.on_dirty:
            self.on_dirty()
```

---

### STEP 6: TESTING & INTEGRATION

#### 6.1 UNIT TESTOVI:
```bash
pytest tests/unit/test_X_service.py -v
pytest tests/unit/test_X_controller.py -v
```

#### 6.2 INTEGRATION TEST:
```python
python -c "
from PySide6.QtWidgets import QApplication
from gui.tabs.X_tab import XTab
from core.draft.draft import DeclarationDraft
import sys

app = QApplication(sys.argv)

# Test kao MainWindow koristi
draft = DeclarationDraft()
draft.field1 = 'TEST-123'

tab = XTab(draft=draft, on_dirty=lambda: print('DIRTY!'))
tab.show()

# Test load
tab.load_from_draft(draft)

# Test save
saved = tab.save_to_draft()
print(f'✅ Wrapper radi! {saved.field1}')
"
```

#### 6.3 APLIKACIJA TEST:
```bash
python __main__.py
```
- Otvori X tab
- Provjeri da UI izgleda IDENTIČNO originalu
- Testiraj load from draft
- Testiraj save to draft
- Testiraj cross-tab komunikaciju

---

### STEP 7: GIT COMMIT

```bash
git add gui/tabs/X_view.py
git add gui/tabs/X_controller.py
git add services/X_service.py
git add gui/tabs/X_tab.py
git add tests/unit/test_X_service.py
git commit -m "Phase X: Complete XTab refactor - 100% coverage

3-LAYER ARCHITECTURE:
✅ XService: Y methods, Z lines
✅ XView: A methods, B lines
✅ XController: C methods, D lines
✅ XTab wrapper: backward compatible

TESTING:
✅ Unit tests: N passing
✅ Integration: XTab ↔ MainWindow
✅ UI identical to original
✅ Full functionality preserved

METRICS:
- Original: X lines
- New: Y lines (-Z% reduction)
- Coverage: 100%
"
```

---

## 5. REDOSLIJED REFAKTORISANJA TABOVA

### PRIORITET 1: ZaglavljeTab ✅ ZAVRŠEN
**Status:** 100% complete, production ready  
**Template:** Koristi kao referenca za sve ostale tabove

---

### PRIORITET 2: FakturaTab (~3,000 linija)

**Zašto sljedeći:**
- Najkritičniji tab (import faktura, PDF/Excel parsing)
- Visoka kompleksnost
- Interakcija sa ZaglavljeTab (cross-tab communication)

**Specifičnosti:**
- PDF parsing logika → FakturaService
- Excel parsing logika → FakturaService
- Table view za stavke → FakturaView
- Complex calculations → FakturaService.calculate_totals()

---

### PRIORITET 3: NaimenovanjaTab (~2,760 linija)

**Zašto treći:**
- Srednja kompleksnost
- Interakcija sa FakturaTab i ZaglavljeTab
- Tariff classification logika

**Specifičnosti:**
- QTableView sa custom model → NaimenovanjaView
- Tariff search → NaimenovanjaService
- Origin statement detection → NaimenovanjaService

---

### PRIORITET 4: SifarniciTab (~3,900 linija)

**Zašto posljednji:**
- Najkompleksniji tab (najviše linija)
- Least changed (reference data)
- Ne blokira druge tabove

**Specifičnosti:**
- Multiple sub-tabs (valute, države, dokumenti, itd.)
- CRUD operacije → SifarniciService
- Admin funkcionalnost

---

## 6. TESTIRANJE STRATEGIJA

### Nivo 1: UNIT TESTS (Service Layer)

**Lokacija:** `tests/unit/test_X_service.py`

**Testirati:**
- `load_from_draft()` - 100% field coverage
- `save_to_draft()` - round-trip test
- `validate_data()` - sve validacione scenarije
- `calculate_*()` - sve kalkulacije
- Database loaders - mock database

**Cilj:** 100% coverage Service layer-a

---

### Nivo 2: INTEGRATION TESTS

**Lokacija:** `tests/integration/test_X_integration.py`

**Testirati:**
- View ↔ Controller komunikacija
- Controller ↔ Service komunikacija
- Signal propagation
- Error handling flow

---

### Nivo 3: END-TO-END TESTS

**Manualno testiranje:**
- Pokreni aplikaciju
- Test svakog taba
- Cross-tab komunikacija
- Full user workflow (import → edit → save → export)

---

### Nivo 4: REGRESSION TESTS

**Prije svakog commit-a:**
```bash
pytest tests/ -v
```
**Očekivano:** Svi testovi passing, 0 regressions

---

## 7. GIT WORKFLOW

### BRANCH STRATEGIJA:
```
main (production)
  ├── dev (development)
      ├── refactor/faktura_tab
      ├── refactor/naimenovanja_tab
      └── refactor/sifarnici_tab
```

### COMMIT CONVENTION:
```
"Phase X.Y: Component - Short description

DETAILED DESCRIPTION:
✅ What was done
✅ Metrics
✅ Testing results

FILES:
- file1.py (+X lines)
- file2.py (+Y lines)
"
```

### COMMIT FREQUENCY:
- Nakon svakog STEP-a ako ima smisla
- **OBAVEZNO** nakon završenog taba
- **OBAVEZNO** nakon svih testova passing

---

## 8. BACKUP & ROLLBACK STRATEGIJA

### PRIJE SVAKE IZMJENE:

1. **Backup original:**
   ```bash
   cp gui/tabs/X_tab.py gui/tabs/X_tab_original.py
   ```

2. **Git commit backup:**
   ```bash
   git add gui/tabs/X_tab_original.py
   git commit -m "Backup XTab before refactor"
   ```

3. **Feature branch:**
   ```bash
   git checkout -b refactor/X_tab
   ```

### ROLLBACK PROCEDURA (ako nešto krene loše):

1. **Vrati original:**
   ```bash
   mv gui/tabs/X_tab_original.py gui/tabs/X_tab.py
   ```

2. **Obriši nove fajlove:**
   ```bash
   rm gui/tabs/X_view.py
   rm gui/tabs/X_controller.py
   rm services/X_service.py
   ```

3. **Git reset:**
   ```bash
   git reset --hard HEAD~1
   ```

---

## 9. KRITIČNE LEKCIJE IZ ZAGLAVLJE TAB REFAKTORA

### LEKCIJA 1: UI LAYOUT MORA BITI IDENTIČAN

**Problem:** Prvi pokušaj imao samo 20% UI elemenata

**Rješenje:**
- Screenshot original UI PRIJE refaktora
- Dokumentuj TAČAN redoslijed grupa
- `View.__init__` MORA pozvati SVE `_create_*` metode
- Test UI vizuelno prije nego što nastaviš

---

### LEKCIJA 2: ICONS - KORISTI VALIDNE FontAwesome NAMES

**Problem:** `"document-new"` nije validan icon name

**Rješenje:**
- Koristi `"fa5s."` prefix (FontAwesome 5 Solid)
- **Validni:** `fa5s.plus-square`, `fa5s.save`, `fa5s.trash-alt`
- **NIKAD:** `"document-new"`, `"edit-delete"` (GTK icon names)

---

### LEKCIJA 3: SIGNALS - NE ZABORAVI data_changed

**Problem:** Wrapper nije emitovao `data_changed` signal

**Rješenje:**
- View MORA imati `data_changed = Signal()`
- View MORA emit-ovati nakon promjena
- Wrapper MORA forward-ovati signal ka MainWindow

---

### LEKCIJA 4: DRAFT CONVERSION - MAPIRAJ SVA POLJA

**Problem:** Nedostajala polja u load_from_draft/save_to_draft

**Rješenje:**
- Dokumentuj SVA polja u Draft objektu (40-50 polja)
- Mapiraj SVAKO polje u oba smjera (Draft ↔ View)
- Round-trip test da provjeriš

---

### LEKCIJA 5: TESTIRANJE NA SVAKOM KORAKU

**Problem:** Mnogo bugova otkriveno prekasno

**Rješenje:**
- Test Service SAMOSTALNO (unit tests)
- Test View SAMOSTALNO (`python -c "..."`)
- Test Controller SAMOSTALNO
- Test Wrapper SAMOSTALNO
- Test u aplikaciji END-TO-END

---

### LEKCIJA 6: JEDNA METODA = JEDAN TASK/PROMPT

**Problem:** Preveliki taskovi = konfuzija

**Rješenje:**
- Jedan prompt = jedna jasna radnja
- Izvještaj nakon svakog prompta
- Ne ići dalje dok prethodni korak nije 100%

---

## 10. CHECKLIST ZA SVAKI TAB

### PRE-REFACTOR CHECKLIST:
- [ ] Backup original tab (X_tab_original.py)
- [ ] Screenshot original UI
- [ ] Feature branch kreiran
- [ ] Testovi passing (baseline)

### SERVICE LAYER CHECKLIST:
- [ ] `load_from_draft()` implementiran (SVA polja!)
- [ ] `save_to_draft()` implementiran (SVA polja!)
- [ ] Round-trip test passing
- [ ] Database loaders implementirani
- [ ] Business logic metode implementirane
- [ ] Unit tests passing (100% coverage)

### VIEW LAYER CHECKLIST:
- [ ] SVE `_create_*` metode implementirane
- [ ] `__init__` poziva SVE `_create_*` metode
- [ ] `get_data()` vraća SVA polja
- [ ] `set_data()` popunjava SVA polja
- [ ] `clear_form()` čisti SVA polja
- [ ] UI IDENTIČAN originalu (vizuelna provjera!)
- [ ] Signali implementirani (data_changed, save_requested)
- [ ] Icons validni (fa5s.* names)

### CONTROLLER LAYER CHECKLIST:
- [ ] `load_data()` orchestration implementiran
- [ ] `save_data()` orchestration implementiran
- [ ] Error handling implementiran
- [ ] Event handlers implementirani (_on_*)
- [ ] Signals connected (_connect_signals)

### WRAPPER LAYER CHECKLIST:
- [ ] Stari API zadržan (__init__ signature)
- [ ] `load_from_draft()` delegira Controller-u
- [ ] `save_to_draft()` delegira Controller-u
- [ ] `data_changed` signal forward-ovan
- [ ] `on_dirty` callback pozvan

### TESTING CHECKLIST:
- [ ] Unit tests passing
- [ ] Integration tests passing
- [ ] Wrapper test passing (izolovano)
- [ ] Application test passing (end-to-end)
- [ ] Cross-tab communication test passing
- [ ] UI vizuelno identičan originalu
- [ ] Full test suite passing (0 regressions)

### GIT CHECKLIST:
- [ ] Changes committed
- [ ] Commit message detaljan
- [ ] Branch merged u dev (ako je sve OK)
- [ ] Tag kreiran (opciono)

---

## 11. OČEKIVANI REZULTATI - CIJELA APLIKACIJA

### PRIJE REFAKTORISANJA:
```
┌──────────────────────────────────────────┐
│ Component        Lines    Files  Status  │
├──────────────────────────────────────────┤
│ ZaglavljeTab     2,545    1      God obj │
│ FakturaTab       3,000    1      God obj │
│ NaimenovanjaTab  2,760    1      God obj │
│ SifarniciTab     3,900    1      God obj │
├──────────────────────────────────────────┤
│ TOTAL           12,205    4      Monolith│
└──────────────────────────────────────────┘
```

**Problemi:**
- ❌ Testabilnost: 0%
- ❌ Reusability: 0%
- ❌ Maintainability: Niska
- ❌ Code duplication: Visoka

---

### POSLIJE REFAKTORISANJA:
```
┌────────────────────────────────────────────────────────┐
│ Component        Service View  Ctrl  Wrap  Total Files│
├────────────────────────────────────────────────────────┤
│ ZaglavljeTab     783    1,052  474   218   2,527  4   │
│ FakturaTab       ~900   ~1,200 ~500  ~220  ~2,820 4   │
│ NaimenovanjaTab  ~800   ~1,000 ~450  ~210  ~2,460 4   │
│ SifarniciTab     ~1,100 ~1,400 ~600  ~250  ~3,350 4   │
├────────────────────────────────────────────────────────┤
│ TOTAL            3,583  4,652  2,024 898   11,157 16  │
└────────────────────────────────────────────────────────┘
```

**Poboljšanja:**
- ✅ Code reduction: -1,048 lines (-8.6%)
- ✅ Testabilitas: 100% (Service layers)
- ✅ Reusability: Service layers Qt-independent
- ✅ Maintainability: Visoka (mali fajlovi, jasna separacija)
- ✅ Files: 4 → 16 (bolja organizacija)

**KVALITATIVNA POBOLJŠANJA:**
- ✅ Separation of Concerns
- ✅ Single Responsibility Principle
- ✅ Dependency Injection
- ✅ Type Safety (type hints)
- ✅ Error Handling (centralizovano)
- ✅ Logging (konsistentno)
- ✅ Documentation (docstrings)

---

## 12. FINALNA INTEGRACIJA I DEPLOYMENT

Nakon što su SVI tabovi refaktorisani:

### INTEGRATION PHASE:
1. Testiraj full application workflow
2. User acceptance testing
3. Performance testing
4. Cross-tab komunikacija
5. Save/Load cycle testing

### DEPLOYMENT CHECKLIST:
- [ ] Svi testovi passing
- [ ] Documentation ažurirana
- [ ] Changelog kreiran
- [ ] Version bump (npr. 2.0.0)
- [ ] Production build
- [ ] Backup production database
- [ ] Deploy na staging
- [ ] Staging testing
- [ ] Deploy na production
- [ ] Post-deployment monitoring

---

## KRAJ MASTER PLANA

Ovaj plan je **KOMPLETNA roadmap** za refaktorisanje cijele Deklarant Pro aplikacije sa god-object monolita u čistu 3-layer arhitekturu.

**Koristi ZaglavljeTab kao TEMPLATE i ponovi proces za svaki tab!**

Prati **STEP-BY-STEP** proceduru i **CHECKLISTOVE** - uspjeh garantovan! 🏆
