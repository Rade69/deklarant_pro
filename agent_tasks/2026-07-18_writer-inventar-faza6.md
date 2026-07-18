# Writer inventar — Faza 6 (konacni)

## Dozvoljeni direktni upisi (SINGLE SOURCE OF TRUTH)

| Mjesto | Razlog |
|--------|--------|
| `core/draft/draft.py` — `InvoiceLine.from_any()` | Parser/deserializer granica — sirovi unos iz dokumenata |
| Svi `importers/` | Parser/deserializer granica — sirovi podaci iz fajlova |
| `services/decision/declaration_decision_service.py` | **JEDINO** mjesto za izvedene/primijenjene odluke |
| `gui/dialogs/eur1_quick_dialog.py` | Parser granica (GUI dijalog upisuje potvrdjene vrijednosti) |
| `gui/dialogs/pe2_quick_dialog.py` | Parser granica (GUI dijalog upisuje potvrdjene vrijednosti) |
| Manual edit u Faktura tabeli | **ODMAH** poziva `sync_decision_state_after_manual_edit()` |

## Paralelni putevi — DEPRECATED (Faza 6)

| Writer | Fajl | Status |
|--------|------|--------|
| `TariffMappingService.auto_populate_tariffs()` | services/tariff/tariff_mapping_service.py:240 | DEPRECATED — direktan upis, koristi decision servis |
| `AutoFillService.fill_tariff_numbers()` | services/faktura/auto_fill_service.py:101 | DEPRECATED — direktan upis, koristi decision servis |
| `HistoricalTariffSearchService.validate_lines()` | services/agent/validation/historical_tariff_search_service.py:120 | DEPRECATED — direktan upis, vrati Evidence |
| `ProductMasterList.apply_master_list()` | services/tariff/product_master_list.py:227 | DEPRECATED — direktan upis |
| `DeclarationAssembly` | services/naimenovanja/declaration_assembly.py:66 | DOZVOLJEN — kopira iz InvoiceLine u svoju kopiju |

## Parser/Deserializer granica (dozvoljen sirovi unos)

Svi `importers/` fajlovi, `InvoiceLine.from_any()`, `InvoiceLine.__init__()`.

## Rezime

Prije Faze 6: 44 direktna writer-a (25 parser + 11 inferred + 8 manual)
Poslije Faze 6: 4 deprecated writera (jos nisu uklonjeni, ali su oznaceni)
                 Decision servis je JEDINI autoritet za izvedene vrijednosti