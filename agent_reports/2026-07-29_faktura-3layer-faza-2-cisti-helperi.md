## Datum

2026-07-29

## Agent

Codex

## Scope

- `services/faktura/faktura_service.py`
- `dist_client/services/faktura/faktura_service.py`
- `gui/tabs/faktura_view.py`
- `dist_client/gui/tabs/faktura_view.py`
- `tests/unit/test_faktura_service_phase2.py`
- `docs/CONTEXT.md`
- `project_rooms/2026-07-29_faktura-faza-2-cisti-helperi.md`

## Status izvora

- `project_rooms/2026-07-27_faktura-3layer-refaktor-detaljni-plan.md` — aktivan fazni plan.
- `docs/CONTEXT.md` §95 — Faza 0 baseline kapija.
- `docs/CONTEXT.md` §96 — Faza 1 composition root i ledger ugovor.
- `project_rooms/2026-07-29_faktura-faza-2-cisti-helperi.md` — HIGH-impact kratki plan za ovaj rez.

## GitNexus impact

- `FakturaService.parse_number` — LOW, 1 direktan pozivalac.
- `FakturaService.parse_weight_input` — LOW.
- `FakturaService.format_issue_counts` — LOW.
- `FakturaView._parse_number` — LOW, 2 direktna / 3 ukupno pogođena simbola.
- `FakturaView._parse_weight_input` — HIGH, 4 direktna / 31 ukupno pogođen simbol.
- `FakturaView._format_issue_counts` — HIGH, 1 direktan / 27 ukupno pogođenih simbola.

## Šta je urađeno

- `FakturaService` sada ima paritetno parsiranje EU/US brojeva.
- `FakturaService.format_weight()` čuva punu preciznost kao View.
- `FakturaService.format_issue_counts()` formatira sažetak kao raniji View helper.
- `FakturaView` helper-i ostaju na istim imenima, ali delegiraju u servis.
- Iste izmjene ogledane su u `dist_client`.
- Dodan `tests/unit/test_faktura_service_phase2.py`.

## Zašto je urađeno

Faza 2 treba premjestiti čistu logiku iz View-a u Service bez promjene aktivnog toka. Prvo je servis usklađen sa View ponašanjem, zatim su View metode pretvorene u compatibility wrapper-e.

## Kako je urađeno

Nije mijenjan nijedan signal, button handler, import workflow ili draft tok. Delegiranje je urađeno lokalnim importom unutar helper metoda da se izbjegne dodatni startup/circular-import rizik.

## Šta nije dirano

- Nisu aktivirani novi Controller tokovi.
- Nije mijenjan `_sync_table_to_draft` osim posrednog poziva parse helper-a.
- Nije mijenjana validaciona logika.
- Nije rađen cleanup starog koda.
- Nisu dirane nepovezane postojeće izmjene u worktree-u.

## Verifikacija

- `python -m pytest tests/unit/test_faktura_service_phase2.py tests/unit/test_faktura_controller.py tests/unit/test_faktura_table_roundtrip.py tests/unit/test_faktura_view_status_bar.py tests/unit/test_faktura_view_validacija_selekcija.py tests/unit/test_import_workflow_parity.py tests/unit/test_tariff_learning_ledger.py -q` — 78 passed.
- `python -m pytest tests/ -q` — 1529 passed, 85 skipped, 5 xfailed, 4 failed, 1 error.

## Pronađeni problemi

`FakturaService.parse_number()` je prije ovog reza bio slabiji od View helper-a: `1.234,56` se nije pouzdano parsirao. `format_weight()` je forsirao 3 decimale, što nije u skladu sa projektnim pravilom pune preciznosti.

## Konflikti / kontradiktorni izvori

Nema konflikta: View ponašanje je tretirano kao autoritativno i servis je usklađen prema njemu.

## Commitovi

| Hash | Poruka |
| --- | --- |
| pending | `refactor(faktura): prebaci ciste helpere u servis` |

## Rizici / ograničenja

Iako je promjena mala, dotaknuti su aktivni View helper-i sa HIGH blast radiusom. Testovi pokrivaju status bar, import parity, table roundtrip i ledger, ali ručni E2E ostaje poželjan prije većih vertikalnih rezova.

## Potreban follow-up

Sljedeći Faza 2 rez može obraditi dodatne read-only helper-e, ali bez miješanja sa import/validacija vertikalnim rezovima iz narednih faza.

## Potrebna korisnička potvrda

Nije obavezna za ovaj mali rez, ali korisnička provjera osnovnog uvoza fakture je korisna prije Faze 3.
