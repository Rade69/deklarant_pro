# Tab Refactor Pattern

## Problem

Veliki tab fajlovi (2500+ linija) koji kombinuju:

- **UI konstrukciju** (widgets, layouts)
- **Business logiku** (validacija, transformacije)
- **Database operacije** (queries, persistence)
- **Event handling** (signals, slots)
- **XML import/export**

Ovo čini kod:

- ❌ Težak za održavanje
- ❌ Nemoguće testirati
- ❌ Rizičan za refaktorisanje
- ❌ Spor za debuggiranje

### Primjer: ZaglavljeTab

```
gui/tabs/zaglavlje_tab.py
├── 2,545 linija koda
├── 59 metoda
├── 63 UI widgeta
├── 10 DB operacija
└── Najveća metoda: get_text (434 linije!)
```

---

## Rješenje: 3-Layer Pattern

### Pregled Arhitekture

```
┌─────────────────────────────────────────────────────────┐
│                    GUI Layer                            │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐         ┌─────────────────────────┐   │
│  │    View     │ ◄─────► │      Controller         │   │
│  │  (UI Only)  │         │   (Orchestration)       │   │
│  └─────────────┘         └─────────────────────────┘   │
│                           │                             │
│                           ▼                             │
│                    ┌─────────────┐                     │
│                    │   Service   │                     │
│                    │  (Business  │                     │
│                    │    Logic)   │                     │
│                    └─────────────┘                     │
│                           │                             │
└───────────────────────────┼─────────────────────────────┘
                            ▼
                    ┌─────────────┐
                    │  Database   │
                    │  /  XML     │
                    └─────────────┘
```

---

### LAYER 1: View (UI)

**Lokacija:** `gui/tabs/{tab_name}_view.py`

**Odgovornost:**

- ✅ Samo konstrukcija widgeta
- ✅ Layout management
- ✅ Signal/slot konekcije
- ❌ Nikakva business logika
- ❌ Nikakve database operacije

**Primjer:**

```python
class ZaglavljeView(QWidget):
    """
    View layer za Zaglavlje tab.
    Samo UI konstrukcija i signal emission.
    """
    
    # Signali za controller
    save_requested = Signal()
    load_requested = Signal(str)
    clear_requested = Signal()
    
    def __init__(self):
        super().__init__()
        
        # Kreiranje widgeta
        self.broj_deklaracije = QLineEdit()
        self.datum = QDateEdit()
        self.save_btn = QPushButton("Sačuvaj")
        
        # Layout
        self._setup_ui()
        
        # Konekcije (samo signali, bez logike)
        self.save_btn.clicked.connect(self.save_requested.emit)
    
    def _setup_ui(self):
        """Konstruiši UI layout."""
        layout = QVBoxLayout()
        layout.addWidget(self.broj_deklaracije)
        layout.addWidget(self.datum)
        layout.addWidget(self.save_btn)
        self.setLayout(layout)
    
    def get_data(self) -> dict:
        """Ekstraktuj podatke iz widgeta."""
        return {
            'broj_deklaracije': self.broj_deklaracije.text(),
            'datum': self.datum.date().toPyDate(),
        }
    
    def set_data(self, data: dict):
        """Popuni widgete podacima."""
        self.broj_deklaracije.setText(data.get('broj_deklaracije', ''))
        self.datum.setDate(QDate.fromPyDate(data.get('datum')))
    
    def show_success(self, message: str):
        """Prikaži success poruku."""
        QMessageBox.information(self, "Uspjeh", message)
    
    def show_error(self, message: str):
        """Prikaži error poruku."""
        QMessageBox.critical(self, "Greška", message)
```

---

### LAYER 2: Controller (Coordinator)

**Lokacija:** `gui/tabs/{tab_name}_controller.py`

**Odgovornost:**

- ✅ Orkestracija između View i Service
- ✅ Event handling
- ✅ Progress tracking
- ✅ Error display
- ❌ Nikakva business logika
- ❌ Nikakve database operacije

**Primjer:**

```python
class ZaglavljeController:
    """
    Controller layer za Zaglavlje tab.
    Orkestracija između View i Service.
    """
    
    def __init__(self, view: ZaglavljeView, service: ZaglavljeService):
        self.view = view
        self.service = service
        
        # Connect signals
        view.save_requested.connect(self._on_save)
        view.load_requested.connect(self._on_load)
        view.clear_requested.connect(self._on_clear)
    
    def _on_save(self):
        """Handle save event."""
        try:
            # Get data from view
            data = self.view.get_data()
            
            # Validate and save via service
            self.service.save_zaglavlje(data)
            
            # Show success
            self.view.show_success("Zaglavlje sačuvano!")
            
        except ValidationError as e:
            # Show validation error
            self.view.show_error(f"Validacija: {e}")
            
        except Exception as e:
            # Show unexpected error
            self.view.show_error(f"Neočekivana greška: {e}")
            logger.exception("Save failed")
    
    def _on_load(self, filename: str):
        """Handle load event."""
        try:
            data = self.service.load_from_xml(filename)
            self.view.set_data(data)
            self.view.show_success("Učitano uspješno!")
            
        except Exception as e:
            self.view.show_error(f"Greška pri učitavanju: {e}")
    
    def _on_clear(self):
        """Handle clear event."""
        self.view.set_data({})  # Clear all fields
```

---

### LAYER 3: Service (Business Logic)

**Lokacija:** `services/{tab_name}_service.py`

**Odgovornost:**

- ✅ Business logika
- ✅ Validacija
- ✅ Database operacije
- ✅ XML import/export
- ✅ Data transformacije
- ✅ Potpuno nezavisan od Qt (bez QWidget, Signal, itd.)

**Primjer:**

```python
class ZaglavljeService:
    """
    Service layer za Zaglavlje tab.
    Business logika bez Qt zavisnosti.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def save_zaglavlje(self, data: dict) -> bool:
        """
        Sačuvaj zaglavlje u bazu.
        
        Args:
            data: Podaci zaglavlja
        
        Returns:
            True ako je uspješno
        
        Raises:
            ValidationError: Ako podaci nisu validni
        """
        # 1. Validacija
        self._validate(data)
        
        # 2. Database operacije
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO zaglavlje (broj, datum, ...)
                    VALUES (%s, %s, ...)
                    ON CONFLICT (broj) DO UPDATE SET ...
                """, (
                    data['broj_deklaracije'],
                    data['datum'],
                    ...
                ))
        
        self.logger.info(f"Zaglavlje sačuvano: {data['broj_deklaracije']}")
        return True
    
    def load_from_xml(self, filename: str) -> dict:
        """
        Učitaj zaglavlje iz XML fajla.
        
        Args:
            filename: Putanja do XML fajla
        
        Returns:
            Dictionary sa podacima zaglavlja
        """
        tree = ET.parse(filename)
        root = tree.getroot()
        
        # Extract data from XML
        return {
            'broj_deklaracije': self._get_text(root, './/Broj'),
            'datum': self._get_date(root, './/Datum'),
            ...
        }
    
    def _validate(self, data: dict):
        """
        Validiraj podatke zaglavlja.
        
        Raises:
            ValidationError: Ako validacija ne prođe
        """
        if not data.get('broj_deklaracije'):
            raise ValidationError("Broj deklaracije je obavezan")
        
        if not data.get('datum'):
            raise ValidationError("Datum je obavezan")
        
        # Add more validation rules...
    
    def _get_text(self, element, tag):
        """Helper za XML parsing."""
        elem = element.find(tag)
        return elem.text if elem is not None else ""
```

---

## Refaktor Proces

### Faza 1: Extract Service Layer

**Cilj:** Izdvojiti business logiku iz tab klase.

**Koraci:**

1. Identifikuj business metode u tab klasi
   - Validacija
   - Database queries
   - XML parsing
   - Data transformacije

2. Kreiraj service klasu
   - `services/zaglavlje_service.py`
   - Kopiraj business metode
   - Ukloni Qt zavisnosti

3. Testiraj izolovano
   - Unit testovi za service
   - Bez GUI zavisnosti

**Primjer:**

```python
# Prije (u tab klasi):
class ZaglavljeTab(QWidget):
    def _save_to_database(self):
        # DB logic here...
        pass

# Poslije:
class ZaglavljeService:
    def save_zaglavlje(self, data: dict):
        # DB logic here...
        pass
```

---

### Faza 2: Create View Layer

**Cilj:** Izdvojiti UI konstrukciju.

**Koraci:**

1. Kreiraj view klasu
   - `gui/tabs/zaglavlje_view.py`
   - Ekstraktuj widget kreiranje
   - Ekstraktuj layout kod

2. Dodaj signale za events
   - `save_requested`
   - `load_requested`
   - `clear_requested`

3. Dodaj interfejse
   - `get_data()` → dict
   - `set_data(data: dict)` → None
   - `show_success(message: str)` → None
   - `show_error(message: str)` → None

**Primjer:**

```python
# Prije (u tab klasi):
class ZaglavljeTab(QWidget):
    def __init__(self):
        self.broj_deklaracije = QLineEdit()
        self.save_btn = QPushButton()
        self.save_btn.clicked.connect(self._on_save)  # Direct handler

# Poslije:
class ZaglavljeView(QWidget):
    save_requested = Signal()
    
    def __init__(self):
        self.broj_deklaracije = QLineEdit()
        self.save_btn = QPushButton()
        self.save_btn.clicked.connect(self.save_requested.emit)  # Signal only
```

---

### Faza 3: Create Controller

**Cilj:** Kreirati coordinator layer.

**Koraci:**

1. Kreiraj controller klasu
   - `gui/tabs/zaglavlje_controller.py`
   - Injektuj view i service

2. Poveži signale
   - View signals → Controller methods
   - Controller → Service calls

3. Implementiraj error handling
   - Try/catch blokovi
   - Error display na view

**Primjer:**

```python
class ZaglavljeController:
    def __init__(self, view: ZaglavljeView, service: ZaglavljeService):
        self.view = view
        self.service = service
        view.save_requested.connect(self._on_save)
    
    def _on_save(self):
        try:
            data = self.view.get_data()
            self.service.save_zaglavlje(data)
            self.view.show_success("Sačuvano!")
        except Exception as e:
            self.view.show_error(str(e))
```

---

### Faza 4: Integration

**Cilj:** Povezati sve layer-e.

**Koraci:**

1. Ažuriraj main tab klasu
   - Kreiraj view, controller, service
   - Dodaj view u layout

2. Integration testovi
   - Testiraj komunikaciju između layer-a
   - Verify existing functionality

3. Cleanup
   - Ukloni duplicirani kod
   - Refaktoriši preostale metode

**Primjer:**

```python
# Finalni main tab
class ZaglavljeTab(QWidget):
    def __init__(self, draft, on_dirty):
        super().__init__()
        
        # Create layers
        self.view = ZaglavljeView()
        self.service = ZaglavljeService()
        self.controller = ZaglavljeController(self.view, self.service)
        
        # Add view to layout
        layout = QVBoxLayout()
        layout.addWidget(self.view)
        self.setLayout(layout)
```

---

## Testing Strategy

### Service Layer (Unit Tests)

**Lokacija:** `tests/unit/services/test_zaglavlje_service.py`

```python
import pytest
from services.zaglavlje_service import ZaglavljeService
from services.exceptions import ValidationError

class TestZaglavljeService:
    
    @pytest.fixture
    def service(self):
        return ZaglavljeService()
    
    def test_validation_empty_broj(self, service):
        """Test da prazan broj deklaracije baca ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            service.save_zaglavlje({"broj_deklaracije": ""})
        
        assert "obavezan" in str(exc_info.value)
    
    def test_validation_missing_datum(self, service):
        """Test da nedostajući datum baca ValidationError."""
        with pytest.raises(ValidationError):
            service.save_zaglavlje({"broj_deklaracije": "123"})
    
    def test_save_valid_data(self, service, mock_db):
        """Test čuvanja validnih podataka."""
        data = {
            "broj_deklaracije": "123",
            "datum": datetime.now(),
        }
        
        result = service.save_zaglavlje(data)
        
        assert result is True
        assert mock_db.insert_called()
```

---

### View Layer (Mock Tests)

**Lokacija:** `tests/unit/gui/test_zaglavlje_view.py`

```python
import pytest
from PySide6.QtWidgets import QApplication
from gui.tabs.zaglavlje_view import ZaglavljeView

class TestZaglavljeView:
    
    @pytest.fixture
    def view(self, qtbot):
        v = ZaglavljeView()
        qtbot.addWidget(v)
        return v
    
    def test_view_emits_save_signal(self, view, qtbot):
        """Test da klik na save button emituje signal."""
        with qtbot.waitSignal(view.save_requested, timeout=1000):
            view.save_btn.click()
    
    def test_get_data_returns_dict(self, view):
        """Test da get_data vraća dictionary."""
        view.broj_deklaracije.setText("123")
        
        data = view.get_data()
        
        assert isinstance(data, dict)
        assert data['broj_deklaracije'] == "123"
    
    def test_set_data_populates_widgets(self, view):
        """Test da set_data popunjava widgete."""
        data = {'broj_deklaracije': '456'}
        
        view.set_data(data)
        
        assert view.broj_deklaracije.text() == "456"
```

---

### Controller Layer (Integration Tests)

**Lokacija:** `tests/integration/test_zaglavlje_controller.py`

```python
import pytest
from unittest.mock import Mock, MagicMock
from gui.tabs.zaglavlje_controller import ZaglavljeController

class TestZaglavljeController:
    
    @pytest.fixture
    def mock_view(self):
        return Mock()
    
    @pytest.fixture
    def mock_service(self):
        return Mock()
    
    @pytest.fixture
    def controller(self, mock_view, mock_service):
        return ZaglavljeController(mock_view, mock_service)
    
    def test_controller_calls_service_on_save(self, controller, mock_view, mock_service):
        """Test da controller poziva service na save."""
        mock_view.get_data.return_value = {'broj': '123'}
        
        controller._on_save()
        
        assert mock_service.save_zaglavlje.called
        assert mock_view.show_success.called
    
    def test_controller_shows_error_on_validation_failure(
        self, controller, mock_view, mock_service
    ):
        """Test da controller prikazuje error pri validaciji."""
        from services.exceptions import ValidationError
        mock_service.save_zaglavlje.side_effect = ValidationError("Invalid")
        
        controller._on_save()
        
        assert mock_view.show_error.called
        assert "Validacija" in str(mock_view.show_error.call_args)
    
    def test_controller_shows_error_on_exception(
        self, controller, mock_view, mock_service
    ):
        """Test da controller prikazuje error pri neočekivanoj grešci."""
        mock_service.save_zaglavlje.side_effect = Exception("Unexpected")
        
        controller._on_save()
        
        assert mock_view.show_error.called
```

---

## Benefits

### ✅ Maintainability

| Prije | Poslije |
|-------|---------|
| 1 fajl: 2,545 linija | 3 fajla: ~500 linija svaki |
| Teško naći bug | Jasna odgovornost po layer-u |
| Promjena riskantna | Izolovane promjene |

### ✅ Testability

| Prije | Poslije |
|-------|---------|
| Nemoguće testirati bez GUI | Service testable bez GUI |
| Mockovanje cijelog taba | Mockovanje pojedinačnih layer-a |
| Niska coverage | Visoka coverage moguća |

### ✅ Reusability

| Prije | Poslije |
|-------|---------|
| Service vezan za GUI | Service reusable |
| Ne može se koristiti van taba | Service usable iz CLI, API, itd. |

### ✅ Type Safety

```python
# Jasni interfejsi između layer-a
class ZaglavljeView:
    def get_data(self) -> dict: ...
    def set_data(self, data: dict) -> None: ...

class ZaglavljeService:
    def save_zaglavlje(self, data: dict) -> bool: ...
    def load_from_xml(self, filename: str) -> dict: ...
```

### ✅ Debugging

```
Data flow je jasan:

User Click → View Signal → Controller → Service → Database
                ↑                              ↓
                └────── Error Display ─────────┘
```

---

## Example Folder Structure

```
gui/tabs/
├── zaglavlje_tab.py          # Main tab (sada tanak wrapper)
├── zaglavlje_view.py         # UI layer (novi fajl)
└── zaglavlje_controller.py   # Controller layer (novi fajl)

services/
└── zaglavlje_service.py      # Service layer (novi fajl)

tests/
├── unit/
│   ├── services/
│   │   └── test_zaglavlje_service.py
│   └── gui/
│       └── test_zaglavlje_view.py
└── integration/
    └── test_zaglavlje_controller.py
```

---

## Migration Checklist

### Prije Refaktora

- [ ] Napravi backup trenutnog koda
- [ ] Kreiraj testove za existing functionality
- [ ] Dokumentuj sve public metode

### Tokom Refaktora

- [ ] Faza 1: Extract Service Layer
- [ ] Faza 2: Create View Layer
- [ ] Faza 3: Create Controller
- [ ] Faza 4: Integration

### Nakon Refaktora

- [ ] Pokreni sve postojeće testove
- [ ] Dodaj nove unit testove
- [ ] Dodaj integration testove
- [ ] Ažuriraj dokumentaciju
- [ ] Obriši backup (ako je sve OK)

---

## Common Pitfalls

### ❌ Anti-Pattern: Service sa Qt zavisnostima

```python
# LOŠE: Service zavisi od Qt
class ZaglavljeService:
    def save(self, data: dict):
        QMessageBox.information(None, "Info", "Saved")  # ❌ Qt u service!
```

```python
# DOBRO: Service je pure Python
class ZaglavljeService:
    def save(self, data: dict) -> bool:
        return True  # ✅ Bez Qt zavisnosti
    
# Controller handle-uje UI
class ZaglavljeController:
    def _on_save(self):
        if self.service.save(data):
            self.view.show_success("Saved")  # ✅ UI u view/controller
```

### ❌ Anti-Pattern: View sa business logikom

```python
# LOŠE: View radi validaciju
class ZaglavljeView:
    def get_data(self):
        broj = self.broj.text()
        if not broj:  # ❌ Validacija u view!
            raise ValueError("Required")
        return {'broj': broj}
```

```python
# DOBRO: Service radi validaciju
class ZaglavljeView:
    def get_data(self):
        return {'broj': self.broj.text()}  # ✅ Samo ekstrakcija

class ZaglavljeService:
    def save(self, data: dict):
        if not data.get('broj'):  # ✅ Validacija u service
            raise ValidationError("Required")
```

### ❌ Anti-Pattern: Controller sa previše logike

```python
# LOŠE: Controller radi transformacije
class ZaglavljeController:
    def _on_save(self):
        data = self.view.get_data()
        # ❌ Business logika u controller!
        data['broj'] = data['broj'].strip().upper()
        data['datum'] = parse_date(data['datum'])
        self.service.save(data)
```

```python
# DOBRO: Service radi transformacije
class ZaglavljeController:
    def _on_save(self):
        data = self.view.get_data()  # ✅ Samo koordinacija
        self.service.save(data)  # ✅ Service radi sve

class ZaglavljeService:
    def save(self, data: dict):
        # ✅ Transformacije ovdje
        data['broj'] = data['broj'].strip().upper()
```

---

## Next Steps

1. **ZaglavljeTab refaktor** - Prvi kandidat (2,545 linija)
2. **FakturaTab refaktor** - Slijedeći (3,000+ linija)
3. **NaimenovanjaTab refaktor** - Već djelimično refaktorisan
4. **Pattern dokumentacija** - Ovo što čitaš!

---

## Resources

- [Martin Fowler - Presentation Model](https://martinfowler.com/eaaDev/PresentationModel.html)
- [Martin Fowler - Model-View-Presenter](https://martinfowler.com/eaaDev/Supersede.html)
- [PySide6 Best Practices](https://doc.qt.io/qtforpython-6/)
- [Clean Architecture by Robert C. Martin](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
