# Jedinstveni import workflow — završne faze batch/runtime

## Datum

2026-07-24

## Agent

Codex

## Scope

- `gui/tabs/faktura_view.py`
- `dist_client/gui/tabs/faktura_view.py`
- `tests/unit/test_import_workflow_parity.py`
- `tests/unit/test_faktura_view_provjeri_nakon_uvoza.py`
- `docs/CONTEXT.md`
- `project_rooms/2026-07-24_import-workflow-zavrsne-faze-batch.md`

## Status izvora

- `docs/architecture/JEDINSTVENI_IMPORT_WORKFLOW_IMPLEMENTATION_PLAN.md`: aktivan plan.
- `docs/CONTEXT.md` §§49-52: aktivna memorija prethodnih faza.
- `agent_reports/2026-07-24_import-workflow-faza7-agent-import.md`: aktivan izvještaj Agent migracije.

## GitNexus impact

- `FakturaView._process_batch_records` root: MEDIUM, 6 direktnih veza, 0 runtime execution-flow procesa.
- `FakturaView._process_batch_records` `dist_client`: LOW, 1 direktna veza, 0 runtime execution-flow procesa.
- `FakturaView._expected_import_partners`: LOW, 1 direktna root veza, 0 runtime execution-flow procesa.
- `gitnexus_detect_changes(scope=all)`: low risk, 0 pogođenih execution-flow procesa.

## Šta je urađeno

Ručni grupni import na Faktura tabu prebačen je na isti zajednički import workflow kao ručni pojedinačni import i Agent import:

1. Batch record se konvertuje u `ImportCandidate`.
2. `prepare_import()` pravi jedan `ImportPlan` za batch.
3. Postojeći UI sloj skuplja partner/valuta/PE2/PE3/EUR1 odluke.
4. `apply_import_plan()` atomski primjenjuje stavke, mase, header i povlastice.
5. UI se osvježava jednom nakon primjene.
6. Historijska tarifna provjera se pokreće jednom nakon uspješne primjene.
7. Runtime kopija u `dist_client` je usklađena samo za ove promjene.

## Zašto je urađeno

Nakon prethodne Agent migracije ostao je ručni grupni import kao zadnji aktivni ulaz koji još ima paralelnu poslovnu obradu. Ovim je poslovni rezultat uvoza poravnat za tri glavne rute: ručni pojedinačni, ručni grupni i Agent import.

## Kako je urađeno

U `FakturaView` su dodati batch helperi:

- `_can_use_unified_batch_import`
- `_batch_record_to_import_candidate`
- `_prepare_manual_batch_import_plan`
- `_confirm_partial_batch_import`
- `_count_applied_batch_file_types`
- `_show_manual_batch_import_workflow_result`

Stara metoda je ostala kao `_process_batch_records_legacy()` i poziva se samo kada je aktivan Assembly/Master-list režim.

## Šta nije dirano

- Parseri i `ManualBatchImportWorker`.
- QThread lifecycle.
- Assembly/Master-list posebni tok.
- `dist_client` UI/stilske razlike u `faktura_view.py`.
- Poznata dva nevezana pada punog test suite-a.

## Verifikacija

Prošlo:

```text
python -m py_compile gui/tabs/faktura_view.py dist_client/gui/tabs/faktura_view.py gui/tabs/agent/agent_controller.py dist_client/gui/tabs/agent/agent_controller.py tests/unit/test_import_workflow_parity.py tests/unit/test_faktura_view_provjeri_nakon_uvoza.py
python -m pytest tests/unit/test_faktura_view_provjeri_nakon_uvoza.py tests/unit/test_import_workflow_parity.py tests/unit/test_import_workflow_apply.py tests/unit/test_import_workflow_adapters.py tests/unit/test_import_workflow_prepare.py tests/unit/test_import_workflow_decisions.py -q
```

Ciljni rezultat:

```text
145 passed
```

Puni suite:

```text
python -m pytest tests/ -q
```

Rezultat:

```text
1073 passed, 58 skipped, 5 xfailed, 1 failed, 1 error
```

Poznati nevezani problemi:

- `tests/test_model_benchmark.py::test_model` traži fixture `model_name`.
- `tests/test_xml_parser_fix.py::test_xml_parser` traži lokalni fajl `/home/radovan/Documents/Računi/1.xml`.

## Pronađeni problemi

`_expected_import_partners()` je mogao vratiti non-string vrijednosti na MagicMock self-u, što bi u `prepare_import()` padalo u `normalize_partner_name()`. Helper sada eksplicitno ignoriše non-string vrijednosti i tek onda koristi fallback iz drafta.

## Konflikti / kontradiktorni izvori

Plan traži uklanjanje duplirane logike tek nakon migracije aktivnih pozivalaca. Legacy batch i single import fallback nisu uklonjeni jer i dalje čuvaju Assembly/Master-list posebni režim koji nije pokriven neutralnim apply servisom.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `80a1335` | `refactor(import): prebaci grupni uvoz na jedinstveni tok` |

## Rizici / ograničenja

Nije rađena ručna GUI proba sa stvarnim batch fajlovima iz `najavauvoza/`. Testovi pokrivaju servisni tok, partner konflikt, REPLACE, historijsku provjeru i legacy fallback, ali stvarni korisnički PE2/PE3/EUR1 batch dijalog treba ručno potvrditi.

## Potreban follow-up

Ako se želi potpuno ukloniti legacy kod, prvo treba posebno migrirati Assembly/Master-list režim na neutralni servis uz zasebne testove.

## Potrebna korisnička potvrda

Ručno provjeriti:

1. Grupni ručni import više faktura istog partnera.
2. Ponovni grupni import iste fakture — očekivanje je REPLACE, ne duplikat.
3. Batch sa različitim pošiljaocem/primaocem — očekivanje je potvrda prije izmjene.
4. Batch sa PE2/EUR1 scenarijem — očekivanje je jedan dijalog po logičkoj fakturi.
