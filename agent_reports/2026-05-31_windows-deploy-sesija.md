# Agent Report — Windows Deploy Sesija
**Datum:** 2026-05-31  
**Trajanje:** Jedna duga sesija  
**Cilj:** Pokrenuti Deklarant Pro na Windows 10/11 klijentskim mašinama

---

## Šta je urađeno

### Faza 1 — PyInstaller EXE (napušteno)
Pokušali smo izgraditi standalone `.exe` putem PyInstaller + Inno Setup. Naišli smo na 12 grešaka:
1. `database/data` folder ne postoji na Windows mašini → spec fajl popravljen
2. Batch sintaksna greška sa zagradama u `echo` → escapovano sa `^(` i `^)`
3. `qtawesome` nije instaliran → `pip install qtawesome`
4. `PermissionError` pri pisanju u `Program Files` → `USER_DATA_DIR` u `%APPDATA%`
5. `plugins` folder u `Program Files` → premješteno u `%APPDATA%`
6. MCP server spawnovao beskonačno novih EXE procesa → skip u frozen modu
7. `.env` nije pronađen → putanja relativna na `sys.executable.parent`
8. `UnicodeEncodeError` s emojima → `sys.stderr` na UTF-8 devnull
9. `tab_factory` vraćao `None` tiho → promijenjeno na `raise`
10. Desktop ikonica bijela → ISS putanja na `_internal\assets\icons\`
11. Toolbar raspored poremećen → font 11pt, column stretch, Validacija premještena
12. `sys.stderr.write(emoji)` u više fajlova → zamijenjeno sa `logger`

**Zaključak:** PyInstaller za ovu aplikaciju stvara previše platform-specifičnih problema. Napušteno u korist venv pristupa.

---

### Faza 2 — Python venv pristup (odabran)
Kreirana `setup_windows_venv.bat` skripta koja:
- Provjerava Python verziju
- Kreira `.venv` virtualno okruženje
- Instalira sve zavisnosti
- Kreira `.env` iz predloška (otvara Notepad)
- Testira konekciju na bazu
- Kreira desktop prečicu

---

### Faza 3 — Nuitka .pyd zaštita koda
Na Windows 11 mašini (Python 3.14.1, Nuitka 4.1.2, MSVC 14.3):

**Kompajlirani moduli:**
| Modul | Output |
|---|---|
| `core/licensing/` | `licensing.cp314-win_amd64.pyd` |
| `core/validation/` | `validation.cp314-win_amd64.pyd` |
| `services/faktura/` | `faktura.cp314-win_amd64.pyd` |
| `services/tariff/` | `tariff.cp314-win_amd64.pyd` |
| `services/export_service.py` | `export_service.cp314-win_amd64.pyd` |
| `services/declaration_assembly.py` | `declaration_assembly.cp314-win_amd64.pyd` |
| `services/tariff_controls_service.py` | `tariff_controls_service.cp314-win_amd64.pyd` |
| `services/tariff_doc_history_service.py` | `tariff_doc_history_service.cp314-win_amd64.pyd` |
| `services/tariff_facade.py` | `tariff_facade.cp314-win_amd64.pyd` |
| `services/tariff_mapping_service.py` | `tariff_mapping_service.cp314-win_amd64.pyd` |
| `services/tariff_tree_service.py` | `tariff_tree_service.cp314-win_amd64.pyd` |

Svi import testovi prošli. Kreiran `scripts/build_distribution.bat` za buduće buildove.

---

### Faza 4 — Bugovi pronađeni tokom testiranja

**Bug: Validacija ne broji `zemlja_porijekla`**
- `_validate_and_color_row` bojio red crveno ali `validation_cache` nije znao
- `FakturaItemValidator.validate()` nije provjeravao `zemlja_porijekla`
- Fix: dodana provjera kao `ValidationLevel.ERROR` u validator
- Fix: dodana provjera u `_validate_and_color_row` za konzistentnost

**Bug: XML uvoz u Zaglavlje pregazi priložene dokumente**
- `_populate_attached_table` s `clear_refs_on_import=True` brisao reference svim docs
- Fix: korisničkim unosima dodan `_user_entered: True` marker u merge funkciji
- Fix: `_populate_attached_table` čuva ref ako `_user_entered` je True
- Fix: `setRowCount` dodan za slučaj više docs nego redova

**Bug: Izvoznik i uvoznik se ne popunjavaju pri XML uvozu**
- `load_from_xml` vraćao `izvoznik_naziv` ali widget ključ je `izvoznik_r1`
- Fix: promijenjeno na `izvoznik_r1` i `primalac_r1` u `zaglavlje_service.py`

**Bug: Adwaita SVG ikone (Linux putanje na Windows)**
- QSS stylesheet koristio `/usr/share/icons/Adwaita/...` — ne postoji na Windows
- Fix: kreiran `assets/icons/chevron-down.svg` (chevron arrow)
- Fix: `_DOWN_ARROW_CSS` modul-level varijabla, `.replace("__ARROW_CSS__", ...)` pattern u QSS

---

## Razlozi za ključne odluke

**Zašto venv umjesto EXE:**
Aplikacija koristi `sys.executable` za MCP server, `__file__` za putanje, i pretpostavlja pisljivost project foldera. Sve ovo se lomi u frozen PyInstaller EXE-u. Za 2 interna klijenta na lokalnoj mreži, venv je jednostavniji i bez ovih problema.

**Zašto Nuitka za zaštitu:**
Aplikacija se spaja na PostgreSQL server koji mi kontrolišemo — ovo je prirodna zaštita od neovlaštenog korišćenja. Nuitka kompajlira poslovnu logiku u `.pyd` fajlove koji su teški za reverse engineering, bez komplikacija PyInstaller-a.

**Zašto `_user_entered` marker:**
`_merge_import_docs_add_only_missing` ispravan po logici (čuva existing_docs), ali `_populate_attached_table` nije razlikovao korisničke od XML dokumenata. Najmanji mogući fix bez refaktoringa.

**Zašto `.replace()` umjesto f-string:**
QSS stringovi sadrže CSS `{` i `}`. U Python f-stringu ovi znakovi uzrokuju SyntaxError (Python ih tumači kao f-string expression). `.replace("__ARROW_CSS__", _DOWN_ARROW_CSS)` je cross-platform rješenje bez escapovanja svih CSS vitičastih zagrada.

---

## Stanje na kraju sesije
- `dist_client/` postoji i funkcionalan je kada je server dostupan
- `dist_client/.env` mora imati `DB_HOST=192.168.0.41`
- Zaglavlje i Naimenovanja tabovi prazni bez DB konekcije (normalno)
- Adwaita greška riješena, čekamo potvrdu korisnika
- `scripts/build_distribution.bat` automatizuje buduće buildove
