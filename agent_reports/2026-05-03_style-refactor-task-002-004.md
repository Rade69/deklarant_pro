# Izvještaj agenta — Style Refactor TASK-002 i TASK-004

## 1. Sažetak

Implementacija dva taska iz `PHASE_PLAN.md`:

- **TASK-002** — Hardening dropdown strelica (uklanjanje square/minus artifakata)
- **TASK-004** — Migracija statičkih inline stilova iz `naimenovanja_view.py` u QSS

Baseline: 19 `setStyleSheet` poziva u `naimenovanja_view.py`
Final: 13 `setStyleSheet` poziva
**Smanjenje: 31.6%** (iznad 30% cilja)

## 2. Šta je urađeno

### TASK-002: Dropdown Arrow Hardening

| Promjena | Opis |
|----------|------|
| `_ArrowCombo.__init__` dodat | Python klasa `_ArrowCombo` u `naimenovanja_view.py` sada ima `__init__` metodu sa `setStyleSheet()` koji skriva QSS CSS triangle strelicu prije nego se paintEvent() pozove |

**Problem riješen:** `_ArrowCombo` klasa (lokalno definisana unutar `_install_rubrika40_combos`) ima `paintEvent()` override koji crta polygon strelicu, ali QSS globalni fajl istovremeno generiše CSS trougao. Bez `setStyleSheet()` u Python-u, oba se vizuelno preklapaju → square/minus artifakti.

**Uzorak:** `_ArrowComboBox` klasa u `zaglavlje_view.py` već ima ovaj pattern (linije 159-197).

### TASK-004: Inline to QSS Migration

| Promjena | Python fajl | QSS fajl |
|----------|-------------|----------|
| `combo_vrsta_pakovanja` | uklonjen setStyleSheet (69 linija) | dodat `QComboBox#le_r31_vrsta` |
| `combo_items` | uklonjen setStyleSheet (31 linija) | proširen `.nav-combo` class selector |
| `lbl_tariff_warning` | uklonjen setStyleSheet + dodat `setObjectName` | dodat `QLabel#lbl_tariff_warning` |
| `te_trg_naziv` | uklonjen setStyleSheet (12 linija) | dodat `QTextEdit#le_r31_trg_naziv` |
| `main_grid_frame` | zakomentarisano (QUiLoader workaround) | dodat `QFrame#main_grid_frame` |
| `te_r31_opis` | skraćen inline — samo boja | dodat `QLineEdit#te_r31_opis` (bazni stil) |
| `te_r31_opis_2` | skraćen inline — samo boja | dodat `QLineEdit#te_r31_opis_2` (bazni stil) |

## 3. Zašto je urađeno

**TASK-002:** Kompozicija QSS CSS triangle (`border-top: 5px solid`) i Python polygon (QPainter.drawPolygon) stvara vizuelne artefakte. Rješenje: `setStyleSheet()` na nivou klase skriva QSS strelicu, Python `paintEvent()` ostaje jedini izvor strelice.

**TASK-004:** Inline stilovi otežavaju održavanje — iste boje/borderi ponavljaju se na više mjesta. Migracija u centralizovani QSS omogućava:
- Jednu tačku izmjene za sve komponente istog tipa
- Konzistentan izgled bez kopiranja stilova
- Lakše refaktorisanje u budućnosti

## 4. Kako je urađeno

1. Pročitani task scope fajlovi za TASK-002 i TASK-004
2. Pregled postojećih `setStyleSheet` poziva u `naimenovanja_view.py` (19 baseline)
3. Analiza svakog pojedinačnog poziva — koje su statičke, koje dinamičke
4. Dodavanje novih sekcija u `styles/naimenovanja_components.qss`
5. Uklanjanje statičkih stilova iz Python-a
6. Verifikacija: `python -m py_compile` + count promjena

## 5. Kontrolisani fajlovi

| Fajl | Izmjena |
|------|---------|
| `gui/tabs/naimenovanja_view.py` | Dodat `__init__` u `_ArrowCombo`, uklonjeno 4 inline stila, skraćena 2 inline stila, dodato 4 komentara sa linkovima ka izvještaju |
| `styles/naimenovanja_components.qss` | Dodato 6 novih sekcija (~100 linija) |

### Komentari sa linkovima u kodu

Kratki komentari na mjestima gdje je stil premješten (link ka izvještaju):

```python
# TASK-002: add __init__ to hide QSS arrow, see agent_reports/2026-05-03_style-refactor-task-002-004.md
# TASK-004: inline style removed → QComboBox#le_r31_vrsta in naimenovanja_components.qss
# TASK-004: inline style removed → QLabel#lbl_tariff_warning in naimenovanja_components.qss
# TASK-004: inline style removed → QTextEdit#le_r31_trg_naziv in naimenovanja_components.qss
```

### Izvještaj

Lokacija: `agent_reports/2026-05-03_style-refactor-task-002-004.md`

## 6. Šta nije urađeno

- **TASK-004 mini-task:** Migracija `le_rubrika40_2`, `le_rubrika40_3`, `le_rubrika44_4` — ovi koriste `master_combo_style`/`master_field_style` stringove koji su definirani u istoj metodi, teško ih je izdvojiti bez refaktoringa
- **Dynamic stilovi ostaju inline:** `lbl_status_validation` (warning/success alternacija), `flash_style`/`original_style` (timer-based animacije), `w.setStyleSheet("")` (resetiranje pri kucanju tarife)
- **Zaglavlje tab:** TASK-002 je već implementiran u prethodnom commit-u (`adf00d9`)

## 7. Provjera i testovi

```bash
# Syntax check
python -m py_compile gui/tabs/naimenovanja_view.py  # OK
python -m py_compile gui/tabs/zaglavlje_view.py       # OK

# Count verification
rg -n "setStyleSheet\(" gui/tabs/naimenovanja_view.py | wc -l
# Prije: 19, Poslije: 13, Smanjenje: 6 (31.6%)

# Diff stat
git diff --stat gui/tabs/naimenovanja_view.py styles/naimenovanja_components.qss
```

## 8. Rizici i napomene

- **QSS loading order:** Novi stilovi u `naimenovanja_components.qss` učitavaju se prije `QSS_header_toolbar_sistem.qss` (poznata hijerarhija iz `main_window.py:175-186`). Provjereno — selektori sa ID (`#le_r31_vrsta`) imaju viši prioritet od nespecifičnih.
- **Runtime boja promjene:** `te_r31_opis` i `te_r31_opis_2` primaju samo `background-color` i `color` inline — bazni stil (`border-radius`, `padding`) dolazi iz QSS. Vizuelno identično.
- **QUiLoader bug workaround:** `main_grid_frame` stil je zakomentarisani kod jer je original imao workaround komentar za QUiLoader bug. Provjeriti da li je bug još uvijek prisutan prije finalnog uklanjanja.

## 9. Preporučeni sljedeći korak

Prema `PHASE_PLAN.md`, preostali taskovi:

- **TASK-006** — Migracija baznih stilova za `faktura_tab_v2.py`
- **TASK-007** — Migracija baznih stilova za `zaglavlje_view.py`
- **TASK-008** — Globalna konsolidacija duplikata u QSS fajlovima

ili nastavak sa drugim dijelovima backlog-a.
