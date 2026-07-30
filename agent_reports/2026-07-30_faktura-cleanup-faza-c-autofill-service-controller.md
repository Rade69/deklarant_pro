## Datum

2026-07-30

## Agent

Codex

## Scope

- `services/faktura/auto_fill_workflow_service.py`
- `services/faktura/models.py`
- `gui/tabs/faktura_controller.py`
- `gui/tabs/faktura_tab.py`
- `gui/tabs/faktura_view.py`
- `dist_client/...` paritet kopije istih modula
- `tests/unit/test_faktura_auto_fill_workflow_service.py`
- `tests/unit/test_faktura_controller.py`
- `docs/context/history.md`

## Status izvora

Aktivni izvori: `docs/CONTEXT.md`, `project_rooms/2026-07-30_faktura-cleanup-migracioni-manifest.md`, Cleanup Faza A/B reporti.

## GitNexus impact

Prije izmjene provjeren je root `FakturaView._on_auto_fill`. GitNexus impact je LOW: direktno ga poziva javni `FakturaView.auto_fill`, bez affected execution flow-ova. Nakon izmjene `gitnexus_detect_changes(scope=unstaged)` prijavio je LOW rizik i 0 affected processes. Izlaz uključuje i ranije nepovezane lokalne izmjene, koje nisu dio commita.

## Šta je urađeno

- Dodati `AutoFillWorkflowRequest` i `AutoFillWorkflowResult`.
- Dodan `AutoFillWorkflowService` za basic-fill, skipped metadata, preview, commit/auto-populate i decision sync hook.
- `FakturaController` dobio auto-fill workflow metode.
- `FakturaTab.auto_fill` ide kroz javni View adapter uz Controller.
- `FakturaView.auto_fill` koristi servisni workflow; `_on_auto_fill` je kompatibilni wrapper.
- Root/dist_client paritet proširen na `services/faktura/auto_fill_workflow_service.py`.
- Dodati servisni testovi za dry-run preview, preview commit bez recalculation-a, auto mode i skipped details.

## Zašto je urađeno

Manifest je označio auto-fill kao sljedeći srednje rizičan cleanup nakon masa. Cilj je izvući poslovnu orkestraciju iz View-a, ali sačuvati preview/commit paritet i ne dirati pravila povlastica.

## Kako je urađeno

View i dalje bira selekciju, prikazuje progress i potvrdu korisnika. Servis računa supplier/skipped metadata, koristi `fill_basic_fields`, `TariffFacade.auto_populate_tariffs(dry_run=True)` za preview i `commit_proposals` za potvrđeni upis, bez ponovnog računanja prijedloga.

## Šta nije dirano

- Nije mijenjan `TariffMappingService` algoritam.
- Nije mijenjan `TariffFacade` API.
- Nisu mijenjana pravila povlastica/EUR.1.
- Nije brisan Agent fallback.
- Nisu dirane nepovezane lokalne izmjene u worktree-u.

## Verifikacija

- `python -m py_compile ...` za izmijenjene root/dist/test fajlove — OK
- Ciljano: `python -m pytest tests/unit/test_faktura_auto_fill_workflow_service.py tests/unit/test_faktura_controller.py tests/unit/test_tariff_mapping_service.py tests/unit/test_puna_auto_pipeline.py -q` — 63 passed
- Šire: Faktura/Agent skup uz `-m "not integration"` — 165 passed, 2 deselected

## Pronađeni problemi

`fill_basic_fields()` mora ostati prije preview-a kao u legacy toku. Zbog toga request nosi `basic_filled_count`, da servis pri commit-u ne računa basic-fill drugi put i da izvještaj korisniku ostane paritetan.

## Konflikti / kontradiktorni izvori

Nema kontradikcije. Manifest nalaže da `_on_auto_fill` ostane do korisničkog E2E; zato je ostavljen kao wrapper.

## Commitovi

| Hash | Poruka |
| --- | --- |
| pending | `refactor(faktura): prebaci autofill u service controller tok` |

## Rizici / ograničenja

Ovo ne dokazuje realni DB kvalitet tarifnih prijedloga; testovi dokazuju orkestraciju i paritet preview/commit ugovora. Ručni E2E na realnim fakturama ostaje potreban prije brisanja fallback-a.

## Potreban follow-up

Cleanup Faza D: create-naimenovanja workflow, raditi u više podfaza jer je najrizičniji dio.

## Potrebna korisnička potvrda

Korisnik treba ručno potvrditi `Auto-popuni` bez selekcije i sa selektovanim redovima na realnim fakturama.
