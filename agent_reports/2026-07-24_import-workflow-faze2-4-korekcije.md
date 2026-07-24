## Datum

2026-07-24

## Agent

Codex

## Scope

`services/import_workflow/*`, mirror u `dist_client/services/import_workflow/*`,
testovi `tests/unit/test_import_workflow_adapters.py`,
`tests/unit/test_import_workflow_prepare.py`,
`tests/unit/test_import_workflow_decisions.py`, `docs/CONTEXT.md` i
`project_rooms/2026-07-24_import-workflow-faze2-4-korekcije.md`.

## Status izvora

Aktivni izvori: `docs/architecture/JEDINSTVENI_IMPORT_WORKFLOW_IMPLEMENTATION_PLAN.md`,
`docs/CONTEXT.md`, Pi agent commitovi Faza 1-4 (`64f905d` do `f52ef8c`) i Codex
revizija tih faza iz razgovora. GitNexus indeks je degradiran za nove Python simbole,
sto je vec evidentirano u `docs/CONTEXT.md`.

## GitNexus impact

`gitnexus_impact` za `prepare_import` i `invoices_to_apply` vratio je `UNKNOWN`
jer simboli nisu pronadjeni. Zbog degradiranog indeksa, promjena je rucno tretirana
kao HIGH: ovo je buduci zajednicki import tok za rucni, batch i Agent uvoz.

`gitnexus_detect_changes(scope=all)` poslije izmjena prijavio je 13 changed files,
ali `changed_symbols: []` i `risk_level: low`; rezultat je evidentiran kao nepouzdan.

## Šta je urađeno

Ispravljene su Faze 2-4 prije nastavka UI integracije:

- adapteri sada kopiraju `InvoiceLine` objekte i ne tretiraju filename fallback kao
  pouzdan broj fakture;
- priprema koristi kanonski `services.faktura.weight_guards.normalize_invoice_key`;
- isti `invoice_number` vise ne spaja fizicke fajlove u jednu fakturu bez
  `is_combined=True`;
- partner i currency konflikti nose `invoice_key`;
- `ABORT`, `SKIP_INVOICE` i `DraftOperation.SKIP` stvarno filtriraju fakture za primjenu;
- warnings/errors kandidata se propagiraju u plan.

## Zašto je urađeno

Revizija je pokazala da korisnikove odluke nisu imale poslovni efekat: faktura je mogla
biti primijenjena i nakon `SKIP_INVOICE` ili `ABORT`. Drugi veliki rizik je bilo sabiranje
stavki i tezina samo zato sto dva fajla imaju isti broj fakture, sto moze duplirati PDF/Excel
parove ako parser nije pravilno oznacio `consumed_paths`.

## Kako je urađeno

Modeli konflikata prosireni su per-invoice identitetom. `prepare_service` sada radi na
kopijama linija, koristi kanonski invoice key i oznacava duplikat u batchu kao `SKIP`.
`decision_service` skuplja partner/currency odluke po fakturi i vraca samo fakture koje
su stvarno primjenjive.

## Šta nije dirano

Nije dirana UI integracija (`FakturaView`, Agent controller), parser API, `ImportService`
niti buduci servis primjene drafta. Faza 5 i migracija stvarnih import tokova ostaju
sljedeci korak.

## Verifikacija

- `python -m pytest tests/unit/test_import_workflow_parity.py tests/unit/test_import_workflow_adapters.py tests/unit/test_import_workflow_prepare.py tests/unit/test_import_workflow_decisions.py -q`
  - rezultat: 129 passed, 2 xfailed
- `python -m pytest tests/unit/test_import_workflow_adapters.py tests/unit/test_import_workflow_prepare.py tests/unit/test_import_workflow_decisions.py -q`
  - rezultat: 111 passed
- `python -m py_compile` za sve izmijenjene root i `dist_client` module
- Git pre-commit hook: py_compile OK

## Pronađeni problemi

GitNexus nije pronasao nove simbole i zato ne smije biti jedini dokaz o riziku. Stari test
koji je branio grupisanje po istom invoice broju bio je pogresna specifikacija i promijenjen
je da brani novo pravilo.

## Konflikti / kontradiktorni izvori

Pi agentov test je tretirao isti `invoice_number` kao dovoljan za spajanje. Vazeca odluka:
`consumed_paths` i `is_combined=True` su jedini autoritativni dokaz spajanja fizickih fajlova.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `228e0aa` | `fix(import): ispravi odluke i pripremu jedinstvenog uvoza` |

## Rizici / ograničenja

Servisi jos nisu integrisani u stvarni rucni/Agent import, pa ova promjena zatvara
pripremni sloj, ali ne mijenja jos vidljivo ponasanje aplikacije. Faza 5 mora pazljivo
mapirati `PreparedInvoice` na postojece draft operacije, per-invoice tezine i PE dijaloge.

## Potreban follow-up

Nastaviti sa Fazom 5: servis primjene drafta, pa tek zatim migracija rucnog single,
rucnog batch i Agent importa na isti tok.

## Potrebna korisnička potvrda

Nakon Faze 5-8 korisnik treba provjeriti stvarni ručni i Agent import na istom paru
fajlova, posebno Excel+PDF kombinacije, partner konflikt, EUR1/PE2 dijalog i batch duplikat.
