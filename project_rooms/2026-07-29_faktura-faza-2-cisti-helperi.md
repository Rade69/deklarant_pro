## Cilj

Zatvoriti mali Faza 2 rez za Faktura 3-layer migraciju: čiste broj/težina/status helper-e držati u `FakturaService`, a postojeće `FakturaView` metode pretvoriti u tanke compatibility wrapper-e bez promjene ponašanja.

## Pogođeno

GitNexus impact:

- `FakturaService.parse_number` — LOW, 1 direktan pozivalac.
- `FakturaService.parse_weight_input` — LOW, 0 direktnih pozivalaca.
- `FakturaService.format_issue_counts` — LOW, 0 direktnih pozivalaca.
- `FakturaView._parse_weight_input` — HIGH, 31 pogođen simbol; koristi se u status baru, legacy importu, brisanju i posredno u validaciji.
- `FakturaView._format_issue_counts` — HIGH, 27 pogođenih simbola; koristi ga `_update_status_bar`.

## Plan

1. Uskladiti `FakturaService` sa postojećim View ponašanjem:
   - EU/US parse brojeva;
   - težine punom preciznošću;
   - issue summary format `3 bez tarife | ... | +N tip`.
2. Ogledati isti servis u `dist_client`.
3. `FakturaView` i `dist_client/FakturaView` metode ostaviti kao compatibility wrapper-e koji delegiraju u servis.
4. Dodati testove za servisni paritet i postojeće Faktura tokove.

## Šta NE dirati

- Ne aktivirati nove signale.
- Ne mijenjati import workflow.
- Ne mijenjati `_sync_table_to_draft` semantiku.
- Ne mijenjati validaciona pravila.
- Ne dirati cleanup starog koda.

## Konflikti

Nema konflikta: View ponašanje je autoritativno, servis se usklađuje sa njim. Ako se test pokaže drugačije, View ponašanje ima prednost.
