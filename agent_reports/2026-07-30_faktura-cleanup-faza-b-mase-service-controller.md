## Datum

2026-07-30

## Agent

Codex

## Scope

- `services/faktura/mass_workflow_service.py`
- `services/faktura/models.py`
- `gui/tabs/faktura_controller.py`
- `gui/tabs/faktura_tab.py`
- `gui/tabs/faktura_view.py`
- `dist_client/...` paritet kopije istih modula
- `tests/unit/test_faktura_mass_workflow_service.py`
- `tests/unit/test_faktura_controller.py`
- `docs/context/history.md`

## Status izvora

Aktivni izvori: `docs/CONTEXT.md`, `project_rooms/2026-07-30_faktura-cleanup-migracioni-manifest.md`, Cleanup Faza A report.

## GitNexus impact

Prije izmjene pregledan je kontekst za root `FakturaView._on_calculate_masses`. GitNexus je pokazao da je direktni pozivalac javni `FakturaView.calculate_masses`, bez indeksiranih execution flow-ova. Nakon izmjene `gitnexus_detect_changes(scope=unstaged)` prijavio je LOW rizik i 0 affected processes. Izlaz uključuje i ranije nepovezane lokalne izmjene, ali scope commita je ograničen na Fazu B.

## Šta je urađeno

- Dodati `CalculateMassesRequest` i `CalculateMassesResult`.
- Dodan `MassWorkflowService` koji preuzima per-invoice računanje masa.
- `FakturaController` dobio `calculate_masses_for_draft`.
- `FakturaTab.calculate_masses` sada ide kroz View javni adapter uz Controller.
- `FakturaView.calculate_masses` koristi servisni rezultat; `_on_calculate_masses` je kompatibilni wrapper.
- Root/dist_client paritet proširen na `services/faktura/mass_workflow_service.py`.
- Dodati servisni testovi za ključne edge case-ove.

## Zašto je urađeno

Manifest za cleanup je označio mase kao najbolji prvi kandidat za stvarnu migraciju jer je poslovno ograničeniji od auto-fill i create-naimenovanja workflow-a. Cilj je smanjiti poslovnu logiku u View-u bez brisanja fallback-a prije E2E potvrde.

## Kako je urađeno

Servis prima draft i neutralni request, koristi postojeće `weight_guards` i `MassCalculator`, pa vraća strukturisan rezultat sa statusom, brojem ažuriranih/preskočenih stavki, fakturama bez težina, mismatch nalazima i fallback stanjem. View je ostao vlasnik toolbar parsiranja, modalnih pitanja i poruka.

## Šta nije dirano

- Nije mijenjan `MassCalculator`.
- Nisu mijenjana pravila Rub.31/XML.
- Nisu mijenjana pravila povlastica/EUR.1.
- Nije brisan Agent fallback.
- Nisu dirane nepovezane lokalne izmjene u worktree-u.

## Verifikacija

- `python -m py_compile ...` za izmijenjene root/dist/test fajlove — OK
- Ciljano: `python -m pytest tests/unit/test_faktura_mass_workflow_service.py tests/unit/test_faktura_controller.py tests/unit/test_mass_calculator.py tests/unit/test_weight_guards.py -q` — 64 passed
- Šire: Faktura/Agent skup uz `-m "not integration"` — 153 passed, 2 deselected

## Pronađeni problemi

Prvi test run je pao na root/dist_client paritetu, jer je root promjena bila ispravna ali dist kopija nije bila sinhronizovana. Sinhronizovani su samo fajlovi iz ovog scope-a i novi servis je dodat u paritet listu.

## Konflikti / kontradiktorni izvori

Nema kontradikcije. Manifest nalaže da legacy fallback ostane do E2E potvrde; zato `_on_calculate_masses` nije obrisan.

## Commitovi

| Hash | Poruka |
| --- | --- |
| 2009552 | `refactor(faktura): prebaci mase u service controller tok` |

## Rizici / ograničenja

Ovo je unutrašnja migracija. Iako su testovi zeleni, ručni E2E za jednu i više faktura ostaje potreban prije bilo kakvog brisanja fallback-a u kasnijoj fazi.

## Potreban follow-up

Cleanup Faza C: auto-fill migracija u Service/Controller, uz preview/commit paritet testove.

## Potrebna korisnička potvrda

Korisnik treba ručno potvrditi `Izračunaj mase` na realnoj fakturi sa jednom fakturom i na batch/multi-faktura slučaju.
