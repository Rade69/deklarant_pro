## Datum
2026-08-03

## Agent
Claude Code (Sonnet 5)

## Scope
`gui/tabs/naimenovanja_view.py`, `gui/tabs/naimenovanja_controller.py`, `gui/tabs/naimenovanja_tab.py`
i njihove `dist_client/` kopije. Novi test:
`tests/unit/test_naimenovanja_controller_declaration_save_load.py`.

## Status izvora
- `agent_reports/2026-08-03_naimenovanja-3layer-audit-i-dead-code-cleanup.md` (ranije u istoj
  sesiji) — aktivan, dokumentovao 3 preostala nalaza (`_apply_xml_import_to_zaglavlje`, `_on_save`,
  dropdown/rb40 setup) nakon što se prvi nalaz (`_add_history_docs`) pokazao kao mrtav kod.
- `project_rooms/2026-08-03_naimenovanja-3layer-status-i-nastavak.md` — dopunjen ovim zadatkom sa
  finalnom "ZATVARANJE (konačno)" sekcijom.
- `git show f561e55:project_rooms/2026-07-27_naimenovanja-3layer-refaktor-detaljni-plan.md` —
  autoritativni plan, referenciran za §7.2 (Controller mapiranje) i Faza 3 gate.

## Impact analiza
GitNexus `impact` (upstream) na sva 4 target simbola prije izmjene:
- `_on_save`: 0 direktnih pozivalaca u statičkom grafu (event-handler entry point, ne poziva ga
  drugi kod) — risk LOW.
- `_apply_xml_import_to_zaglavlje`: 0 direktnih pozivalaca — risk LOW (kasnije potvrđeno da je
  potpuno mrtav kod repo-wide grep-om).
- `_setup_package_dropdown` / `_setup_rb40_widgets`: 1 pozivalac svaki (`NaimenovanjaView.__init__`)
  — risk LOW.
GitNexus statički broj pozivalaca ne mjeri stvaran poslovni rizik ovih promjena (npr. `_on_save`
je LOW po grafu jer je UI-signal entry point, ali stvarno dira snimanje kompletne carinske
deklaracije) — nezavisno procijenjeno kao MEDIUM po stvarnom domenu (draft/XML I/O), zato
karakterizacioni test prije izmjene i puna test svita poslije.

## Reprodukcija prije izmjene
N/A za dio koji je mrtav kod (`_apply_xml_import_to_zaglavlje` — dokaz: 0 poziva repo-wide grep,
vidi "Kontekst korišćen"). Za `_on_save`/`is_draft_file` granu: nije bugfix nego arhitektonska
migracija bez namjeravane promjene ponašanja — dokaz da je stari kod ŽIV (a ne mrtav kao ostatak):
`btn_sacuvaj.clicked.connect(self._on_save)` i `("Ctrl+S", self._on_save)` u istom fajlu.

## Kontekst korišćen
- `gui/tabs/naimenovanja_controller.py` (313 → 344 linija) — pročitan u cijelosti prije i poslije
  izmjene radi provjere postojećih konvencija (`_notify_mutation`, `reload_header_fn` pattern,
  inline service importi).
- `services/naimenovanja/naimenovanja_service.py:608` (`import_xml`) — pročitano u cijelosti da se
  potvrdi da stvarno duplira/nadmašuje logiku mrtvog `_apply_xml_import_to_zaglavlje` (transport_id
  zadržavanje, DIS-only referenca, PE distribucija).
  `services/declaration_draft_service.py` — pročitano u cijelosti (154 linije) da se utvrdi koje
  funkcije su čisto (`suggested_filename`, `default_drafts_directory`, `is_draft_file` — legitimno
  ostaju u View-u) a koje su I/O-mutirajuće (`DeclarationDraftService.save/load` — moraju u
  Controller).
- Repo-wide grep za `_apply_xml_import_to_zaglavlje` (svi fajlovi uklj. worktree-ove) — potvrda da
  je pozivan SAMO u starim worktree-ovima (`agent-v2`, `codex-faktura-toolbar`), nikad na `windows`.

## Šta je urađeno
1. GitNexus impact analiza za sva 4 preostala target simbola.
2. Ponovna klasifikacija `_setup_package_dropdown`/`_setup_rb40_widgets` istim standardom kao
   ranije za `_add_history_docs` — potvrđeno da NIJE gap (read-only lookup, isti prihvaćeni
   obrazac kao Faktura View, plus strukturalno ograničenje: View se konstruiše prije Controllera).
   Netaknuto.
3. `_apply_xml_import_to_zaglavlje` — potvrđeno mrtvim kodom (repo-wide grep, 0 poziva na
   `windows`), obrisana iz `gui/` i `dist_client/`.
4. Napisan karakterizacioni test (`tests/unit/test_naimenovanja_controller_declaration_save_load.py`,
   4 testa) PRIJE migracije `_on_save`.
5. Dodane `NaimenovanjaController.save_declaration(view, filename)` i `.load_declaration(view,
   filename)` metode + `save_header_fn`/`replace_draft_fn` konstruktorski parametri (isti obrazac
   kao postojeći `reload_header_fn`).
6. `NaimenovanjaTab`: dodane `_save_header()`/`_replace_draft()` metode (isti obrazac kao postojeći
   `_reload_header()`), ožičeni novi signali `save_declaration_requested`/`open_declaration_requested`.
7. `NaimenovanjaView`: `_on_save()` sveden na file dialog + signal emit (business logika uklonjena);
   `_on_import_xml()`-ova `is_draft_file` grana (otvaranje postojećeg nacrta, otkrivena usput kao
   ista klasa problema, nije bila u originalnoj listi od 3) sad emituje
   `open_declaration_requested` umjesto direktnog `DeclarationDraftService().load()` +
   `main_window._replace_draft_contents()`.
8. `py_compile` + novi testovi (4/4 passed) + puna `pytest tests/ -q` (izuzev DB-zavisnih testova
   koji su padali zbog nedostupnog `dmserver` — nepovezano, vidi "Verifikacija").
9. Sync `dist_client/` kopije za sva 3 fajla (`cp` + `diff -q` potvrda identičnosti + zaseban
   `py_compile`).
10. `npx gitnexus analyze` + `gitnexus_detect_changes` — scope potvrđen (10 fajlova, risk LOW,
    affected_processes prazno; 6 od 10 su pre-postojeći nepovezan WIP drugog agenta).
11. Commit `3625286`.
12. Dopunjen `project_rooms/2026-08-03_naimenovanja-3layer-status-i-nastavak.md` sa finalnom
    "ZATVARANJE (konačno)" sekcijom — status refaktora sad ZAVRŠENO.

## Zašto je urađeno
Korisnik je nakon prethodnog djelimičnog audita (isti dan) eksplicitno zatražio "popravi sve" —
da se preostale 3 dokumentovane stavke isto riješe, ne samo dokumentuju. Pri istrazi se
ispostavilo da 2 od 3 slijede isti obrazac kao prvi nalaz te sesije (`_add_history_docs`): kod koji
"izgleda kao direktna arhitektonska greška" (View mutira draft/zove MainWindow direktno) je pri
provjeri pozivalaca bio mrtav kod, superseded ispravnim Controller-tokom. Treća stavka
(`_setup_package_dropdown`/`_setup_rb40_widgets`) je re-klasifikovana kao NE-gap nakon poređenja sa
već prihvaćenim presedanom (read-only Service pozivi direktno iz View-a su OK kad nema mutacije).
Jedina stavka koja je zahtijevala stvarnu kod-migraciju bila je `_on_save` (i usput otkrivena
`is_draft_file` grana iz iste porodice problema — isti servis, ista vrsta Controller-bypass-a).

## Kako je urađeno
Vidi "Šta je urađeno" — tehnički pristup slijedi već uspostavljen obrazac u ovom Controlleru
(`reload_header_fn` callback injektovan iz Tab-a) za nova dva callback-a, i već uspostavljen
signal→Controller obrazac (`import_xml_requested`) za nova dva signala.

## Šta nije dirano
- `_setup_package_dropdown` / `_setup_rb40_widgets` — namjerno, obrazloženo gore.
- `_ask_update_knowledge_base`, `_auto_populate_supplementary_unit` — spomenuti u ranijem audit
  izvještaju kao "nisu provjereni ovom sesijom", i dalje nisu — van scope-a ovog zadatka
  (korisnik je tražio popravku 3 KONKRETNO dokumentovane stavke, ne novi pun audit).
- Faza 0 (karakterizacioni testovi za CIO `naimenovanja_view.py`) — nije urađena, ostaje generalni
  dug, nije uslov za ovaj zadatak.
- Zatečen nekomitovan WIP drugog agenta/sesije (`AGENTS.md`, `CLAUDE.md`,
  `dist_client/ui/naimenovanja_tab_OPTIMIZED_ui.py`, `dist_client/ui/zaglavlje_tab_ui.py`,
  `.worktrees/`, ostali netrackovani fajlovi) — nije diran, nije staged.

## Verifikacija
- `python -m py_compile` na sva 3 root + 3 dist_client fajla — OK.
- Novi testovi: `pytest tests/unit/test_naimenovanja_controller_declaration_save_load.py -v` — 4/4
  passed (stvaran `DeclarationDraftService` file I/O round-trip na `tmp_path`, fake `view` bez
  Qt-a, bez mock-ovanja same logike koja se testira).
- Puna `pytest tests/ -q`: 13 failed + 3 errors — ISTRAŽENO i potvrđeno nepovezano: sve su
  PostgreSQL-zavisni testovi (`test_decision_characterization.py`, `test_tariff_learning_ledger.py`)
  koji padaju sa `psycopg2.OperationalError: connection to server at "192.168.0.25" ... timeout
  expired` — `dmserver` je bio nedostupan u trenutku ovog test run-a. Ponovljeno sa
  `-k "not test_db_ and not test_decision_characterization and not tariff_learning_ledger"`:
  3 failed + 1 error, identično baseline-u utvrđenom ranije ove sesije (prije bilo kakve izmjene) —
  potvrđuje da moja izmjena nije unijela regresiju.
- GitNexus `detect_changes` (poslije `npx gitnexus analyze`): risk_level low, affected_processes
  prazno, scope tačno odgovara namjeravanim fajlovima (za razliku od prethodnog dijela sesije gdje
  čisto brisanje metode nije bilo detektovano — sada JESTE detektovano jer su ove izmjene dodavale/
  mijenjale linije, ne samo brisale cio blok).

## Nezavisna provjera
- Checker korišćen: NE
- Razlog: Po AGENTS.md kriterijumu ("Nezavisna provjera" obavezna za HIGH/CRITICAL ili kad
  hipoteza nije pouzdano reprodukovana), GitNexus impact je LOW za sve dirane simbole, a za dio
  koji je live kod (`_on_save`/`is_draft_file`) postoji karakterizacioni test + puna test svita
  zelena + tačno poređenje starog/novog toka linija-po-linija tokom migracije (nije prepisivanje
  od nule, nego premještanje istog koda u novi sloj s istim redoslijedom operacija). Preporučuje se
  ipak GUI ručna provjera na stvarnom Windows računaru (vidi "Potrebna korisnička potvrda") prije
  nego se ovaj tok smatra 100% dokazanim, jer GUI ponašanje (file dialog, Ctrl+S, poruke) nije
  automatski testirano end-to-end.

## Pronađeni problemi
- Isti obrazac lažno pozitivnog nalaza ponovljen: 2 od 3 preostale "arhitektonske greške" iz
  prethodnog audita ispale su mrtav kod pri dubljoj provjeri (isto kao `_add_history_docs` ranije
  u sesiji). Obrazac sad potvrđen 3x u istoj sesiji — vrijedna, ponovljena pouka (upisana u
  memoriju): kod koji "izgleda kao View mutira draft direktno" MORA se prvo provjeriti da li je
  uopšte dostižan prije tretiranja kao aktivan bug.
- Usput otkriven dodatni, prethodno nedokumentovan primjer iste klase problema:
  `is_draft_file` grana u `_on_import_xml` — nije bio u originalnoj listi od 3, ali je ista
  arhitektonska greška u istom servisu (`DeclarationDraftService`). Uključen u ovaj zadatak jer je
  direktno susjedan i dijeli isti servis/rizik profil sa `_on_save`.
- Puna test svita je pri prvom pokretanju ove faze pokazala 13 novih failova — ISTRAŽENO odmah
  (ne pretpostavljeno da je "vjerovatno nepovezano") i potvrđeno kao `dmserver` nedostupnost, ne
  regresija. Zapisano radi transparentnosti da je ovo provjereno, ne pretpostavljeno.

## Odbačene opcije
- Opcija: migrirati `_setup_package_dropdown`/`_setup_rb40_widgets` u Controller radi doslovnog
  ispunjavanja Faza 3 gate-a iz plana.
- Zašto je razmatrana: korisnik je tražio "popravi sve", a ovo je bilo eksplicitno na listi od 3.
- Zašto je odbačena: nema draft mutacije za zaštititi (čist read-only lookup), postoji direktan
  arhitektonski presedan da je ovakav poziv OK (Faktura View, 96 importa), i migracija bi
  zahtijevala reorganizaciju composition roota (View se konstruiše prije Controllera) za nultu
  stvarnu korist — čisto teorijsko usklađivanje sa slovom plana bez praktičnog rizika koji se time
  smanjuje. Suprotno je AGENTS.md "ne dodavati... za scenarije koji se ne mogu desiti".
- Kada odluku ponovo otvoriti: ako se composition root ikad reorganizuje iz drugog razloga (npr.
  Faza 0 karakterizacioni testovi zahtijevaju drugačiji injection redoslijed), ponovo razmotriti.

## Konflikti / kontradiktorni izvori
Prethodni agent_report (`2026-08-03_naimenovanja-3layer-audit-i-dead-code-cleanup.md`) je
`_apply_xml_import_to_zaglavlje` i `_on_save` naveo kao "NIJE popravljeno" sa istim statusom
(oba "stvarna arhitektonska greška"). Ovaj zadatak pokazuje da je to bilo NETAČNO za
`_apply_xml_import_to_zaglavlje` (bio je mrtav kod, ne live bug) — tretirano kao: raniji izvještaj
je bio ispravan u IDENTIFIKACIJI simptoma (View mutira draft direktno) ali nije provjerio
DOSTIŽNOST (da li se ta linija koda ikad izvrši), što je upravo pouka zapisana u "Pronađeni
problemi" gore. Korisnička potvrda nije potrebna — dokaz je direktno u kodu (repo-wide grep).

## Commitovi
| Hash | Poruka |
| --- | --- |
| `3625286` | `refactor(naimenovanja): dovrsi Fazu 7/8 - save/load deklaracije kroz Controller` |

## Rizici / ograničenja
- `_on_save`/`is_draft_file` migracija NIJE ručno GUI-testirana na stvarnom Windows računaru u
  ovoj sesiji (offscreen/headless okruženje ovdje nije pogodno za file dialog interakciju) — vidi
  "Potrebna korisnička potvrda".
- `settings.setValue("drafts/lastDirectory", ...)` u `_on_save` sad se upisuje ODMAH nakon što
  korisnik potvrdi putanju u dialogu, umjesto TEK nakon uspješnog snimanja (originalno ponašanje).
  Namjerna, mala izmjena ponašanja radi usklađivanja sa već postojećim obrascem u susjednom
  `_on_import_xml`-u (koji je oduvijek radio ovako) — praktična razlika je zanemarljiva (folder
  ostaje isti bez obzira na uspjeh snimanja), ali eksplicitno navedeno po AGENTS.md pravilu da se
  bugfix/refactor/behavior-change ne miješaju bez najave.
- Nema karakterizacionih testova za CIO `naimenovanja_view.py` (Faza 0 plana) — svaka buduća
  izmjena preostalih View metoda i dalje nosi rizik regresije bez automatizovane zaštite.

## Potreban follow-up
Nema poznatih preostalih arhitektonskih gap-ova u Naimenovanja Controller-migraciji nakon ovog
zadatka. Generalni (ne-hitni) dug: Faza 0 karakterizacioni testovi za `naimenovanja_view.py` u
cjelini, ako se bude dalje diralo u taj fajl.

## Potrebna korisnička potvrda
- Ručna GUI provjera na Windows računaru: dugme "Sačuvaj" (Ctrl+S) na Naimenovanja tabu — snimi
  nacrt, provjeri da se XML fajl kreira i da se poruka "Nacrt sačuvan" prikaže. Zatim: dugme
  "Uvezi XML" → izabrati prethodno sačuvan `.xml` nacrt (ne ASYCUDA XML) → provjeri da se pita
  potvrda ako ima nesačuvanih izmjena, da se svi tabovi ponovo učitaju iz novog drafta, i da se
  poruka "Otvoren je nacrt deklaracije" prikaže.
