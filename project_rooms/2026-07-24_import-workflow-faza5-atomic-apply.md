# Import workflow Faza 5 — atomska primjena

## Cilj

Uvesti servis koji primjenjuje vec pripremljen i korisnicki potvrdjen `ImportPlan`
na `DeclarationDraft` kao jednu atomsku operaciju. Servis mora vratiti strukturisan
rezultat, podrzati rollback i ne smije pozivati Qt/UI.

## Pogođeno

GitNexus impact za `DeclarationDraft` je CRITICAL: 245 pogođenih simbola, 140 direktnih
importa. Model se ne mijenja, ali novi servis upisuje u `invoice_lines`,
`invoice_weights`, `source_files`, `warnings` i `dirty`, pa se rizik tretira kao visok.

GitNexus impact za nove import_workflow simbole moze biti nepouzdan zbog ranije
evidentirane degradacije indeksa; dopuna se radi rucnom `rg` analizom i ciljanim testovima.

## Plan

1. Dodati neutralni `apply_models.py` sa `ImportApplyResult`.
2. Dodati `apply_service.py` koji prima draft, plan i odluke.
3. Koristiti `invoices_to_apply()` kao jedini filter odluka.
4. Podrzati `ADD`, `REPLACE`, per-invoice `invoice_weights`, source_files i warnings.
5. Rollback realizovati preko `deepcopy(draft)` snapshot-a i restore-a polja.
6. Dodati ciljane testove: add, replace, skip, rollback, source_files, warnings, dirty.
7. Mirrovati servis u `dist_client/services/import_workflow`.

## Šta NE dirati

Ne dirati `DeclarationDraft` model, `FakturaView`, Agent controller, parsere, PE dijaloge
ni UI osvjezavanje. Ne mijesati `draft.items` sa `draft.invoice_lines`.

## Konflikti

Plan pominje Undo tacku, ali u servisnom sloju nema neutralnog Undo managera. Faza 5 zato
vraca informaciju da je undo snapshot interno napravljen za rollback, dok stvarna GUI Undo
tacka ostaje zadatak Faza 6-8 kada controller bude orkestrirao UI.
