<!--
Ovaj fajl je operativni plan za VIŠE agent sesija (Codex, druge Claude sesije).
Kopiran je iz project_room_template.md ali proširen fazama jer je posao
prevelik za jedan project_room task — svaka faza ispod je zapravo zaseban
project_room task, grupisan ovdje da se ne gubi cjelina.

PRAVILO ZA SVAKOG AGENTA KOJI OVO ČITA: pročitaj CIJEO ovaj fajl prije nego
počneš bilo koju fazu, čak i ako radiš samo jednu. Faze zavise jedna od
druge (redoslijed nije proizvoljan — vidi "Zašto ovaj redoslijed" niže).
Kad završiš fazu, ažuriraj status te faze u ovom fajlu (PENDING → DONE,
datum, commit hash) PRIJE nego kreiraš agent_report.
-->

# Faktura 3-layer refaktor — fazni plan ekstrakcije poslovne logike

## Cilj

`gui/tabs/faktura_view.py` (6267 linija) treba svesti na tanak View (samo
UI/signali) po 3-layer pravilu iz `AGENTS.md`. Prethodni Codex refaktor
(52 commit-a, Faza 8-12 + cleanup A-E8, spojen u `windows`) je izgradio
servisnu infrastrukturu (`services/faktura/`, ~1746 linija kroz 12+
fajlova) i preimenovao dio privatnih metoda, ali NIJE smanjio View —
linijski je pao samo -2.4% (6424→6267). Legacy implementacije su
NAMJERNO ostale kao fallback (potvrđeno u Codex-ovom vlastitom
`agent_reports/2026-08-01_faktura-zavrsni-e-cleanup-audit.md`). Ovaj plan
pokriva STVARNU ekstrakciju — dio koji tek predstoji.

## Trenutno stanje (mjereno 2026-08-01, provjeriti ponovo prije svake faze)

| Metrika | Vrijednost |
|---|---|
| `gui/tabs/faktura_view.py` | 6267 linija |
| `services/faktura/` | ~1746 linija, 18 fajlova |
| `faktura_controller.py` | 217 linija |
| `faktura_tab.py` | 189 linija |
| Ukupno metoda u `faktura_view.py` | 157 (`grep -c "^    def "`) |
| `_on_*` Qt signal handleri (legitimni, NE dirati u ovom planu) | 25 |
| Ostale privatne metode (inventarisane niže po fazama) | 119 |
| Direktni pozivi `self.validator.*`/`self.assembly.*` iz View-a | 13 (10 van `_on_*`, 3 unutar `_on_load_master_list`) |
| Direktan SQL/DB poziv u View-u | 0 (već čisto) |

**Update 2026-08-01 (nakon spajanja Faza 1+2+3)**: Pi je uradio Faze 1+2
(grana `refactor/faktura-3layer-claude`), Codex nezavisno Fazu 3 (grana
`refactor/faktura-3layer-codex`) — OBJE bazirane na istom plan-commitu,
rađene paralelno bez znanja jedna o drugoj (vidi "Paralelni agenti" u
AGENTS.md). Spojeno u `refactor/faktura-3layer-claude` preko
`git merge-tree` provjere (0 konflikata) pa pravog merge-a (commit
`fae293b`, auto-merged bez konflikata). Nakon spajanja: `faktura_view.py`
= **6046 linija** (bilo 6267), **148 metoda** (bilo 157). Pun test suite:
**1417 passed / 71 skipped / 2 deselected / 5 xfailed / 1 failed** —
taj jedan fail (`test_db_tariff_mapping_unknown_product_returns_none`)
NIJE regresija ovog merge-a, isti je poznati recidivni DB-data-quality
bug iz `~/.claude/projects/.../memory/2026-08-01_product-tariff-mapping-word-overlap-mina-bug.md`
(red se vratio, usage_count sada 8) — algoritam nije popravljen, samo je
red bio jednom obrisan ranije istog dana. Grana JOŠ NIJE spojena u
`windows`.

**⚠️ Ne ponavljati "% završeno" bez provjere.** Prije svake tvrdnje o
napretku, ponoviti: `grep -c "^    def " gui/tabs/faktura_view.py`,
`wc -l gui/tabs/faktura_view.py services/faktura/*.py`. Vidi
`~/.claude/projects/.../memory/2026-08-01_faktura-3layer-refaktor-nije-zavrsen.md`
za istoriju ovog istog previda (Codex je ranije tvrdio "65%" na osnovu
workflow-coverage, ne linija koda).

## Pogođeno (GitNexus impact, provjereno 2026-08-01)

- `FakturaView` klasa (upstream, depth 2): **LOW** rizik, 10 pogođenih,
  4 direktna importera (`faktura_tab.py`, `agent_controller.py`, oba i u
  `dist_client/`). Sama klasa nije široko nasljeđivana/reusable — rizik je
  lokalizovan na sam fajl i njegovo wiring.
- `FakturaItemValidator` (upstream, depth 2): **MEDIUM** rizik, 30
  pogođenih, 14 direktnih (validation adapteri, agent chat intent handler,
  import pipeline service, `invoice_review_service.py`). Ova klasa se
  dijeli sa agent-chat tokom — Faza 3 (koja mijenja KO je poziva, ne ŠTA
  ona radi) mora ostaviti javni API `FakturaItemValidator`/
  `DeclarationAssembly` netaknut, samo premjestiti mjesto poziva.
- Svaki agent koji radi na Fazi 3+ MORA ponovo pokrenuti
  `gitnexus_impact` na konkretan simbol koji dira (metod-po-metod), ovo
  gore je samo klasni nivo, ne pokriva sve.

## Konflikti / poznati rizici prije početka

1. **`.worktrees/faktura-3layer/` (grana `refactor/faktura-3layer`) je
   ZASTARJELA** — njen vrh (`b5801b6`) je ancestor od `windows`, ali
   `windows` je od tad otišao dalje (Codex-ov 52-commit talas). Worktree
   ima i nepovezan uncommitted WIP (`ui/naimenovanja_tab_OPTIMIZED_ui.py`,
   `ui/zaglavlje_tab_ui.py` i dist_client parnjaci). **NE koristiti ovaj
   worktree kao polaznu tačku** — radi se na `windows` direktno ili u
   NOVOM worktree-u. Korisnik nije još odlučio da li da se stari worktree
   obriše — ne dirati ga dok se to ne potvrdi.
2. **`services/faktura/import_service.py` (`ImportService`) NIJE mrtav
   kod globalno** — koristi ga `gui/tabs/agent/widgets/processing_worker.py`
   (agent import pipeline) — ali NIJE ožičen u `FakturaView`. Metode sa
   istim imenom u `faktura_view.py` (`_get_invoice_name`,
   `_track_file_type`, `_extract_import_result_data`) NE smiju se slijepo
   zamijeniti pozivom na `ImportService` — prvo uporediti ponašanje
   red-po-red (agent pipeline nema GUI kontekst, View ima), vidjeti Fazu 2.
3. **`_finish_import_legacy_path` i `_process_batch_records_legacy` NISU
   mrtav kod, i NISU nedovršena migracija.** `_can_use_unified_manual_import()`
   vraća `False` (aktivira legacy granu) kad god je
   `self.assembly.master_list_loaded` True. PROBE (2026-08-02, vidi
   `project_rooms/2026-08-02_faza6-probe-legacy-uvoz-status.md`) je
   potvrdio da je ovo TRAJNA, namjerna arhitektonska odluka iz odobrenog
   master plana (`docs/architecture/JEDINSTVENI_IMPORT_WORKFLOW_
   IMPLEMENTATION_PLAN.md`) — Assembly/master-list tok se NEĆE spajati sa
   unified putem. Faza 6 je preformulisana: ekstrakcija u servis, ne
   odluka o arhitekturi (ta odluka je već donesena).
4. **`_collect_tariff_previews` (linija 5441) nema nijednog pozivaoca**
   nigdje u repou (provjereno grep na cio repo, samo definicija u
   `faktura_view.py`/`dist_client`/worktree kopijama) — vjerovatno mrtav
   kod, kandidat za brisanje u Fazi 1, ali agent koji to radi treba još
   jednom potvrditi (git blame — da nije namijenjen za skoro korišćenje;
   provjeriti da nema dynamic dispatch preko `getattr`).

## Zašto ovaj redoslijed faza

Rastući rizik i veličina — svaka faza je samostalno commit-ovana i
verifikovana prije sljedeće, tako da se refaktor može zaustaviti bilo gdje
bez da ostane u polu-završenom stanju:

1. Mehanički thin-wrapperi (skoro nulti rizik) →
2. Čiste funkcije bez Qt zavisnosti (nizak rizik) →
3. Arhitektonski fix direktnih servisnih poziva (MEDIUM gitnexus, ali
   mala količina koda) →
4. Srednje orkestracione metode (veći obim, mixed UI+logika) →
5. UI-utkana poslovna logika (zahtijeva pažljivo razdvajanje) →
6. Legacy uvoz putevi — najveći i najrizičniji, aktivna grana →
7. `_on_*` handleri sa utkanom logikom — van trenutnog inventara, sledeći krug

---

## FAZA 1 — Mehanički thin-wrapperi i mrtav kod

**Status: DONE — 2026-08-01, commit `365d0a7` (Pi), fix `e9cdf18`**

**Cilj**: Ukloniti View metode koje su već čist duplikat postojeće servisne
funkcije — zamijeniti pozive direktnim pozivom servisa, obrisati wrapper.

| Metoda | Linije | Akcija |
|---|---|---|
| `_format_issue_counts` (static) | 1992-1994 | Obrisati, pozivaoci → `FakturaService.format_issue_counts` |
| `_parse_number` | 1996-1998 | Obrisati, pozivaoci → `FakturaService.parse_number` |
| `_parse_weight_input` | 2000-2002 | Obrisati, pozivaoci → `FakturaService.parse_weight_input` |
| `_distribute_invoice_weights` | 2907-2919 | Obrisati, pozivaoci → `MassCalculator.calculate_masses` |
| `_format_weight` | 3045-3074 | Obrisati, pozivaoci → `FakturaService.format_weight` (ili `WeightManager.format_weight` — PRVO provjeriti da su ta dva servisa identična, ako nisu, ovo je "EKSTRAKCIJA" ne "DUPLIKAT", eskalirati) |
| `_accumulate_weights` | 3076-3105 | View verzija dodatno piše `input_bruto`/`input_neto` (UI polja) — razdvojiti: kalkulacija → `WeightManager.accumulate_weights`, UI upis ostaje tanak poziv u View |
| `_collect_tariff_previews` | 5441-5468 | Obrisati (mrtav kod — vidi "Konflikti" #4), NE ekstrahovati |

**Šta NE dirati**: `_format_weight`/`_accumulate_weights` semantiku
(preciznost, bez zaokruživanja — AGENTS.md pravilo "Formatiranje težina").

**Plan verifikacije**: `python -m pytest tests/unit -k "faktura or weight" -q -m "not integration"` prije/poslije identičan broj passed; `wc -l gui/tabs/faktura_view.py` mora pasti za otprilike 60-80 linija; ručna GUI provjera: import fakture + provjera da su bruto/neto/format brojeva identični kao prije.

**Nezavisni checker**: nije obavezan (LOW rizik), ali preporučen brz `/code-review` pregled diff-a.

**Ko radi**: pogodno za Codex ili bilo koju agent sesiju bez posebnog konteksta — najmehaničkija faza.

---

## FAZA 2 — Čiste funkcije bez Qt zavisnosti

**Status: DONE — 2026-08-01, commit `365d0a7` (Pi), fix `e9cdf18`. Faza 1+2 rađene u istom commitu.**

**Cilj**: Premjestiti čiste funkcije (bez `self.table`/Qt widget pristupa)
u `services/faktura/` — ili postojeći fajl po temi, ili novi
`services/faktura/undo_redo_service.py`.

| Metoda | Linije | Target servis |
|---|---|---|
| `_format_number` | 1416-1424 | `FakturaService` (uz postojeći `format_weight`) |
| `_validation_issue_label` (static) | 1977-1989 | `validation_service.py` |
| `_normalize_partner` (static) | 2959-2964 | novi ili postojeći partner-utility |
| `_is_same_combined_invoice` | 2921-2937 | `import_service.py` ili `weight_guards.py` |
| `_append_imported_files_message` | 2939-2951 | isti fajl kao gore (poruke uvoza) |
| `_calculate_masses_success_message` | 5128-5150 | `mass_workflow_service.py` |
| `_extract_header_from_xml` (static) | 6096-6144 | novi `xml_header_extraction.py` ili postojeći XML servis — VISOKA vrijednost, XML parsing bez Qt |
| `_count_applied_batch_file_types` | 3512-3525 | `import_service.py` |
| `_postprocess_master_frigo_pairs_records` | 2460-2502 | `import_service.py` — provjeriti da ne dira dobavljač-specifičan parser kod van scope-a |
| `_push_undo_snapshot` / `_undo` / `_redo` | 1677-1708 | novi `undo_redo_service.py` — `_undo`/`_redo` imaju UI refresh dio, taj dio ostaje u View kao tanak poziv |
| `_reset_partner_expectations` | 3040-3043 | isti fajl kao `_normalize_partner` |

**Šta NE dirati**: Rb.31 max 280 znakova/3 linije pravilo u `_extract_header_from_xml` ako postoji dodir sa tim poljem (provjeriti prije premještanja) — `docs/CONTEXT.md` §3.

**Plan verifikacije**: isti kao Faza 1, plus test XML uvoza sa realnim fajlom iz `najavauvoza/` prije/poslije (za `_extract_header_from_xml`).

**Ko radi**: srednje iskustvo sa projektom — treba pratiti importe da se ne naprave kružni importi (AGENTS.md zabrana: `agent_controller.py` → servis kružni import).

---

## FAZA 3 — Ukloniti direktne View→Servis pozive (arhitektonski fix)

**Status: DONE — 2026-08-01, commit `603da5e`**

Rezultat: Controller sada kreira i posjeduje `FakturaItemValidator` i
`DeclarationAssembly`; `FakturaTab` veže Controller u View kroz
`view.set_controller(controller)`. `FakturaView._validation_issue_counts()` više
ne koristi `self.validator.validate(...)`, nego ide kroz Controller adapter.
`FakturaView._update_status_bar()` više ne čita assembly status direktno nego
preko Controller adaptera. Legacy/master-list `self.assembly` pozivi su
namjerno ostavljeni za Fazu 6/7, uz migracioni alias na Controller-owned
assembly.

Stvarno mjerenje poslije faze u Codex worktree-u:
`faktura_view.py` 6289 linija / 160 metoda; `faktura_controller.py` 234 linije;
`faktura_tab.py` 190 linija; `services/faktura/` 18 fajlova / 1954 linije.
Faza 3 je arhitektonski fix, ne line-reduction faza, pa je View privremeno
porastao zbog tri mala adaptera. Test kapija: py_compile root/dist Faktura
fajlova; root controller/status 44/44; dist status 8/8; fokusirani
Faktura/import/pipeline set 71/71. Širi `tests/unit -m "not integration"`:
1398 passed, 21 failed zbog postojećih DB/env problema (`tarifa_2026`,
`DB_PASSWORD`, `DEBUG=release`), ne zbog Faze 3.

**Cilj**: `self.validator`/`self.assembly` prestaju biti direktno
instancirani i pozivani iz `FakturaView.__init__` (linije 262-263) i iz
metoda ispod — Controller preuzima vlasništvo nad tim instancama, View
poziva Controller.

| Metoda | Linije | Direktni pozivi |
|---|---|---|
| `_validation_issue_counts` | 1957-1974 | `self.validator.validate(line)` (linija 1967) |
| `_update_status_bar` | 2063-2199 | `self.assembly.master_list_loaded`/`get_completion_status()` (linije 2176-2177) |

**Napomena**: `_finish_import_legacy_path` i `_process_batch_records_legacy`
imaju još 7 direktnih poziva ukupno — namjerno OSTAVLJENI za Fazu 6 jer su
te metode toliko velike da razdvajanje "direktan poziv" od "ostatak logike"
nema smisla raditi odvojeno. `_on_load_master_list` (3 poziva) je van
scope-a ovog plana (vidi Fazu 7).

**Plan verifikacije**: **OBAVEZNO** ponovo pokrenuti
`gitnexus_impact({target: "FakturaItemValidator", direction: "upstream"})`
i `gitnexus_impact({target: "DeclarationAssembly", direction: "upstream"})`
prije izmjene — ovaj plan dokument ima MEDIUM iz 2026-08-01, provjeriti da
se nije promijenilo. Puni test suite (`python -m pytest tests/unit -q -m
"not integration"`) mora ostati na istom broju passed/failed kao baseline
(trenutno 1414 passed / 1 unrelated fail — DB podatak, već riješeno).

**Nezavisni checker: OBAVEZAN** (MEDIUM GitNexus impact po AGENTS.md
pravilu). Checker posebno provjerava da agent-chat tok (koji dijeli
`FakturaItemValidator` — vidi `services/agent/validation/*`) i dalje radi
identično nakon promjene mjesta poziva.

**Ko radi**: agent sa punim kontekstom 3-layer pravila, PLUS nezavisan
checker (druga sesija).

---

## FAZA 4 — Srednje orkestracione metode (mixed UI+logika)

**Status: DONE — sve 4 podfaze (4a-4d) završene, vidi statuse ispod**

Grupisano po funkcionalnoj oblasti — svaka grupa može biti zaseban
pod-zadatak unutar ove faze, ne mora sve jedan agent odjednom:

**4a. Uvoz-workflow orkestracija** (novi ili postojeći `import_workflow` servisi):

**Status: DONE — 2026-08-01**

Urađeno:
- Codex (`1b3a708`): 9 metoda u `ImportWorkflowService`
- Pi (`08f77b0`): preostale 2 metode — `_start_import` ostaje u View-u
  (čist UI metod, nema poslovne logike za ekstrakciju),
  `_collect_manual_import_decisions` delegira inicijalizaciju
  `UserDecisions`/`InvoiceDecision` u `ImportWorkflowService.init_import_decisions()`,
  dijalozi za konflikte ostaju u View-u.

**Status: DONE — 2026-08-01, commit `009d69d` (Pi)**

Urađeno: novi `services/faktura/preference_rules_service.py` (111 linija):
- `similar_partner_names(a, b)` — token-overlap logika iz `_check_partner_consistency`
- `suggest_preference_by_country(country_code, exporter_name)` — EU/CEFTA/TR/IR pravila +
  istorijsko učenje
- `should_show_eur1_dialog(items)` / `should_show_pe2_dialog(items)` — pravila odluke
- `auto_handle_povlastice_agent(draft, has_origin_statement)` — agent mod logika

View metode postale thin wrapper-i koji delegiraju servisu.
`_check_partner_consistency` zadržava QMessageBox dijalog (UI), ali `similar()` logika
je izdvojena u servis.

`faktura_view.py`: 5888 linija (-130), 149 metoda (isto).

**Status: DONE — 2026-08-01, commit `1ec7b19` (Pi)**

Urađeno: novi `services/faktura/header_doc_sync_service.py` (87 linija):
- `collect_pe_docs_from_items(items)` — sakupljanje PE1/PE2/PE3 iz attached_document4
- `build_pe_attached_documents(pe_entries)` — kreiranje AttachedDocument objekata
- `collect_inspection_docs_from_items(items, existing_codes)` — inspekcijski dokumenti
  po tarifnom broju

`_sync_pe_docs_to_header` i `_sync_inspection_docs_to_header` postale thin wrapper-i.

Namjerno ostavljeno u View-u (nisu kandidati za ekstrakciju):
- `_run_create_naimenovanja_post_actions` — orkestracija signala/UI poziva,
  flagovi su već u `plan` objektu, nema poslovne logike za izdvajanje
- `_reload_naimenovanja_tab` — 100% cross-tab UI (Qt window, tab reference,
  reload_data, _sync_header_packages, load_from_draft)
- `_set_weight_inputs_from_draft` — trivijalna (7 linija), kalkulacija totala
  + UI upis, premalo za izdvajanje

`faktura_view.py`: 5837 linija (-51), 149 metoda (isto).

**Status: DONE — 2026-08-01, commit `3aa8227` (Pi)**

Urađeno:
- `FakturaService.parse_mass_inputs(bruto_text, neto_text)` — parsiranje toolbar
  polja sa validacijom (baca ValueError za prazna/nula polja)
- `FakturaService.analyze_draft_rows(rows)` + `format_analysis_summary(analysis)` —
  analiza redova (bez tarife/zemlje/EUR1, zemlje) i formatiranje
- `ValidationService.count_issues_from_cache(cache, row_indexes)` — brojanje
  grešaka/upozorenja iz cache-a, skopirano na selekciju
- `ValidationService.build_validation_message(counts, error_issues, warning_issues, row_indexes)` —
  formatiranje validacionog message stringa

`_build_calculate_masses_request` — parsiranje delegirano servisu, QMessageBox ostaje u View-u.
`_build_analysis_summary_from_draft` — analiza delegirana servisu, čitanje iz Qt tabele ostaje.
`_validate_all_items` — brojanje i message builder delegirani servisu, Qt selekcija/bojenje ostaje.

Namjerno ostavljeno u View-u:
- `_run_historical_tariff_validation` — 100% UI orkestracija (Qt selekcija,
  HistoricalValidationWorker kreiranje, signal povezivanje, thread start),
  isti obrazac kao `_start_import` u Fazi 4a

`faktura_view.py`: 5763 linija (-74), 149 metoda (isto).
`faktura_service.py`: 202 linije (+70). `validation_service.py`: 197 linija (+55).

**Šta NE dirati**: fuzzy matching threshold `min_similarity=0.92` u bilo
kojoj od ovih putanja (AGENTS.md — ne spuštati bez eksplicitnog razloga);
tarifna politika (koja zemlja dobija koju povlasticu) je poslovna odluka —
`_suggest_preference_by_country` se SAMO premješta, pravila unutra se ne
mijenjaju u ovoj fazi.

**Plan verifikacije**: puni test suite + ručna GUI provjera stvarnim
fakturama iz `najavauvoza/` za svaku pod-grupu (posebno 4a i 4b — visok
broj edge case-ova po AGENTS.md "Testiranje" sekciji).

**Ko radi**: agent sa dobrim poznavanjem carinske domene (povlastice/EUR.1
pravila nisu očigledna iz koda) — preporučeno da PROČITA
`docs/CONTEXT.md` prije 4b posebno.

---

## FAZA 5 — UI-utkana poslovna logika (bojenje/tooltip pravila)

**Status: DONE — 2026-08-01 (Claude, ova sesija), vizuelno potvrđeno 2026-08-02**

Urađeno: `_apply_country_confidence_color` (sada linija 1479, ranije
1462-1534, linije se pomjerile nakon Faza 1-4), `_apply_preference_confidence_color`
(sada 1553) — pravilo (koja kombinacija evidence/confidence → koja
boja/ikonica/tooltip) premješteno u `services/faktura/validation_service.py`
kao `ValidationService.country_confidence_style(item)` i
`ValidationService.preference_confidence_style(item)`, obje vraćaju
`dict` ili `None`. Qt primjena (cell lookup, `setData`, `Qt.UserRole`
upis, tooltip merge sa postojećim tekstom) ostaje u View-u kao tanak
poziv — identična logika, samo premješteno mjesto odluke.

Prije izmjene pročitano svih 6 memorijskih zapisa iz "Zemlja porijekla /
povlastica" porodice (vidi MEMORY.md). Ključno pravilo iz
`2026-06-07_neutralna-boja-zemlje-bez-povlastice.md` ("Krug 3", finalna
verzija) — boja/ikonica na koloni Zemlja prati ISKLJUČIVO
`has_preferential_doc` (povlastica + PE dokaz), NIKAD `country_confidence`
samostalno — prekopirano bez izmjene, uz novi karakterizacioni test koji
to zaključava (vidi ispod).

**Novo**: `tests/unit/test_faktura_confidence_color_rules.py` (10 testova,
i u `dist_client/`) — ova oblast do sad NIJE imala automatski test,
svih 6 prethodnih bugova otkriveno preko korisničkog screenshot-a. Testovi
direktno kodiraju pravila iz memorije (Krug 1/2/3), uključujući regresioni
test da MEDIUM/LOW/CONFLICT confidence bez potvrđene povlastice i dalje
mora biti neutralna boja (ne prati svoju "confidence" boju) — tačno bug
iz Kruga 3.

`faktura_view.py`: 5763→**5682 linija** (-81). `validation_service.py`:
127→307 linija. `_CONFIDENCE_COLORS`/`_NEUTRAL_COUNTRY_COLOR` uklonjeni iz
`FakturaView` (mrtvi nakon ekstrakcije, `_CONFIDENCE_ICONS` ostaje —
koristi ga druga metoda). `evidence_from_preference` import uklonjen iz
`faktura_view.py` (nema više pozivaoca). GitNexus impact: LOW za obje
metode (1 pozivalac svaka — `_validate_and_color_row`), `gitnexus_detect_changes`
potvrđuje risk LOW, 0 affected_processes.

Pun test suite: 1433 passed / 1 poznat nepovezan DB nalaz (isti kao ranije).

**Plan verifikacije — ZATVORENO 2026-08-02**: korisnik pokrenuo aplikaciju
preko `python run.py`, uvezao stvarnu fakturu (94 stavke, više zemalja:
AT/DE/FR/IT/PL/PT/US...) kroz cio tok — uvoz → auto-ažuriranje tarifa →
Zaglavlje → Naimenovanja → Agent EUR.1 dijalog — bez ijedne greške.
Screenshot dijaloga "Automatski ažurirane tarife" potvrđuje red sa DE
(potvrđena EUPR povlastica preko PE dokaza) prikazan zeleno sa ✅, dok
red sa US (zemlja bez mogućnosti povlastice) ima praznu Povlastica
ćeliju bez upozorenja — poklapa se sa binarnim pravilom.

**Drugi screenshot (2026-08-02) — izolovan "Krug 3" slučaj eksplicitno
potvrđen** na realnoj fakturi (720/2026, 721/2026): RS redovi (CEFTA,
teoretski eligible) i CN redovi (nikad eligible) OBA prikazuju kolonu
Zemlja BEZ ✅ kvačice — identičan neutralni tretman, tačno kako pravilo
zahtijeva (eligibility ne smije uticati na ovu kolonu). Istovremeno,
kolona Povlastica ih ispravno razlikuje: RS redovi imaju žućkastu
pozadinu ("provjerite ručno" upozorenje — eligible ali nepotvrđena), CN
redovi nemaju nikakvu boju (upozorenje bi bilo besmisleno jer CN nikad
neće imati povlasticu). Ovo je tačna distinkcija tri kruga korekcije iz
memorije — potpuno vizuelno potvrđena, ne samo test-pokrivena.

**Nezavisni checker**: nije korišćen u ovoj sesiji — korisnikova vizuelna
potvrda + funkcionalni end-to-end test služe kao ekvivalent za GUI dio;
kod-nivo je pokriven novim karakterizacionim testovima umjesto ljudskog
code-review-a.

---

## FAZA 6 — Assembly/master-list uvoz logika (preformulisano nakon PROBE-a)

**Status: DONE — 2026-08-02 (Claude, ova sesija), commit `039e080` + e2e test `7b79367`, vizuelno potvrđeno u GUI-ju**

**Šta je stvarno urađeno (uže od originalnog cilja ispod, namjerno)**: nakon
čitanja pune ~330-linijske `_finish_import_legacy_path` metode, procjena je
bila da je to duboko Qt-isprepletena orkestracija (progress bar, redoslijed
dijaloga, mutacija drafta) — puna ekstrakcija "Assembly matching logike"
nije realna niti bezbjedna, jer ta logika VEĆ živi u `DeclarationAssembly`
servisu (`assembly.add_invoice()`); View samo orkestrira poziv i prikaz,
što je legitiman Controller/View posao, ne poslovna logika za izdvajanje.

Umjesto toga izdvojene su 3 ČISTE funkcije za građenje poruka (bez ijedne
Qt/self zavisnosti) u novi `services/faktura/legacy_import_service.py`:
`build_assembly_match_message`, `build_manual_import_prefix_message` +
`build_manual_import_suffix_message`, `build_legacy_batch_import_message`.
16 karakterizacionih testova napisano PRIJE ekstrakcije. Kontrolni tok,
redoslijed EUR.1/PE2 dijaloga, REPLACE/EXTEND odluka i sva mutacija drafta
OSTAJU namjerno u View-u — nisu poslovna logika u smislu koji Faze 1-5
ciljaju, nego orkestracija koja tu i pripada.

`faktura_view.py`: 5682→**5620 linija** (-62). Pun test suite (ponovljen
2026-08-02 nakon što je `dmserver` opet dostupan): **1449 passed / 71
skipped / 1 failed** — svih 10 ranije mrežno-blokiranih DB testova sada
prolazi čisto, potvrđujući da Faza 6 nije unijela regresiju. Jedini
preostali fail je poznati recidivni `product_tariff_mapping` "Test
proizvod" nalaz (usage_count sad 22) — nepovezan sa ovom ili bilo kojom
fazom refaktora.

**VAŽNA IZMJENA nakon PROBE-a**: originalna formulacija ove faze ("najveći,
najrizičniji, treba odlučiti da li legacy umire ili se unified proširuje")
je bila zasnovana na pretpostavci da je pitanje otvoreno. PROBE je otkrio
da postoji poseban, ranije odobren master plan
(`docs/architecture/JEDINSTVENI_IMPORT_WORKFLOW_IMPLEMENTATION_PLAN.md`,
2026-07-24) čije su Faze 0-8 već izvršene (Codex/Pi, `docs/context/
history.md` #49-53, #57, uklj. e2e test na 4 realna vendor formata).
Odluka je već donesena: **Assembly/master-list tok OSTAJE trajno odvojen
od unified puta, po dizajnu** — ne slučajno zaboravljen, nego eksplicitno
izuzet iz unifikacije (test matrica §17: "Assembly/master lista: postojeći
podržani tok ostaje funkcionalan"). `history.md` #53 eksplicitno traži:
"ne brisati ove fallback-e dok poseban Assembly tok ne bude eksplicitno
pokriven servisom i testovima" — što je upravo posao koji ostaje ispod.

`_finish_import_legacy_path` (3439-3767 nakon ekstrakcije), `_process_batch_records_legacy`,
`_process_batch_records`, `_import_multiple_files` — sve i dalje u `faktura_view.py`.

**Originalni cilj ove faze (prije stvarnog rada, djelimično revidiran)**:
izdvojiti Assembly-specifičnu logiku (matching preko
`DeclarationAssembly.add_invoice()`) u zaseban servis. Nakon čitanja koda
ispostavilo se da ta logika VEĆ jeste u servisu (`DeclarationAssembly`) —
preostalo je samo poruke izdvojiti, ne matching logiku (vidi "Šta je
stvarno urađeno" iznad za obrazloženje).

~~Ekvivalentan e2e test za Assembly/master-list put~~ — **riješeno
2026-08-02**: `tests/integration/test_assembly_master_list_import_e2e.py`
(5 testova, i u `dist_client/`), sa STVARNOM master listom (`Podela po
poreklu.xlsx`, 88 stavki) i stvarnim fakturama Master Frigo (R2503393,
R2503394) — isti scenario koji je korisnik ručno testirao u GUI-ju.
Pokriva: master lista bez ijedne kompletne stavke prije matchovanja,
matchovanje jedne fakture (4/4 stavke, 0 unmatched), akumulacija dvije
fakture bez gubitka prvog matcha, `create_draft()` čuva redoslijed cijele
master liste (88, ne samo matched), i direktna provjera da
`build_assembly_match_message` (Faza 6 ekstrakcija) ispravno renderuje sa
STVARNIM matched/unmatched/status vrijednostima, ne samo sintetičkim
fixture-ima. Ovim je zatvorena rupa koju `history.md` #53 traži prije
nego se Assembly tok smatra potpuno "pokrivenim servisom i testovima".

~~Ručna GUI provjera "Učitaj glavnu listu" toka~~ — **riješeno 2026-08-02**:
korisnik je u GUI-ju uvezao sve 4 PDF fakture pojedinačno (ne batch) nakon
učitane master liste — status traka potvrđuje "✅ 100% (4 faktura)", "Sve
validne", bez grešaka. Poklapa se sa e2e testom (0%→100% completion, 0
unmatched). Ovo je pravi korisnički put kroz `_finish_import_legacy_path`
Assembly granu, kod koje su Faza 6 poruke izdvojene — potvrđeno i
programski i vizuelno.

**Preostalo (nije urađeno u ovoj sesiji)**:
- `_import_multiple_files`/`ImportService.import_multiple_files`
  preklapanje pomenuto u originalnom plan-u NIJE potvrđeno kao stvaran
  problem u ovoj sesiji — van scope-a nakon PROBE-a, ne dirano.

~~10 `test_db_*` testova trenutno ne prolazi zbog mrežnog tajmauta~~ —
**riješeno 2026-08-02**: `dmserver` opet dostupan, svih 10 testova
prolazi čisto na ponovnom pokretanju, potvrđena odsutnost regresije.

**Nezavisni checker**: preporučen ali ne obavezan — kod-nivo rad (3
message-building funkcije + Assembly matching netaknut) je nizak rizik i
sad pokriven i karakterizacionim I e2e testovima sa stvarnim podacima.

---

## Zatvoreno pitanje: `_import_multiple_files`/`ImportService.import_multiple_files`

**Riješeno 2026-08-02**: `services/faktura/import_service.py::ImportService.
import_multiple_files` ima **0 pozivalaca u cijelom repou** (potvrđeno grep
na cio kod, uklj. worktrees) — mrtav kod, nikad pozvan. Nema stvarnog
preklapanja sa `FakturaView._import_multiple_files` (koja je aktivna i
koristi se). Sumnja iz originalnog plana je bila zasnovana samo na sličnosti
imena — ne treba dalja akcija, mrtav kod van scope-a ovog refaktora za
brisanje.

## FAZA 7 — Van trenutnog inventara (sledeći krug, nije dio ovog plana)

Subagent koji je napravio inventar (2026-08-01) je primijetio da
`_on_export_excel`, `_on_export_pdf`, `_on_load_mappings_from_xml`,
`_on_load_previous_declaration`, `_on_load_master_list` — iako su
legitimni `_on_*` Qt handleri (van scope-a Faza 1-6 jer taj scope
namjerno pokriva samo NE-`_on_*` metode) — sadrže znatnu poslovnu logiku
utkanu u handler (npr. cijela XML mapping logika, parsiranje prethodne
deklaracije). `_on_load_master_list` takođe ima preostala 3 od 13
direktnih `self.validator`/`self.assembly` poziva. Ovo NIJE planirano u
Fazama 1-6 — zahtijeva zaseban project_room kad dođe na red, jer prvo
treba odlučiti da li se `_on_*` handleri uopšte diraju (rizik: to su
signal-wired metode, greška u razdvajanju lakše lomi Qt signal chain).

---

## Handoff protokol za svaku agent sesiju

1. Pročitaj OVAJ CIO fajl prije početka bilo koje faze (ne samo svoju fazu
   — kontekst prethodnih/budućih faza sprječava sudaranje).
2. Pročitaj `AGENTS.md` (3-layer pravilo, Definition of Done, Nezavisna
   provjera) — ako već nije u tvom kontekstu.
3. Provjeri `git status --short` i `git log --oneline -1` PRIJE početka —
   moguće da je druga agent sesija paralelno radila (vidi AGENTS.md
   "Paralelni agenti").
4. Ponovi `wc -l`/`grep -c` mjerenja iz "Trenutno stanje" — ako se ne
   poklapaju sa ovim planom, neko je već radio na tome od kad je ovaj plan
   pisan — ažuriraj plan prije nastavka, ne pretpostavljaj.
5. Radi SAMO jednu fazu po sesiji (ili jednu pod-grupu unutar Faze 4) —
   ne pokušavati sve odjednom, faze su namjerno male za nezavisnu
   verifikaciju.
6. Nakon završetka: ažuriraj status te faze u ovom fajlu (PENDING → DONE,
   datum, commit hash, stvarni izmjereni rezultat linija/testova — NE
   procenat), zatim standardna AGENTS.md procedura (Korak 1-5: commit,
   memorija, agent_report, opciono link u kodu, GitNexus re-analiza).
7. Commit poruka format: `refactor(faktura): Faza N - kratak opis` +
   `Co-Authored-By:` linija.
8. Preporučeno: raditi u NOVOM `git worktree` (`.worktrees/faktura-fazaN/`)
   ne u postojećem zastarjelom `.worktrees/faktura-3layer/` (vidi
   "Konflikti" #1) — pogotovo ako više agenata radi paralelno na različitim
   fazama.
9. **Prije PRVOG pokretanja testova u novom worktree-u**, kopirati
   gitignore-ovane lokalne fajlove iz root working tree-a — oni se NE
   kopiraju automatski pri `git worktree add`:
   - `.env` (bez njega `get_db_settings()` puca sa `DB_PASSWORD` missing —
     PostgreSQL-zavisni testovi tada padaju sa pogrešnim uzrokom)
   - `database/deklarant_sistem.db` (bez njega SQLite-zavisni testovi
     — `tarifa_2026` tabela, `TarifaService`, penetration/SQL injection
     testovi — padaju sa "no such table", ne sa stvarnim bugom)
   Ovo je (2026-08-01, Faza 4a) DRUGI PUT da je ovaj tačan obrazac lažno
   prijavio 19-22 "regresije" koje nisu postojale — prije bilo kakvog
   zaključka o "puklo je zbog izmjene", prvo provjeriti da li worktree
   uopšte ima ova dva fajla (`ls .env database/deklarant_sistem.db`).

## Rollback / oporavak

Svaka faza je zaseban commit (ili mali niz commit-ova) — revert te faze
ne dira prethodne. Ako Faza N pokvari testove koje je Faza N-1 ostavila
zelene, prvo `git revert` samo commit-e Faze N, ne cijelu granu.

## Odbačene opcije

- Opcija: raditi sve u jednom velikom PR-u/sesiji.
- Zašto je razmatrana: brže za jednog agenta sa punim kontekstom.
- Zašto je odbačena: 119 metoda, 6267 linija — previsok rizik za jedan
  neverifikovan korak; onemogućava nezavisnu provjeru po dijelovima;
  ne staje u kontekst jedne agent sesije bez gubitka preciznosti.
- Kada odluku ponovo otvoriti: ako se pokaže da je faza-po-faza overhead
  veći od koristi (npr. svaka faza troši previše vremena na re-orijentaciju).
