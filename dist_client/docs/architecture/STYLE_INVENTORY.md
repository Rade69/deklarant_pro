# Style Inventory — Inventar svih stil izvora i konflikt mapa

**Datum:** 2026-05-03
**Task:** TASK-001
**Scope:** Dokumentacija, bez izmjena source koda

---

## 1. Layer model stilova

Stilovi dolaze iz 3 sloja, po prioritetu (najviši → najniži):

| Sloj | Prioritet | Izvor | Primjer |
|------|-----------|-------|---------|
| **L1 — Inline** | 🔴 Najviši | `widget.setStyleSheet(...)` | `faktura_view.py:712` |
| **L2 — Tab/Component QSS** | 🟡 Srednji | `.qss` fajl loadovan za tab | `admin_tab.qss`, `naimenovanja_components.qss` |
| **L3 — Global QSS** | 🟢 Najniži | `.qss` fajlovi učitani u `main_window.py` | `unified_color_system.qss`, `button_system.qss` |

---

## 2. Globalni QSS fajlovi (L3)

Učitani u `main_window.py:176-185` redoslijedom — **posljednji ima najviši prioritet**:

| # | Fajl | Linija | Sadržaj |
|---|------|--------|---------|
| 1 | `asycuda_modern_material.qss` | ~100 linija | Osnovni stilovi (QLineEdit, QComboBox, QPushButton, QTableWidget) |
| 2 | `typography.qss` | — | Tekst stilovi (font-size, font-weight) |
| 3 | `spacing_system.qss` | — | Razmaci (padding, margin) |
| 4 | `main_tabs.qss` | — | Stilovi glavnog QTabWidget-a |
| 5 | `zone_styling.qss` | — | Hijerarhija zona (`.zone_primary_input`, `.zone_secondary_input`) |
| 6 | `naimenovanja_components.qss` | — | Komponente Naimenovanja taba (scoped `#naimenovanjaUiWidget`) |
| 7 | `button_system.qss` | ~520 linija | Kategorije dugmadi (`.btn_primary`, `.btn_secondary`, `.btn_danger`, `btnType` atributi) |
| 8 | `faktura_tab_v2.qss` | — | Osnovni stilovi Faktura taba |
| 9 | `QSS_header_toolbar_sistem.qss` | ~520 linija | Inputi, scrollbari, tabele, combobox, toolbar dugmad (po ID-ju) |
| 10 | `unified_color_system.qss` | ~280 linija | **Najviši L3 prioritet** — unificirana paleta boja, dugmad po btnType i ID |

**Dodatni L2 fajlovi** (loadovani pojedinačno):
- `gui/styles/admin_tab.qss` — Admin tab (loaduje `admin_view.py:41`)
- `styles/admin_tab.qss` — Duplikat/prethodna verzija?

---

## 3. Inline setStyleSheet pozivi (L1)

**Ukupno:** 401 poziv u `gui/` folderu

### Top 20 fajlova po broju poziva:

| Rang | Fajl | Poziva | Rizik |
|------|------|--------|-------|
| 1 | `gui/tabs/sifarnici_view.py` | 37 | 🔴 Visok — centralni tab |
| 2 | `gui/dialogs/tariff_suggestion_dialog.py` | 25 | 🟡 Srednji — dialog |
| 3 | `gui/tabs/agent/widgets/chat_panel.py` | 23 | 🟡 Srednji — AI widget |
| 4 | `gui/dialogs/enhanced_validation_dialog.py` | 21 | 🟡 Srednji — dialog |
| 5 | `gui/tabs/sifarnici/partner_form_strip.py` | 20 | 🔴 Visok — shared komponenta |
| 6 | `gui/tabs/naimenovanja_view.py` | 19 | 🔴 Visok — centralni tab |
| 7 | `gui/tabs/agent/widgets/upload_area.py` | 18 | 🟢 Nizak — utility widget |
| 8 | `gui/dialogs/pe2_quick_dialog.py` | 17 | 🟢 Nizak — quick dialog |
| 9 | `gui/dialogs/enhanced_tariff_suggestion_dialog.py` | 17 | 🟡 Srednji — dialog |
| 10 | `gui/tabs/zaglavlje_view.py` | 14 | 🔴 Visok — centralni tab |
| 11 | `gui/tabs/agent/widgets/tariff_validation_dialog.py` | 13 | 🟢 Nizak — dialog |
| 12 | `gui/tabs/agent/widgets/proposal_card.py` | 13 | 🟢 Nizak — utility widget |
| 13 | `gui/tabs/admin/panels/plugin_panel.py` | 13 | 🟢 Nizak — admin panel |
| 14 | `gui/dialogs/eur1_quick_dialog.py` | 13 | 🟢 Nizak — quick dialog |
| 15 | `gui/tabs/admin/panels/learning_panel.py` | 12 | 🟢 Nizak — admin panel |
| 16 | `gui/tabs/admin/panels/database_panel.py` | 12 | 🟢 Nizak — admin panel |
| 17 | `gui/tabs/admin/panels/analytics_panel.py` | 12 | 🟢 Nizak — admin panel |
| 18 | `gui/dialogs/inspection_dialog.py` | 11 | 🟢 Nizak — dialog |
| 19 | `gui/tabs/admin/panels/system_panel.py` | 11 | 🟢 Nizak — admin panel |
| 20 | `gui/tabs/admin/panels/settings_panel.py` | 9 | 🟢 Nizak — admin panel |

---

## 4. Konflikt mapa po widget tipu

### QComboBox::down-arrow — 3 deklaracije u različitim .qss

| Fajl | Linija | Sadržaj | Rizik |
|------|--------|---------|-------|
| `asycuda_modern_material.qss` | 100 | `border: none; image: url(...)` | 🟡 Pregazi manje specifične |
| `deklarant_modern_material.qss` | 100 | `border: none; image: url(...)` | 🟡 Duplikat — identičan kao asycuda |
| `QSS_header_toolbar_sistem.qss` | 510 | `image: url(...); width/height` | 🟢 Scoped, najviše specificnosti |

**Problem:** `asycuda_modern_material.qss` i `deklarant_modern_material.qss` imaju **identične** `QComboBox::down-arrow` deklaracije. Duplikatni kod — potencijalna divergencija.

### QLineEdit — 10+ fajlova deklariše

| Fajl | Specificnost | Sadržaj | Rizik |
|------|-------------|---------|-------|
| `asycuda_pro_ui.qss` | Global | Border, padding, focus | 🟡 Globalni uticaj |
| `deklarant_pro_ui.qss` | Global | Identičan kao asycuda_pro_ui | 🔴 Duplikat |
| `deklarant_modern_material.qss` | Global | Border, padding, focus | 🟡 Identičan kao asycuda_modern |
| `asycuda_modern_material.qss` | Global | Border, padding, focus | 🟡 Pregazi ostale |
| `QSS_header_toolbar_sistem.qss` | Global | Background, border, padding | 🟡 Loadan poslije, pregazi |
| `zone_styling.qss` | Klasa (`.zone_*`) | Border boje po zoni | 🟢 Nizak — po klasi |
| `naimenovanja_components.qss` | Scoped (`#widget`) | `#naimenovanjaUiWidget QLineEdit` | 🟢 Niski — scoped |
| `unified_color_system.qss` | Tab ID (`#Tab`) | `#SifarniciTab QLineEdit`, `#ZaglavljeTab QLineEdit` | 🟡 Srednji — po tabu |
| `admin_tab.qss` | Global | Border, hover, focus | 🟡 Lokalni za admin |

**Kritični konflikt:** `#ZaglavljeTab QLineEdit` u `unified_color_system.qss:261` vs globalni `QLineEdit` u `QSS_header_toolbar_sistem.qss:260` — koji ima prioritet zavisi redoslijeda učitavanja.

### QPushButton — 8+ fajlova deklariše

| Fajl | Specificnost | Sadržaj | Rizik |
|------|-------------|---------|-------|
| `button_system.qss` | Klasa (`.btn_*`) | ~500 linija, najbolja organizacija | 🟢 Referentna implementacija |
| `unified_color_system.qss` | ID + atribut | `btnType="primary"`, `#btnSnimi` | 🟡 Pregazi klase ako je loadan poslije |
| `QSS_header_toolbar_sistem.qss` | ID | `#importBtn`, `#snimiBtn`, `#xmlBtn` | 🟡 High specificnost |
| `naimenovanja_components.qss` | ID | `#btnPrevItem`, `#btnNextItem` | 🟢 Scoped |
| `asycuda_modern_material.qss` | Global | Osnovni (bg, hover, pressed) | 🟡 Pregazi klase ako je prethodni |
| `deklarant_modern_material.qss` | Global | Identičan kao asycuda | 🔴 Duplikat |

**Kritični konflikt:** `unified_color_system.qss` i `button_system.qss` targetuju iste dugmadi putem različitih selektora (ID/attr vs class). `btnKreirajNaimenovanja` ima definiciju u oba fajla. Koji pobjeđuje zavisi od redoslijeda učitavanja.

---

## 5. Top 10 najrizičnijih inline stilova

| Rang | Fajl | Linija | Šta radi | Zašto je rizično |
|------|------|--------|----------|-----------------|
| 1 | `faktura_view.py` | ~2598 | Veliki inline block za toolbar dugmad | 🔴 Pregazi sve QSS definicije dugmadi; 20+ linija inline CSS |
| 2 | `sifarnici_view.py` | ~37 poziva | Razni widgeti (QPushButton, QLabel, QFrame) | 🔴 Centralni tab; inline stilovi po cijelom fajlu |
| 3 | `naimenovanja_view.py` | ~409, ~1336 | `#naimenovanjaUiWidget` stilizacija | 🔴 Inline + external QSS overlap; nepouzdano koja deklaracija pobjeđuje |
| 4 | `partner_form_strip.py` | 20 | Forma za partnere | 🟡 Shared komponenta — svaka izmjena utiče na 2+ taba |
| 5 | `tariff_suggestion_dialog.py` | 25 | Dialog za tarife | 🟡 Ponavljajući pattern (card hover/pressed) koji ide u QSS |
| 6 | `enhanced_validation_dialog.py` | 21 | Validacioni dialog | 🟡 Boje hardkodirane (#2c3e50, #bdc3c7) — ne koriste paletu |
| 7 | `zaglavlje_view.py` | 14 | Zaglavlje tab | 🟡 Centralni tab; mixin boja sa QSS |
| 8 | `chat_panel.py` | 23 | AI chat panel | 🟡 Widget-specific stilovi (bubble, avatar) |
| 9 | `pe2_quick_dialog.py` | 17 | Quick dialog za PE2 | 🟢 Sličan pattern kao eur1_quick_dialog |
| 10 | `enhanced_tariff_suggestion_dialog.py` | 17 | Dialog za tarife v2 | 🟢 Duplikat tariff_suggestion_dialog patterna |

---

## 6. Tabela prioriteta po widget tipu

| Widget | Finalni prioritet ima | Lokacija | Napomena |
|--------|----------------------|----------|----------|
| `QComboBox::down-arrow` | `QSS_header_toolbar_sistem.qss` (L3) | L3, loadan poslije unificiranog | Scoped override nedostaje |
| `QLineEdit` (globalni) | `QSS_header_toolbar_sistem.qss` | L3 | Pregazi modern_material |
| `QLineEdit` (Zaglavlje) | `unified_color_system.qss` + inline | L1/L3 | Inline L1 ima prednost |
| `QLineEdit` (Sifarnici) | `unified_color_system.qss` | L3 | Tab-scoped |
| `QPushButton` (globalni) | `unified_color_system.qss` | L3 | Po ID/attr — visoka specificnost |
| `QPushButton` (btn_primary) | `button_system.qss` | L3 | Klasni selektor |
| `QTableWidget` | `asycuda_modern_material.qss` | L3 | Globalni stil |
| QTabWidget | `main_tabs.qss` | L3 | Loadan relativno rano |

---

## 7. Preporuke (out-of-scope za TASK-001, za sljedeće faze)

1. **Ukloniti duplikate:** `asycuda_modern_material.qss` i `deklarant_modern_material.qss` su identični — merge.
2. **Ukloniti duplikate:** `asycuda_pro_ui.qss` i `deklarant_pro_ui.qss` su identični — merge.
3. **Razriješiti QComboBox::down-arrow:** 3 deklaracije → 1 sa fallback mehanizmom.
4. **Dodati objectName-ove** na top 10 najrizičnijih inline mjesta za migraciju u QSS.
5. **Uvesti tab-level QSS** za `sifarnici_view.py` i `faktura_view.py` umjesto inline-a.
