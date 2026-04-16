---
section: import_pipeline
file: services/import_service.py
---

## Svrha

Centralni orchestrator importa. Svaki fajl koji korisnik uveze prolazi kroz ovaj pipeline. Odgovornost: koordinacija između memorijskog kombinovanja, detekcije packing liste i strategy registry-a.

## Zavisnosti i pretpostavke

- `ImportService` je singleton (`get_import_service()`)
- Stanje iz prethodnog importa dostupno je u `self.last_import_*` atributima
- Strategy registry (`importers/strategy_registry.py`) je zadužen za konkretno parsiranje

## Pravila i granice

4-koračni redoslijed je fiksiran — redoslijed je bitan:

| Korak | Akcija | Zašto mora biti ovaj redoslijed |
|-------|--------|--------------------------------|
| 1 | `_try_combine_with_previous()` | Kombinovanje ima prioritet — ako je par spreman, ne treba detekcija |
| 2 | `_try_import_as_packing_list()` (samo PDF) | Mora biti **prije** registry-a jer registry ne zna šta je "packing list" |
| 3 | `registry.import_file()` | Standardno parsiranje |
| 4 | `_save_import_state()` | Uvijek posljednje — tek kad znamo rezultat |

## Zašto ovako

ImportService je uveden kao sloj iznad registry-a jer registry ne može pamtiti stanje između dva poziva. Kombinovanje Excel+PDF je inherentno stateful (korisnik importuje jedan pa drugi fajl), pa je memorija neophodna.
