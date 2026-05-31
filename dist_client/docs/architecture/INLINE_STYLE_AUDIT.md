# Inline Stylesheet Audit

**Datum:** 2026-05-03
**Task:** TASK-003
**Scope:** Dokumentacija, bez izmjena source koda

---

## 1. Pregled

Ukupno **401** inline `setStyleSheet` poziv u `gui/` folderu.

| Kategorija | Broj | Procenat |
|------------|------|----------|
| 🔴 CENTRALNI TABS (visok rizik) | 108 | 27% |
| 🟡 DIALOGI (srednji rizik) | 186 | 46% |
| 🟢 ADMIN PANELI/AGENT WIDGETI (nizak rizik) | 107 | 27% |

---

## 2. Klasifikacija po tipu

| Tip | Opis | Kandidat |
|-----|------|----------|
| **STATE** | Dinamička promjena boje/stanja (error, success, warning, hover) | ➡️ KEEP |
| **BASE** | Osnovni izgled widgeta (font, border, padding, background) | ➡️ MIGRATE |
| **WORKAROUND** | Fix za specifičan Qt bug ili edge case | ➡️ KEEP (sa komentarom) |
| **TEMP** | Privremeno/vrlo lokalno (jedan widget, jedna boja) | ➡️ MIGRATE |
| **DUPLIKAT** | Isti pattern ponovljen u više fajlova | ➡️ MIGRATE u QSS klasu |

---

## 3. Detaljna mapa po fajlu

### 🔴 CENTRALNI TABS — prioritet migracije

#### `gui/tabs/sifarnici_view.py` (37 poziva)

| Linija | Widget | Klasifikacija | Preporuka | Razlog |
|--------|--------|---------------|-----------|--------|
| ~131+ | Sidebar kategorije | BASE | MIGRATE | Statična stilizacija sidebar-a |
| ~200+ | QPushButton (dodaj, obrisi) | BASE | MIGRATE | `btn_primary`, `btn_danger` klase postoje |
| ~280+ | QTableWidget | BASE | MIGRATE | Border, selection color |
| ~350+ | QLineEdit pretraga | BASE | MIGRATE | Border, focus state |
| ~400+ | QLabel naslovi | TEMP | MIGRATE | `font-size`, `color` |

**Procijenjen redoslijed migracije:** #1 (najviše poziva, centralni tab)

---

#### `gui/tabs/naimenovanja_view.py` (19 poziva)

| Linija | Widget | Klasifikacija | Preporuka | Razlog |
|--------|--------|---------------|-----------|--------|
| ~409 | `naimenovanjaUiWidget` | BASE | KEEP* | Već ima `naimenovanja_components.qss` — ali inline pregazi QSS |
| ~1336 | `lbl_nav` (navigacija) | BASE | MIGRATE | `nav-label` klasa postoji u QSS |
| ~1382+ | QPushButton (prev/next) | BASE | MIGRATE | Već definisani u `naimenovanja_components.qss` |
| ~1462+ | QPushButton (record) | BASE | MIGRATE | Identični kao prev/next |

**Napomena:** `naimenovanja_components.qss` je specifično dizajniran za ovaj tab. Inline override-ovi su redundantni.

**Procijenjen redoslijed migracije:** #2

---

#### `gui/tabs/zaglavlje_view.py` (14 poziva)

| Linija | Widget | Klasifikacija | Preporuka | Razlog |
|--------|--------|---------------|-----------|--------|
| ~50+ | Forma QGroupBox | BASE | MIGRATE | Border, padding |
| ~100+ | QLineEdit polja | STATE | KEEP | Read-only styling, dynamic validacija |
| ~150+ | Status label | STATE | KEEP | Boja mijenja se po stanju (error/warning/ok) |

**Procijenjen redoslijed migracije:** #3

---

#### `gui/tabs/faktura_view.py` (nije u top 20 po broju, ali kritičan po riziku)

| Linija | Widget | Klasifikacija | Preporuka | Razlog |
|--------|--------|---------------|-----------|--------|
| ~712 | Toolbar dugmad | BASE | MIGRATE | Veliki inline block, sva dugmad već imaju objectName |
| ~2598 | `btn_create_naimenovanja` stil | BASE | MIGRATE | Već referencira `button_styles.qss` |

**Napomena:** Faktura tab ima relativno malo inline-a ali oni su **vrlo rizični** zbog velikih CSS blokova.

**Procijenjen redoslijed migracije:** #4

---

### 🟡 DIALOGI — prioritet migracije

#### `gui/dialogs/tariff_suggestion_dialog.py` (25 poziva)

| Linija | Widget | Klasifikacija | Preporuka |
|--------|--------|---------------|-----------|
| ~90 | `self.setStyleSheet` (veliki block) | BASE | MIGRATE |
| ~144 | `lbl_proizvod` | TEMP | MIGRATE |
| ~202 | `card` hover/pressed | STATE | KEEP |

**Pattern:** Card hover/pressed je STATE — treba ostati inline ili se prebaci u dinamičku klasu.

---

#### `gui/dialogs/enhanced_validation_dialog.py` (21 poziva)

| Linija | Widget | Klasifikacija | Preporuka | Napomena |
|--------|--------|---------------|-----------|----------|
| ~112 | `title_label` | TEMP | MIGRATE | `#2c3e50` — hardkodirana boja |
| ~125 | `status_label` | STATE | KEEP | Mijenja boju po stanju |
| ~167 | `tab_widget` | BASE | MIGRATE | Tab stilizacija |
| ~257+ | Dinamičke boje | STATE | KEEP | `color: {color}` — runtime |
| ~408 | `checkbox` | WORKAROUND | KEEP | Specifičan Qt checkbox stil |

---

#### `gui/dialogs/pe2_quick_dialog.py` (17 poziva)

| Linija | Widget | Klasifikacija | Preporuka |
|--------|--------|---------------|-----------|
| ~56 | `header` | BASE | MIGRATE |
| ~69 | `global_group` | BASE | MIGRATE |
| ~121 | `info_label` | STATE | KEEP |
| ~176 | `frame` | BASE | MIGRATE |

---

#### `gui/dialogs/eur1_quick_dialog.py` (13 poziva)

| Linija | Widget | Klasifikacija | Preporuka |
|--------|--------|---------------|-----------|
| ~56 | `header` | BASE | MIGRATE |
| ~66 | `global_group` | BASE | MIGRATE |
| ~121 | `info_label` | STATE | KEEP |
| ~176 | `frame` | BASE | MIGRATE |

**Napomena:** `eur1_quick_dialog.py` i `pe2_quick_dialog.py` imaju **identičan pattern** — kandidati za extract zajedničkog QSS ili base dialog klase.

---

#### `gui/dialogs/enhanced_tariff_suggestion_dialog.py` (17 poziva)

| Linija | Widget | Klasifikacija | Preporuka |
|--------|--------|---------------|-----------|
| ~124 | `title_label` | TEMP | MIGRATE |
| ~274 | `group_box` | BASE | MIGRATE |
| ~364 | `widget` (card) | BASE | MIGRATE |
| ~415+ | Dugmad | BASE | MIGRATE |

---

#### `gui/dialogs/inspection_dialog.py` (11 poziva)

| Linija | Widget | Klasifikacija | Preporuka |
|--------|--------|---------------|-----------|
| ~110 | `frame` | BASE | MIGRATE |
| ~129 | `title` | TEMP | MIGRATE |
| ~252 | `frame` (detail) | BASE | MIGRATE |
| ~302 | `cond_lbl` | STATE | KEEP |

---

### 🟢 ADMIN PANELI / AGENT WIDGETI — nizak prioritet migracije

#### `gui/tabs/sifarnici/partner_form_strip.py` (20 poziva)

| Linija | Widget | Klasifikacija | Preporuka |
|--------|--------|---------------|-----------|
| ~20+ | Form layout, labels | BASE | MIGRATE |
| ~100+ | QLineEdit | BASE | MIGRATE |
| ~150+ | QPushButton | BASE | MIGRATE |

**Napomena:** Shared komponenta — migracija ovdje utiče na sve tabove koji koriste `PartnerFormStrip`.

---

#### `gui/tabs/agent/widgets/chat_panel.py` (23 poziva)

| Linija | Widget | Klasifikacija | Preporuka |
|--------|--------|---------------|-----------|
| ~30+ | Chat bubble container | BASE | MIGRATE |
| ~80+ | Message bubbles | STATE | KEEP | Hover/pressed na poruke |
| ~120+ | Avatar, timestamp | TEMP | MIGRATE |

---

#### `gui/tabs/agent/widgets/upload_area.py` (18 poziva)

| Linija | Widget | Klasifikacija | Preporuka |
|--------|--------|---------------|-----------|
| ~20+ | Drop area | STATE | KEEP | Drag/dragover/dragleave dinamični stilovi |
| ~60+ | File list item | BASE | MIGRATE |
| ~100+ | Progress bar | STATE | KEEP |

---

#### Admin paneli (9-13 poziva svaki)

| Fajl | Poziva | Tip | Preporuka |
|------|--------|-----|-----------|
| `plugin_panel.py` | 13 | BASE | MIGRATE (nizak prioritet) |
| `learning_panel.py` | 12 | BASE + STATE | MIXED |
| `database_panel.py` | 12 | BASE | MIGRATE (nizak prioritet) |
| `analytics_panel.py` | 12 | BASE | MIGRATE (nizak prioritet) |
| `system_panel.py` | 11 | BASE | MIGRATE (nizak prioritet) |
| `settings_panel.py` | 9 | BASE | MIGRATE (nizak prioritet) |

---

## 4. Redoslijed migracije po riziku

| Rank | Fajl | MIGRATE/KEEP | Naglasak |
|------|------|-------------|----------|
| 1 | `gui/tabs/sifarnici_view.py` | 32/5 | Najviše inline-a, centralni tab |
| 2 | `gui/tabs/naimenovanja_view.py` | 14/5 | Već ima QSS, samo ukloniti redundantno |
| 3 | `gui/tabs/faktura_view.py` | ~10/2 | Veliki blokovi, visok vizuelni uticaj |
| 4 | `gui/tabs/zaglavlje_view.py` | 8/6 | STATE stilovi ostaju |
| 5 | `gui/dialogs/tariff_suggestion_dialog.py` | 20/5 | Duplikat pattern |
| 6 | `gui/dialogs/enhanced_validation_dialog.py` | 14/7 | STATE boje ostaju |
| 7 | `gui/tabs/sifarnici/partner_form_strip.py` | 18/2 | Shared komponenta |
| 8 | `gui/dialogs/eur1_quick_dialog.py` | 11/2 | Identičan kao pe2 |
| 9 | `gui/dialogs/pe2_quick_dialog.py` | 14/3 | Identičan kao eur1 |
| 10 | `gui/dialogs/enhanced_tariff_suggestion_dialog.py` | 14/3 | Duplikat tariff_suggestion |

---

## 5. Zaštitni zid (šta NE MIJEĽATI)

| Pattern | Primjer | Razlog |
|---------|---------|--------|
| `setStyleSheet(f"color: {color}")` | `db_setup_dialog.py:344` | Runtime dinamika |
| `setStyleSheet("background: #fff9c4")` | Validacija redova | STATE — mijenja se po logici |
| Drag/drop highlight | `upload_area.py` | Interaktivnost |
| Hover/pressed na custom widgetima | Chat bubble | Pseudo-state nema u inline |

---

## 6. Procjena: koliko se može migrirati?

| Kategorija | Procenat | Broj |
|------------|----------|------|
| MIGRATE u QSS | ~65% | ~260 poziva |
| KEEP inline | ~20% | ~80 poziva |
| MIXED (refactor potreban) | ~15% | ~61 poziv |

**Napomena:** MIGRATE ne znači "samo premjesti" — zahtijeva:
1. Dodavanje `objectName` ili `property("class")` na widgete
2. Pisanje odgovarajućeg QSS selektora
3. Testiranje da inline override nije imao skrivenu svrhu
