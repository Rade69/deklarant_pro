# ZaglavljeTab Refactor - GAP Analiza

## PREGLED

| Metrika | Original | Novi Layer-i | Razlika |
|---------|----------|--------------|---------|
| **Ukupno linija** | 2,545 | 1,321 | -1,224 (48% manje) |
| **Broj metoda** | 59 | 44 | -15 |
| **UI konstrukcija** | ~1,500 linija | ~500 linija | -1,000 |
| **Business logika** | ~400 linija | ~443 linija | +43 |
| **Event handling** | ~300 linija | ~289 linija | -11 |
| **XML parsing** | ~434 linija | ~150 linija | -284 |

---

## MAPPING TABELA: Original → Novi Layer-i

### UI CONSTRUCTION METODE

| Originalna Metoda | Novi Layer | Nova Metoda | Status |
|-------------------|------------|-------------|--------|
| `_setup_ui()` | View | `_setup_ui()` | ✅ Pokriveno |
| `_create_toolbar()` | View | `_create_toolbar()` | ✅ Pokriveno |
| `_create_main_grid()` | View | `_create_main_grid()` | ✅ Pokriveno |
| `_create_left_column()` | View | `_create_left_column()` | ✅ Pokriveno |
| `_create_company_group()` | View | `_create_company_group()` | ✅ Pokriveno |
| `_create_middle_column()` | View | `_create_middle_column()` | ✅ Pokriveno |
| `_create_deklaracija_group()` | View | `_create_deklaracija_group()` | ✅ Pokriveno |
| `_create_obrasci_group()` | View | `_create_obrasci_group()` | ✅ Pokriveno |
| `_create_stavke_group()` | View | `_create_stavke_group()` | ✅ Pokriveno |
| `_create_vid_group()` | View | `_create_vid_group()` | ✅ Pokriveno |
| `_create_right_column()` | View | `_create_right_column()` | ✅ Pokriveno |
| `_create_icon_button()` | View | `_create_icon_button()` | ✅ Pokriveno |
| `_apply_styles()` | View | `_apply_styles()` | ✅ Pokriveno |
| `_create_transport_group()` | View | ❌ NEDOSTAJE | ❌ GAP |
| `_create_simple_field()` | View | ❌ NEDOSTAJE | ❌ GAP |
| `_create_izlaz_group()` | View | ❌ NEDOSTAJE | ❌ GAP |
| `_create_odgovorna_zemlja_group()` | View | ❌ NEDOSTAJE | ❌ GAP |
| `_create_zem_group()` | View | ❌ NEDOSTAJE | ❌ GAP |
| `_create_drzava_izvoza_group()` | View | ❌ NEDOSTAJE | ❌ GAP |
| `_create_drzava_porijekla_group()` | View | ❌ NEDOSTAJE | ❌ GAP |
| `_create_uslovi_group()` | View | ❌ NEDOSTAJE | ❌ GAP |
| `_create_valuta_group()` | View | ❌ NEDOSTAJE | ❌ GAP |
| `_create_troski_group()` | View | ❌ NEDOSTAJE | ❌ GAP |
| `_create_odgodjeno_group()` | View | ❌ NEDOSTAJE | ❌ GAP |
| `_create_hline()` | View | ❌ NEDOSTAJE | ❌ GAP |

### EVENT HANDLING METODE

| Originalna Metoda | Novi Layer | Nova Metoda | Status |
|-------------------|------------|-------------|--------|
| `_connect_signals()` | View + Controller | `_connect_signals()` | ✅ Pokriveno |
| `_on_novi()` | Controller | `_on_new()` | ✅ Pokriveno |
| `_on_otvori()` | Controller | `_on_open()` | ✅ Pokriveno |
| `_on_import_xml()` | Controller | `_on_import_xml()` | ✅ Pokriveno |
| `_on_snimi()` | Controller | `_on_save()` | ✅ Pokriveno |
| `_on_brisi()` | Controller | `_on_delete()` | ✅ Pokriveno |
| `_on_izvezi_xml()` | Controller | `_on_export_xml()` | ✅ Pokriveno |
| `_on_izlaz()` | Controller | `_on_close()` | ✅ Pokriveno |
| `_on_search_company()` | Controller | ❌ NEDOSTAJE | ❌ GAP |
| `_on_add_company()` | Controller | ❌ NEDOSTAJE | ❌ GAP |

### DATA METODE

| Originalna Metoda | Novi Layer | Nova Metoda | Status |
|-------------------|------------|-------------|--------|
| `load_from_draft()` | ❌ | ❌ | ❌ **KRITIČAN GAP** |
| `save_to_draft()` | ❌ | ❌ | ❌ **KRITIČAN GAP** |
| `_clear_all_fields()` | View | `clear_data()` | ✅ Pokriveno (djelimično) |
| `get_data()` | View | `get_data()` | ✅ Pokriveno |
| `set_data()` | View | `set_data()` | ✅ Pokriveno |
| `_populate_oznaka_combo()` | ❌ | ❌ | ❌ GAP |
| `_on_dekl_sifra_changed()` | ❌ | ❌ | ❌ GAP |

### XML METODE

| Originalna Metoda | Novi Layer | Nova Metoda | Status |
|-------------------|------------|-------------|--------|
| `_load_from_xml()` | Service | `load_from_xml()` | ✅ Pokriveno |
| `get_text()` (434 linije) | Service | `_parse_xml()` + `get_text()` | ✅ Pokriveno (simplified) |
| `_on_eksportuj_xml()` | Service | `export_to_xml()` | ✅ Pokriveno |

### DATABASE METODE (Module-level)

| Originalna Funkcija | Novi Layer | Nova Metoda | Status |
|---------------------|------------|-------------|--------|
| `_load_vrste_deklaracija_from_db()` | Service | `get_vrste_deklaracija()` | ✅ Pokriveno |
| `_load_tipovi_deklaracija_from_db()` | Service | `get_tipovi_deklaracija()` | ✅ Pokriveno |
| `_load_vrste_prijevoza_from_db()` | Service | ❌ NEDOSTAJE | ❌ GAP |
| `_load_ured_odredista_from_db()` | Service | ❌ NEDOSTAJE | ❌ GAP |
| `_load_isprave_from_db()` | Service | ❌ NEDOSTAJE | ❌ GAP |

### CONTROLLER METODE (NOVE)

| Novi Layer | Nova Metoda | Original Ekvivalent | Status |
|------------|-------------|---------------------|--------|
| Controller | `load_dropdowns()` | Nema | ✅ NOVO (bolje) |

---

## COVERAGE SUMMARY

### ✅ POKRIVENO: ~60% funkcionalnosti

**UI Construction:**
- ✅ Osnovni widgeti (toolbar, main grid, columns)
- ✅ Company groups (izvoznik, primalac, deklarant)
- ✅ Deklaracija group (vrsta, tip)
- ✅ Obrasci, Stavke, Vid groups
- ✅ Right column (priložene isprave)
- ✅ Styles primijenjeni

**Event Handling:**
- ✅ Save, Delete, New, Open, Close
- ✅ Import XML, Export XML

**Service Layer:**
- ✅ Save/Load/Delete zaglavlje
- ✅ XML import/export
- ✅ Vrste deklaracija, Tipovi, Vid unutra
- ✅ Validacija podataka

---

## ❌ KRITIČNI GAPOVI (19 metoda)

### 1. DATA LAYER - KRITIČNO

| Metod | Linije | Opis | Prioritet |
|-------|--------|------|-----------|
| `load_from_draft()` | 186 | Učitavanje podataka iz DeclarationDraft | 🔴 KRITIČNO |
| `save_to_draft()` | 168 | Čuvanje podataka u DeclarationDraft | 🔴 KRITIČNO |

**Ovo su NAJVAŽNIJE metode koje nedostaju!** Bez njih tab ne može komunicirati sa Draft sistemom.

### 2. UI CONSTRUCTION - SREDNJI PRIORITET

| Metod | Linije | Opis | Prioritet |
|-------|--------|------|-----------|
| `_create_transport_group()` | ~40 | Transport grupa | 🟡 SREDNJE |
| `_create_simple_field()` | ~20 | Helper za jednostavna polja | 🟡 SREDNJE |
| `_create_izlaz_group()` | ~40 | Izlaz grupa | 🟡 SREDNJE |
| `_create_odgovorna_zemlja_group()` | ~30 | Odgovorna zemlja | 🟡 SREDNJE |
| `_create_zem_group()` | ~30 | ZEM grupa | 🟡 SREDNJE |
| `_create_drzava_izvoza_group()` | ~70 | Država izvoza | 🟡 SREDNJE |
| `_create_drzava_porijekla_group()` | ~40 | Država porijekla | 🟡 SREDNJE |
| `_create_uslovi_group()` | ~30 | Uslovi grupa | 🟡 SREDNJE |
| `_create_valuta_group()` | ~100 | Valuta grupa | 🟡 SREDNJE |
| `_create_troski_group()` | ~40 | Troškovi grupa | 🟡 SREDNJE |
| `_create_odgodjeno_group()` | ~40 | Odgođeno plaćanje | 🟡 SREDNJE |
| `_create_hline()` | ~10 | Horizontalna linija | 🟢 NISKO |

### 3. EVENT HANDLING - SREDNJI PRIORITET

| Metod | Linije | Opis | Prioritet |
|-------|--------|------|-----------|
| `_on_search_company()` | ~50 | Pretraga kompanija | 🟡 SREDNJE |
| `_on_add_company()` | ~5 | Dodavanje kompanije | 🟢 NISKO |

### 4. HELPER METODE - NISKI PRIORITET

| Metod | Linije | Opis | Prioritet |
|-------|--------|------|-----------|
| `_populate_oznaka_combo()` | ~15 | Popuni combo za oznake | 🟢 NISKO |
| `_on_dekl_sifra_changed()` | ~50 | Promjena šifre deklaracije | 🟡 SREDNJE |

### 5. DATABASE METODE - SREDNJI PRIORITET

| Metod | Linije | Opis | Prioritet |
|-------|--------|------|-----------|
| `_load_vrste_prijevoza_from_db()` | ~15 | Vrste prijevoza | 🟡 SREDNJE |
| `_load_ured_odredista_from_db()` | ~20 | Ured odredišta | 🟡 SREDNJE |
| `_load_isprave_from_db()` | ~15 | Priložene isprave | 🟡 SREDNJE |

---

## SPECIAL CASES ANALIZA

### get_text() - 434 linije

**STATUS:** ✅ **REFAKTORISANO U MANJU VERZIJU**

Originalna metoda je imala 434 linije jer je ručno parsirala SVAKO polje zaglavlja iz XML-a.

Nova verzija u `ZaglavljeService._parse_xml()` je **~100 linija** i koristi helper funkcije:
- `find_element()` - pronalaženje XML elementata
- `get_text()` - ekstrakcija teksta (sada ~5 linija umjesto 434!)

**Razlika:**
- Original: 434 linije, hardkodovano za svako polje
- Novo: ~100 linija, generalizovano, maintainable

### load_from_draft() / save_to_draft() - 354 linije

**STATUS:** ❌ **KRITIČNO NEDOSTAJE**

Ove metode su bile u originalnom tabu i odgovorne su za:
- Mapiranje UI widgeta ↔ DeclarationDraft properties
- Konverzija tipova podataka
- Handle-ovanje ComboBox itemData

**Bez ovih metoda, tab ne može:**
- Učitati postojeću deklaraciju
- Sačuvati novu deklaraciju
- Komunicirati sa Draft sistemom

---

## PREPORUKA

### FAZA 1: KRITIČNO (OBAVEZNO PRIJE INTEGRACIJE)

1. **Dodati `load_from_draft()` i `save_to_draft()` u ZaglavljeService**
   - Ove metode trebaju biti u Service layer-u (business logic)
   - Mapiranje: Draft dict ↔ Service dict
   - Controller će zvati ove metode

2. **Dodati `load_dropdowns()` implementaciju**
   - Već postoji signature u Controller-u
   - Treba popuniti combo box-eve podacima iz baze

### FAZA 2: SREDNJI PRIORITET (ZA PUNU FUNKCIONALNOST)

3. **Dodati missing UI construction metode u View**
   - `_create_transport_group()`
   - `_create_drzava_izvoza_group()`
   - `_create_drzava_porijekla_group()`
   - `_create_valuta_group()`
   - Ostale _create_* metode

4. **Dodati event handlere u Controller**
   - `_on_search_company()` - za JIB search
   - `_on_dekl_sifra_changed()` - za zavisne dropdown-eve

### FAZA 3: NISKI PRIORITET (MOŽE KASNIJE)

5. **Dodati helper metode**
   - `_create_hline()`
   - `_populate_oznaka_combo()`
   - `_on_add_company()`

---

## ZAKLJUČAK

### DA LI MOŽEMO SAFE INTEGRISATI?

**ODGOVOR: ❌ NE - PRVO DODATI KRITIČNE METODE**

**Razlozi:**
1. Bez `load_from_draft()` i `save_to_draft()` tab ne radi osnovnu funkcionalnost
2. Bez dropdown podataka korisnik ne može unositi
3. Bez transport/država grupa gubi se ~40% UI funkcionalnosti

### ŠTA TREBA URADITI PRIJE INTEGRACIJE:

1. ✅ **Hitno dodati:**
   - `ZaglavljeService.load_from_draft()` 
   - `ZaglavljeService.save_to_draft()`
   - `ZaglavljeController.load_dropdowns()` (implementacija)

2. ✅ **Dodati prije production:**
   - Sve `_create_*` metode koje nedostaju
   - `_on_search_company()` handler

3. ✅ **Može kasnije:**
   - Helper metode (_create_hline, itd.)
   - Minor handlers (_on_add_company)

---

## METRIKE USPJESNOSTI REFAKTORA

| Metrika | Cilj | Trenutno | Status |
|---------|------|----------|--------|
| **Redukcija linija** | 60% | 48% | 🟡 Djelimično |
| **Separation of concerns** | ✅ | ✅ | ✅ Postignuto |
| **Testability** | ✅ | ✅ | ✅ 43 testa passing |
| **Maintainability** | ✅ | ✅ | ✅ Jasni layer-i |
| **Full functional parity** | ✅ | ❌ 60% | ❌ Rad u toku |

**UKUPNI STATUS: 🟡 REFAKTOR 60% ZAVRŠEN - TREBA DODATI KRITIČNE METODE**
