## Datum

2026-07-24

## Agent

Codex

## Scope

Faza 5 jedinstvenog import workflow plana: `services/import_workflow/apply_models.py`,
`services/import_workflow/apply_service.py`, mirror u `dist_client/services/import_workflow/`,
`tests/unit/test_import_workflow_apply.py`, `docs/CONTEXT.md` i
`project_rooms/2026-07-24_import-workflow-faza5-atomic-apply.md`.

## Status izvora

Aktivni izvori: `docs/CONTEXT.md`, plan
`docs/architecture/JEDINSTVENI_IMPORT_WORKFLOW_IMPLEMENTATION_PLAN.md`, prethodni commit
Faza 2-4 korekcija `228e0aa` i agent report
`agent_reports/2026-07-24_import-workflow-faze2-4-korekcije.md`.

## GitNexus impact

`DeclarationDraft` impact je CRITICAL: 245 pogođenih simbola, 140 direktnih importa.
Model nije mijenjan, ali novi servis pise u njegova kljucna polja (`invoice_lines`,
`invoice_weights`, `source_files`, `warnings`, header i `dirty`).

`MassCalculator` impact je LOW: 5 pogođenih simbola, 3 direktna importa.
`invoices_to_apply` impact je LOW: nema aktivnih pozivalaca jer je workflow jos u
pripremnom sloju.

`gitnexus_detect_changes(scope=staged)` prijavio je 7 fajlova, ali nove Python simbole nije
mapirao u `changed_symbols`; ovo je zabiljezeno kao ogranicenje alata.

## Šta je urađeno

Dodana je Faza 5:

- `ImportApplyResult` model za strukturisan rezultat primjene;
- `apply_import_plan(draft, plan, decisions)` kao neutralni servisni ulaz;
- ADD/REPLACE/SKIP primjena preko `invoices_to_apply()`;
- per-invoice `invoice_weights`;
- kopiranje linija prije upisa u draft;
- primjena header polja samo kada su prazna;
- primjena povlastica samo iz eksplicitnog `OriginDialogResponse.dialog_data`;
- `source_files`, warnings i `dirty` stanje;
- rollback preko snapshot-a svih draft polja osim callback liste.

## Zašto je urađeno

Rucni, batch i Agent import treba da zavrse u istom servisnom ulazu. Bez Faze 5 bi svaka
migracija UI toka opet morala sama mijenjati draft, sto bi vratilo paralelne poslovne
tokove koje ovaj plan uklanja.

## Kako je urađeno

Servis prima pripremljen `ImportPlan` i validirane `UserDecisions`, poziva
`validate_decisions()` i `invoices_to_apply()`, zatim primjenjuje fakture na draft. Za
tezine koristi postojeci `MassCalculator`, a za invoice kljuceve
`services.faktura.weight_guards.normalize_invoice_key`.

## Šta nije dirano

Nisu dirani `FakturaView`, Agent controller, parseri, PE/EUR dijalozi, UI refresh, stvarni
GUI Undo manager ni `DeclarationDraft` model. Faza 5 ne mijenja vidljivo ponasanje aplikacije
dok Faze 6-8 ne prebace pozivaoce na novi servis.

## Verifikacija

- `python -m pytest tests/unit/test_import_workflow_apply.py tests/unit/test_import_workflow_adapters.py tests/unit/test_import_workflow_prepare.py tests/unit/test_import_workflow_decisions.py -q`
  - rezultat: 118 passed
- `python -m pytest tests/unit/test_import_workflow_parity.py tests/unit/test_import_workflow_adapters.py tests/unit/test_import_workflow_prepare.py tests/unit/test_import_workflow_decisions.py tests/unit/test_import_workflow_apply.py -q`
  - rezultat: 136 passed, 2 xfailed
- `python -m py_compile` za nove root i `dist_client` module
- Git pre-commit hook: py_compile OK

## Pronađeni problemi

GitNexus ne mapira nove untracked Python simbole u `detect_changes`, pa je rucna provjera
scope-a i test pokrivenost bila obavezna dopuna.

## Konflikti / kontradiktorni izvori

Plan trazi jednu Undo tacku, ali neutralni servis nema pristup GUI Undo manageru. Odluka:
Faza 5 implementira servisni rollback; GUI/controller Undo tacka ostaje za Faze 6-8.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `59c4592` | `refactor(import): uvedi atomsku primjenu plana na draft` |

## Rizici / ograničenja

Servis jos nije prikacen na stvarni import. Najveci rizik za narednu fazu je da controller
doda Undo tacku i UI osvjezavanje tacno jednom, bez ponovnog uvodjenja poslovne logike u View.

## Potreban follow-up

Faza 6: prebaciti `_on_import_finished()` na adapter -> prepare -> decisions -> apply tok.
Zatim Faza 7 batch i Faza 8 Agent.

## Potrebna korisnička potvrda

Nakon Faza 6-8 provjeriti isti fajl rucno i preko Agenta: ADD, REPLACE, partner konflikt,
PE2/EUR1, per-invoice tezine i rollback pri gresci.
