# Faktura 3-layer cleanup/migracioni manifest

Datum: 2026-07-30  
Grana: `windows`  
Status: manifest za buduće faze, bez izmjena produkcionog koda

## Cilj

Ovaj manifest definiše kako bezbjedno nastaviti migraciju Faktura taba iz legacy `FakturaView._on_*` handlera u stvarni 3-layer model. Svrha nije brisanje sada, nego jasno razdvajanje:

- šta je već javni ulaz;
- šta legacy handler još radi;
- šta mora preći u Service/Controller prije uklanjanja;
- koji testovi i E2E potvrde su obavezni.

Scope ovog manifesta je ručni toolbar i Agent pipeline za četiri pametna procesa:

- `Provjeri`
- `Auto-popuni`
- `Izračunaj mase`
- `Kreiraj Naimenovanja`

Import/export, dodavanje/brisanje/čišćenje stavki i kontekstni meni nisu predmet ovog manifesta.

## Trenutno stanje poslije stabilizacije

| Proces | Ručni UI ulaz | Agent ulaz | Trenutni izvršni put | Status |
| --- | --- | --- | --- | --- |
| Provjeri | `validate_requested` | `validate(auto=True)` | ručno: Controller/Service; auto: legacy adapter | djelimično migrirano |
| Auto-popuni | `auto_fill_requested` | `auto_fill(auto=True)` | javni adapter → legacy View | signal stabilizovan, logika nije migrirana |
| Izračunaj mase | `calculate_masses_requested` | `calculate_masses(auto=True)` | javni adapter → legacy View | signal stabilizovan, logika nije migrirana |
| Kreiraj Naimenovanja | `create_naimenovanja_requested(False)` | `create_naimenovanja(auto=True)` | javni adapter → legacy View | signal stabilizovan, Controller create nije paritetan |

Root i `dist_client` za `gui/tabs/faktura_tab.py` i `gui/tabs/faktura_view.py` moraju ostati sadržajno identični dok se ne donese drugačija produkciona odluka.

## Invarijante koje se ne smiju slomiti

1. `draft_uid` mora stići do tarifnog učenja (`TariffFacade.learn_from_draft(..., draft_uid=...)`).
2. Rub.31 i ASYCUDA ograničenja ostaju netaknuta; ovaj refaktor ne smije promijeniti XML izlaz.
3. `Auto-popuni` ne smije upisivati povlastice.
4. `Izračunaj mase` mora zadržati per-invoice raspodjelu i punu preciznost težina.
5. `Kreiraj Naimenovanja` mora zadržati split draftove, preflight, PE/header sync, reload tabova i ASYCUDA 99 limit.
6. Agent pipeline mora i dalje koristiti javne metode prije privatnih fallback-a.
7. Privatni `_on_*` fallback-i se ne brišu dok svi testovi i korisnički E2E ne potvrde paritet.

## Manifest po procesu

### 1. Provjeri

Trenutni javni ulazi:

- ručno dugme: `FakturaView._emit_validate_requested()` → `validate_requested`
- `FakturaTab.validate(auto=True)`
- `FakturaView.validate(auto=True)`
- Agent pipeline: `fw.validate(auto=True)` prije `_on_validate_all(auto=True)` fallback-a

Legacy handler:

- `FakturaView._on_validate_all(auto=False)`

Šta legacy handler još radi:

- sinhronizuje tabelu u draft;
- određuje selekcijski scope;
- koristi `ValidationService`/cache i Qt bojenje;
- pokreće istorijsku tarifnu provjeru;
- u auto modu vraća `(ok, error_count, warning_count)`;
- u ručnom modu prikazuje sažetak i dijaloge.

Već migrirano:

- ručni `Provjeri` ide kroz `FakturaTab._on_validate_requested`;
- osnovna validaciona boja je u `ValidationService`;
- handler koristi `blockSignals`.

Preostala migracija:

- izjednačiti auto put sa Controller/Service putem bez promjene `HistoricalValidationWorker` tajminga;
- jasno razdvojiti validacioni rezultat od GUI poruka;
- sačuvati selekcijski scope i `validation_cache` semantiku.

Testovi prije brisanja `_on_validate_all`:

- karakterizacioni test ručno `Provjeri` za all i selekciju;
- auto pipeline test sa 0 grešaka, upozorenjima, kritičnim greškama i izuzetkom;
- test čekanja istorijske validacije;
- test da nema `itemChanged` spam-a;
- E2E: uvoz realne fakture → ručna validacija → puna automatizacija.

Brisanje dozvoljeno tek kada:

- Agent pipeline više ne koristi `_on_validate_all` fallback;
- `FakturaView.validate` i `FakturaTab.validate` idu kroz isti kontrolisani API;
- korisnik potvrdi isti rezultat na realnim fakturama.

### 2. Auto-popuni

Trenutni javni ulazi:

- ručno dugme: `auto_fill_requested`
- `FakturaTab.auto_fill(auto=True/False)`
- `FakturaView.auto_fill(auto=True/False)`
- Agent pipeline: `fw.auto_fill(auto=True)` prije `_on_auto_fill(auto=True)` fallback-a

Legacy handler:

- `FakturaView._on_auto_fill(auto=False)`

Šta legacy handler još radi:

- pravi undo snapshot;
- popunjava osnovna polja;
- poštuje selekcijski scope i vraća selekciju;
- određuje supplier/exporter;
- koristi `TariffFacade`;
- pravi preview i commit prijedloga;
- poštuje threshold `min_similarity=0.92`;
- prikazuje dijaloge i rezultat;
- reloaduje tabelu i status bar;
- emituje `data_changed`/dirty;
- sinhronizuje decision state nakon auto-popune.

Preostala migracija:

- izdvojiti čistu auto-fill orkestraciju u Service koji ne zna za Qt;
- ostaviti View samo za selekciju, dijalog, progress i render;
- Controller treba da prima scope/redove i vraća strukturisan rezultat;
- preview i commit moraju ostati isti proračun, bez ponovnog računanja.

Testovi prije brisanja `_on_auto_fill`:

- selektovani redovi vs sve stavke;
- stavke sa postojećom tarifom se preskaču;
- PE1/PE2/PE3 ne smije dobiti povlasticu preko auto-fill-a;
- preview rezultat mora biti isti kao commit;
- result summary mora razlikovati matched/unmatched/skipped;
- Agent pipeline partial status kada ostanu stavke bez tarife.

Brisanje dozvoljeno tek kada:

- `FakturaTab.auto_fill` ne delegira na `_on_auto_fill`;
- `FakturaView.auto_fill` je tanki adapter bez poslovne logike;
- korisnik potvrdi ručni `Auto-popuni` na realnim fakturama sa selekcijom i bez selekcije.

### 3. Izračunaj mase

Trenutni javni ulazi:

- ručno dugme: `calculate_masses_requested`
- `FakturaTab.calculate_masses(auto=True/False)`
- `FakturaView.calculate_masses(auto=True/False)`
- Agent pipeline: `fw.calculate_masses(auto=True)` prije `_on_calculate_masses(auto=True)` fallback-a

Legacy handler:

- `FakturaView._on_calculate_masses(auto=False)`

Šta legacy handler još radi:

- čita toolbar bruto/neto polja;
- parsira težine;
- koristi `group_lines_by_invoice`, `normalized_invoice_weights`, `MassCalculator`;
- radi per-invoice raspodjelu;
- tretira stavke bez broja fakture;
- ima suspicious fallback guard;
- prikazuje warning/question dijaloge;
- reloaduje tabelu, status bar, dirty/data_changed;
- vraća `True/False` ugovor za Agent pipeline.

Preostala migracija:

- parsiranje toolbar ulaza i formatiranje ostaju u View/adapteru;
- odluka i računanje treba u Service/Controller;
- fallback za stavke bez invoice number mora imati eksplicitan policy objekt;
- return ugovor mora razlikovati: uspjeh, benigni no-op, korisnik odbio, greška.

Testovi prije brisanja `_on_calculate_masses`:

- per-invoice raspodjela za više faktura;
- toolbar neto fallback kada fakture nemaju neto;
- stavke bez invoice number;
- suspicious fallback sa korisničkim Yes/No;
- auto mode bez modalnih dijaloga;
- puna preciznost i korekcija zbirnog ostatka.

Brisanje dozvoljeno tek kada:

- Agent pipeline više ne zavisi od boolean nijansi legacy handlera;
- ručni i auto tok daju isti rezultat na fakturama sa jednom i više faktura;
- korisnik potvrdi realni obračun masa.

### 4. Kreiraj Naimenovanja

Trenutni javni ulazi:

- ručno dugme: `create_naimenovanja_requested(False)`
- `FakturaTab.create_naimenovanja(auto=True/False)`
- `FakturaView.create_naimenovanja(auto=True/False)`
- Agent pipeline: `fw.create_naimenovanja(auto=True)` prije `_on_create_naimenovanja(auto=True)` fallback-a

Legacy handler:

- `FakturaView._on_create_naimenovanja(auto=False)`

Šta legacy handler još radi:

- čuva/restaurira geometriju prozora;
- disable/restore dugmeta;
- nudi split po zemljama kada treba;
- obrađuje sve split draftove ili trenutni draft;
- radi preflight dijalog;
- koristi `CreateNaimenovanjaService.create_smart_group`;
- zapisuje tarifno učenje preko `TariffFacade.learn_from_draft(..., draft_uid=...)`;
- prikazuje ASYCUDA 99 overflow poruku;
- dirty/data_changed;
- sinhronizuje PE i inspection dokumente u header;
- reloaduje Faktura tabelu;
- reloaduje Naimenovanja i Zaglavlje tab;
- emituje `naimenovanja_created`;
- čisti import service memory.

Zašto Controller create put još nije paritetan:

- Controller trenutno pokriva osnovno kreiranje i `draft_uid` učenje, ali ne pokriva kompletan View workflow;
- zato je ručni signal handler namjerno vraćen na javni legacy adapter, ne na Controller create.

Preostala migracija:

- izdvojiti split/preflight/workflow orkestraciju iz View-a;
- Controller mora postati vlasnik flow-a, View samo prikazuje dijaloge i refresh;
- reload tabova treba postati eksplicitni post-action event, ne direktna pretraga main_window-a iz View-a;
- import service cleanup treba biti jasno definisan post-create hook;
- `TariffFacade.learn_from_draft` i `draft_uid` ostaju obavezna invarijanta.

Testovi prije brisanja `_on_create_naimenovanja`:

- no-lines vraća False bez kreiranja;
- korisnik odustaje na preflight-u;
- jedna deklaracija, više deklaracija, split po zemljama;
- ASYCUDA 99 overflow;
- PE/header sync;
- Naimenovanja/Zaglavlje reload;
- `draft_uid` stiže do učenja;
- import service memory cleanup;
- Agent auto mode bez ručnih modalnih dijaloga osim eksplicitne deklarantske potvrde iz pipeline-a.

Brisanje dozvoljeno tek kada:

- Controller create put pokriva sve stavke iz liste iznad;
- postoje paritetni testovi za root i `dist_client`;
- korisnik potvrdi E2E: uvoz realne fakture → mase → auto-fill → validacija → kreiranje naimenovanja → pregled u Naimenovanja/Zaglavlje.

## Faze preporučene za dalje

### Cleanup Faza A — zaključavanje trenutnog stanja

Bez produkcionih izmjena.

- proširiti characterization testove za četiri javna ulaza;
- dodati root/dist_client paritet test ako nije već u relevantnoj listi;
- dokumentovati sve privatne fallback pozivaoce kroz `rg`.

Izlaz: test-only commit.

### Cleanup Faza B — mase u Service/Controller

Najbolji prvi kandidat za dublju migraciju jer je poslovno ograničeniji od kreiranja naimenovanja.

- definisati `CalculateMassesRequest/Result`;
- Service računa, View samo daje toolbar ulaze i prikazuje dijalog;
- zadržati legacy adapter do E2E potvrde.

Izlaz: ručni i Agent `calculate_masses` idu kroz novi servis, `_on_calculate_masses` postaje wrapper.

### Cleanup Faza C — auto-fill u Service/Controller

Srednji rizik.

- izdvojiti target line selection, preview, commit, result summary;
- decision sync ostaje post-action hook;
- validirati da preview i commit ostaju identični.

Izlaz: `_on_auto_fill` postaje View wrapper.

### Cleanup Faza D — create naimenovanja workflow

Najveći rizik.

- tek nakon B/C;
- raditi u više podfaza;
- ne aktivirati Controller create kao produkcioni put dok ne pokrije legacy workflow.

Izlaz: Controller workflow ima paritet; legacy View create handler može biti kandidat za brisanje.

### Cleanup Faza E — uklanjanje fallback-a

Samo nakon korisničkog E2E.

- ukloniti privatne fallback pozive iz Agent pipeline-a;
- zatim privatne `_on_*` metode koje više nemaju pozivaoce;
- koristiti `gitnexus_impact`, `rg`, test suite i ručni E2E prije svakog brisanja.

## Zabranjeno za cleanup bez posebne dozvole

- Brisati `_on_create_naimenovanja` prije paritetnog Controller workflow-a.
- Brisati Agent fallback-e prije potvrde da svi runtime objekti imaju javne adaptere.
- Premještati XML/Rb.31 logiku u ovoj cleanup seriji.
- Mijenjati `CreateNaimenovanjaService.create_smart_group` grupisanje.
- Mijenjati `TariffFacade.learn_from_draft`/ledger ponašanje.
- Mijenjati pravila povlastica ili EUR.1/PE dijaloge.

## Minimalna E2E kapija prije bilo kakvog brisanja

Na realnim fakturama korisnik treba potvrditi:

1. ručni `Auto-popuni` bez selekcije;
2. ručni `Auto-popuni` sa selektovanim redovima;
3. ručni `Izračunaj mase` za jednu fakturu;
4. ručni `Izračunaj mase` za više faktura;
5. ručni `Kreiraj Naimenovanja`;
6. puna automatizacija do kreiranja naimenovanja;
7. pregled Naimenovanja i Zaglavlje taba poslije kreiranja;
8. XML export smoke test.

## Zaključak

Trenutni sistem je stabilizovan za signalni ulaz, ali nije spreman za agresivno brisanje legacy handlera. Najsigurniji redoslijed je:

1. zaključati paritet testovima;
2. migrirati mase;
3. migrirati auto-fill;
4. tek onda raditi create-naimenovanja workflow;
5. cleanup fallback-a i privatnih metoda ostaviti za posljednju, posebnu granu.
