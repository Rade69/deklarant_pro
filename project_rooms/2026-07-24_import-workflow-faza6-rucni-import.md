# Faza 6 — ručni pojedinačni import preko jedinstvenog workflow-a

## Cilj

Migrirati obični ručni pojedinačni import u `FakturaView._on_import_finished()` na zajednički tok:
`ImportResult -> ImportCandidate -> ImportPlan -> UserDecisions -> apply_import_plan`.

## Pogođeno

- `gui/tabs/faktura_view.py::FakturaView._on_import_finished`
  - GitNexus impact: MEDIUM
  - 10 direktnih testova zavisi od starog ponašanja.
- `services/import_workflow/apply_service.py::_apply_origin_decision`
  - GitNexus impact: LOW
  - koristi ga samo `_apply_invoice`, posredno `apply_import_plan`.

## Plan

1. Zadržati postojeći tok kao legacy fallback za slučajeve koje faza 6 ne pokriva.
2. Obični `ImportResult` bez aktivne master liste provesti kroz adapter/prepare/decision/apply.
3. Korisničke odluke za partner/valutu/origin prikupiti u `UserDecisions`.
4. Proširiti apply servis da razumije postojeći PE2/EUR1 dialog format po zemlji/grupi.
5. Osvježiti tabelu, težine, status bar, poruke i historijsku validaciju kao do sada.
6. Mirror u `dist_client` samo za iste izmjene koje su potrebne runtime kopiji.
7. Pokriti testovima i pokrenuti ciljane testove.

## Šta NE dirati

- Ne mijenjati batch ručni import (`_process_batch_records`) u ovoj fazi.
- Ne mijenjati Agent import u ovoj fazi.
- Ne mijenjati Assembly/Master-list tok dok zajednički servis ne dobije eksplicitnu podršku za assembly.
- Ne mijenjati parser API.
- Ne mijenjati vizuelni layout taba Faktura.

## Konflikti

Nema kontradiktornih izvora. `docs/CONTEXT.md §50` kaže da servis primjene ne otvara Qt dijaloge; zato dijaloge prikazuje View i u servis šalje samo prikupljene odluke.
