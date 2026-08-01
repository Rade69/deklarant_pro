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
   mrtav kod.** `_can_use_unified_manual_import()` (linija 3380) vraća
   `False` (aktivira legacy granu) kad god je
   `self.assembly.master_list_loaded` True — tj. legacy put je AKTIVAN za
   master-list/PZT workflow uvoza. Ne brisati bez zamjene, ne potcijeniti
   Fazu 6.
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

**Status: PENDING**

Grupisano po funkcionalnoj oblasti — svaka grupa može biti zaseban
pod-zadatak unutar ove faze, ne mora sve jedan agent odjednom:

**4a. Uvoz-workflow orkestracija** (novi ili postojeći `import_workflow` servisi):

**Status: DONE — 2026-08-01**

Urađeno:
- Codex (`1b3a708`): 9 metoda u `ImportWorkflowService`
- Pi (`<novi_commit>`): preostale 2 metode — `_start_import` ostaje u View-u
  (čist UI metod, nema poslovne logike za ekstrakciju),
  `_collect_manual_import_decisions` delegira inicijalizaciju
  `UserDecisions`/`InvoiceDecision` u `ImportWorkflowService.init_import_decisions()`,
  dijalozi za konflikte ostaju u View-u.

**4b. Povlastice/porijeklo** (`validation_service.py` ili novi `preference_rules_service.py`):
`_check_partner_consistency` (2966-3038) — core `similar()` logika je
poslovna, dijalog dio ostaje u View;
`_suggest_preference_by_country` (3111-3149) — **VISOKA VRIJEDNOST**,
netrivijalno poslovno pravilo (EU/CEFTA/TR/IR + istorijsko učenje) bez
ikakvog servisnog ekvivalenta danas;
`_auto_handle_povlastice_agent` (3151-3192),
`_should_show_eur1_dialog` (3194-3223), `_should_show_pe2_dialog` (3225-3241)
— poslovno pravilo odluke, dijalog prikaz ostaje u View.

**4c. Naimenovanja post-processing**:
`_run_create_naimenovanja_post_actions` (4421-4451),
`_set_weight_inputs_from_draft` (4453-4459),
`_reload_naimenovanja_tab` (4461-4506) — cross-tab, provjeriti da ne dira
Naimenovanja/Zaglavlje refaktor koji ide paralelno (provjeriti
`docs/context/history.md` za status tog rada prije početka, izbjeći
sudar),
`_sync_pe_docs_to_header` (6171-6223), `_sync_inspection_docs_to_header` (6225-6262).

**4d. Masa/validacija**:
`_build_calculate_masses_request` (5023-5081),
`_build_analysis_summary_from_draft` (1873-1949),
`_validate_all_items` (4508-4626), `_run_historical_tariff_validation` (4645-4727).

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

**Status: PENDING**

`_apply_country_confidence_color` (1462-1534),
`_apply_preference_confidence_color` (1536-1577) — sadrže netrivijalna
evidence/confidence pravila (koja boja/tooltip za koji nivo pouzdanosti)
utkana u Qt bojenje ćelije. Izdvojiti PRAVILO (koja kombinacija
evidence/confidence → koja boja/poruka) u `validation_service.py` kao
čistu funkciju koja vraća `(color, tooltip)`, Qt primjena boje ostaje u
View kao tanak poziv.

**Zašto pažljivo**: ovo područje ima 6 nezavisnih memorijskih zapisa u
"Zemlja porijekla / povlastica" porodici bugova (vidi
`~/.claude/projects/.../memory/MEMORY.md` sekciju "Zemlja porijekla /
povlastica") — ekstrakcija NE SMIJE promijeniti ijedno pravilo, samo
premjestiti gdje živi. Pročitati sve te memorijske zapise prije početka.

**Plan verifikacije**: screenshot prije/poslije za par test-faktura sa
poznatim scenarijima (EU zemlja+povlastica, CEFTA, zemlja bez povlastice,
nepoznata zemlja) — GUI vizuelna promjena zahtijeva screenshot dokaz po
AGENTS.md "Definition of Done".

**Nezavisni checker**: preporučen (nije GitNexus HIGH, ali visoka cijena
greške — 6 prethodnih bugova u istoj oblasti).

---

## FAZA 6 — Legacy uvoz putevi (najveći, najrizičniji, raditi POSLEDNJE)

**Status: PENDING**

`_finish_import_legacy_path` (3835-4165, ~330 linija),
`_process_batch_records_legacy` (2594-2722), `_process_batch_records` (2504-2592),
`_import_multiple_files` (2392-2442, razriješiti preklapanje sa `ImportService.import_multiple_files`).

**OBAVEZNO PROČITATI PRIJE POČETKA**: "Konflikti" #2 i #3 iznad — ovo NIJE
mrtav kod, aktivna je grana za master-list/PZT uvoz. Ne raditi ovu fazu
dok Faze 1-5 nisu završene i stabilne (najveći rizik od regresije, treba
najviše prostora za sigurno testiranje).

**Preporučeni prvi korak (PROBE, ne implementacija)**: utvrditi tačan
% stvarnih uvoza koji prolaze kroz legacy vs unified granu (log-based ili
test-based dokaz) prije nego se odluči da li se legacy grana refaktoriše
in-place ili se unified put proširuje da pokrije i master-list slučaj (što
bi eliminisalo legacy granu potpuno umjesto da se ona samo čisti). Ovo je
prava arhitektonska odluka — agent SAMO PREDLAŽE, korisnik odlučuje
(AGENTS.md "Podjela odgovornosti").

**Plan verifikacije**: **najstroža u cijelom planu** — deterministički
testovi za OBA puta (unified i legacy) sa realnim fakturama koje
specifično aktiviraju master-list granu (provjeriti koji fajlovi u
`najavauvoza/` su master-list/PZT tip), pun regression pass, ručna GUI
provjera oba toka.

**Nezavisni checker: OBAVEZAN.** Ovo je najveća promjena u cijelom planu.

**Ko radi**: agent sa najvišim nivoom povjerenja/iskustva na projektu,
NIKAKO prva faza koju nova agent sesija radi na ovom refaktoru.

---

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
