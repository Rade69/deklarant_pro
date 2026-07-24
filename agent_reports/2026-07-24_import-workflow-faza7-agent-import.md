# Faza 7 — Agent import kroz jedinstveni import workflow

## Datum

2026-07-24

## Agent

Codex

## Scope

- `gui/tabs/agent/agent_controller.py`
- `dist_client/gui/tabs/agent/agent_controller.py`
- `tests/unit/test_import_workflow_parity.py`
- `tests/unit/test_agent_controller_provjeri_nakon_uvoza.py`
- `docs/CONTEXT.md`
- `project_rooms/2026-07-24_import-workflow-faza7-agent-import.md`

## Status izvora

- `docs/CONTEXT.md` §§49-51: aktivno, korišćeno kao kanonski kontekst za faze 2-6.
- `agent_reports/2026-07-24_import-workflow-faza6-rucni-import.md`: aktivno, korišćeno za ručni import tok koji Agent sada prati.
- Stari parity testovi Agent importa: zastarjeli kao opis razlika, ažurirani da dokazuju novi paritet ponašanja.

## GitNexus impact

- Root `AgentController._on_all_completed`: MEDIUM, 11 direktnih test veza, 0 runtime execution-flow procesa.
- `dist_client` `AgentController._on_all_completed`: LOW, 0 direktnih veza, 0 runtime execution-flow procesa.
- `gitnexus_detect_changes(scope=all)`: low risk, 0 pogođenih execution-flow procesa.

## Šta je urađeno

Agent import u modovima "Uvezi u deklaraciju" i "Puna automatizacija" prebačen je sa stare per-file obrade na zajednički import workflow:

1. `FileItem` rezultati se pretvaraju u `ImportCandidate`.
2. `prepare_import()` priprema `ImportPlan` sa ADD/REPLACE/SKIP odlukama, konfliktima i origin dijalozima.
3. Agent controller skuplja UI odluke kroz postojeće `FakturaView` potvrde/dijaloge.
4. `apply_import_plan()` atomski primjenjuje stavke, header, težine i PE2/PE3/EUR1 podatke na draft.
5. Agent zadržava chat rezime, prebacivanje na Faktura tab, historijsku provjeru i EUR1 follow-up prema naimenovanjima.
6. Ista izmjena mirrovana je u `dist_client`.

## Zašto je urađeno

Pi agent je utvrdio da isti fajl može dati različite rezultate zavisno od toga da li se uvozi ručno ili preko Agenta. Najkritičnije razlike bile su kombinovanje/REPLACE logika, provjera partnera i raspodjela težina. Faza 7 uklanja paralelni Agent tok i time smanjuje rizik da se budući import fix primijeni samo na jednu rutu.

## Kako je urađeno

U `AgentController` su dodati mali helperi za:

- dohvat Faktura view-a;
- čitanje očekivanih partnera/valute bez MagicMock šuma;
- skupljanje postojećih invoice ključeva;
- pripremu plana;
- skupljanje partner/valuta/origin odluka;
- sinhronizaciju toolbar težina i expected partner cache-a nakon primjene;
- chat rezime po fakturi;
- EUR1 follow-up prema naimenovanjima.

Glavni `_on_all_completed()` sada poziva ove helper metode i neutralni `apply_import_plan()` umjesto da ručno čisti draft i obrađuje svaku fakturu zasebno.

## Šta nije dirano

- Parseri i `ProcessingWorker`.
- Agent "Analiza" mod.
- Puna automatizacija poslije uvoza, osim što sada dobija linije iz jedinstvenog toka.
- Ručni import implementiran u fazi 6.
- Dva postojeća nevezana pada u punom test suite-u.

## Verifikacija

Prošlo:

```text
python -m py_compile gui/tabs/agent/agent_controller.py dist_client/gui/tabs/agent/agent_controller.py tests/unit/test_import_workflow_parity.py tests/unit/test_agent_controller_provjeri_nakon_uvoza.py
python -m pytest tests/unit/test_agent_controller_provjeri_nakon_uvoza.py tests/unit/test_import_workflow_parity.py tests/unit/test_import_workflow_apply.py tests/unit/test_import_workflow_adapters.py tests/unit/test_import_workflow_prepare.py tests/unit/test_import_workflow_decisions.py -q
```

Ciljni pytest rezultat:

```text
140 passed
```

Puni suite je pokrenut:

```text
python -m pytest tests/ -q
```

Rezultat:

```text
1070 passed, 58 skipped, 5 xfailed, 1 failed, 1 error
```

Padovi su nevezani za fazu 7:

- `tests/test_model_benchmark.py::test_model` traži nepostojeći fixture `model_name`.
- `tests/test_xml_parser_fix.py::test_xml_parser` traži lokalni fajl `/home/radovan/Documents/Računi/1.xml`.

## Pronađeni problemi

Stari parity testovi su tvrdili da Agent ne poziva ručne helper metode. Nakon faze 7 to više nije korisna karakterizacija; testovi su prepisani da provjeravaju stvarni efekat zajedničkog toka: normalizaciju tarifa, header, mase, partner konflikt, REPLACE i ADD bez per-file čišćenja drafta.

## Konflikti / kontradiktorni izvori

Nema aktivnog konflikta. Stari testovi su tretirani kao zastarjela dokumentacija razlika koje faza 7 upravo uklanja.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `4a298e8` | `refactor(import): povezi agent uvoz sa jedinstvenim tokom` |

## Rizici / ograničenja

Faza 7 i dalje koristi postojeće Qt dijaloge iz `FakturaView`, pa ručna vizuelna provjera PE2/PE3/EUR1 dijaloga kroz Agent ostaje korisna. `dist_client` je mirrovan 1:1 za `agent_controller.py`, ali nije pokretan GUI runtime u ovoj sesiji.

## Potreban follow-up

Faza 8 može pokriti batch/list import i Assembly/Master-list specifičnosti ako se odluči da i oni uđu u neutralni workflow.

## Potrebna korisnička potvrda

Ručno provjeriti u aplikaciji:

1. Agent "Uvezi u deklaraciju" sa jednom fakturom.
2. Agent "Uvezi u deklaraciju" sa ponovnim uvozom iste fakture — očekivanje je REPLACE, ne duplikat.
3. Agent import sa konfliktom pošiljaoca/primaoca — očekivanje je potvrda prije izmjene drafta.
4. Agent import sa PE2/EUR1 scenarijem — očekivanje je isti dijalog i isti efekat kao ručni import.
