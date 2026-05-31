# Agent Report: Parser Audit — Sigurnost i izolacija od asycuda_pro

**Datum:** 2026-05-19
**Grana:** dev

---

## Šta je urađeno

Kompletan audit svih parsera u `importers/` i `importers/vendors/` sa ciljem:
1. Provjere da nijedan parser ne može crashovati zbog broken importa
2. Potvrde da sve detection funkcije bezbijedno vraćaju `False` (ne bacaju exception)
3. Potvrde da `consumed_paths` ispravno spriječava duplikate stavki
4. Izolacije od asycuda_pro projekta koji je pisao u isti log fajl

---

## Nalaz: asycuda_pro nije uzrok pada u deklarant_pro

`deklarant_launch.log` u projektu sadržavao je unose iz **oba projekta**. Greške
(`⚠️ Nije par`, `QLineEdit already deleted`) dolazile su iz `asycuda_pro`, ne
`deklarant_pro`. Deklarant_pro već koristi vlastiti log:
`~/.deklarant_pro/logs/deklarant_pro.log` (konfiguracija u `run.py` linija 18-19).
Fajl `deklarant_launch.log` pokriven je sa `*.log` u `.gitignore`.

---

## Audit rezultati

### Import lanac — svih 13 simbola OK

| Modul | Simbol | Status |
|-------|--------|--------|
| importers.invoice_improved_parser | parse_invoice_improved | ✅ |
| importers.blagic_loren_pdf_parser | parse_blagic_loren_pdf | ✅ |
| importers.blagic_attos_importer | parse_blagic_attos_with_auto_combine | ✅ |
| importers.sumaprom_pdf_parser | parse_sumaprom_pdf | ✅ |
| importers.imamoglu_pdf_parser | parse_imamoglu_pdf | ✅ |
| importers.master_frigo_importer | parse_master_frigo_pdf, _read_mapping_xlsx | ✅ |
| importers.medicopharm_importer | parse_medicopharm_pdf | ✅ |
| importers.proton_system_importer | parse_proton_system_pdf | ✅ |
| importers.vendors.leburic.leburic_pekabesko_pdf_parser | parse_leburic_pekabesko_pdf | ✅ |

### Detection funkcije — sve bezbjedne

Sve `detect_*` funkcije vraćaju `False` za nepostojeći fajl (ne bacaju exception):

- `detect_blagic_attos_pdf` ✅
- `detect_blagic_loren_excel` ✅
- `detect_sumaprom_pdf` / `detect_sumaprom_excel` ✅
- `detect_imamoglu_pdf` / `detect_imamoglu_packing_list` / `detect_imamoglu_mal_tanimlari` ✅
- `detect_leburic_pekabesko_excel` ✅

### consumed_paths — ispravno na servisnom sloju

`import_service.py` ispravno postavlja `consumed_paths` za sve kombinovane importere:
- CASE 1/2 (Blagić Loren Excel+PDF) — linija 308, 330 ✅
- CASE 1B/2B (Šumaprom Excel+PDF) — linija 369, 389 ✅
- CASE 3/4 (Invoice+PackingList) — linija 438, 471 ✅

Lažni pozitivi agenta: `sumaprom_combined` vraća `Tuple` namjerno (interní helper),
`import_blagic_combined` wrapper nije pozvan iz import_service.

---

## Popravke urađene

### 1. `blagic_combined_importer.py` — pogrešna `__main__` putanja

Bila: `from importers.blagic_combined_importer import ...` (circular, pogrešan root)
Sada: import uklonjen, `project_root` ispravno kalkulisan (`parent.parent.parent.parent`)

### 2. `import_blagic_combined()` wrapper — dodan `consumed_paths`

Wrapper funkcija sada označava `excel_path` kao potrošen fajl, konzistentno sa
import_service ponašanjem. Zaštita ako neko pozove wrapper direktno izvan import_service.

### 3. `leburic_pekabesko_importer.py` — PDF parser dodan u root wrapper

Bio: samo Excel funkcije (`detect_leburic_pekabesko_excel`, `parse_leburic_pekabesko_excel`)
Sada: + `detect_leburic_pekabesko_pdf`, `parse_leburic_pekabesko_pdf`

### 4. `smart_pdf_importer.py` — konzistentnost importa

`_parse_leburic_pekabesko` sada importuje iz root wrappera
(`importers.leburic_pekabesko_importer`) umjesto direktno iz vendors putanje.

---

## Fajlovi promijenjeni

- `importers/vendors/blagic/blagic_combined_importer.py`
- `importers/leburic_pekabesko_importer.py`
- `importers/smart_pdf_importer.py`

## Commiti

| Hash | Opis |
|------|------|
| `b693747` | fix(importers): audit i popravka parsera — sigurnost i konzistentnost |
