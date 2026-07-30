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

- `docs/CONTEXT.md` §99 — aktivno; ručna validacija je već aktivirana kroz signal.
- `project_rooms/2026-07-29_faktura-stvarna-3layer-migracija-i-ciscenje-plan.md` — aktivan kao širi plan, ali numeracija faza više nije potpuno jednaka stvarnom redoslijedu malih rezova.

## GitNexus impact

- `FakturaView._on_validate_all` — LOW, 2 direktna test poziva.
- `_puna_auto_pipeline` — MEDIUM, 13 direktnih pozivalaca/testova; zato je rez ograničen na javni adapter i Agent poziv, bez promjene pipeline semantike.

## Šta je urađeno

- Uveden javni `validate(auto: bool = False) -> tuple[bool, int, int]` adapter na `FakturaTab`.
- Uveden kompatibilni javni `validate(auto: bool = False)` adapter na `FakturaView`, jer Agent trenutno često dobija sam View.
- `_puna_auto_pipeline` prvo koristi `fw.validate(auto=True)`.
- Privatni `_on_validate_all(auto=True)` ostaje fallback.
- Testovi Puna automatizacija pipeline-a sada potvrđuju da se koristi `validate(auto=True)`, a ne privatni `_on_validate_all`.
- Root i `dist_client` su usklađeni.

## Zašto je urađeno

Faza 4 je aktivirala ručnu validaciju, ali Agent Puna automatizacija je i dalje zavisila od privatnog View imena `_on_validate_all`. Ovaj rez uvodi javni API bez promjene poslovnog ponašanja i omogućava kasnijim fazama da prebacuju preostale Agent/MainWindow pozive sa privatnih View metoda.

## Kako je urađeno

`FakturaTab.validate(auto=True)` delegira na postojeći automatski validation put u View-u. `FakturaView.validate(auto=True)` je privremeni kompatibilni javni adapter. Agent pipeline preferira `validate`, a stari privatni poziv koristi samo ako javni adapter ne postoji.

## Šta nije dirano

- Nije mijenjana unutrašnja logika `_on_validate_all(auto=True)`.
- Nisu mijenjani historical worker, generation token, import pipeline tajming ni validacioni kriterijumi.
- Nije uklonjen privatni `_on_validate_all` fallback.
- Nisu dirani mase, auto-popuna tarifa, naimenovanja, import ni XML.
- Nepovezane lokalne izmjene u worktree-u nisu dirane.

## Verifikacija

- `python -m pytest tests/unit/test_faktura_controller.py tests/unit/test_puna_auto_pipeline.py -q` — 36/36 passed.
- Širi Faktura/Agent validacioni skup bez integration testova — 107/107 passed, 2 deselected.
- Isti širi skup sa integration ledger testovima: 107 passed, 2 errors zbog PostgreSQL konekcije na `192.168.100.154` / circuit breaker.

## Pronađeni problemi

PostgreSQL integration ledger testovi trenutno ne mogu do servera iz aktivne konfiguracije (`192.168.100.154`). To nije regresija Faze 5, ali sprečava potpunu DB integration potvrdu dok se `.env`/server adresa ne uskladi.

## Konflikti / kontradiktorni izvori

Veliki plan naziva Fazu 5 auto-popunom tarifa, dok je stvarni prethodni rad završio ručnu validaciju kao Fazu 4. Za ovaj zadatak važi stvarni tekući redoslijed: Faza 5 je javni validation API za Agent pipeline.

## Commitovi

| Hash | Poruka |
| --- | --- |
| bf6b3e9 | `refactor(faktura): uvedi javni validation api za agent` |

## Rizici / ograničenja

Ovo je adapter faza, ne završetak migracije automatske validacije. Dok Agent u nekim putanjama dobija `FakturaView`, javni adapter mora postojati i na View-u. Kasniji cilj je da Agent koristi `FakturaTab` javni API, a privatni fallback nestane tek u cleanup fazi.

## Potreban follow-up

- Uskladiti aktivnu DB adresu za PostgreSQL integration ledger testove.
- Nastaviti premještanje Agent/MainWindow poziva na javni `FakturaTab` API.
- Kasnije otvoriti poseban rez za potpunu automatsku validaciju kroz Controller/Service bez oslanjanja na `_on_validate_all`.

## Potrebna korisnička potvrda

Pokrenuti Punu automatizaciju na jednoj stvarnoj fakturi i potvrditi da faza “Validacija stavki” radi isto kao prije: bez dodatnog modala, bez duplog čekanja i bez preskakanja historijske validacije.
