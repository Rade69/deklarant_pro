## Datum

2026-07-29

## Agent

Codex

## Scope

- `services/faktura/validation_service.py`
- `dist_client/services/faktura/validation_service.py`
- `gui/tabs/faktura_view.py`
- `dist_client/gui/tabs/faktura_view.py`
- `tests/unit/test_faktura_validation_service_phase3.py`
- `tests/unit/test_inline_validation_gui.py`
- `docs/CONTEXT.md`
- `project_rooms/2026-07-29_faktura-faza-3-validacija-bojenje.md`

## Status izvora

- `project_rooms/2026-07-27_faktura-3layer-refaktor-detaljni-plan.md` — aktivan fazni plan.
- `docs/CONTEXT.md` §95-§97 — aktivne kapije Faza 0-2.
- `project_rooms/2026-07-29_faktura-faza-3-validacija-bojenje.md` — kratki plan za MEDIUM/HIGH-validacioni rez.

## GitNexus impact

- `ValidationService.validate_and_get_color` — LOW, 2 direktna / 3 ukupno pogođena simbola.
- `FakturaView._validate_and_color_row` — MEDIUM, 10 direktnih / 35 ukupno pogođenih simbola.

## Šta je urađeno

- Dodan neutralni `RowValidationStyle`.
- `ValidationService.validate_and_get_style()` sada reprodukuje osnovnu View logiku bojenja.
- `validate_and_get_color()` ostaje backward-compatible wrapper.
- `FakturaView._validate_and_color_row()` delegira osnovnu odluku servisu.
- Qt primjena boje, `validation_cache`, country confidence i preference confidence ostaju u View-u.
- Root i `dist_client` su ogledani.
- Dodani Faza 3 servisni testovi i dopunjeni inline GUI testovi da koriste stvarni `InvoiceLine`.

## Zašto je urađeno

Prethodni `ValidationService` nije bio paritetan sa stvarnim GUI ponašanjem: koristio je staru paletu, nije podržavao fuzzy tarifu i nije vraćao per-cell override-e. Da bi Faza 3 bila bezbjedna, servis je prvo usklađen sa View-om.

## Kako je urađeno

Servis vraća neutralne podatke bez PySide6/Qt importa. View ostaje odgovoran za tabelu i delegate role. Time se razdvaja poslovna odluka od UI primjene bez aktiviranja novih signala.

## Šta nije dirano

- Nisu aktivirani novi Controller signalni tokovi.
- Nije mijenjano QTimer chunkovanje.
- Nije mijenjan `FakturaItemValidator`.
- Nije premješteno country/preference confidence bojenje.
- Nije rađen cleanup starog koda.

## Verifikacija

- `python -m pytest tests/unit/test_faktura_validation_service_phase3.py tests/unit/test_inline_validation_gui.py tests/unit/test_faktura_controller.py tests/unit/test_faktura_view_validacija_selekcija.py tests/unit/test_faktura_view_status_bar.py tests/unit/test_import_workflow_parity.py tests/unit/test_tariff_learning_ledger.py -q` — 69 passed.
- `python -m pytest tests/unit/test_faktura_service_phase2.py tests/unit/test_faktura_table_roundtrip.py tests/unit/test_faktura_view_provjeri_nakon_uvoza.py tests/unit/test_faktura_view_provjeri_selekcija.py tests/unit/test_historical_validation_worker.py tests/unit/test_import_workflow_parity.py tests/unit/test_tariff_learning_ledger.py tests/unit/test_faktura_validation_service_phase3.py tests/unit/test_inline_validation_gui.py tests/unit/test_faktura_controller.py -q` — 104 passed.
- `python -m pytest tests/ -q` — 1534 passed, 85 skipped, 5 xfailed, 4 failed, 1 error.

## Pronađeni problemi

Prvi test run je otkrio da su stari inline GUI testovi koristili `SimpleNamespace` umjesto stvarnog `InvoiceLine`, pa novi servisni validator nije imao sva potrebna polja. Test fixture je prebačen na `InvoiceLine`, što je bliže produkcionom toku.

## Konflikti / kontradiktorni izvori

`ValidationService` prije ove faze nije bio važeći izvor za GUI paletu. `FakturaView` ponašanje je tretirano kao autoritativno i servis je usklađen prema njemu.

## Commitovi

| Hash | Poruka |
| --- | --- |
| pending | `refactor(faktura): premjesti osnovnu validacionu boju u servis` |

## Rizici / ograničenja

Faza 3 ne završava cijelu validacionu migraciju. `FakturaView` i dalje orkestrira cache, repaint, chunkove i confidence bojenje. To je namjerno da se izbjegne veći rizik u jednom rezu.

## Potreban follow-up

Sljedeći rez može obraditi Controller chunk orkestraciju ili country/preference confidence, ali ne oboje u istom commitu.

## Potrebna korisnička potvrda

Poželjna je ručna provjera Faktura taba sa par stavki koje imaju: validnu tarifu, nedostajuću tarifu, nedostajuću zemlju i fuzzy tarifu.
