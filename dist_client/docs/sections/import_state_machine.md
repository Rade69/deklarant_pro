---
section: import_state_machine
file: services/import_service.py
---

## Svrha

Nakon svakog uspješnog importa, pamti tip datoteke (`last_import_type`) koji `_try_combine_with_previous()` koristi pri sljedećem importu da odluči da li je stigao par.

## Zavisnosti i pretpostavke

- Poziva `detect_blagic_loren_excel()`, `detect_sumaprom_excel()`, `_detect_pdf_format()`
- Greške pri detekciji tipa su nekritične — fallback je generički tip (`"excel"`, `"invoice"`)

## Pravila i granice

Mogući tipovi koje `last_import_type` može dobiti:

| Vrijednost | Šta triggera |
|------------|-------------|
| `"loren_excel"` | CASE 1 ili 2 — čeka Loren PDF |
| `"loren_pdf"` | CASE 1 ili 2 — čeka Loren Excel |
| `"sumaprom_excel"` | CASE 1B ili 2B — čeka ŠUMAPROM PDF |
| `"sumaprom_pdf"` | CASE 1B ili 2B — čeka ŠUMAPROM Excel |
| `"invoice"` | CASE 3 — čeka packing listu istog broja |
| `"packing_list"` | CASE 4 — čeka invoice istog broja (setuje se u `_try_import_as_packing_list()`) |
| `"excel"`, `"other"` | Ne triggera kombinovanje |

## Zašto ovako

Tip se detektuje u ovoj funkciji umjesto da se pamti iz detekcije u korak 2-3, jer registry ne vraća tip formata — samo vraća `ImportResult`. Ova funkcija je jedino mjesto gdje se format i tip dovode u vezu.
