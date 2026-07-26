# Bugfix: paritet isporuke se nije upisivao — unified import workflow

## Datum
2026-07-26

## Agent
Claude (Sonnet 5)

## Scope
- `services/import_workflow/models.py` — `ImportCandidate.incoterm_code`
- `services/import_workflow/adapters.py` — `from_import_result()`, `from_file_item()`
- `services/import_workflow/plan_models.py` — `PreparedInvoice.incoterm_code`
- `services/import_workflow/prepare_service.py` — merge logika
- `services/import_workflow/apply_service.py` — `_apply_header_if_empty()`
- `gui/tabs/agent/models/file_item.py` — `FileItem.incoterm_code`
- `gui/tabs/agent/widgets/processing_worker.py` — `ProcessingWorker.run()`
- `tests/unit/test_import_workflow_adapters.py`, `test_import_workflow_prepare.py`, `test_import_workflow_apply.py`
- Svi gorenavedeni fajlovi sinhronizovani u `dist_client/`

## Status izvora
Direktan follow-up bug na `agent_reports/2026-07-26_paritet-isporuke-auto-detekcija.md`
(§70 u docs/CONTEXT.md) — korisnik je uživo testirao feature odmah nakon
implementacije i prijavio da ne radi. Ovaj izvještaj dokumentuje uzrok i
fix; §70 opis feature-a ostaje validan (parser logika je ispravna), samo
je dopunjen §71 objašnjenjem gdje se vrijednost gubila.

## GitNexus impact
- `ImportCandidate` upstream: MEDIUM (24 impacted, 8 direktno —
  `prepare_service.py`, `plan_models.py`, `adapters.py`, `faktura_view.py`,
  `decision_service.py`, `decision_models.py`, `apply_service.py`,
  `faktura_tab.py`, `agent_controller.py`). Potvrđuje da je ovo zajednički
  model za ručni i agent uvoz.
- `detect_changes(scope=unstaged)`: "critical" risk_level zbog obima
  (`ProcessingWorker.run()` je step 1 u više execution flow-ova — to je
  glavna petlja agent-processing threada, dodiruje mnogo procesa
  topološki), ali svi touched simboli potvrđeni namjerni. Jedan lažno
  pripisan simbol (`_apply_party_to_exporter`) provjeren `git diff` —
  samo pomjeren 3 linije zbog susjednog dodatka, tijelo netaknuto.

## Šta je urađeno
Korisnik je uvezao stvarnu fakturu (`1476 BIH.pdf`, Medicopharm dobavljač,
tekst sadrži "PARITET: CIP BIJELJINA") i Rb.20 "Uslovi isporuke" je ostao
prazan uprkos §70 implementaciji. Dijagnostika uživo (bez pisanja koda,
prvo debug):
1. Ekstraktovan sirovi PDF tekst — potvrđeno da linija "PARITET: CIP
   BIJELJINA" postoji na strani 5 fakture.
2. `detect_incoterm()` pozvan direktno na tom tekstu — vraća `'CIP'`
   ispravno.
3. `parse_medicopharm_pdf()` pozvan direktno na stvarnom fajlu — vraća
   `ImportResult.incoterm_code == 'CIP'` ispravno.
4. Praćenje `FakturaView` koda otkrilo DVA paralelna toka primjene uvoza:
   `_on_import_finished_legacy` (poziva `_apply_import_result_to_header`,
   popravljeno u §70) i `_on_import_finished` (unified workflow, DEFAULT
   put kad `_can_use_unified_manual_import()` vrati True — normalan
   slučaj za ručni uvoz jedne fakture).
5. Unified put ide kroz lanac `ImportResult` → `ImportCandidate`
   (`adapters.py`) → `PreparedInvoice` (`prepare_service.py`) → `draft`
   (`apply_service.py`) — nijedan od ta dva međumodela nije imao
   `incoterm_code` polje, pa se vrijednost gubila između koraka 3 i 4.
6. Isti gap identifikovan i za Agent (chat) uvoz — `FileItem` model
   (`gui/tabs/agent/models/file_item.py`) ima eksplicitan komentar da
   prenosi polja "iz ImportResult ... za _apply_import_result_to_header"
   za exporter/importer/currency, ali ne i za incoterm; `ProcessingWorker.
   run()` ga ni ne kopira sa `result` na `file_item`.

Fix: `incoterm_code` dodano na SVA 4+2 mjesta u oba lanca (ručni unified +
agent), isti "prvi neprazan pobjeđuje" / "samo ako prazno" obrazac kao
postojeći exporter/importer/currency kod na svakom koraku.

## Zašto je urađeno
Bez ovog fixa, §70 feature (auto-detekcija pariteta) bi radila SAMO u
legacy kodnom putu, koji se u praksi rijetko/nikad ne aktivira za normalan
ručni uvoz jedne fakture (unified put je default otkad je uveden
`invoice_weights` dict na draftu, što je standardno stanje). Feature bi
bila efektivno mrtva za većinu korisnika bez ovog dodatnog koraka.

## Kako je urađeno
Prateći TAČNO isti obrazac koji već postoji za `currency`/`exporter`/
`importer` na svakom sloju (nijedna nova arhitektura, samo dodavanje
polja tamo gdje analogna polja već postoje i teku kroz isti kod):
- `ImportCandidate`/`PreparedInvoice`: novo `str = ""` polje u "Partneri i
  valuta" sekciji.
- `adapters.py`: `getattr(result/file_item, "incoterm_code", "") or ""`.
- `prepare_service.py`: ista `if not incoterm_code and c.incoterm_code:`
  petlja kao za currency (prvi neprazan kandidat u grupi pobjeđuje).
- `apply_service.py`: ista `if incoterm_code and not draft.uslovi_kod:`
  provjera kao za currency.
- `FileItem`/`ProcessingWorker`: novo polje + jedna linija kopiranja,
  odmah pored postojeće `file_item.currency = ...` linije.

## Šta nije dirano
- Sama `detect_incoterm()` logika (§70) — potvrđeno ispravna, nije bio
  uzrok bug-a.
- `_apply_import_result_to_header` (legacy put, §70 fix) — već ispravan,
  nedirano.
- Preostale 2 nepovezane test greške (`test_ima_tacno_12_alata`,
  `test_svi_ocekivani_alati_postoje`) — iz tuđeg commit-a `d8de0a3`
  ("Agent V2 Faza 1 — konsolidacija alata 12→9"), sletjelog usred ove
  sesije nezavisno od mog rada. Nisu dirane.

## Verifikacija
- `python -m py_compile` na svih 14 izmijenjenih fajlova (7 root + 7
  dist_client) — čisto.
- **End-to-end reprodukcija tačnog korisničkog scenarija**: pozvano
  `parse_medicopharm_pdf()` → `from_import_result()` → `prepare_import()`
  → `_apply_header_if_empty()` direktno na stvarnom fajlu `1476 BIH.pdf`
  (korisnikova stvarna faktura iz Downloads foldera) — `draft.uslovi_kod`
  na kraju lanca ispravno `'CIP'` (prije fixa bio bi `''`).
- `pytest tests/ -k "import_workflow or prepare_service or apply_service
  or adapters" -q` — 148 passed (uklj. 7 novih testova).
- Pun test suite: 1287 passed, 85 skipped, 5 xfailed, 3 failed + 1 error
  — od toga 2 fail-a i 1 error su PRETPOSTOJEĆI/nepovezani problem
  (`test_xml_parser_fix.py`, `test_model_benchmark.py` — isti kao ranije
  u sesiji), 2 NOVA fail-a su iz tuđeg commit-a (`test_ima_tacno_12_alata`,
  `test_svi_ocekivani_alati_postoje` — nevezano za import/paritet).
- `gitnexus_detect_changes(scope=unstaged)` — "critical" po obimu
  (verifikovano namjerno), 0 iznenađujućih pogodaka.
- Sinhronizacija dist_client: `diff --strip-trailing-cr` (uz BOM-strip)
  potvrdio semantičku identičnost nakon izmjene za svih 7 fajlova (1 imao
  trivijalan pre-postojeći BOM drift).

## Pronađeni problemi
Glavni nalaz JE ovaj bug sam po sebi — feature iz prethodnog izvještaja
(§70) je bio nepotpun jer nije uzeo u obzir da FakturaView ima dva
paralelna import-apply toka. Zabilježena pouka u docs/CONTEXT.md §71 za
buduće slične auto-popune zaglavlja.

## Konflikti / kontradiktorni izvori
Nema — §70 izvještaj ostaje tačan opis feature-a, ovaj izvještaj je čist
dodatak/ispravka lanca prenosa podataka, ne revizija ranije odluke.

## Commitovi
| Hash | Poruka |
| --- | --- |
| (sljedeći commit) | `fix(importers): prenesi incoterm_code kroz unified import workflow` |
| (sljedeći commit) | `docs(report): evidentiraj bugfix za paritet u unified workflow-u` |

## Rizici / ograničenja
Nema novih — izmjena je additive (novo opciono polje na 2 dataklase +
prosljeđivanje kroz postojeće funkcije), prati dokazano ispravan obrazac
za srodna polja koja su već godinama u produkciji.

## Potreban follow-up
Korisnik treba ponovo testirati uvoz iste ili slične fakture uživo da
potvrdi da Rb.20 sad stvarno prikazuje "CIP" u Zaglavlju nakon uvoza (ova
verifikacija je urađena programski na svakom koraku lanca, ali ne i kroz
stvaran GUI klik).

## Potrebna korisnička potvrda
Da — ponoviti uvoz `1476 BIH.pdf` (ili bilo koje druge fakture sa
paritetom u tekstu) kroz aplikaciju i potvrditi da se Rb.20 "Uslovi
isporuke" u Zaglavlju sad popuni automatski.
