## Datum

2026-07-24

## Agent

Codex

## Scope

- `gui/tabs/faktura_view.py`
- `dist_client/gui/tabs/faktura_view.py`
- `services/import_workflow/apply_service.py`
- `dist_client/services/import_workflow/apply_service.py`
- `tests/unit/test_import_workflow_apply.py`
- `tests/unit/test_import_workflow_parity.py`
- `docs/CONTEXT.md`
- `project_rooms/2026-07-24_import-workflow-faza6-rucni-import.md`

## Status izvora

- `docs/CONTEXT.md §49-50` — aktivan: faze 2-5 jedinstvenog import workflow-a.
- `project_rooms/2026-07-24_import-workflow-faza6-rucni-import.md` — aktivan: scope lock za fazu 6.
- Stari parity testovi — aktivni kao fallback/karakterizaciona zaštita za legacy slučajeve.

## GitNexus impact

- `FakturaView._on_import_finished` (`gui/tabs/faktura_view.py`) — MEDIUM:
  10 direktnih testova, bez indeksiranih runtime procesa.
- `_apply_origin_decision` (`services/import_workflow/apply_service.py`) — LOW:
  1 direktni pozivalac (`_apply_invoice`), posredno `apply_import_plan`.
- `FakturaView._on_import_finished` (`dist_client/gui/tabs/faktura_view.py`) — LOW:
  bez direktno indeksiranih pozivalaca.
- `gitnexus_detect_changes(scope=all)` prije commita — MEDIUM:
  pogođeni očekivani procesi `apply_import_plan -> get_invoice_decision` i
  `apply_import_plan -> _first`.

## Šta je urađeno

- Obični ručni pojedinačni `ImportResult` u `FakturaView._on_import_finished()` sada ide kroz:
  `from_import_result()` → `prepare_import()` → `UserDecisions` → `apply_import_plan()`.
- Stari ručni import tok je zadržan kao `_on_import_finished_legacy()`.
- Legacy fallback ostaje za:
  - list-import/backward compatibility,
  - Assembly/Master-list tok,
  - slučajeve gdje `draft.invoice_weights` nije realan dict.
- Dodati su UI helperi za prikupljanje odluka o partner konfliktu, valuti i PE2/PE3/EUR1 dijalozima.
- `apply_service` sada razumije postojeći format PE2/EUR1 dialog data po zemlji/grupi.
- Promjene su mirrovane u `dist_client`.

## Zašto je urađeno

Ručni i Agent import su imali različite završne tokove. Faza 6 počinje ukidanje te razlike
tako što ručni pojedinačni import koristi isti neutralni servisni tok kao planirane Agent faze,
ali bez rizika po batch i Assembly tok koji još nisu migrirani.

Posebno je bilo važno ne izgubiti postojeće PE2/EUR1 ponašanje po zemlji/grupi, jer flat
povlastica za cijelu fakturu nije dovoljna kada jedna faktura ima više zemalja porijekla.

## Kako je urađeno

- `FakturaView._on_import_finished()` je pretvoren u tanak orchestrator za obični
  `ImportResult`.
- `_on_import_finished_legacy()` čuva stari kod za slučajeve van scope-a faze 6.
- View prikazuje postojeće Qt dijaloge i vraća neutralne `OriginDialogResponse` objekte.
- `apply_service._apply_origin_decision()` prvo provjerava grouped dialog format i mapira
  odluke na kopije stavki preko identiteta linije.
- Dodati su testovi za grouped origin data i realan faza 6 `ImportResult` tok.

## Šta nije dirano

- Nije migriran ručni batch import (`_process_batch_records`).
- Nije migriran Agent import.
- Nije mijenjan `DeclarationAssembly.add_invoice()` / Master-list matching.
- Nije mijenjan parser API.
- Nije mijenjan layout ili QSS taba Faktura.

## Verifikacija

- `python -m py_compile gui/tabs/faktura_view.py services/import_workflow/apply_service.py`
- `python -m py_compile dist_client/gui/tabs/faktura_view.py dist_client/services/import_workflow/apply_service.py`
- `python -m pytest tests/unit/test_import_workflow_apply.py tests/unit/test_import_workflow_adapters.py tests/unit/test_import_workflow_prepare.py tests/unit/test_import_workflow_decisions.py tests/unit/test_faktura_view_provjeri_nakon_uvoza.py tests/unit/test_import_workflow_parity.py -q`
  - rezultat: 142 passed, 2 xfailed
- Pre-commit hook: py_compile staged `.py` fajlova — OK.

## Pronađeni problemi

- MagicMock karakterizacioni testovi presretali su helper metode preko `self`; zato su
  ključni helper pozivi u novom orchestratoru pozvani preko `FakturaView.<method>(self, ...)`.
- Grouped PE2/EUR1 mapping mora uključiti `zemlja_porijekla` u identitet linije; inače dvije
  slične stavke mogu kolidirati.
- `dist_client` ima postojeći UI drift u `faktura_view.py`; mirror je zato urađen ciljano,
  bez kopiranja cijelog root fajla.

## Konflikti / kontradiktorni izvori

Nema aktivnih kontradikcija. Faza 6 namjerno ne dira Assembly tok, iako se metoda nalazi u
istoj ulaznoj tački, jer faza 5 servis nema Assembly matching API.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `f6465f6` | `refactor(import): povezi rucni import sa jedinstvenim tokom` |

## Rizici / ograničenja

- Obični ručni pojedinačni import je migriran, ali batch i Agent još mogu imati staru logiku
  dok se ne urade naredne faze.
- Origin odluke se mapiraju preko identiteta linije. Ako parser proizvede dvije potpuno
  identične stavke u istoj zemlji i grupi, obje svakako pripadaju istoj odluci; ako budu
  potrebne strožije garancije, treba uvesti stabilni privremeni line UID u prepare fazi.

## Potreban follow-up

- Faza 7: migrirati Agent import na isti `apply_import_plan()` tok.
- Faza 8: migrirati ručni batch import ili izričito razdvojiti batch-only pravila.
- Kasnije: razmotriti eksplicitnu Assembly podršku u zajedničkom servisu.

## Potrebna korisnička potvrda

- Ručno provjeriti obični pojedinačni import jedne PDF/Excel fakture iz aplikacije.
- Ručno provjeriti PE2/EUR1 dijalog na fakturi sa zemljom porijekla.
- Ručno provjeriti da Master-list/Assembly import i dalje ide starim tokom.
