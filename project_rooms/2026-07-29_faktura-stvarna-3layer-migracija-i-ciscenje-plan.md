# Faktura — plan stvarne 3-layer migracije i preciznog čišćenja

## 1. Cilj

Stvarno migrirati Faktura tab na aktivni tok:

```text
View → signal → Controller → Service → rezultat → View
```

Nakon dokazane funkcionalne jednakosti precizno ukloniti zamijenjenu poslovnu
logiku, pasivni scaffold i legacy View wiring.

Plan namjerno razdvaja:

1. migraciju ponašanja bez brisanja aktivnog starog koda;
2. korisničku i automatsku potvrdu migriranog toka;
3. zasebno brisanje dokazano nepovezanog koda.

Refaktor nije završen dok stari Faktura View handleri ostaju autoritativan
produkcioni put.

## 2. Polazno stanje

Autoritativni početni commit je:

```text
9409005 feat(tarifa): implementiraj dedup ledger za usage_count po deklaraciji
```

Na `windows` su već spojeni:

- `FakturaController`;
- `FakturaTab` composition root;
- pasivni View signali;
- dio čistih metoda u `FakturaService`;
- neutralni modeli u `services/faktura/models.py`;
- root/`dist_client` paritet za ključne Faktura module.

Ovo nije aktivna 3-layer migracija:

- produkcioni Faktura View ne emituje pripremljene poslovne signale;
- dugmad i workeri direktno pozivaju stare `_on_*` View metode;
- dio `FakturaTab` handlera se vraća u privatne View metode;
- Agent Puna automatizacija direktno poziva privatne Faktura metode;
- `FakturaView` je nakon scaffolding refaktora porastao, nije smanjen.

## 3. Claudeov posljednji rad koji plan mora zaštititi

Commit `9409005` uvodi tarifni dedup ledger:

- `DeclarationDraft.draft_uid`;
- migraciju `database/migrations/013_tariff_learning_ledger.sql`;
- `TariffMappingService.learn_with_dedup()`;
- `TariffFacade.learn_from_draft(..., draft_uid=...)`;
- učenje pri ručnoj izmjeni tarife u Fakturi;
- učenje pri kreiranju naimenovanja;
- završnu idempotentnu sinhronizaciju poslije XML exporta;
- pun `dist_client/services/tariff/tariff_mapping_service.py`, čime je uklonjen
  raniji pokvareni jednolinijski shim.

### Obavezne invarijante dedup ledgera

Migracija Fakture ne smije:

- vratiti `_auto_learn_edits()` na direktni `save_mapping()`;
- pozvati `learn_from_draft()` bez `draft_uid`;
- generisati novi `draft_uid` pri reloadu, promjeni taba ili navigaciji;
- promijeniti `line_key` bez posebne migracije i testova;
- povećati `usage_count` više puta za istu stavku iste deklaracije;
- ukloniti završnu XML sinhronizaciju bez dokazane zamjene;
- automatski naučiti tarifu koja nije ručno potvrđena;
- skrivati nedostupnu ledger tabelu kao uspješno učenje.

### Operativna kapija prije refaktora

Migraciju 013 mora primijeniti PostgreSQL admin/owner nalog. Runtime nalog
`deklarant_app` namjerno nema DDL privilegije.

Prije Faze 1 mora važiti:

```text
tests/unit/test_tariff_learning_ledger.py: 9/9 passed
```

Trenutni baseline bez migracije:

```text
64 passed, 2 failed
```

Oba pada su direktno izazvana nepostojećom
`catalogs.tariff_learning_ledger` tabelom. Refaktor se ne smije koristiti da
zaobiđe ili utiša ovu operativnu kapiju.

## 4. Scope lock

### Tip promjene

Arhitektonski refaktor bez promjene poslovnog rezultata.

### Prihvatljiv ishod

Mora ostati identično:

- broj i sadržaj uvezenih faktura-stavki;
- `consumed_paths` deduplikacija;
- REPLACE/EXTEND ponašanje;
- redoslijed EUR.1/PE dijaloga;
- zvuk završetka parsiranja;
- tarifna normalizacija na najviše osam cifara;
- puna preciznost težina;
- grupiranje naimenovanja po četiri ključa;
- eksplicitna potvrda povlastice;
- multi-draft ponašanje;
- ASYCUDA limit od 99 naimenovanja;
- XML izlaz;
- tarifni dedup ledger;
- Agent Puna automatizacija do Zaglavlja;
- `data_changed`, dirty i revision semantika.

### Nivo dozvole

- rad samo u novom worktree-u i refaktor grani;
- nema direktnog rada na `windows`;
- nema automatskog mergea;
- obavezan review poslije svake faze;
- obavezni test gate prije svakog sljedećeg vertikalnog reza;
- obavezna korisnička provjera prije brisanja starog koda;
- obavezna druga korisnička provjera poslije brisanja.

### Nije dio zadatka

- redizajn GUI-ja;
- promjena palete, layouta ili teksta dugmadi;
- nova funkcionalnost Faktura taba;
- promjena importer algoritama;
- promjena unified import odluka;
- promjena tarifnog fuzzy praga;
- promjena modela povlastica;
- promjena ASYCUDA XML šeme;
- redizajn `dist_client` produkcione strukture;
- čišćenje drugih tabova;
- popravke nepovezanih bugova pronađenih usput.

## 5. Git i branch strategija

### 5.1 Grana migracije

Kreirati novi worktree iz potvrđenog čistog `windows` commita koji sadrži
`9409005` i eventualne naknadne odobrene Claude commitove:

```text
refactor/faktura-3layer-aktivna-migracija
```

Prije kreiranja evidentirati:

```text
git rev-parse windows
git status --short
git merge-base windows refactor/faktura-3layer-aktivna-migracija
```

Ne prenositi necommitovane fajlove iz `windows` radnog stabla.

### 5.2 Grana čišćenja

Tek nakon što sve migracione faze prođu automatske testove i korisnik ručno
potvrdi E2E tok, kreirati:

```text
cleanup/faktura-view-legacy
```

iz posljednjeg zelenog commita migracione grane.

Brisanje se ne radi u istim commitovima u kojima se prespaja poslovni tok.

### 5.3 Merge politika

Ni migraciona ni cleanup grana ne spajaju se u `windows` dok:

- obje ne prođu svoje acceptance kriterije;
- nema root/`dist_client` drifta;
- puna test svita nema novi pad;
- korisnik ne potvrdi stvarni Windows tok;
- završni review ne potvrdi da nema duplog izvršavanja.

## 6. GitNexus i ručni impact

GitNexus za `_on_import_finished()` trenutno prijavljuje:

```text
risk: MEDIUM
direct dependents: 14
```

Za `_on_create_naimenovanja()` prijavljuje `LOW`, ali ne vidi:

- Qt button wiring;
- Qt signale;
- `hasattr()` dinamičke pozive;
- Agent Puna automatizacija;
- dio MainWindow koordinacije.

Ručna analiza zato tretira sljedeće porodice kao HIGH:

- import i batch import;
- kreiranje naimenovanja;
- mase;
- validacija i historijska validacija;
- auto-popuna tarifa;
- item edit i tarifno učenje;
- multi-draft;
- Agent Puna automatizacija.

Prije izmjene svake postojeće metode obavezno ponoviti
`gitnexus_impact(direction="upstream")` i dopuniti ga `rg` pretragom dinamičkih
pozivalaca.

## 7. Trenutni scaffold — šta se smije iskoristiti

### Može se zadržati kao osnova

- `FakturaTab` kao composition root;
- `FakturaController` sa `get_draft_fn`;
- `services/faktura/validation_service.py`;
- `services/faktura/mass_calculator.py`;
- `services/faktura/weight_manager.py`;
- `services/faktura/weight_guards.py`;
- `services/faktura/auto_fill_service.py`;
- `services/import_workflow/`;
- `CreateNaimenovanjaService`;
- `TariffFacade`;
- postojeći QThread workeri;
- postojeći `FakturaView` render i modal helperi.

### Ne smije se automatski proglasiti važećim

`services/faktura/models.py` trenutno sadrži šest result dataclassa bez
produkcijskih pozivalaca:

- `ImportFinishedResult`;
- `MassCalculationResult`;
- `ValidationPassResult`;
- `TariffAutoFillResult`;
- `NaimenovanjaCreationResult`;
- `PartnerConsistencyResult`.

Svaki model mora biti:

1. stvarno uveden kao ugovor jednog vertikalnog reza; ili
2. uklonjen u cleanup grani.

Ne dodavati sedmi paralelni result model bez provjere postojećih.

### Scaffold koji je kandidat za uklanjanje

`FakturaService.sync_table_to_draft()` ima prazno tijelo sa `pass`.
`add_item`, `delete_item`, `clear_all` i veći dio čistih helpera nemaju aktivne
produkcione pozivaoce.

Ne popunjavati ove metode samo zato što postoje. Za svaki rez prvo odrediti
kanonski servis i ugovor; neupotrebljivi scaffold ukloniti tek u cleanup fazi.

## 8. Arhitektonski ugovori

## 8.1 View

View smije:

- kreirati i prikazivati widgete;
- čitati korisnički unos;
- emitovati namjeru;
- birati fajl kroz `QFileDialog`;
- prikazati potvrdu, upozorenje ili grešku;
- prikazati progress;
- renderovati neutralni rezultat;
- koristiti `blockSignals` pri bulk renderu;
- upravljati isključivo UI timerima.

View ne smije:

- pozivati DB;
- pozivati `TariffFacade` radi mutacije;
- kreirati naimenovanja;
- raspoređivati mase;
- odlučivati REPLACE/EXTEND;
- učiti tarife;
- primjenjivati import plan;
- mijenjati draft izvan jasno definisanog form-to-draft adaptera;
- pozivati Controller direktno.

## 8.2 Controller

Controller smije:

- primiti View signal;
- uzeti trenutni draft kroz getter;
- orkestrirati Service pozive;
- upravljati redoslijedom poslovnih koraka;
- vratiti neutralni rezultat View-u;
- emitovati završne domenske/UI koordinacione signale;
- pokrenuti postojeći worker preko jasno definisanog adaptera.

Controller ne smije:

- keširati draft;
- čitati ili pisati `QTableWidgetItem`;
- koristiti `findChild`, `widget_cache` ili geometriju;
- izvršavati SQL;
- sadržati tarifna, težinska ili XML pravila;
- zvati privatne `_on_*` View handlere;
- prikazivati `QMessageBox` ili `QFileDialog`.

## 8.3 Service

Service smije:

- primiti draft, `InvoiceLine` ili neutralni DTO;
- izvršiti poslovnu odluku;
- pozvati bazu kroz postojeći DB sloj;
- vratiti strukturirani rezultat;
- raditi transakcione mutacije drafta;
- prijaviti status `success`, `cancelled`, `needs_confirmation`, `error`.

Service ne smije:

- importovati PySide6;
- pristupati View-u ili MainWindow-u;
- prikazivati modale;
- čitati widgete;
- koristiti globalni aktivni draft;
- progutati poslovnu grešku i vratiti lažni uspjeh.

## 8.4 FakturaTab javni API

Agent, MainWindow i drugi tabovi moraju koristiti javni FakturaTab API, ne
privatne View metode.

Minimalni cilj:

```text
start_import(filepaths)
validate(scope, rows, auto)
calculate_masses(auto)
auto_fill(auto)
create_naimenovanja(auto)
load_previous_declaration(path/selection)
export_invoice(format)
replace_draft(draft)
```

Tačni potpisi se zaključavaju karakterizacionim testovima prije migracije.

## 9. Globalne invarijante događaja

Za jednu korisničku akciju mora važiti:

- najviše jedno izvršenje poslovnog servisa;
- najviše jedan završni `data_changed`;
- najviše jedan `mark_dirty()` za jednu logičku mutaciju;
- najviše jedno učenje iste tarifne stavke;
- najviše jedan EUR.1/PE modal po odgovarajućoj fakturi;
- najviše jedan završni zvuk;
- `naimenovanja_created` tačno jednom nakon uspjeha;
- otkazivanje ne proizvodi mutaciju;
- greška ne proizvodi lažni success status.

Ne emitovati novi signal na kraju starog View handlera. Prespajanje znači:

```text
stari događaj → novi signal → Controller
```

a ne:

```text
stari događaj → stari handler → novi signal → Controller
```

## 10. Faza 0 — čisti baseline i operativne kapije

### Rad

1. Primijeniti DB migraciju 013 admin/owner nalogom.
2. Potvrditi `9/9` ledger testova.
3. Kreirati migracioni worktree iz čistog `windows` commita.
4. Sačuvati pun rezultat `pytest tests/ -q`.
5. Sačuvati listu poznatih padova sa dokazom da prethode grani.
6. Pokrenuti aplikaciju iz migracione grane.
7. Obraditi najmanje dvije stvarne fakture različitih parsera.
8. Sačuvati agregirani snapshot drafta prije refaktora:
   - broj stavki;
   - fakture;
   - iznosi;
   - količine;
   - bruto/neto;
   - zemlje;
   - tarife;
   - povlastice;
   - naimenovanja;
   - attached dokumenti;
   - `draft_uid`;
   - `revision`.
9. Sačuvati XML izlaz za sadržajno poređenje bez ličnih podataka u repou.

### Obavezni testovi baseline-a

- `test_faktura_table_roundtrip.py`;
- `test_faktura_characterization.py`;
- `test_import_workflow_parity.py`;
- `test_faktura_view_provjeri_nakon_uvoza.py`;
- `test_faktura_view_validacija_selekcija.py`;
- `test_faktura_view_provjeri_selekcija.py`;
- `test_mass_calculator.py`;
- `test_weight_guards.py`;
- `test_puna_auto_pipeline.py`;
- `test_tariff_learning_ledger.py`;
- testovi EUR.1/PE dijaloga;
- testovi zvuka;
- stvarni E2E import.

### Gate

- nema neobjašnjenog pada;
- ledger testovi su zeleni;
- aplikacija se pokreće;
- snapshot i XML baseline postoje lokalno;
- root i `dist_client` imaju potvrđen paritet pogođenih modula.

### Commit

```text
test(faktura): zakljucaj baseline aktivne 3layer migracije
```

## 11. Faza 1 — zaključavanje ugovora, bez prespajanja

### Rad

1. Inventarisati svaki Faktura View signal i njegov stvarni emiter.
2. Inventarisati sve direktne Agent/MainWindow pozive privatnih metoda.
3. Definisati javni FakturaTab API.
4. Za svaki postojeći result model odlučiti `USE` ili `DELETE_LATER`.
5. Dodati rezultat statusa koji razlikuje:
   - success;
   - cancelled;
   - needs_confirmation;
   - skipped;
   - error.
6. Dodati View metode za render rezultata, bez poslovne logike.
7. Dodati signal-spy testove:
   - jedan klik → jedan signal;
   - nema duple konekcije;
   - nema automatskog emitovanja pri renderu.

### Posebno

U ovoj fazi nijedno dugme ne mijenja aktivni poslovni put.

### Gate

- ponašanje aplikacije identično baseline-u;
- javni API testiran;
- nema novog direktnog View → Controller poziva;
- Service modeli nemaju Qt tipove.

### Commit

```text
refactor(faktura): zakljucaj javne ugovore aktivne migracije
```

## 12. Faza 2 — item edit, add/delete/clear i undo/redo

Ovo je prvi aktivni vertikalni rez jer je manji od importa, a uspostavlja
kanonski obrazac signala, draft mutacije i rendera.

### Aktivni tokovi

- dodavanje stavke;
- brisanje stavke;
- čišćenje svih stavki;
- promjena ćelije;
- bulk promjena tarife;
- undo;
- redo;
- debounce validacije poslije izmjene;
- ručno tarifno učenje.

### Ciljni tok

```text
View event
→ neutralni payload
→ signal
→ FakturaController
→ Faktura item/undo servis
→ draft mutation
→ Controller result
→ View render
```

### Claude ledger zaštita

Ručna tarifna izmjena mora završiti kroz:

```text
learn_with_dedup(draft_uid, line_key, ...)
```

Ne smije postojati paralelni `save_mapping()` put za istu potvrdu.

### Metode koje se zamjenjuju, ali još ne brišu

- `_on_add_item`;
- `_on_delete_item`;
- `_on_clear_all`;
- `_on_item_changed`;
- `_on_bulk_change_tariff`;
- `_push_undo_snapshot`;
- `_undo`;
- `_redo`;
- `_auto_learn_edits`;
- `_correct_tariff_in_db`;
- `_sync_table_to_draft`;
- `_update_weights_after_deletion`.

### Gate

- jedna izmjena → jedan dirty/revision događaj;
- `blockSignals` pri renderu;
- undo/redo vraća kompletno stanje;
- delete ne remeti težine drugih faktura;
- bulk tarifa ostaje najviše osam cifara;
- ledger `usage_count` raste tačno jednom;
- korekcija tarife skida/dodaje bod prema ledger pravilima;
- Agent i MainWindow nemaju regresiju.

### Commit

```text
refactor(faktura): aktiviraj item edit i undo tok kroz controller
```

## 13. Faza 3 — tabelarna i historijska validacija

### Aktivni tokovi

- klik „Provjeri“;
- validacija selekcije;
- validacija svih redova;
- QTimer chunkovanje;
- generation token;
- bojenje ćelija;
- historijska validacija u workeru;
- dijalog tarifnih prijedloga;
- automatska provjera poslije importa.

### Ciljni tok

```text
View validate_requested
→ Controller planira scope i generation
→ ValidationService validira neutralne InvoiceLine podatke
→ Controller odbacuje zastarjeli generation
→ View blockSignals render boja
→ Controller pokreće postojeći historical worker
→ View prikazuje rezultat
```

### Invarijante

- QTimer validacija ostaje u UI event loopu;
- historical worker ostaje QThread;
- worker nikad ne dodiruje Qt widget;
- svi redovi se provjeravaju;
- scope selekcije se poštuje;
- 0 `itemChanged` događaja pri bulk bojenju;
- DB greška nije „nema prijedloga“;
- nepotvrđeni izvor se ne prikazuje;
- validacija ne mijenja tarifu bez potvrde.

### Metode koje se zamjenjuju, ali još ne brišu

- `_on_validate_all`;
- `_validation_pass_chunk`;
- `_flush_pending_validation`;
- `_validate_and_color_row`;
- `_apply_country_confidence_color`;
- `_apply_preference_confidence_color`;
- `_run_historical_tariff_validation`;
- `_on_historical_validation_finished`;
- `_on_historical_validation_error`;
- `_validation_issue_counts`;
- `_validation_issue_label`.

UI-only primjena boje može ostati u View-u pod novim javnim nazivom.

### Gate

- karakterizacioni rezultati identični;
- selekcija i full scope rade;
- nema duple validacije;
- nema debounce petlje;
- import poslije završetka pokreće validaciju tačno jednom;
- Agent `Provjeri` koristi javni FakturaTab API.

### Commit

```text
refactor(faktura): aktiviraj validaciju kroz controller i servis
```

## 14. Faza 4 — mase i weight manager

### Aktivni tokovi

- ručni klik „Izračunaj mase“;
- Agent Puna automatizacija;
- per-invoice akumulacija;
- proporcionalna raspodjela;
- stavke bez broja fakture;
- sumnjivi fallback;
- brisanje stavke;
- multi-draft.

### Ciljni tok

```text
View calculate_masses_requested
→ Controller
→ WeightGuard/WeightManager/MassCalculator
→ MassCalculationResult
→ View render težina
```

### Invarijante

- puna interna preciznost;
- prikaz koristi kanonski `_format_weight`;
- zbir bruto/neto ostaje identičan;
- bruto nije manje od neto;
- per-invoice mase se ne miješaju;
- već popunjene mase u Puna automatizaciji znače `skipped_success`, ne grešku;
- otkazivanje sumnjivog fallbacka ne mutira draft.

### Metode koje se zamjenjuju, ali još ne brišu

- `_on_calculate_masses`;
- `_distribute_invoice_weights`;
- `_accumulate_weights`;
- `_update_weights_after_deletion`;
- View-side parse težina poslovne grane.

### Gate

- svi mass/weight testovi;
- stvarna faktura sa više faktura u jednom draftu;
- Agent faza mase;
- multi-draft;
- jedan `data_changed`.

### Commit

```text
refactor(faktura): aktiviraj mase kroz controller i weight servise
```

## 15. Faza 5 — auto-popuna tarifa

### Aktivni tokovi

- ručni klik „Auto-popuni“;
- Agent Puna automatizacija;
- istorijski prijedlozi;
- local mapping;
- preview/dijalog;
- prihvatanje/odbijanje;
- auto-primijenjene i ranije odbijene tarife;
- finalni render.

### Ciljni tok

```text
View auto_fill_requested
→ Controller
→ TariffFacade/AutoFillService
→ proposal result
→ View potvrda
→ Controller commit potvrđenih prijedloga
→ View render
```

### Invarijante

- auto-popuna mijenja samo tarifni broj;
- ne upisuje povlasticu;
- ne nagađa zemlju;
- ne prikazuje prijedlog bez potvrđenog izvora;
- odbijeni prijedlozi ostaju odbijeni;
- fuzzy prag se ne mijenja;
- tarifni broj ostaje do osam cifara;
- KB učenje samo poslije eksplicitnog prihvatanja;
- ledger identitet ostaje `draft_uid`.

### Metode koje se zamjenjuju, ali još ne brišu

- `_on_auto_fill`;
- View poslovni dio obrade proposal rezultata;
- dupli lookup/commit helperi koji zaobilaze `TariffFacade`.

### Gate

- ručni i Agent tok daju isti draft rezultat;
- modal se pojavljuje najviše jednom;
- odbijanje ne mutira draft;
- nema direktnog DB poziva u View-u;
- ledger testovi i historijski tarifni testovi prolaze.

### Commit

```text
refactor(faktura): aktiviraj auto-popunu kroz controller i tariff facade
```

## 16. Faza 6 — kreiranje naimenovanja

### Aktivni tokovi

- ručni klik;
- Puna automatizacija `auto=True`;
- pre-flight dijalog;
- split po zemlji/valuti;
- ASYCUDA limit 99;
- multi-draft;
- `CreateNaimenovanjaService.create_smart_group()`;
- PE dokumenti;
- tarifno učenje;
- reload Naimenovanja i Zaglavlja;
- `naimenovanja_created`.

### Ciljni tok

```text
View create_naimenovanja_requested(auto)
→ Controller
→ pre-flight status
→ View potvrda ako je ručni tok
→ Controller
→ CreateNaimenovanjaService
→ TariffFacade.learn_from_draft(lines, draft_uid)
→ PE/header sync servis
→ Controller result
→ View/FakturaTab koordinacioni signali
```

### Claude ledger zaštita

Za svaki draft:

```text
TariffFacade.learn_from_draft(
    draft.invoice_lines,
    draft_uid=draft.draft_uid,
)
```

Ne pozivati učenje dva puta u istom toku. Završna XML sinhronizacija ostaje
idempotentna sigurnosna mreža.

### Metode koje se zamjenjuju, ali još ne brišu

- `_on_create_naimenovanja`;
- `_offer_split_by_country`;
- View dio PE/header sinhronizacije;
- direktni `_reload_naimenovanja_tab`;
- direktni Agent poziv privatne metode.

### Gate

- grupiranje po četiri ključa;
- `auto=True` bez ručnih modala;
- ručni pre-flight ostaje;
- 99 overflow ponašanje identično;
- multi-draft navigator radi;
- `naimenovanja_created` tačno jednom;
- `data_changed` tačno jednom po draftu prema zaključanom ugovoru;
- ledger ne povećava duplo usage;
- Naimenovanja i Zaglavlje se osvježe.

### Commit

```text
refactor(faktura): aktiviraj kreiranje naimenovanja kroz controller
```

## 17. Faza 7 — pojedinačni i grupni import

Ovo je najrizičniji rez i radi se tek kada su svi downstream tokovi već
dostupni kroz javni FakturaTab API.

### Aktivni tokovi

- PDF;
- Excel;
- faktura XML;
- glavna lista;
- pojedinačni import;
- više fajlova;
- unified import;
- legacy semantika;
- parser worker;
- batch worker;
- REPLACE/EXTEND;
- combined invoice;
- partner provjera;
- header autofill;
- težine;
- `consumed_paths`;
- EUR.1/PE;
- zvuk;
- validacija poslije importa;
- Agent import.

### Važna odluka

Legacy ponašanje se u ovoj fazi ne ukida. Ono se premješta iz View-a u
Controller/Service kao eksplicitna strategija:

```text
UnifiedImportStrategy
LegacyImportStrategy
```

Strategije ne smiju sadržati Qt. Controller bira strategiju po istom
`_can_use_unified_manual_import` uslovu kao baseline.

Legacy strategija se može ukinuti tek u posebnom budućem zadatku ako unified
tok dokaže punu pokrivenost svih slučajeva.

### Ciljni tok

```text
View bira fajlove
→ import_requested(filepaths)
→ Controller pokreće worker
→ worker vraća ImportResult/records
→ Controller bira strategiju
→ Service priprema neutralni plan
→ View traži samo potrebne odluke
→ Controller primjenjuje plan
→ View render/progress/modal/zvuk
→ Controller pokreće javni validation API
```

### Invarijante

- privatna `ImportService()` instanca po workeru;
- nema UI poziva iz workera;
- `consumed_paths` sprečava duplikate;
- REPLACE/EXTEND identičan;
- partner mismatch potvrda identična;
- header se popunjava samo u prazna polja;
- EUR.1/PE modal tačno jednom;
- zvuk prije prvog modalnog dijaloga poslije uspješnog parser rezultata;
- `data_changed` tačno jednom po završenom logičkom importu;
- otkazan import ne mutira draft;
- greška čisti worker reference;
- `invoice_weights` ostaje per-invoice;
- tarifni brojevi se normalizuju na ulazu.

### Metode koje se zamjenjuju, ali još ne brišu

- `_on_import_files`;
- `_on_import_pdf`;
- `_on_import_excel`;
- `_on_import_xml`;
- `_start_import`;
- `_import_multiple_files`;
- `_on_batch_progress`;
- `_on_batch_parse_error`;
- `_on_batch_done`;
- `_process_batch_records`;
- `_process_batch_records_legacy`;
- `_on_import_progress`;
- `_on_import_finished`;
- `_on_import_finished_legacy`;
- `_on_import_error`;
- `_extract_import_result_data`;
- `_get_invoice_name`;
- `_assign_invoice_name`;
- `_normalize_item_tariffs`;
- `_track_file_type`;
- `_check_partner_consistency`;
- `_is_same_combined_invoice`;
- `_apply_import_result_to_header`;
- `_sync_import_workflow_state_after_apply`;
- `_auto_handle_povlastice_agent`;
- `_postprocess_master_frigo_pairs_records`;
- `_extract_header_from_xml`.

UI prikaz, progress i modal helperi ostaju u View-u pod javnim render nazivima.

### Gate

- svi import characterization/parity testovi;
- najmanje po jedna stvarna faktura:
  - obični PDF;
  - Excel;
  - kombinovani PDF+Excel;
  - Invoice+PackingList;
  - batch;
  - faktura XML;
- consumed_paths dokaz;
- EUR.1 i PE2 scenariji;
- REPLACE i EXTEND;
- mixed zemlja/valuta;
- Agent import;
- zvuk;
- bez duplih stavki;
- sadržajni draft snapshot jednak baseline-u.

### Commit

```text
refactor(faktura): aktiviraj pojedinacni i grupni import kroz controller
```

## 18. Faza 8 — export, prethodna deklaracija i javni adapteri

### Aktivni tokovi

- Excel export;
- PDF export;
- pregled faktura;
- prethodna deklaracija;
- XML mapping import;
- MainWindow reload;
- Agent Puna automatizacija;
- multi-draft promjena.

### Ciljni tok

View bira putanju i prikazuje rezultat. Controller orkestrira. Export servis
gradi sadržaj. Drugi moduli koriste samo javni FakturaTab API.

### Metode koje se zamjenjuju, ali još ne brišu

- `_on_export_excel`;
- `_on_export_pdf`;
- `_on_export_pregled_faktura`;
- `_on_load_mappings_from_xml`;
- `_on_load_previous_declaration`;
- direktni Agent/MainWindow pozivi privatnih Faktura metoda.

### Invarijante

- export sadržajno identičan;
- otkazivanje file dijaloga nije greška;
- PDF export koji prethodno kreira naimenovanja koristi javni API;
- Puna automatizacija više ne koristi `hasattr(fw, "_on_*")`;
- drugi tabovi ne pišu direktno u Faktura widgete;
- završna XML ledger sinhronizacija ostaje;
- multi-draft koristi trenutni draft getter.

### Gate

- svi export testovi;
- sadržajno poređenje izlaza;
- Agent Puna automatizacija od importa do Zaglavlja;
- `rg` ne nalazi produkcione spoljne pozive privatnih Faktura metoda;
- MainWindow i Naimenovanja rade poslije promjene drafta.

### Commit

```text
refactor(faktura): uvedi javne adaptere za agent export i reload
```

## 19. Migracioni završni checkpoint — prije brisanja

U ovoj tački novi tok mora biti jedini aktivni produkcioni wiring, ali stari
metodni kod još postoji radi jednostavnog poređenja i rollbacka.

### Obavezne statičke provjere

```text
1. Svaki Faktura poslovni signal ima produkcionog emitera.
2. Nijedno dugme nije spojeno na zamijenjeni stari _on_* handler.
3. FakturaTab handleri ne pozivaju privatne View metode.
4. Agent/MainWindow ne pozivaju privatne Faktura metode.
5. View nema SQL/DB konekcije.
6. View nema TariffFacade mutacije.
7. Controller nema QMessageBox/QFileDialog.
8. Controller nema direktni QTableWidgetItem pristup.
9. Service nema PySide6.
10. Root i dist produkcioni moduli imaju paritet.
```

### Obavezni testovi

- svi ciljani Faktura testovi;
- svi Agent pipeline testovi;
- svi Naimenovanja testovi;
- svi Zaglavlje testovi;
- ledger 9/9;
- full `pytest tests/ -q`;
- `py_compile`;
- offscreen MainWindow smoke;
- standalone `dist_client` import;
- build test ako su pogođeni `.pyd` moduli.

### Obavezni korisnički E2E

Korisnik mora potvrditi:

1. pojedinačni PDF import;
2. grupni import;
3. EUR.1/PE dijalog;
4. ručnu izmjenu tarife;
5. „Provjeri“;
6. „Izračunaj mase“;
7. „Auto-popuni“;
8. „Kreiraj naimenovanja“;
9. Naimenovanja pregled/izmjenu;
10. XML export;
11. Punu automatizaciju;
12. multi-draft ako je primjenjiv.

Tek eksplicitna potvrda otključava cleanup granu.

## 20. Cleanup grana — precizno brisanje

Cleanup nije refaktor ponašanja. U njoj je zabranjeno dodavati novu
funkcionalnost ili mijenjati poslovni rezultat.

## 20.1 Manifest brisanja

Prije prvog delete commita napraviti tabelu:

| Stari simbol | Novi vlasnik | Produkcioni pozivaoci | Test pozivaoci | Dokaz zamjene | Odluka |
|---|---|---:|---:|---|---|
| `_on_import_finished_legacy` | LegacyImportStrategy + Controller | 0 | karakterizacija | E2E + parity | DELETE |

Svaki simbol mora imati:

- nula produkcionih pozivalaca;
- test koji pokriva novi put;
- dokumentovan novi vlasnik;
- uspješan E2E scenario;
- root/`dist_client` plan;
- mogućnost rollbacka kroz prethodni commit.

## 20.2 Redoslijed brisanja

### Cleanup A — lažni/pasivni scaffold

Ukloniti ili pretvoriti u stvarno korišćen ugovor:

- nekorišćene dataclass modele;
- `FakturaService.sync_table_to_draft()` sa `pass`;
- nekorišćene service metode bez pozivalaca;
- stare fazne komentare;
- `FakturaTab` handlere koji se vraćaju u privatni View;
- duple Controller helper implementacije koje je zamijenio kanonski servis.

Commit:

```text
refactor(faktura): ukloni neaktivni scaffold nakon migracije
```

### Cleanup B — item/validation/mass metode

Brisati po porodici:

- item edit/undo;
- validacija;
- historijska validacija;
- mase.

Poslije svake porodice pokrenuti njene ciljane testove.

Commitovi:

```text
refactor(faktura): ukloni zamijenjeni item i undo kod iz viewa
refactor(faktura): ukloni zamijenjeni validation kod iz viewa
refactor(faktura): ukloni zamijenjeni mass kod iz viewa
```

### Cleanup C — tariff i naimenovanja metode

Brisati:

- stari auto-fill tok;
- stari create-naimenovanja tok;
- duple ledger/tariff helper pozive;
- direktne header/PE sync metode koje imaju servisnu zamjenu.

Commit:

```text
refactor(faktura): ukloni zamijenjeni tariff i naimenovanja kod
```

### Cleanup D — import porodica

Brisati View implementacije importa, uključujući
`_on_import_finished_legacy`, tek kada je legacy ponašanje očuvano u neutralnoj
strategiji.

Ne brisati LegacyImportStrategy samo zato što u nazivu ima `legacy`.
Brisanje View metode i ukidanje poslovne strategije nisu ista odluka.

Commit:

```text
refactor(faktura): ukloni zamijenjeni import kod iz viewa
```

### Cleanup E — export i adapteri

Brisati:

- privatne export handlere koji više nisu spojeni;
- kompatibilne privatne View shimove;
- stare Agent `hasattr` grane;
- zastarjele testove starog wiringa.

Karakterizacione testove ne brisati ako i dalje potvrđuju poslovni rezultat;
prebaciti ih na javni FakturaTab API.

Commit:

```text
refactor(faktura): ukloni privatne adaptere i stari export wiring
```

## 20.3 Pravilo protiv agresivnog brisanja

Metoda se ne briše samo zato što `rg` nema rezultat. Dodatno provjeriti:

- `getattr`/`hasattr`;
- Qt `.connect`;
- string reference;
- `tab_factory`;
- MainWindow;
- Agent servise;
- build/spec fajlove;
- `dist_client`;
- test fixture monkeypatch;
- plugin/dinamički import;
- GitNexus kontekst.

## 20.4 Zabranjeni cleanup obrasci

- `git rm` cijele klase bez manifest pregleda;
- find/replace brisanje;
- zakomentarisanje starog koda;
- compatibility fallback koji ponovo poziva obrisani View put;
- `except Exception: pass` radi prolaska testova;
- mijenjanje očekivanja testa bez dokaza da je staro očekivanje pogrešno;
- brisanje legacy strategije bez stvarnog parser/import scenarija;
- brisanje root koda bez `dist_client` odluke u istom checkpointu.

## 21. Konačni acceptance kriteriji

Refaktor se smije označiti završenim samo ako:

- View dugmad emituju aktivne signale;
- Controller je jedini orkestrator poslovnih tokova;
- Service je jedini vlasnik poslovnih/DB pravila;
- FakturaTab je jedini javni API prema Agentu i MainWindow-u;
- nema produkcionih poziva privatnih Faktura View metoda;
- nema duplog izvršavanja;
- nema praznih scaffold metoda;
- nema nekorišćenih result modela;
- stari View poslovni kod je obrisan;
- View nema DB/TariffFacade/ImportService poslovne mutacije;
- Controller nema raw widget pristup;
- Service nema Qt;
- `draft_uid` i dedup ledger rade;
- `usage_count` se ne naduvava;
- import rezultat je jednak baseline-u;
- mase su jednake baseline-u;
- naimenovanja su jednaka baseline-u;
- XML je sadržajno jednak baseline-u;
- Agent Puna automatizacija radi;
- Naimenovanja i Zaglavlje nisu regresirani;
- root i `dist_client` su produkciono usklađeni;
- puna svita nema novi pad;
- korisnik je potvrdio pre-cleanup i post-cleanup Windows E2E;
- završni agent report sadrži manifest obrisanih simbola i commitove.

## 22. Stop kriteriji

Odmah zaustaviti fazu ako:

- broj stavki odstupa od baseline-a;
- `consumed_paths` ne ukloni duplikat;
- REPLACE zamijeni pogrešnu fakturu;
- modal ili zvuk se pojavi dvaput;
- `data_changed`/dirty se emituje u petlji;
- validacija preskoči red;
- mase izgube preciznost;
- auto-fill upiše povlasticu;
- prijedlog bez izvora postane vidljiv;
- `usage_count` poraste dvaput;
- `draft_uid` se promijeni;
- kreiranje naimenovanja promijeni grupiranje;
- Agent pipeline pozove stari privatni View metod;
- root/`dist_client` drift nastane;
- puna svita dobije novi pad;
- novi kod zahtijeva compatibility granu koja ponavlja staru poslovnu logiku.

## 23. Rollback

Svaka faza je jedan ili više malih logičkih commitova.

Kod regresije:

1. ne popravljati dodavanjem još jednog fallbacka;
2. revertovati samo commit problematičnog vertikalnog reza;
3. vratiti prethodni zeleni checkpoint;
4. dodati nedostajući karakterizacioni test;
5. ponoviti rez manjim obimom;
6. zadržati sve kasnije faze blokirane.

Cleanup commit se revertuje nezavisno od migracionog commita, što vraća stari
kod bez vraćanja aktivnog starog wiringa.

## 24. Test matrica

| Tok | Unit | Integracija | Offscreen | Stvarna faktura | Ručno Windows |
|---|---|---|---|---|---|
| item edit/undo | obavezno | — | obavezno | — | obavezno |
| ledger učenje | obavezno | prava PG tabela | — | obavezno | obavezno |
| validacija | obavezno | prava tarifa DB | obavezno | obavezno | obavezno |
| mase | obavezno | — | obavezno | obavezno | obavezno |
| auto-fill | obavezno | prava tarifa DB | obavezno | obavezno | obavezno |
| naimenovanja | obavezno | obavezno | obavezno | obavezno | obavezno |
| pojedinačni import | obavezno | obavezno | obavezno | obavezno | obavezno |
| batch import | obavezno | obavezno | obavezno | obavezno | obavezno |
| EUR.1/PE | obavezno | — | obavezno | obavezno | obavezno |
| multi-draft | obavezno | obavezno | obavezno | obavezno | obavezno |
| export | obavezno | obavezno | — | obavezno | obavezno |
| Agent puna automatizacija | obavezno | obavezno | obavezno | obavezno | obavezno |
| root/dist parity | obavezno | standalone import | — | — | build smoke |

SQLite/PostgreSQL poslovni testovi ne koriste mock baze.

## 25. Obavezni izvještaj po fazi

Svaka faza mora evidentirati:

- početni i završni commit;
- GitNexus impact;
- ručno pronađene dinamičke pozivaoce;
- aktivirani signal;
- ugašeni stari wiring;
- servisni vlasnik;
- testove;
- root/`dist_client` paritet;
- poznata ograničenja;
- šta nije dirano;
- rollback commit.

Cleanup izvještaj dodatno mora imati manifest svih obrisanih simbola.

## 26. Procjena vremena

| Faza | Procjena |
|---|---:|
| 0 — baseline i DB kapija | 5–8 h |
| 1 — ugovori i inventar | 4–6 h |
| 2 — item edit/undo/ledger | 6–9 h |
| 3 — validacija | 6–9 h |
| 4 — mase | 4–7 h |
| 5 — auto-fill | 5–8 h |
| 6 — naimenovanja | 6–9 h |
| 7 — import | 10–16 h |
| 8 — export i adapteri | 5–8 h |
| migracioni E2E/review | 4–6 h |
| cleanup A–E | 10–16 h |
| završni E2E/review | 4–6 h |
| ukupno | 69–110 h |

Procjena uključuje stvarni rad, testove, root/`dist_client` produkcioni paritet
i dva ručna korisnička checkpointa. Ne uključuje čekanje na DB admina niti
popravke nepovezanih bugova.

## 27. Preporučena odluka

Realizaciju započeti samo ako:

1. DB migracija 013 bude primijenjena;
2. Claudeov `9409005` ledger rad bude zeleni baseline;
3. novi worktree bude kreiran iz čistog odobrenog `windows` commita;
4. Faza 0 bude završena i predata na pregled prije produkcionog prespajanja;
5. korisnik prihvati da se stari kod ne briše tokom migracionih faza;
6. korisnik ručno potvrdi migraciju prije otvaranja cleanup grane;
7. merge u `windows` bude odobren tek nakon završnog cleanup E2E testa.
