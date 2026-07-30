# Datum

2026-07-30

## Agent

Codex

## Scope

- `gui/tabs/faktura_tab.py`
- `gui/tabs/faktura_view.py`
- `gui/tabs/agent/services/import_pipeline_service.py`
- `dist_client/gui/tabs/faktura_tab.py`
- `dist_client/gui/tabs/faktura_view.py`
- `dist_client/gui/tabs/agent/services/import_pipeline_service.py`
- `tests/unit/test_faktura_controller.py`
- `tests/unit/test_puna_auto_pipeline.py`
- `docs/CONTEXT.md`

## Status izvora

- `docs/CONTEXT.md` §96 — aktivno; `FakturaController.create_naimenovanja()` mora proslijediti `draft_uid`.
- `docs/CONTEXT.md` §100 — aktivno; Faza 5 je uvela obrazac javnog adaptera za Agent pipeline.
- `project_rooms/2026-07-29_faktura-stvarna-3layer-migracija-i-ciscenje-plan.md` — aktivan kao širi plan, ali ova faza je mali adapter rez, ne potpuna Faza 6 iz velikog plana.

## GitNexus impact

- `FakturaView._on_create_naimenovanja` — LOW, 2 direktna poziva u indeksu (`_on_export_pdf` i karakterizacioni test).
- `_puna_auto_pipeline` — MEDIUM po prethodnoj provjeri; ručno tretiran kao osjetljiv Agent tok, pa je promjena ograničena na javni adapter i fallback.

## Šta je urađeno

- Uveden javni `create_naimenovanja(auto: bool = False) -> bool` adapter na `FakturaTab`.
- Uveden kompatibilni javni adapter istog imena na `FakturaView`.
- `_puna_auto_pipeline` prvo koristi `fw.create_naimenovanja(auto=True)`.
- Privatni `_on_create_naimenovanja(auto=True)` ostaje fallback.
- Testovi Puna automatizacija pipeline-a sada potvrđuju da se koristi javni `create_naimenovanja(auto=True)`, a ne privatni `_on_create_naimenovanja`.
- Root i `dist_client` su usklađeni.

## Zašto je urađeno

Nakon Faze 5 Agent više nije zavisio od privatne validacione metode, ali je i dalje direktno pozivao privatno kreiranje naimenovanja. Ova faza uvodi javni API za taj korak, bez promjene poslovnog ponašanja i bez rizika da se zaobiđe kompletna legacy logika koja još nije paritetno prenesena u Controller.

## Kako je urađeno

`FakturaTab.create_naimenovanja(auto=True)` i `FakturaView.create_naimenovanja(auto=True)` za sada delegiraju na postojeći `_on_create_naimenovanja(auto=True)`. Agent pipeline preferira javni adapter, a fallback na privatni naziv ostaje radi kompatibilnosti.

## Šta nije dirano

- Nije mijenjana unutrašnja logika `_on_create_naimenovanja`.
- Nije prebačen split/pre-flight/PE/header/reload/ASYCUDA/import cleanup tok u Controller.
- Nije uklonjen privatni fallback.
- Nisu dirani mase, auto-popuna tarifa, import, XML ni export.
- Nepovezane lokalne izmjene u worktree-u nisu dirane.

## Verifikacija

- `python -m pytest tests/unit/test_faktura_controller.py tests/unit/test_puna_auto_pipeline.py -q` — 38/38 passed.
- Širi Faktura/Agent skup bez integration testova — 109/109 passed, 2 deselected.

## Pronađeni problemi

Nije pronađena nova regresija. Ostaje raniji uslov iz Faze 5: PostgreSQL integration ledger testovi zavise od dostupne aktivne DB adrese.

## Konflikti / kontradiktorni izvori

`FakturaController.create_naimenovanja()` postoji, ali nije paritetna zamjena za cijeli View tok. Važeća odluka za ovu fazu: javni adapter delegira na legacy View metodu dok se ne napravi zasebna, šira migracija kreiranja naimenovanja.

## Commitovi

| Hash | Poruka |
| --- | --- |
| c525c83 | `refactor(faktura): uvedi javni create naimenovanja api za agent` |

## Rizici / ograničenja

Ovo je adapter faza. Agent više koristi javno ime, ali stvarni poslovni vlasnik za auto kreiranje naimenovanja je i dalje legacy View tok. Privatni fallback smije nestati tek kada Agent bude dobijao `FakturaTab` javni API i kada Controller/Service tok paritetno pokrije sve View grane.

## Potreban follow-up

- Napraviti posebnu fazu za stvarnu Controller migraciju kreiranja naimenovanja.
- Prebacivati Agent/MainWindow da koriste `FakturaTab`, ne direktno `FakturaView`.
- Nastaviti adaptere za preostale privatne Agent pozive, najvjerovatnije mase ili auto-popunu.

## Potrebna korisnička potvrda

Pokrenuti Punu automatizaciju na stvarnoj fakturi i potvrditi da se naimenovanja kreiraju kao ranije, uključujući reload Naimenovanja/Zaglavlje tabova i eventualne PE dokumente.
