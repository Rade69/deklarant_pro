---
section: combine_pairs
file: services/import_service.py
---

## Svrha

State machine sa 4 case-a koji kombinuje dva konsekutivna importa u jedan `ImportResult`. Ovo je srž automatskog sparivanja: korisnik importuje Excel pa PDF (ili obrnuto), sistem ih automatski spoji.

## Zavisnosti i pretpostavke

- Oslanja se na `last_import_type` koji je setovan u `_save_import_state()`
- Oslanja se na `_similar_invoice_number()` za potvrdu da su to zaista isti posao
- `combine_blagic_excel_and_pdf()` mora biti dostupan u `importers/blagic_combined_importer.py`
- ŠUMAPROM kombinovanje može baciti `ImportError` (parser još nije implementiran) — ovo je **očekivano**

## Pravila i granice

| Case | Trigger | Akcija |
|------|---------|--------|
| 1 | `last=loren_excel` + `current=loren_pdf` | `combine_blagic_excel_and_pdf(last, current)` |
| 2 | `last=loren_pdf` + `current=loren_excel` | `combine_blagic_excel_and_pdf(current, last)` |
| 1B | `last=sumaprom_excel` + `current=sumaprom_pdf` | `combine_sumaprom_excel_and_pdf(last, current)` |
| 2B | `last=sumaprom_pdf` + `current=sumaprom_excel` | `combine_sumaprom_excel_and_pdf(current, last)` |
| 3 | `last=invoice` + `current=packing_list` | `combine_invoice_and_packing(last.items, packing)` |
| 4 | `last=packing_list` + `current=pdf_invoice` | Registry importuje invoice → `combine_invoice_and_packing(invoice, last.items)` |

**Nakon kombinovanja**: `clear_memory()` se uvijek poziva — rezultat je isporučen, memorija se resetuje.

**Ako nije par**: vraća `None` — pipeline nastavlja normalnim tokom (korak 3).

## Zašto ovako

Vendori kao Blagić-Loren šalju Excel sa šiframa/cijenama i PDF sa težinama odvojeno. Nije moguće uvesti jedno bez drugog i dobiti kompletan rezultat. Stateful kombinovanje je nužno jer korisnik ne treba ručno birati par fajlova.
