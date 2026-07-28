# Faktura tab 3-layer refaktor — detaljni plan bez funkcionalne regresije

## 1. Status dokumenta

- Datum analize: 2026-07-27
- Autor plana: Pi
- Revizija plana: Codex, 2026-07-28
- Polazni dokument: Codex plan za Naimenovanja (`project_rooms/2026-07-27_naimenovanja-3layer-refaktor-detaljni-plan.md`)
- Prvobitno analizirana grana: `windows` (commit `86da0f8`)
- Ponovo provjereno stanje: `windows` (commit `c46a6ce`)
- Ovaj dokument je plan, ne odobrenje za automatski merge.
- Implementacija se ne smije raditi direktno na `windows`, `main`, `master` ili
  drugoj integracionoj grani.

### 1.1 Zaključak revizije 2026-07-28

Osnovna strategija plana je dobra, ali prvobitna LOW procjena rizika više nije
važeća. `FakturaView` i centralni render `_load_data_from_draft` imaju HIGH
impact. Implementacija zato mora imati strože fazne kapije, eksplicitni adapter
za postojeće Agent/MainWindow pozivaoce i manju završnu fazu.

Plan je ispravljen tako da:

- ne tretira čitanje QTableWidget ćelija kao Service odgovornost;
- ne tvrdi da QTimer chunk validacija radi van UI threada;
- čuva postojeći agent ugovor `_on_create_naimenovanja(auto=True)`;
- razdvaja item-edit/undo od exporta i integracionih adaptera;
- zahtijeva root i `dist_client` samostalni import test;
- ne hardkoduje budući branch base dok sve odobrene grane nisu integrisane.

## 2. Cilj

Razdvojiti postojeći `FakturaView` na View, Controller i Service sloj bez
promjene carinske poslovne logike, prikaza, redoslijeda događaja, draft
semantike, XML sadržaja ili ponašanja drugih tabova.

Primarni rezultat nije samo manji broj linija, nego:

- View nema DB pristup ni poslovne odluke.
- View prema Controlleru komunicira signalima.
- Controller orkestrira, ali ne implementira carinska pravila.
- Service nema Qt widgete, modalne dijaloge niti pristup `MainWindow`.
- Postoji samo jedna autoritativna draft referenca.
- Javni API `FakturaTab` ostaje kompatibilan.
- Root i `dist_client` ostaju sadržajno usklađeni.
- Unified import workflow (Faze 0-8 import plana) ostaje netaknut.

## 3. Obavezna strategija grane i worktreea

### 3.1 Priprema

Prije početka implementacije:

1. Završiti ili arhivirati sve aktivne izmjene koje dodiruju:
   - `gui/tabs/faktura_view.py`
   - `gui/tabs/faktura_tab.py`
   - `services/faktura/`
   - njihove `dist_client` kopije
   - testove fakture
2. Integraciona grana mora sadržavati sve odobrene izmjene. Posebno provjeriti
   status `refactor/naimenovanja-3layer`, Agent V2 i drugih grana koje mijenjaju
   direktne pozivaoce Faktura taba; plan ne daje dozvolu za njihov automatski
   merge.
3. Provjeriti da integracioni worktree nema staged refaktor izmjene.
4. Kreirati posebnu granu i poseban worktree:

```text
grana: refactor/faktura-3layer
worktree: .worktrees/faktura-3layer
base: posljednji ručno potvrđeni commit integracione windows grane u trenutku
kreiranja worktreea
```

```bash
git worktree add .worktrees/faktura-3layer \
  -b refactor/faktura-3layer windows
```

### 3.2 Pravilo jednog autora nad monolitom

Dok traje refaktor, samo jedan aktivni agent smije mijenjati
`faktura_view.py`. Drugi agenti smiju paralelno raditi testove ili
nezavisne service module samo ako im je dodijeljen tačan, nepreklapajući scope.

### 3.3 Commit strategija

Svaka faza ima zaseban commit i mora biti reverzibilna bez ručnog rastavljanja
drugih faza. Zabranjen je jedan veliki commit za cijeli refaktor.

## 4. Dokazano trenutno stanje

### 4.1 Veličina i struktura

| Komponenta | Stanje |
| --- | --- |
| `gui/tabs/faktura_view.py` | 6.329 linija |
| `FakturaView` | 148 metoda |
| `services/faktura/` | 14 servisa, 1.326 linija ukupno |
| `gui/tabs/faktura_tab.py` | 28 linija, wrapper bez Controllera |
| View signali prema gore | `naimenovanja_created`, naslijeđeni `data_changed` |
| Unified import workflow | `services/import_workflow/` (Faze 0-8 gotove) |
| Legacy metode | `_on_import_finished_legacy` (324 l.), `_process_batch_records_legacy` (116 l.) |

Brojevi linija legacy metoda moraju se ponovo izmjeriti u Fazi 0; navedene
vrijednosti su iz prvobitne analize i nisu acceptance kriterij.

### 4.2 Najvažniji blast radius

GitNexus rezultat na `windows@c46a6ce`:

- `FakturaView`: **HIGH**, 20 direktnih importera i 33 ukupno pogođena simbola.
- `_load_data_from_draft`: **HIGH**, 17 direktnih i 39 ukupno pogođenih
  simbola kroz četiri modula.
- `_on_create_naimenovanja`: graf prikazuje LOW, ali rezultat je nepotpun jer
  dinamički Agent/Qt pozivi nisu svi vidljivi u statičkom grafu.
- `_on_import_finished` i `_on_item_changed`: Qt signalne veze ne smiju se
  tretirati kao „nema pozivalaca“ samo zato što graf vraća nula upstream veza.

Za `FakturaView` i `_load_data_from_draft` obavezan je HIGH-risk handoff prije
produkcione izmjene.

`_on_import_finished` trenutno u jednom toku:

1. provjerava `_can_use_unified_manual_import`;
2. ako da → kreira ImportPlan preko `services/import_workflow`;
3. ako ne → pada na `_on_import_finished_legacy` (324 linije):
   - ekstraktuje podatke iz ImportResult;
   - provjerava konzistentnost partnera;
   - normalizuje tarifne brojeve;
   - raspoređuje težine;
   - REPLACE/EXTEND logiku za draft;
   - akumulira težine;
   - EUR1/PE2 dijalog;
   - prikazuje QMessageBox.

`_on_create_naimenovanja` (164 linije) u jednom toku:

1. provjerava split po zemljama;
2. Kreira naimenovanja kroz `CreateNaimenovanjaService`;
3. auto-učenje tarifa;
4. prikaz rezultata;
5. sinhronizacija PE dokumenata;
6. reload tabele;
7. emituje `naimenovanja_created` signal.

### 4.3 Spoljni ugovori koji moraju ostati stabilni

Drugi dijelovi aplikacije koriste:

- `FakturaTab.view` — direktno iz `MainWindow` i `AgentTab`
- `FakturaTab.data_changed` — signal
- `FakturaView.naimenovanja_created` — signal (sluša `AgentController`)
- `FakturaView.draft` — direktno iz `MainWindow._on_tab_changed`
- `FakturaView._load_data_from_draft()` — iz `AgentController._on_all_completed`
- `FakturaView._apply_import_result_to_header()` — iz `AgentController`
- `FakturaView._normalize_item_tariffs()` — iz `AgentController`
- `FakturaView._on_create_naimenovanja()` — iz dugmeta i agenta
- `FakturaView._on_validate_all()` — iz dugmeta i agenta
- `FakturaView._run_historical_tariff_validation()` — nakon svakog importa
- `FakturaView.weight_manager` — iz `MainWindow`
- `FakturaView._set_weight_inputs_from_draft()` — iz `MainWindow._reload_all_tabs`
- `AgentController` direktno resetuje i sabira `weight_manager`, te direktno
  piše `input_bruto`/`input_neto`
- Agent import pipeline poziva `_on_create_naimenovanja(auto=True)` i
  `_load_data_from_draft()`
- `AgentTab`, `chat_intent_handler` i `declaration_workflow_service` očekuju
  `FakturaTab.view`
- testovi i pomoćni moduli direktno uvoze `FakturaView`, `ValidationDelegate`
  i `_manual_invoice_record_sort_key`

Tokom refaktora wrapper zadržava postojeće metode. Privatne metode dobijaju
javne aliase, ali se stari nazivi ne brišu dok svi pozivaoci ne budu migrirani.

Kompatibilnost se ne rješava tako što Controller dobije pristup widgetima.
`FakturaTab` treba postepeno dobiti javne adapter metode:
`reload_from_draft()`, `set_weight_inputs_from_draft()`,
`create_naimenovanja(auto=False)` i `apply_import_header(result)`. Postojeći
privatni View API ostaje kao delegirajući shim samo dok svi pozivaoci ne pređu
na wrapper.

### 4.4 Poznate zamke

- `FakturaView.draft` mora se ažurirati pri multi-draft promjeni.
- `_on_item_changed` se poziva pri svakoj izmjeni ćelije — mora biti debounced.
- `blockSignals(True/False)` je obavezan pri bulk operacijama na tabeli.
- `_validation_generation` counter otkazuje starije validacione lance.
- Legacy metode su aktivne fallback — ne smiju se obrisati dok unified tok
  nije potvrđen stabilnim na svim scenarioima.
- `QTimer.singleShot(0, ...)` se koristi za chunkovanje validacije.
- `_pending_learn_rows` čeka debounce prije auto-učenja tarifa.
- `weight_manager` ima akumulirane težine — ne smije se resetirati pri navigaciji.
- `_agent_mode` flag mijenja ponašanje EUR1/PE2 dijaloga.
- `assembly.master_list_loaded` mijenja REPLACE/EXTEND logiku.
- Unified import workflow (`services/import_workflow/`) je VEĆ implementiran
  i ne smije se dirati.
- `dist_client` može imati drugačiji BOM/EOL.

### 4.5 Razlike od Naimenovanja refaktora

| Aspekt | Naimenovanja | Faktura |
| --- | --- | --- |
| Veličina | 3.681 linija | 6.329 linija |
| Metode | 108 | 123 |
| Postojeći servisi | 7 | 14 + import_workflow |
| Unified import | ne | da (Faze 0-8 gotove) |
| Legacy metode | ne | da (2 aktivne) |
| Tabela | forma (polja) | QTableWidget (ćelije) |
| Signali prema gore | 2 | 2 (+ naimenovanja_created) |
| BLAST radius | MEDIUM | HIGH |

Faktura je veća i ima HIGH blast radius uprkos postojećim servisima. Postojeći
servisi i unified import smanjuju količinu nove poslovne logike, ali ne smanjuju
broj direktnih GUI/Agent ugovora koji se moraju očuvati.

## 5. Ciljna arhitektura

### 5.1 Composition root: `FakturaTab`

```text
FakturaTab
├── FakturaView
├── FakturaController
├── FakturaService (postojeći services/faktura/)
├── ImportWorkflowService (postojeći services/import_workflow/)
└── TariffFacade / TariffService / MassCalculator (postojeći)
```

`FakturaTab` sastavlja slojeve. Controller dobija `get_draft_fn`.

Tokom ovog refaktora `view.draft` ostaje jedina autoritativna draft referenca.

### 5.2 View odgovornosti

View smije:

- kreirati i raspoređivati widgete (tabela, toolbar, status bar);
- čitati tabelu u neutralni dict / list of dicts;
- prikazati neutralni dict ili view-model u tabeli;
- održavati `is_loading`, `blockSignals` i UI timer; Controller je vlasnik
  generation tokena koji odlučuje da li se rezultat smije primijeniti;
- prikazati modal koji Controller zatraži;
- emitovati korisničke namjere kao signale.

View ne smije:

- pozivati DB ili repository;
- učiti tarifno mapiranje (`TariffFacade.learn`);
- odlučivati REPLACE/EXTEND logiku;
- direktno pozivati Controller metode;
- implementirati carinsku validaciju;
- raditi `QApplication.processEvents()` u poslovnom toku.

Minimalni javni View API:

```text
read_table_data() -> list[dict]
render_table_from_draft(draft) -> None
read_cell(row: int, column: int) -> str
read_selected_rows() -> list[int]
set_weight_inputs(bruto, neto) -> None
show_import_progress(visible: bool) -> None
show_eur1_dialog(items, invoice_name) -> bool
show_pe2_dialog(items, invoice_name, doc_code) -> bool
show_tariff_preview(proposals) -> None
show_success/error/warning(...)
focus_row(row: int) -> None
```

### 5.3 Controller odgovornosti

Controller:

- povezuje View signale;
- garantuje save-before-navigation (u tabeli: commit ćelije prije reload);
- uzima draft kroz `get_draft_fn`;
- poziva Service, ImportWorkflowService, TariffFacade;
- primjenjuje rezultate na draft;
- poziva View render API;
- emituje/propagira `data_changed` i `naimenovanja_created`;
- koordinira import, validaciju, auto-popunu i kreiranje naimenovanja.
- drži `validation_generation` i debounce orkestraciju kada oni određuju da li
  se rezultat još smije primijeniti; View samo izvršava UI timer/render korak.

Controller ne smije:

- koristiti `findChild`, `widget_cache`, `setText`, `setGeometry`;
- sadržavati SQL;
- implementirati carinsku validaciju;
- keširati zasebnu draft referencu;
- pozivati `QMessageBox` direktno (preko View metode).

### 5.4 Service odgovornosti

Service prima modele/primitivne vrijednosti i vraća modele, dataclasses ili
dict rezultate. Nema PySide6 import.

Postojeći servisi se koriste prije dodavanja novih:

- `services/faktura/mass_calculator.py`
- `services/faktura/weight_manager.py`
- `services/faktura/weight_guards.py`
- `services/faktura/validation_service.py`
- `services/faktura/validation_cache.py`
- `services/faktura/auto_fill_service.py`
- `services/faktura/declaration_split_service.py`
- `services/faktura/error_handler.py`
- `services/faktura/import_service.py`
- `services/faktura/export_service.py`
- `services/import_workflow/` (Faze 0-8)
- `services/tariff_facade.py`
- `services/tariff/tariff_mapping_service.py`

Ako logika postane prevelika, dozvoljen je uski `FakturaImportController`
ili `FakturaValidationService`; ne širiti postojeći `FakturaService` u god object.

### 5.5 Neutralni rezultati

Preporučene male dataclasses u `services/faktura/models.py`:

```text
ImportFinishedResult
MassCalculationResult
ValidationPassResult
TariffAutoFillResult
NaimenovanjaCreationResult
PartnerConsistencyResult
```

Ne vraćati Qt objekte iz Service-a.

## 6. Signalni ugovor

View definiše najmanje (stvarni PySide oblik je `Signal(list)`, `Signal(str)`,
`Signal(bool)` itd.; tekst ispod opisuje ugovor, ne Python deklaraciju):

```text
import_requested(filepaths: list)
validate_requested(scope: str, rows: list)
auto_fill_requested()
create_naimenovanja_requested(auto: bool)
calculate_masses_requested()
historical_validation_requested(auto: bool)
export_pdf_requested(report_type: str)
export_excel_requested()
load_previous_requested()
item_changed(row: int, col: int, value: str)
tariff_bulk_change_requested(rows: list, tariff: str)
split_by_country_requested()
```

Pravila:

- dugme ili widget povezuje se samo sa View handlerom koji emituje signal;
- Controller jedini povezuje signal sa poslovnim handlerom;
- tokom migracije stari handler i novi Controller ne smiju oba obraditi isti
  događaj;
- `blockSignals` se koristi pri bulk renderovanju tabele;
- rezultat validacije nosi generation token; Controller odbacuje zastarjeli
  rezultat, a View primjenjuje samo već prihvaćen rezultat;
- postojeći agent poziv `auto=True` mora ostati funkcionalno različit od
  ručnog klika, posebno za dijaloge i automatski tok.

## 7. Mapiranje postojećih metoda

### 7.1 Ostaje u View-u

UI konstrukcija i prikaz:

- `__init__` nakon smanjenja orkestracije
- `_create_controls_section`
- `_populate_toolbar_section`
- `_populate_grid_sections`
- `_create_table`
- `_create_status_bar`
- `_create_button`
- `_add_section_heading` (ako postoji)
- `apply_display_profile`
- `_load_data_from_draft` (samo UI dio — punjenje tabele)
- `_add_item_to_table_fast` / `_add_item_to_table`
- `_set_table_item`
- `_format_number`
- `_populate_row_cells`
- `_update_status_bar` (samo UI)
- `_show_tariff_preview_dialog` (modal)
- `_show_tariff_mapping_result` (modal)
- `_show_eur1_dialog` (modal)
- `_show_pe2_dialog` (modal)
- `_build_tariff_table_widget` (UI)
- `_build_analysis_summary_from_draft` (UI prikaz)
- `_flash_field_border` (ako postoji)
- `_set_weight_inputs_from_draft` (UI)
- `_update_weight_totals` (UI)
- `_install_bottom_scroll_buffer`
- `_track_file_type`
- `_append_imported_files_message`
- `_show_no_export_items`
- `_show_scrollable_info_dialog`
- `_darken_color`
- `_create_label` / `_create_separator`
- `resizeEvent`, `eventFilter`, `keyPressEvent`

### 7.2 Prelazi u Controller

- import tok: `_on_import_finished`, `_on_import_finished_legacy`,
  `_process_batch_records`, `_process_batch_records_legacy`,
  `_import_multiple_files`, `_on_import_xml`, `_on_load_master_list`,
  `_start_import`, `_on_batch_progress`, `_on_batch_done`
- `_can_use_unified_manual_import`, `_prepare_manual_import_plan`,
  `_existing_invoice_keys_for_import_workflow`, `_expected_import_partners`,
  `_manual_import_source_path`, `_batch_record_to_import_candidate`,
  `_collect_manual_import_decisions`, `_collect_manual_origin_response`,
  `_show_manual_import_workflow_result`, `_show_manual_batch_import_workflow_result`
- `_on_create_naimenovanja` — orkestracija kreiranja
- `_on_validate_all` — orkestracija validacije
- `_run_historical_tariff_validation` — orkestracija historijske provjere
- `_on_historical_validation_finished`
- `_on_auto_fill` — orkestracija auto-popune
- `_on_calculate_masses` — orkestracija računanja masa
- `_on_item_changed` — event handler (debounce + dirty + notify)
- `_on_bulk_change_tariff` — bulk izmjena tarife
- `_correct_tariff_in_db` — KB korekcija
- `_auto_learn_edits` — KB učenje
- `_on_delete_item` — brisanje stavke
- `_on_clear_all` — čišćenje
- `_on_load_previous_declaration`
- `_on_export_pdf` / `_on_export_excel` / `_on_export_pregled_faktura`
- `_check_partner_consistency`
- `_is_same_combined_invoice`
- `_apply_import_result_to_header`
- `_assign_invoice_name`
- `_distribute_invoice_weights`
- `_accumulate_weights`
- `_normalize_item_tariffs`
- `_sync_pe_docs_to_header` / `_sync_inspection_docs_to_header`
- `_reload_naimenovanja_tab`
- `_offer_split_by_country`
- `_auto_handle_povlastice_agent`
- `_suggest_preference_by_country`
- `_postprocess_master_frigo_pairs_records`
- `_collect_tariff_previews`
- `_notify_auto_applied_tariffs`
- `_extract_import_result_data`
- `_get_invoice_name`
- `_extract_header_from_xml`
- `_on_load_mappings_from_xml`
- `_restore_validation_label`
- `_set_analysis_summary_text`

### 7.3 Prelazi u Service ili postojeći specijalizovani servis

- `_validate_and_color_row` → `FakturaValidationService.validate_and_color`
- `_apply_country_confidence_color` → Service
- `_apply_preference_confidence_color` → Service
- `_validation_issue_counts` / `_validation_issue_label` / `_format_issue_counts` → Service
- `_parse_number` / `_parse_weight_input` → Service
- `_update_weights_after_deletion` → Service / WeightManager
- `_get_cell_value` → View `read_cell()`; Service nikad ne prima QTableWidget
- `_sync_table_to_draft` → Service
- `_validation_pass_chunk` → Controller orkestracija + Service validacija
- `_push_undo_snapshot` / `_undo` / `_redo` → Service (UndoManager)
- `_set_buttons_enabled` → ostaje u View (UI)

### 7.4 Mora se razbiti, ne premjestiti kao cjelina

| Postojeća metoda | Razdvajanje |
| --- | --- |
| `_on_import_finished` | View signal → Controller → ImportWorkflowService → Controller primjena → View render |
| `_on_import_finished_legacy` | Razdvojiti na: ekstrakt podataka (Service) → provjera partnera (Controller) → normalizacija (Service) → REPLACE/EXTEND (Controller) → dijalog (View) |
| `_process_batch_records_legacy` | Razdvojiti slično kao `_on_import_finished_legacy` |
| `_on_create_naimenovanja` | Controller orkestrira → `CreateNaimenovanjaService` → auto-učenje (TariffFacade) → sinhronizacija PE (Service) → reload (View) |
| `_on_auto_fill` | Controller → `TariffFacade.auto_populate_tariffs` → `commit_proposals` → View render |
| `_on_calculate_masses` | Controller → `MassCalculator.calculate_masses` → View render težina |
| `_run_historical_tariff_validation` | Controller → `HistoricalTariffSearchService.validate_lines` → dijalog (View) |
| `_on_item_changed` | View emituje signal → Controller debounce → dirty + notify → generation-token validacija |

## 8. Faze implementacije

## Faza 0 — baseline, karakterizacija i branch zaštita

### Rad

- Kreirati refaktor granu/worktree `refactor/faktura-3layer`.
- Sačuvati početni commit hash.
- Evidentirati `git merge-base windows refactor/faktura-3layer` i dokazati da
  branch stvarno polazi od odobrenog Windows HEAD-a.
- Pokrenuti punu suite i evidentirati postojeće padove.
- Napraviti offscreen screenshot ili widget-state snapshot taba.
- Dodati karakterizacione testove bez promjene produkcionog ponašanja.

### Obavezni novi testovi

1. `test_faktura_table_roundtrip.py`
   - svako polje InvoiceLine → View tabela → InvoiceLine;
   - Decimal/float/prazne vrijednosti;
   - tarifni format ostaje bez tačaka.
2. `test_faktura_import_characterization.py`
   - ručni pojedinačni import (legacy i unified);
   - ručni grupni import;
   - REPLACE/EXTEND logika;
   - consumed_paths deduplikacija.
3. `test_faktura_validation_characterization.py`
   - validacija svih stavki (ne samo prvih N);
   - blockSignals pri bulk validaciji;
   - validation_generation counter otkazuje starije lance.
4. `test_faktura_signal_characterization.py`
   - jedan klik emituje jedan signal;
   - `naimenovanja_created` se emituje jednom po kreiranju;
   - nema duplih konekcija poslije reload-a.
5. `test_faktura_weight_characterization.py`
   - akumulacija težina po fakturi;
   - `weight_manager` ne resetira pri navigaciji;
   - `_distribute_invoice_weights` raspoređuje proporcionalno.
6. `test_faktura_auto_fill_characterization.py`
   - `TariffFacade.auto_populate_tariffs` rezultat;
   - `commit_proposals` upisuje u draft;
   - KB učenje se pokreće samo nakon prihvatanja.
7. Proširiti postojeće testove za `naimenovanja_created` signal i
   `_run_historical_tariff_validation`.
8. `test_faktura_public_contracts.py`
   - MainWindow i Agent koriste wrapper adaptere;
   - `create_naimenovanja(auto=True)` čuva agent semantiku;
   - zamjena aktivnog drafta ne ostavlja keširanu referencu;
   - direktni weight widget pristup je evidentiran prije migracije.
9. `test_faktura_dist_standalone.py`
   - ključni root i dist moduli imaju paritet;
   - `dist_client` importuje FakturaTab kao samostalan root.

### Gate

- Nema produkcionih izmjena.
- Novi karakterizacioni testovi prolaze na starom kodu.
- Puna suite rezultat nije lošiji od baseline-a.
- Baseline se pokreće sa validnim procesnim `DEBUG=false`; lokalni
  `DEBUG=release` nije validan Pydantic boolean i ne smije se tumačiti kao
  produkcioni pad refaktora.

### Commit

`test(faktura): zakljucaj ponasanje prije 3layer refaktora`

## Faza 1 — ugovori i composition root bez promjene ponašanja

### Rad

- Dodati `FakturaController` sa praznim/bezbjednim signal wiringom.
- Dodati neutralne result dataclasses u `services/faktura/models.py`.
- `FakturaTab` dobija injektovani Service i kreira Controller.
- Controller koristi `get_draft_fn`, bez `self.draft`.
- Zadržati sve stare View handlere aktivne dok nema migriranog signala.

### Posebna zaštita

Ne povezivati Controller na signal koji još obrađuje View. Svaki signal se
prespaja tek u fazi njegovog vertikalnog reza.

### Gate

- Kreiranje taba radi preko `TabFactory`.
- `reload_data`, `naimenovanja_created` i `data_changed` ostaju kompatibilni.
- Test potvrđuje da je ista service instanca proslijeđena.

### Commit

`refactor(faktura): uvedi controller composition root bez promjene toka`

## Faza 2 — čiste kalkulacije i read-only lookupi

### Rad

Prvo izdvojiti metode bez side-effecta:

- `_parse_number` / `_parse_weight_input` → Service
- `_format_number` → ostaje u View (prikaz)
- `_validation_issue_counts` / `_format_issue_counts` → Service
- `_get_cell_value` → View `read_cell()`; Service dobija neutralnu vrijednost
- `_extract_import_result_data` → Service
- `_get_invoice_name` → Service
- `_normalize_item_tariffs` → već u `import_service.py`, ali View ima sopstvenu kopiju
- `_track_file_type` → Service
- `_append_imported_files_message` → ostaje u View (prikaz)
- `_darken_color` → ostaje u View (prikaz)

Service testovi koriste stvarni testni SQLite/PostgreSQL gdje postoji DB
pristup. Ne smiju pisati u produkcione tabele niti zavisiti od trenutnog
sadržaja korisničke baze.

### Gate

- Service moduli nemaju `PySide6` import.
- Rezultati su identični karakterizacionim očekivanjima.

### Commit

`refactor(faktura): izdvoji ciste kalkulacije i lookup rezultate`

## Faza 3 — validacija i bojenje

### Rad

Izdvojiti validacione metode u `FakturaValidationService` (proširiti postojeći):

- `_validate_and_color_row` → Service (vraća boju + tooltip)
- `_apply_country_confidence_color` → Service
- `_apply_preference_confidence_color` → Service
- Controller planira chunkove i nosi generation token; Service validira
  neutralne redove; View primjenjuje boju i tooltip
- `_check_and_show_tariff_warning` → View (prikaz), Service (logika)

View samo primjenjuje boju koju Service vrati. QTimer chunkovanje je
kooperativno u Qt event loopu i **nije rad van UI threada**. QThread se uvodi
samo kao zasebno odobrena promjena uz dokaz da worker ne dodiruje Qt objekte.

### Gate

- Validacija za >20 stavki ne blokira UI: radi u malim QTimer chunkovima ili u
  posebno testiranom workeru; plan ne miješa ta dva modela.
- Bojenje je identično baseline-u.
- `blockSignals` se koristi pri bulk validaciji.

### Commit

`refactor(faktura): izdvoji validaciju i bojenje u servis`

## Faza 4 — import tok kao prvi Controller vertikalni rez

### Rad

1. View dobija `show_import_progress()` i `show_import_result()`.
2. Controller implementira:
   - `_on_import_finished(result)` → unified ili legacy;
   - `_process_batch_records(records)`;
   - `_import_multiple_files(filepaths)`;
   - `_start_import(filepath)`.
3. Controller koristi postojeći `services/import_workflow/` za unified tok.
4. Legacy fallback ostaje dok unified tok nije potvrđen.
5. Prespojiti samo odgovarajuće View signale.
6. `FakturaTab` dobija privremene javne adaptere za Agent/MainWindow, ali
   adapteri delegiraju u Controller/View API i ne čuvaju drugi draft.

### Invarijante

- `_can_use_unified_manual_import` uslov ostaje isti;
- REPLACE/EXTEND logika ostaje ista;
- EUR1/PE2 dijalog se prikazuje jednom po fakturi;
- `consumed_paths` deduplikacija radi;
- `naimenovanja_created` se ne emituje pri importu;
- `weight_manager` akumulira ispravno;
- `data_changed` se emituje jednom po završenom importu.

### Gate

- GitNexus impact ponoviti za `_on_import_finished` prije izmjene.
- Svi import karakterizacioni testovi prolaze.
- Ručni offscreen test sa stvarnim fakturama iz `najavauvoza/`.

### Commit

`refactor(faktura): premjesti import tok u controller`

## Faza 5 — kreiranje naimenovanja i auto-popuna

### Rad

Migrirati kao jedan koherentan tok:

```text
create_naimenovanja_requested
→ Controller provjerava split po zemljama
→ CreateNaimenovanjaService.create_smart_group()
→ TariffFacade.learn_from_draft() (auto-učenje)
→ Controller sinhronizuje PE dokumente
→ Controller reload tabele
→ View render
→ Controller emituje naimenovanja_created
```

Signal i wrapper adapter nose `auto: bool`: ručni klik šalje `False`, agent
šalje `True`. Time se čuva postojeća razlika u dijalozima i punoj automatizaciji.

Auto-popuna tarifa:

```text
auto_fill_requested
→ Controller → TariffFacade.auto_populate_tariffs()
→ TariffFacade.commit_proposals()
→ View render (bojenje + preview)
→ KB učenje samo nakon prihvatanja
```

### Kritična korekcija

`_on_create_naimenovanja` NE smije pozivati `QApplication.processEvents()`
u Controlleru. UI osvježavanje ide kroz View metode.

### Gate

- `naimenovanja_created` se emituje jednom po kreiranju;
- auto-učenje se pokreće jednom;
- PE dokumenti se sinhronizuju;
- `_offer_split_by_country` ostaje funkcionalan;
- `data_changed` se emituje jednom.

### Commit

`refactor(faktura): premjesti kreiranje naimenovanja i auto-popunu u controller`

## Faza 6 — mase, težine i historijska validacija

### Rad

- `_on_calculate_masses` → Controller → `MassCalculator` → View render
- `_distribute_invoice_weights` → Service
- `_accumulate_weights` → Service / WeightManager
- `_update_weights_after_deletion` → Service
- `_run_historical_tariff_validation` → Controller →
  `HistoricalTariffSearchService.validate_lines()` → dijalog (View)
- `_on_historical_validation_finished` → Controller
- `_on_validate_all` → Controller → `FakturaValidationService` → View render

### Invarijante

- Mase se ne zaokružuju na 2 decimale;
- `weight_manager` akumulira ispravno;
- historijska validacija zadržava postojeći worker/QThread model;
- tabelarna validacija zadržava QTimer chunk model dok se eksplicitno ne
  odobri prelazak na worker;
- `validation_generation` counter otkazuje starije lance;
- selekcija redova se poštuje u "Provjeri".

### Gate

- Svi weight i validation karakterizacioni testovi prolaze;
- Ručni test sa stvarnim fakturama.

### Commit

`refactor(faktura): premjesti mase i historijsku validaciju u controller`

## Faza 7A — item edit, undo/redo i destruktivne operacije

### Rad

- `_on_item_changed` → View emituje signal → Controller debounce → dirty + notify
- `_push_undo_snapshot` / `_undo` / `_redo` → Service (UndoManager)
- `_on_bulk_change_tariff` → Controller → Service → KB učenje
- `_correct_tariff_in_db` → Service → TariffFacade.sync_mapping
- `_auto_learn_edits` → Controller → TariffFacade
- `_on_delete_item` → Controller → Service → View render
- `_on_clear_all` → Controller → Service → View render
- `_on_load_mappings_from_xml` → Controller → TariffFacade
- `_check_partner_consistency` → Service (vraća rezultat, View prikazuje)
- `_is_same_combined_invoice` → Service
- `_apply_import_result_to_header` → Service
- `_sync_pe_docs_to_header` / `_sync_inspection_docs_to_header` → Service
- `_reload_naimenovanja_tab` se više ne poziva direktno iz View-a; Controller
  emituje rezultat koji `FakturaTab`/MainWindow koordinira
- `_suggest_preference_by_country` → Service
- `_auto_handle_povlastice_agent` → Controller → Service
- `_postprocess_master_frigo_pairs_records` → Service
- `_extract_header_from_xml` → Service

### Gate

- Undo/redo radi za sve operacije;
- KB učenje se pokreće samo nakon ručne izmjene;
- Partner konzistentnost se provjerava prije primjene.
- Delete i Clear ne aktiviraju `itemChanged` u petlji.
- Jedna ručna izmjena proizvodi najviše jedan dirty/data_changed događaj.

### Commit

`refactor(faktura): premjesti item edit undo i destruktivne operacije`

## Faza 7B — export, prethodna deklaracija i integracioni adapteri

### Rad

- `_on_export_pdf` / `_on_export_excel` / `_on_export_pregled_faktura` →
  Controller → ExportService → View bira putanju i prikazuje rezultat.
- `_on_load_previous_declaration` → Controller → Service → View render.
- Migrirati MainWindow i Agent pozivaoce na javni `FakturaTab` API.
- Ukloniti direktno Agent pisanje `weight_manager` i weight widgeta.
- Zadržati privatne View shimove dok test i pretraga ne dokažu da više nemaju
  spoljne pozivaoce.

### Gate

- Export generiše sadržajno identičan PDF/Excel kao baseline.
- Agent puna automatizacija radi bez direktnog pristupa Faktura widgetima.
- MainWindow reload i multi-draft promjena koriste javni wrapper API.
- `rg` ne nalazi produkcione pozive migriranih privatnih View metoda.

### Commit

`refactor(faktura): uvedi javne adaptere i premjesti export tok`

## Faza 8 — čišćenje, paritet i završna validacija

### Rad

- Obrisati samo dokazano nepovezane stare metode.
- Ukloniti legacy metode ONLY ako je unified tok potvrđen stabilnim.
- Provjeriti da nema zakomentiranog starog koda.
- Preslikati tačno odobrene fajlove u `dist_client`.
- Za svaki novi root modul dokazati da postoji u `dist_client` prije brisanja
  compatibility importa; samostalni dist import je obavezna kapija.
- Ažurirati dokumentaciju i agent report.

### Statičke kapije

```text
faktura_view.py:
  nema SQL/DB konekcije
  nema TariffFacade mutacije
  nema direktnog Controller poziva
  nema QApplication.processEvents() u poslovnom toku

service moduli:
  nema PySide6 importa
  nema QMessageBox/QFileDialog
  nema MainWindow pristupa

controller:
  nema findChild/widget_cache/setGeometry
  nema SQL
  nema keširanog drafta
```

### Test kapije

1. Ciljani Faktura testovi.
2. Import → kreiranje naimenovanja → reload.
3. Agent → Faktura refresh.
4. XML import i XML preflight.
5. Multi-draft.
6. Root/`dist_client` sadržajni paritet.
7. `py_compile`.
8. Puna `pytest tests/ -q` suite.
9. Offscreen GUI smoke test.
10. Ručna provjera na stvarnoj fakturi iz `najavauvoza/`.

### Commit

`refactor(faktura): ukloni stari monolitni wiring i potvrdi paritet`

## 9. Test matrica

| Tok | Unit | Integracija | GUI/offscreen | Ručno |
| --- | --- | --- | --- | --- |
| tabela roundtrip | obavezno | — | obavezno | — |
| import (pojedinačni) | obavezno | stvarne fakture | obavezno | obavezno |
| import (grupni) | obavezno | stvarne fakture | obavezno | obavezno |
| import (agent) | obavezno | obavezno | obavezno | obavezno |
| REPLACE/EXTEND | obavezno | — | — | obavezno |
| validacija | obavezno | — | obavezno | obavezno |
| auto-popuna tarifa | obavezno | stvarna tarifa DB | obavezno | obavezno |
| KB učenje | obavezno | stvarni test DB | — | kontrolisano |
| mase | obavezno | — | obavezno | obavezno |
| historijska validacija | obavezno | stvarna DB | obavezno | obavezno |
| kreiranje naimenovanja | obavezno | obavezno | obavezno | obavezno |
| undo/redo | obavezno | — | obavezno | — |
| export PDF/Excel | — | obavezno | — | obavezno |
| signal wiring | obavezno | — | obavezno | — |
| multi-draft | obavezno | obavezno | obavezno | obavezno |

DB testove ne zamjenjivati mockovima.

## 10. Stop i rollback kriteriji

Implementacija se odmah zaustavlja ako:

- tabela gubi stavke pri reload-u;
- import ne poštuje `consumed_paths` (duplikati stavki);
- REPLACE zamijeni pogrešnu fakturu;
- `naimenovanja_created` se ne emituje nakon kreiranja;
- `weight_manager` akumulira pogrešno;
- validacija preskoči stavke;
- KB učenje upiše pogrešnu tarifu;
- undo/redo izgubi stanje;
- `dist_client` odstupa od root implementacije;
- puna suite dobije novi pad.

Rollback:

- revertovati samo commit te faze;
- ne popravljati regresiju dodavanjem compatibility grananja;
- vratiti se na prethodni zeleni checkpoint;
- dopuniti karakterizacioni test koji je nedostajao;
- ponoviti fazu manjim vertikalnim rezom.

## 11. Obavezni pregled po fazi

Za svaku fazu:

1. `gitnexus_impact` prije izmjene svakog postojećeg simbola.
2. HIGH/CRITICAL handoff i project-room dopuna prije koda.
3. Implementacija samo odobrenog vertikalnog reza.
4. Ciljani testovi.
5. Root/`dist_client` parity gdje je runtime kopija pogođena.
6. `gitnexus_detect_changes`.
7. Pregled staged fajlova.
8. Logički commit.
9. Agent report dopuna ili fazni report.
10. GitNexus reindex ako je stale.

## 12. Šta nije dio refaktora

- Redizajn taba ili promjena palete.
- Promjena `.ui` geometrije.
- Promjena grupiranja naimenovanja.
- Promjena tarifnog fuzzy thresholda.
- Promjena unified import workflow (`services/import_workflow/`).
- Automatsko dodjeljivanje povlastice.
- Promjena ASYCUDA XML šeme.
- Potpuno premještanje vlasništva drafta iz View-a.
- Preimenovanje srpskih `InvoiceLine` polja.
- Čišćenje drugih tabova.
- Brisaje legacy metoda dok unified tok nije potvrđen.

Svaki pronađeni funkcionalni bug van ovog scope-a evidentirati kao poseban
follow-up; ne popravljati ga usput u refaktor commitu.

## 13. Procjena vremena

| Faza | Procjena |
| --- | --- |
| 0 — baseline/karakterizacija | 6–10 h |
| 1 — ugovori/composition root | 3–5 h |
| 2 — čiste kalkulacije | 4–6 h |
| 3 — validacija i bojenje | 5–8 h |
| 4 — import tok | 8–12 h |
| 5 — kreiranje naimenovanja i auto-popuna | 6–9 h |
| 6 — mase i historijska validacija | 5–8 h |
| 7A — item edit/undo/destruktivne operacije | 6–9 h |
| 7B — export i integracioni adapteri | 5–8 h |
| 8 — čišćenje/puna validacija | 5–8 h |
| Ukupno | 53–83 h |

Procjena je povećana jer je potvrđen HIGH blast radius, 148 metoda, direktni
Agent/MainWindow widget pristup i samostalni `dist_client` runtime. Unified
import i postojeći servisi ostaju značajna prednost, ali ne uklanjaju potrebu
za kompatibilnim adapterima i živim Windows testom.

## 14. Konačni acceptance kriteriji

Refaktor je završen tek kada:

- Faze 0–8, uključujući odvojene 7A i 7B, imaju zeleni checkpoint;
- nema novih padova pune suite;
- Faktura tab radi sa pojedinačnim i grupisanim importima;
- REPLACE/EXTEND logika je dokazana testom;
- `naimenovanja_created` se emituje jednom po kreiranju;
- `weight_manager` akumulira ispravno;
- validacija provjerava sve stavke;
- KB učenje se pokreće samo nakon ručne izmjene;
- undo/redo radi;
- drugi tabovi koriste stabilan wrapper API;
- Agent i MainWindow više ne pišu direktno u Faktura widgete ili
  `weight_manager`;
- View nema DB/business side-effecte;
- Service nema Qt;
- Controller koristi signale i nema widget pristup;
- root i `dist_client` su sadržajno jednaki;
- korisnik ručno potvrdi osnovni tok na Windows instalaciji;
- promjene prođu obavezni review prije mergea u `windows`.

## 15. Preporučena odluka

Plan je spreman za realizaciju tek nakon korisničke potvrde:

1. da se `refactor/faktura-3layer` kreira tek iz tada potvrđenog `windows`
   basea, nakon eksplicitne odluke šta je od drugih aktivnih grana integrisano;
2. da se Faza 0 realizuje i preda na pregled prije produkcionog refaktora;
3. da se svaka naredna faza nastavlja samo iz posljednjeg zelenog checkpointa;
4. da merge u `windows` bude ručno odobren tek nakon Faze 8.
