# ZaglavljeTab Integration Analysis

## Executive Summary

Analiza kako se originalni `ZaglavljeTab` koristi u aplikaciji radi planiranja integracije novog 3-layer sistema.

---

## 1. GDJE SE KORISTI

### Fajl 1: `gui/main_window.py` (linija 53)

```python
# Inicijalizacija
self.zaglavlje_tab = ZaglavljeTab(self.draft, on_dirty=self._on_dirty)
tabs.addTab(self.zaglavlje_tab, "Zaglavlje")
```

### Fajl 2: `gui/tabs/faktura_tab_v2.py` (linija ~200)

```python
# Cross-tab komunikacija
if hasattr(main_window, "zaglavlje_tab"):
    main_window.zaglavlje_tab.load_from_draft(self.draft)
```

### Fajl 3: `gui/tabs/naimenovanja_tab.py`

- Samo reference u komentarima (poređenje UI pattern-a)

### Fajl 4: `ui/zaglavlje_tab_ui.py`

- Auto-generisani UI kod (ne koristi se direktno u runtime)

---

## 2. TRENUTNA INTEGRACIJA

### U `main_window.py`:

```python
class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        
        # 1. Kreiranje Draft objekta
        self.draft = DeclarationDraft()
        self.draft.ensure_min_items(1)
        
        # 2. Kreiranje tabova
        tabs = QTabWidget()
        self.setCentralWidget(tabs)
        
        # 3. ZaglavljeTab instanciranje
        self.zaglavlje_tab = ZaglavljeTab(
            self.draft,           # DeclarationDraft objekat
            on_dirty=self._on_dirty  # Callback za dirty flag
        )
        tabs.addTab(self.zaglavlje_tab, "Zaglavlje")
        
        # 4. Registracija callback-a za promjene u Draft-u
        self.draft.register_data_change_callback(self._on_draft_data_changed)
    
    def _on_draft_data_changed(self) -> None:
        """Kada se Draft promijeni, osvježi ZaglavljeTab."""
        self.zaglavlje_tab.load_from_draft(self.draft)
        self.zaglavlje_tab.update()
    
    def _on_dirty(self) -> None:
        """Kada se podaci promijene, označi prozor kao 'dirty'."""
        current_title = self.windowTitle()
        if not current_title.endswith("*"):
            self.setWindowTitle(current_title + " *")
```

---

## 3. __INIT__ SIGNATURE

### Originalni `ZaglavljeTab`:

```python
class ZaglavljeTab(QWidget):
    # Signals
    data_changed = Signal()
    
    def __init__(
        self,
        draft: Optional[DeclarationDraft] = None,
        on_dirty: Optional[Callable] = None
    ):
        super().__init__()
        self.draft = draft if draft else DeclarationDraft()
        self.on_dirty = on_dirty
        self.setObjectName("ZaglavljeTab")
        
        # Widget storage
        self.field_widgets = {}
        
        # UI setup
        self._setup_ui()
        self._apply_styles()
        self._connect_signals()
```

**Parametri:**
- `draft`: DeclarationDraft objekat (optional, default: kreira novi)
- `on_dirty`: Callback funkcija za dirty flag (optional)

---

## 4. DRAFT LIFECYCLE

### Kreiranje:
```python
# U main_window.py
self.draft = DeclarationDraft()
self.draft.ensure_min_items(1)
```

### Load (kada se podaci učitavaju):
```python
# 1. Kroz callback iz Draft-a
self.draft.register_data_change_callback(self._on_draft_data_changed)

def _on_draft_data_changed(self):
    self.zaglavlje_tab.load_from_draft(self.draft)

# 2. Iz drugog taba (FakturaTab)
main_window.zaglavlje_tab.load_from_draft(self.draft)
```

### Save (kada se podaci čuvaju):
```python
# U _on_snimi() metodi (linija ~2056)
def _on_snimi(self):
    # ... save dialog ...
    self.save_to_draft()  # Čuvanje UI podataka u Draft
    # ... nastavi sa čuvanjem ...
```

---

## 5. SIGNALS

### Emitovani signali iz `ZaglavljeTab`:

```python
# 1. data_changed - kada se podaci promijene
# Linije: 218, 1532, 2034, 2049
self.data_changed.emit()

# Korišćenje:
# - Nakon import-a XML-a
# - Nakon snimanja
# - Nakon brisanja
```

### Primljeni signali (kroz `on_dirty` callback):
```python
# Kada se podaci promijene, poziva se callback
if self.on_dirty:
    self.on_dirty()  # Postavi "*" u naslov prozora
```

---

## 6. KLJUČNE DEPENDENCIJE

### Database:
- **DA** - direktno u `_load_*_from_db()` funkcijama
- Način: `get_db_connection()` context manager
- Lokacije: 5 module-level funkcija (linije 60-140)

### Draft:
- **DA** - kroz `__init__` parametar
- Način: `self.draft = draft` (direct assignment)
- Korišćenje: `load_from_draft(draft)`, `save_to_draft()`

### Config:
- **NE** - hardcoded vrijednosti u kodu
- Nema reference na `config/settings.py`

---

## 7. INTEGRATION STRATEGY PREPORUKA

### Analiza opcija:

#### OPCIJA A: Wrapper pristup ⭐ **PREPORUČENO**

```python
# gui/tabs/zaglavlje_tab.py (stari fajl ostaje)
class ZaglavljeTab(QWidget):
    """Wrapper oko novih layer-a za backward compatibility."""
    
    def __init__(self, draft=None, on_dirty=None):
        super().__init__()
        
        # Kreiraj nove layer-e
        self.service = ZaglavljeService()
        self.view = ZaglavljeView()
        self.controller = ZaglavljeController(self.view, self.service)
        
        # Postavi view kao child widget
        layout = QVBoxLayout(self)
        layout.addWidget(self.view)
        
        # Zadrži stari API za kompatibilnost
        self.draft = draft
        self.on_dirty = on_dirty
        
        # Poveži signale
        self.view.data_changed.connect(self._on_data_changed)
    
    def load_from_draft(self, draft):
        """Delegiraj na novi service."""
        data = self.service.load_from_draft(draft)
        self.view.set_data(data)
    
    def save_to_draft(self):
        """Delegiraj na novi service."""
        data = self.view.get_data()
        self.service.save_to_draft(draft, data)
    
    def _on_data_changed(self):
        """Forward signal."""
        self.data_changed.emit()
        if self.on_dirty:
            self.on_dirty()
```

**Prednosti:**
- ✅ Zero breaking changes
- ✅ Main window code ostaje isti
- ✅ Postepena migracija moguća
- ✅ Rollback moguć ako treba

**Mane:**
- ⚠️ Jedan dodatni layer indirection
- ⚠️ Wrapper overhead (~50 linija koda)

---

#### OPCIJA B: Direct replacement

```python
# gui/main_window.py (promjena)
from gui.tabs.zaglavlje_view import ZaglavljeView
from gui.tabs.zaglavlje_controller import ZaglavljeController
from services.zaglavlje_service import ZaglavljeService

# U MainWindow.__init__():
self.zaglavlje_service = ZaglavljeService()
self.zaglavlje_view = ZaglavljeView()
self.zaglavlje_controller = ZaglavljeController(
    self.zaglavlje_view,
    self.zaglavlje_service
)

# Poveži draft
data = self.zaglavlje_service.load_from_draft(self.draft)
self.zaglavlje_view.set_data(data)

tabs.addTab(self.zaglavlje_view, "Zaglavlje")
```

**Prednosti:**
- ✅ Čist kod bez wrapper-a
- ✅ Puna prednost 3-layer arhitekture

**Mane:**
- ❌ Breaking change u main_window.py
- ❌ Zahtijeva promjenu na više mjesta
- ❌ Teži rollback

---

#### OPCIJA C: Parallel deployment

```python
# Zadrži oba sistema paralelno
USE_NEW_ZAGLAVLJE = True  # Feature flag

if USE_NEW_ZAGLAVLJE:
    # Novi sistem
    self.zaglavlje_view = ZaglavljeView()
    # ...
else:
    # Stari sistem
    self.zaglavlje_tab = ZaglavljeTab()
```

**Prednosti:**
- ✅ A/B testing moguć
- ✅ Postepena migracija

**Mane:**
- ⚠️ Duplicirani kod
- ⚠️ Kompleksniji maintenance

---

## 8. PREPORUČENA INTEGRACIJA

### **OPCIJA A: Wrapper pristup** ⭐

**Razlozi:**
1. ✅ **Zero breaking changes** - main_window.py ostaje isti
2. ✅ **Safe migration** - može se rollback-ovati lako
3. ✅ **Incremental** - može se testirati postepeno
4. ✅ **Clean API** - stari interfejs ostaje isti

**Implementacija:**

```python
# Korak 1: Kreiraj wrapper klasu
class ZaglavljeTabWrapper(QWidget):
    """Wrapper za 3-layer sistem sa starim API-jem."""
    
    data_changed = Signal()
    
    def __init__(self, draft=None, on_dirty=None):
        super().__init__()
        
        # Novi layer-i
        self.service = ZaglavljeService()
        self.view = ZaglavljeView()
        self.controller = ZaglavljeController(self.view, self.service)
        
        # UI setup
        layout = QVBoxLayout(self)
        layout.addWidget(self.view)
        
        # Zadrži kompatibilnost
        self.draft = draft
        self.on_dirty = on_dirty
        
        # Poveži signale
        self.view.data_changed.connect(self._forward_data_changed)
    
    def load_from_draft(self, draft):
        """Kompatibilnost sa starim API-jem."""
        data = self.service.load_from_draft(draft)
        self.view.set_data(data)
    
    def save_to_draft(self):
        """Kompatibilnost sa starim API-jem."""
        data = self.view.get_data()
        self.service.save_to_draft(self.draft, data)
    
    def _forward_data_changed(self):
        """Forward signal za kompatibilnost."""
        self.data_changed.emit()
        if self.on_dirty:
            self.on_dirty()

# Korak 2: Zamijeni u main_window.py (jedna linija)
# FROM:
from gui.tabs.zaglavlje_tab import ZaglavljeTab
# TO:
from gui.tabs.zaglavlje_tab_wrapper import ZaglavljeTabWrapper as ZaglavljeTab
```

---

## 9. MIGRATION CHECKLIST

### Prije integracije:
- [ ] Napravi backup trenutnog koda
- [ ] Kreiraj feature branch
- [ ] Pripremi rollback plan

### Integracija:
- [ ] Kreiraj wrapper klasu
- [ ] Testiraj wrapper izolovano
- [ ] Zamijeni import u main_window.py
- [ ] Testiraj full application

### Nakon integracije:
- [ ] Testiraj sve tabove zajedno
- [ ] Provjeri cross-tab komunikaciju
- [ ] Testiraj save/load cycle
- [ ] Provjeri dirty flag functionality
- [ ] User acceptance testing

---

## 10. RISK ANALYSIS

### Niski rizik:
- ✅ Wrapper approach - lako rollback-ovati
- ✅ Originalni kod ostaje netaknut
- ✅ Testovi pokrivaju obje verzije

### Srednji rizik:
- ⚠️ Cross-tab komunikacija (FakturaTab → ZaglavljeTab)
- ⚠️ Signal forwarding (data_changed signal)

### Visoki rizik:
- ❌ Nema (sa wrapper pristupom)

---

## 11. CONCLUSION

**Preporuka:** Koristiti **OPCIJA A (Wrapper)** za integraciju.

**Razlozi:**
1. Minimalan rizik
2. Zero breaking changes
3. Postepena migracija moguća
4. Easy rollback ako treba
5. Čista separacija između starog i novog

**Implementation effort:** ~2-3 sata
**Testing effort:** ~2-3 sata
**Total estimated time:** 4-6 sati

**Next step:** Kreirati `gui/tabs/zaglavlje_tab_wrapper.py` sa wrapper implementacijom.
