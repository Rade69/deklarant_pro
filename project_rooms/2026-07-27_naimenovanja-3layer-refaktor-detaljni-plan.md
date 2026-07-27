# Naimenovanja 3-layer refaktor — detaljni plan bez funkcionalne regresije

## 1. Status dokumenta

- Datum analize: 2026-07-27
- Autor plana: Codex
- Polazni dokument: `project_rooms/2026-07-26_naimenovanja-3layer-refaktor-plan.md`
- Analizirana grana: `feature/agent-v2`
- Ovaj dokument je plan, ne odobrenje za automatski merge.
- Implementacija se ne smije raditi direktno na `windows`, `main`, `master` ili
  drugoj integracionoj grani.

## 2. Cilj

Razdvojiti postojeći `NaimenovanjaView` na View, Controller i Service sloj bez
promjene carinske poslovne logike, prikaza, redoslijeda događaja, draft
semantike, XML sadržaja ili ponašanja drugih tabova.

Primarni rezultat nije samo manji broj linija, nego:

- View nema DB pristup ni poslovne odluke.
- View prema Controlleru komunicira signalima.
- Controller orkestrira, ali ne implementira carinska pravila.
- Service nema Qt widgete, modalne dijaloge niti pristup `MainWindow`.
- Postoji samo jedna autoritativna draft referenca.
- Javni API `NaimenovanjaTab` ostaje kompatibilan.
- Root i `dist_client` ostaju sadržajno usklađeni.

## 3. Obavezna strategija grane i worktreea

### 3.1 Priprema

Prije početka implementacije:

1. Završiti ili arhivirati sve aktivne izmjene koje dodiruju:
   - `gui/tabs/naimenovanja_view.py`
   - `gui/tabs/naimenovanja_tab.py`
   - `services/naimenovanja/`
   - njihove `dist_client` kopije
   - testove naimenovanja
2. Integraciona grana mora sadržavati sve odobrene izmjene iz
   `feature/agent-v2`.
3. Provjeriti da integracioni worktree nema staged refaktor izmjene.
4. Kreirati posebnu granu i poseban worktree:

```text
grana: refactor/naimenovanja-3layer
worktree: .worktrees/naimenovanja-3layer
base: posljednji potvrđeni commit integracione windows grane
```

Primjer komande nakon potvrde tačnog base commita:

```bash
git worktree add .worktrees/naimenovanja-3layer \
  -b refactor/naimenovanja-3layer windows
```

Ne koristiti postojeći prljavi `windows` worktree za implementaciju.

### 3.2 Pravilo jednog autora nad monolitom

Dok traje refaktor, samo jedan aktivni agent smije mijenjati
`naimenovanja_view.py`. Drugi agenti smiju paralelno raditi testove ili
nezavisne service module samo ako im je dodijeljen tačan, nepreklapajući scope.

### 3.3 Commit strategija

Svaka faza ima zaseban commit i mora biti reverzibilna bez ručnog rastavljanja
drugih faza. Zabranjen je jedan veliki commit za cijeli refaktor.

## 4. Dokazano trenutno stanje

### 4.1 Veličina i struktura

Na analiziranom commitu:

| Komponenta | Stanje |
| --- | --- |
| `gui/tabs/naimenovanja_view.py` | 3.681 linija |
| `NaimenovanjaView` | 108 metoda |
| `services/naimenovanja/naimenovanja_service.py` | 439 linija |
| `NaimenovanjaService` | 17 metoda |
| `gui/tabs/naimenovanja_tab.py` | 41 linija, wrapper bez Controllera |
| View signali prema gore | `import_xml_requested`, `suggest_tariff_requested`, naslijeđeni `data_changed` |

Originalni Pi plan navodi 52 metode i 3.888 linija. To je koristan parcijalni
inventar, ali nije dovoljan kao implementaciona kontrolna lista.

### 4.2 Najvažniji blast radius

GitNexus rezultat:

- `NaimenovanjaView`: MEDIUM, 5 direktnih importera, 11 ukupno pogođenih.
- `_save_current_item`: MEDIUM, 11 direktnih pozivalaca i 25 ukupno pogođenih.
- `_on_import_xml`: LOW prema statičkom grafu, ali ručno je procijenjen kao
  MEDIUM zbog draft, Zaglavlje i dokument side-effecta.

`_save_current_item` trenutno u jednom toku:

1. čita widgete;
2. normalizuje vrijednosti;
3. mijenja `NaimenovanjeDraft`;
4. čisti sekundarne PE dokumente;
5. označava draft dirty;
6. sinhronizuje tarifu u `InvoiceLine`;
7. trajno ažurira bazu tarifnog mapiranja.

Zato se ne smije samo premjestiti u Controller kao jedna velika metoda.

### 4.3 Spoljni ugovori koji moraju ostati stabilni

Drugi dijelovi aplikacije koriste:

- `NaimenovanjaTab.reload_data()`
- `NaimenovanjaTab._sync_header_packages()`
- `NaimenovanjaTab.data_changed`
- `MainWindow.naimenovanje_tab`
- Faktura tok koji poslije kreiranja naimenovanja poziva reload i package sync
- Agent chat tok koji poziva reload
- testove koji direktno pozivaju neke `NaimenovanjaView` metode

Tokom refaktora wrapper zadržava postojeće metode. Privatni
`_sync_header_packages()` dobija javni alias `sync_header_packages()`, ali se
stari naziv ne briše dok svi pozivaoci ne budu migrirani i testirani.

### 4.4 Poznate zamke

- `NaimenovanjaView.draft` mora se ažurirati pri multi-draft promjeni.
- `_save_current_item` se poziva prije navigacije i iz više Rub.40/44 tokova.
- `QTimer` debounce čuva pending tarifni broj.
- Signalno dupliranje može dva puta snimiti ili dva puta pokrenuti DB učenje.
- `itemChanged`/widget signali moraju biti blokirani pri bulk renderovanju.
- Rub.31 XML ograničenje ostaje u XML builderu; GUI prikaz ne smije biti
  skraćen na pogrešnom mjestu.
- PE1/PE2/PE3 dokumenti zavise od Rub.36 i ne smiju se nekontrolisano kopirati.
- Grupisano naimenovanje ne može se pouzdano mapirati na `InvoiceLine` samo kao
  `ordinal_no - 1`.
- `dist_client` može imati drugačiji BOM/EOL i mora se porediti sadržajno.
- U View-u postoje dvije definicije `_extract_short_code`; čišćenje tek nakon
  karakterizacionih testova.

## 5. Ciljna arhitektura

## 5.1 Composition root: `NaimenovanjaTab`

`NaimenovanjaTab` sastavlja slojeve:

```text
NaimenovanjaTab
├── NaimenovanjaView
├── NaimenovanjaController
├── NaimenovanjaService
└── TariffService / postojeće specijalizovane servise
```

`TabFactory` dobavlja `NaimenovanjaService` iz postojećeg DI containera.
Controller ne smije praviti novu `NaimenovanjaService()` instancu ako je servis
već injektovan.

Tokom ovog refaktora `view.draft` ostaje jedina autoritativna draft referenca
radi minimalnog rizika. Controller dobija:

```python
get_draft_fn=lambda: view.draft
```

Controller ne smije imati keširani `self.draft`. Promjena drafta ide samo kroz
jednu wrapper/View metodu `set_draft(draft)` koja zatim radi render.

Potpuno premještanje vlasništva drafta iz View-a nije dio ovog zadatka.

## 5.2 View odgovornosti

View smije:

- kreirati i raspoređivati widgete;
- čitati formu u neutralni dict;
- prikazati neutralni dict ili view-model;
- održavati `is_loading`, widget cache, fokus, highlight i status;
- prikazati modal koji Controller zatraži kroz javnu View metodu;
- emitovati korisničke namjere kao signale.

View ne smije:

- pozivati DB ili repository;
- učiti tarifno mapiranje;
- odlučivati koje dokumente treba dodati;
- direktno pozivati Controller metode;
- tražiti `MainWindow` radi mijenjanja Zaglavlja;
- implementirati carinsku validaciju.

Minimalni javni View API:

```text
read_current_form() -> dict
render_current_item(item, render_context) -> None
render_navigation(navigation_state) -> None
render_tariff_result(result) -> None
render_tariff_warning(warning) -> None
set_draft(draft) -> None
choose_xml_file() -> str
show_success/error/warning(...)
ask_confirmation(...) -> bool
focus_field(field_name) -> None
```

## 5.3 Controller odgovornosti

Controller:

- povezuje View signale;
- garantuje save-before-navigation;
- uzima draft kroz `get_draft_fn`;
- poziva Service i TariffService;
- primjenjuje rezultate na draft;
- poziva View render API;
- emituje/propagira `data_changed`;
- koordinira XML, Zaglavlje, Faktura i KB side-effecte.

Controller ne smije:

- koristiti `findChild`, `widget_cache`, `setText` ili `setGeometry`;
- sadržavati SQL;
- implementirati tarifno grupiranje ili dokument pravila;
- keširati zasebnu draft referencu.

## 5.4 Service odgovornosti

Service prima modele/primitivne vrijednosti i vraća modele, dataclasses ili
dict rezultate. Nema PySide6 import, modal, parent widget ili `MainWindow`.

Postojeći servisi se koriste prije dodavanja novih:

- `NaimenovanjaService`
- `TariffService`
- `TariffFacade`
- `CreateNaimenovanjaService`
- `tariff_controls_service`
- `tariff_doc_history_service`
- `ZaglavljeService`

Ako dokument logika postane prevelika, dozvoljen je uski
`NaimenovanjaDocumentService`; ne širiti `NaimenovanjaService` u novi god
object.

## 5.5 Neutralni rezultati

Preporučene male dataclasses u `services/naimenovanja/models.py`:

```text
NavigationState
TariffLookupResult
TariffMutationResult
SupplementaryUnitResult
DocumentMergeResult
XmlImportResult
NaimenovanjeRenderContext
```

Ne vraćati Qt objekte iz Service-a.

## 6. Signalni ugovor

View definiše najmanje:

```text
save_requested()
navigate_requested(index: int)
add_requested()
delete_requested(index: int)
tariff_text_changed(code: str)
tariff_confirmed(code: str)
tariff_suggestion_requested()
tariff_suggestion_accepted(payload: dict)
manual_tariff_search_requested()
xml_import_requested(path: str)
inspection_requested(index: int)
field_edit_finished(field_name: str)
reset_requested()
```

Pravila:

- dugme ili widget povezuje se samo sa View handlerom koji emituje signal;
- Controller jedini povezuje signal sa poslovnim handlerom;
- tokom migracije stari handler i novi Controller ne smiju oba obraditi isti
  događaj;
- svaki signal dobija test „jedan klik = jedan poziv“;
- timer timeout se povezuje jednom i testira se da nema duplih konekcija.

## 7. Mapiranje postojećih metoda

### 7.1 Ostaje u View-u

UI konstrukcija i prikaz:

- `__init__` nakon smanjenja orkestracije
- `_create_icon_button`
- `_load_ui_from_file`
- `_apply_ui_scaling`
- `_init_widget_cache`, `_get_widget`
- `_set_widget_value`, `_read_widget_value`, `_set_combo_value`
- `_clear_all_input_fields`
- `_setup_package_dropdown` samo UI dio
- `_setup_trading_name_field`
- `_setup_rb40_widgets` samo UI dio
- `_add_navigation_controls`
- `_add_section_heading`
- `_position_section_heading_buttons`
- `_add_status_bar`
- `_setup_rb44_pd_codes_field`
- `_setup_apply_to_all_indicators`
- `_setup_tab_order`, `_setup_keyboard_shortcuts`
- `_flash_field_border`
- `_populate_tariff_description` preimenovan u `render_tariff_result`
- `_check_and_show_tariff_warning` preimenovan u `render_tariff_warning`
- `_show_tariff_suggestion_dialog`
- validation highlight/focus metode
- `resizeEvent`, `eventFilter`, `keyPressEvent`

View helperi za normalizaciju ostaju samo ako su čisto prezentacioni. Model
normalizacija prelazi u Service.

### 7.2 Prelazi u Controller

- save-before-navigation tok iz `_navigate_to_item`
- `_on_add_item`
- `_on_delete_item`
- `_on_save`
- `_on_tariff_enter`
- debounce orchestration iz `_perform_tariff_lookup`
- `_on_tariff_suggestion_accepted`
- `_on_manual_tariff_search`
- `_on_import_xml`
- `_on_inspekcije`
- `_on_rubrika40_1_finished`
- `_on_rubrika40_2_finished`
- `_on_rubrika40_3_finished`
- `_on_rubrika44_4_finished`
- `_on_ponisti`
- koordinacija `_sync_header_packages`
- koordinacija `_sync_pe_docs_to_header`
- koordinacija Zaglavlje reload-a poslije XML importa

Controller metode primaju podatke/signale, ne čitaju widgete direktno.

### 7.3 Prelazi u Service ili postojeći specijalizovani servis

- `_normalize_field_value`
- `_format_trading_names`, ali prima `draft`, item/ordinal i `max_chars`
- `_parse_cost`
- `_compute_pd_codes`
- `_compute_statistical_value`
- `_resolve_supplementary_unit`
- tarifni opis lookup u postojeći `TariffService`
- dohvat pakovanja i prethodnih dokumenata u postojeći `NaimenovanjaService`
- dohvat historijskih dokumenata
- dohvat tarifnih kontrolnih dokumenata
- merge/deduplikacija globalnih XML dokumenata
- PE dokument normalizacija
- priprema izmjene tarife za povezane `InvoiceLine` stavke

### 7.4 Mora se razbiti, ne premjestiti kao cjelina

| Postojeća metoda | Razdvajanje |
| --- | --- |
| `_save_current_item` | View `read_current_form` → Service normalize/apply → Controller sync side-effect → View refresh |
| `_load_current_item` | Controller bira item/kontekst → Service računa vrijednosti → View renderuje |
| `_perform_tariff_lookup` | Controller debounce handler → TariffService lookup → document service → View render |
| `_auto_populate_supplementary_unit` | Service odredi kod/količinu → Controller primijeni na item → View render |
| `_ask_update_knowledge_base` | View potvrda → Controller → `TariffFacade.sync_mapping` |
| `_sync_tariff_to_source` | Service pouzdano pronađe sve povezane linije → Controller primijeni → TariffFacade učenje |
| `_apply_xml_import_to_zaglavlje` | View bira fajl → Controller → ZaglavljeService → draft → Zaglavlje reload callback |
| `_suggest_tariff_impl` | Service priprema kandidata → View dijalog → Controller primijeni prihvaćeni rezultat |

## 8. Faze implementacije

## Faza 0 — baseline, karakterizacija i branch zaštita

### Rad

- Kreirati refaktor granu/worktree.
- Sačuvati početni commit hash.
- Pokrenuti punu suite i evidentirati postojeće padove.
- Napraviti offscreen screenshot ili widget-state snapshot taba.
- Dodati karakterizacione testove bez promjene produkcionog ponašanja.

### Obavezni novi testovi

1. `test_naimenovanja_form_roundtrip.py`
   - svako mapirano polje item → View → item;
   - `Decimal`/float/prazne vrijednosti;
   - tarifni format ostaje bez tačaka.
2. `test_naimenovanja_navigation_characterization.py`
   - save prije next/previous/combo;
   - granice prvog i zadnjeg itema;
   - jedno snimanje po navigaciji.
3. `test_naimenovanja_signal_characterization.py`
   - jedan klik emituje jedan signal;
   - nema duplih konekcija poslije reload-a.
4. `test_naimenovanja_multidraft.py`
   - promjena drafta ne prikazuje niti mijenja stari draft.
5. Proširiti Rub.40/44, PE i XML testove.

### Gate

- Nema produkcionih izmjena.
- Novi karakterizacioni testovi prolaze na starom kodu.
- Puna suite rezultat nije lošiji od baseline-a.

### Commit

`test(naimenovanja): zakljucaj ponasanje prije 3layer refaktora`

## Faza 1 — ugovori i composition root bez promjene ponašanja

### Rad

- Dodati `NaimenovanjaController` sa praznim/bezbjednim signal wiringom.
- Dodati neutralne result dataclasses.
- `NaimenovanjaTab` dobija injektovani Service i kreira Controller.
- `TabFactory` stvarno prosljeđuje registrovani `NaimenovanjaService`.
- Controller koristi `get_draft_fn`, bez `self.draft`.
- Zadržati sve stare View handlere aktivne dok nema migriranog signala.

### Posebna zaštita

Ne povezivati Controller na signal koji još obrađuje View. Svaki signal se
prespaja tek u fazi njegovog vertikalnog reza.

### Gate

- Kreiranje taba radi preko `TabFactory`.
- `reload_data`, package sync i `data_changed` ostaju kompatibilni.
- Test potvrđuje da je ista service instanca proslijeđena iz DI containera.

### Commit

`refactor(naimenovanja): uvedi controller composition root bez promjene toka`

## Faza 2 — čiste kalkulacije i read-only lookupi

### Rad

Prvo izdvojiti metode bez side-effecta:

- format trgovačkih naziva;
- parse troška;
- PD kodove;
- statističku vrijednost;
- dopunsku jedinicu;
- package/previous-document kataloge;
- tarifne opise kroz postojeći `TariffService`.

Service testovi koriste stvarni SQLite/PostgreSQL gdje postoji DB pristup; ne
mockovati bazu. Čiste kalkulacije testirati direktno.

### Gate

- Service moduli nemaju `PySide6` import.
- Rezultati su identični karakterizacionim očekivanjima.
- Rb.31 GUI prikaz i XML builder pravila ostaju odvojeni.

### Commit

`refactor(naimenovanja): izdvoji ciste kalkulacije i lookup rezultate`

## Faza 3 — DB/UI setup razdvajanje

### Rad

Razdvojiti:

- `_setup_package_dropdown`
- `_setup_rb40_widgets`

Service vraća kataloge; View samo kreira i puni widgete uz `blockSignals`.
Nema DB poziva iz View-a.

### Gate

- Statička provjera: nema `get_db_connection`, SQL ili repository importa u
  `naimenovanja_view.py`.
- Dropdown sadržaj i trenutna selekcija identični baseline-u.
- Reload ne duplira stavke niti signalne konekcije.

### Commit

`refactor(naimenovanja): razdvoji sifarnike od widget setupa`

## Faza 4 — save i navigacija kao prvi Controller vertikalni rez

### Rad

1. View dobija `read_current_form()` i `render_current_item()`.
2. Service dobija normalizaciju i primjenu forme na item.
3. Controller implementira:
   - save current;
   - next/previous/combo navigation;
   - add;
   - delete;
   - save draft;
   - reset.
4. Prespojiti samo odgovarajuće View signale.
5. Ukloniti samo migrirane stare handlere.

### Invarijante

- trenutni item se snima prije promjene indeksa;
- `is_loading` blokira rekurzivno snimanje;
- `current_item_index` uvijek pripada aktivnom draftu;
- delete posljednjeg itema ostavlja validno stanje;
- `data_changed` se emituje jednom po potvrđenoj mutaciji;
- `on_dirty` se poziva jednom.

### Gate

- GitNexus impact ponoviti za `_save_current_item` prije izmjene.
- Svi navigation/roundtrip/multi-draft testovi prolaze.
- Ručni offscreen test 100+ itema prolazi.

### Commit

`refactor(naimenovanja): premjesti save i navigaciju u controller`

## Faza 5 — tarifni tok

### Rad

Migrirati kao jedan koherentan tok:

```text
tariff text changed
→ View čisti prikaz i emituje kod
→ Controller upravlja debounce timerom
→ TariffService lookup
→ Service određuje dopunsku JM i dokument kandidate
→ Controller primjenjuje rezultat na aktivni item/draft
→ View renderuje opis/upozorenje
```

KB učenje se pokreće samo nakon eksplicitne potvrde korisnika. View prikazuje
potvrdu, Controller poziva `TariffFacade`.

### Kritična korekcija

`_sync_tariff_to_source` ne smije pretpostaviti samo
`ordinal_no - 1`. Za grupisana naimenovanja treba koristiti stvarnu vezu
`assigned_naimenovanje_ordinal` i ažurirati sve pripadajuće `InvoiceLine`
stavke prema eksplicitnom pravilu. Prije promjene napisati karakterizacioni
test za 1:1 i grupisani slučaj.

### Gate

- fuzzy threshold i postojeći prioriteti nisu mijenjani;
- ručna promjena tarife ne uči pogrešnu stavku;
- jedan Enter daje najviše jedno KB ažuriranje;
- bez direktnog Groq/Gemini poziva;
- tarifni opisi, warning i dokumenti identični baseline-u.

### Commit

`refactor(naimenovanja): premjesti tarifni tok u controller i servise`

## Faza 6 — Rub.40, Rub.44, PE i dokumenti

### Rad

- Service vraća deduplikovan `DocumentMergeResult`.
- Controller primjenjuje dokumente na draft.
- View prikazuje kombinovane vrijednosti.
- Sinhronizacija prema Zaglavlju ide callbackom kroz wrapper/MainWindow
  integraciju, ne `self.window()` iz Service-a.

### Invarijante

- PE1/PE2/PE3 ne postoje u Rub.44 bez odgovarajuće Rub.36 povlastice;
- sekundarni PE dokumenti se čiste po postojećem pravilu;
- DIS broj se zadržava, ostale XML reference se prazne;
- header i item dokumenti se ne dupliraju;
- historijski/kontrolni dokument ne postaje dokaz za povlasticu;
- `from_rule` semantika ostaje ista.

### Gate

- svi `test_pe_rub44_consistency.py` testovi;
- novi testovi za deduplikaciju i XML dokumente;
- decision/XML preflight integracioni testovi.

### Commit

`refactor(naimenovanja): izdvoji rub40 rub44 i pe dokument tok`

## Faza 7 — XML import, prijedlozi, inspekcije i kompatibilni API

### XML tok

```text
View file dialog
→ xml_import_requested(path)
→ Controller parsira preko postojećeg servisa
→ Service vraća neutralan rezultat
→ Controller ažurira isti draft
→ Controller traži reload Zaglavlja
→ View renderuje aktivni item
```

`NaimenovanjaTab` izlaže potrebne callbacke umjesto da Service traži
`MainWindow`.

### Tarifni prijedlog

- Service priprema kandidata.
- View prikazuje postojeći dijalog.
- View emituje prihvaćeni payload.
- Controller validira i primjenjuje.

### Inspekcije

View može otvoriti dijalog, ali podatke i pravila dobija iz Service-a.

### Gate

- XML import ne mijenja Rb.18/21 prevoz;
- Zaglavlje dobija očekivane podatke;
- odbijen dijalog nema mutaciju;
- prihvaćen prijedlog mijenja tačno aktivni item;
- wrapper API ostaje kompatibilan za MainWindow, Faktura i Agent tok.

### Commit

`refactor(naimenovanja): dovrsi xml i prijedlog controller tokove`

## Faza 8 — čišćenje, paritet i završna validacija

### Rad

- Obrisati samo dokazano nepovezane stare metode.
- Ukloniti duplikat `_extract_short_code`.
- Ukloniti lokalne service importe iz View-a.
- Provjeriti da nema zakomentiranog starog koda.
- Preslikati tačno odobrene fajlove u `dist_client`.
- Ne regenerisati `.ui` Python fajlove ako UI izvor nije mijenjan.
- Ažurirati dokumentaciju i agent report.

### Statičke kapije

```text
naimenovanja_view.py:
  nema SQL/DB konekcije
  nema TariffFacade mutacije
  nema direktnog Controller poziva

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

1. Ciljani Naimenovanja testovi.
2. Faktura → kreiranje → Naimenovanja reload.
3. Agent → Naimenovanja refresh.
4. XML import i XML preflight.
5. Multi-draft.
6. Root/`dist_client` sadržajni paritet.
7. `py_compile`.
8. Puna `pytest tests/ -q` suite.
9. Offscreen GUI smoke test.
10. Ručna provjera na stvarnoj fakturi iz `najavauvoza/`.

### Commit

`refactor(naimenovanja): ukloni stari monolitni wiring i potvrdi paritet`

## 9. Test matrica

| Tok | Unit | Integracija | GUI/offscreen | Ručno |
| --- | --- | --- | --- | --- |
| item roundtrip | obavezno | — | obavezno | — |
| navigacija | obavezno | — | obavezno | obavezno |
| multi-draft | obavezno | obavezno | obavezno | obavezno |
| tarifa/dopunska JM | obavezno | stvarna tarifa DB | obavezno | obavezno |
| KB učenje | obavezno | stvarni test DB | — | kontrolisano |
| Rub.40/44/PE | obavezno | XML preflight | obavezno | obavezno |
| XML import | obavezno | obavezno | obavezno | obavezno |
| package katalog | obavezno | stvarna baza | obavezno | — |
| signal wiring | obavezno | — | obavezno | — |
| Faktura/Agent reload | — | obavezno | obavezno | obavezno |

DB testove ne zamjenjivati mockovima. Dozvoljen je fake Service u čistim
Controller testovima, ali repository/SQLite/PostgreSQL integracija mora imati
poseban test sa stvarnom test bazom.

## 10. Stop i rollback kriteriji

Implementacija se odmah zaustavlja ako:

- aktivni draft i prikazani item više nisu isti;
- navigacija izgubi nesnimljenu vrijednost;
- jedan signal pokrene handler dva puta;
- XML sadržaj se promijeni bez eksplicitne poslovne odluke;
- Rub.36/Rub.44 konzistentnost se pogorša;
- grupisana tarifa izmijeni nepovezanu InvoiceLine;
- `dist_client` odstupa od root implementacije;
- puna suite dobije novi pad.

Rollback:

- revertovati samo commit te faze;
- ne popravljati regresiju dodavanjem compatibility grananja u više slojeva;
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
- Promjena Rb.31 XML builder pravila.
- Automatsko dodjeljivanje povlastice.
- Promjena ASYCUDA XML šeme.
- Potpuno premještanje vlasništva drafta iz View-a.
- Preimenovanje srpskih `InvoiceLine` polja.
- Čišćenje drugih tabova.

Svaki pronađeni funkcionalni bug van ovog scope-a evidentirati kao poseban
follow-up; ne popravljati ga usput u refaktor commitu.

## 13. Procjena vremena

Realna procjena za jednog agenta uz testove:

| Faza | Procjena |
| --- | --- |
| 0 — baseline/karakterizacija | 3–5 h |
| 1 — ugovori/composition root | 2–3 h |
| 2 — čiste kalkulacije | 3–5 h |
| 3 — DB/UI setup | 2–4 h |
| 4 — save/navigacija | 4–6 h |
| 5 — tarifni tok | 4–7 h |
| 6 — Rub.40/44/PE | 4–7 h |
| 7 — XML/prijedlozi/integracija | 4–6 h |
| 8 — čišćenje/puna validacija | 3–5 h |
| Ukupno | 29–48 h |

Vrijeme je veće od Pi procjene jer uključuje karakterizaciju 108 metoda,
multi-draft, signal wiring, stvarne DB testove, integracione tokove i
`dist_client` paritet.

## 14. Konačni acceptance kriteriji

Refaktor je završen tek kada:

- svih osam faza ima zeleni checkpoint;
- nema novih padova pune suite;
- Naimenovanja tab radi sa pojedinačnim i grupisanim stavkama;
- save-before-navigation je dokazan testom;
- multi-draft je dokazan testom;
- tarifna promjena ažurira samo pripadajuće InvoiceLine stavke;
- Rub.40/44/PE i XML preflight ostaju konzistentni;
- drugi tabovi koriste stabilan wrapper API;
- View nema DB/business side-effecte;
- Service nema Qt;
- Controller koristi signale i nema widget pristup;
- root i `dist_client` su sadržajno jednaki;
- korisnik ručno potvrdi osnovni tok na Windows instalaciji;
- promjene prođu obavezni review prije mergea u `windows`.

## 15. Preporučena odluka

Plan je spreman za realizaciju tek nakon korisničke potvrde:

1. da se kreira `refactor/naimenovanja-3layer` iz potvrđenog `windows` basea;
2. da se Faza 0 realizuje i preda na pregled prije produkcionog refaktora;
3. da se svaka naredna faza nastavlja samo iz posljednjeg zelenog checkpointa;
4. da merge u `windows` bude ručno odobren tek nakon Faze 8.
