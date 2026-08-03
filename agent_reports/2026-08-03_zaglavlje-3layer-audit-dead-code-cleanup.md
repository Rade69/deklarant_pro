## Datum
2026-08-03

## Agent
Claude Code (Sonnet 5)

## Scope
Audit: `gui/tabs/zaglavlje_view.py`, `gui/tabs/zaglavlje_controller.py`, `gui/tabs/zaglavlje_tab.py`,
`services/zaglavlje_service.py`. Izmjena: `gui/tabs/zaglavlje_controller.py`,
`services/zaglavlje_service.py` i njihove `dist_client/` kopije.

## Status izvora
Nema postojećeg project_room/plan dokumenta za Zaglavlje 3-layer refaktor (za razliku od Faktura i
Naimenovanja, koji su imali eksplicitne fazne planove) — commit istorija (`zaglavlje_tab.py` nepromijenjen
od `0149de9`, prvog commita na `windows`) pokazuje da je Zaglavlje bio 3-layer OD POČETKA te grane, ne
naknadno refaktorisan.

## Impact analiza
GitNexus `impact` (upstream) na `load_dropdowns`: nije uspio direktno (ambiguous — root/dist_client
duplikat), disambiguisano na `gui/tabs/zaglavlje_controller.py` verziju — repo-wide grep potvrđuje 0
pozivalaca u produkcionom kodu. Za `load_vrste_prijevoza`/`load_ured_odredista`/`load_isprave`: repo-wide
grep (uklj. sve worktree-ove) pokazuje da su jedini pogoci `>>>` docstring primjeri unutar samih metoda —
nikad stvarno pozvane, čak ni u starim worktree-ovima (za razliku od Naimenovanja nalaza gdje su stari
worktree-ovi imali žive pozive). Risk: LOW (brisanje potpuno nedostupnog koda).

## Reprodukcija prije izmjene
N/A — nije bugfix, audit + cleanup mrtvog koda pronađenog tokom traženog pregleda arhitekture.

## Kontekst korišćen
- `gui/tabs/zaglavlje_view.py` (2579 linija) — NIJE pročitan u cijelosti, ciljano pretražen (grep za
  `from services.`, `self.window()`, `self.draft.`, `QFileDialog`, `Signal(`, `_on_`, `get_db_connection`).
- `gui/tabs/zaglavlje_controller.py` (1204 linije) — ciljano pretražen (grep za pozive Service metoda),
  pročitan odsjek oko `load_dropdowns()` i `_populate_oznaka_combo`/`_on_dekl_sifra_changed` u cijelosti
  radi razumijevanja da li je `load_dropdowns()` zaista redundantan (ne samo neupotrijebljen, nego i
  funkcionalno nadmašen drugim putem).
- `services/zaglavlje_service.py` (1948 linija) — čitani samo odsjeci oko `get_vrste_deklaracija`,
  `get_vid_unutra`, `load_vrste_prijevoza`, `load_ured_odredista`, `load_isprave`.
- `gui/tabs/zaglavlje_tab.py` (223 linije) — pročitan u cijelosti (composition root, malen fajl).

## Šta je urađeno
1. Audit 3-layer stanja Zaglavlje taba na zahtjev korisnika (paralelno sa ručnim GUI testiranjem
   Naimenovanja izmjena iz prethodnog zadatka).
2. Utvrđeno: View nema `self.draft` (čist `get_data()`/`set_data()` dict ugovor), nema `self.window()`/
   MainWindow pozive, nema `DeclarationDraftService`, 11 signala ka Controlleru — arhitektura znatno
   zrelija nego Naimenovanja prije refaktora.
3. Jedini nalaz: 6 direktnih `get_db_connection()` + sirovog SQL-a u View-u (read-only katalog lookupi za
   dropdown popunjavanje) — gore od Naimenovanja slučaja jer nema ni servisnu apstrakciju.
4. Istraženo dalje: `ZaglavljeService` ima gotovo identične metode koje bi trebalo da preuzmu tu ulogu.
   Otkriveno da `ZaglavljeController.load_dropdowns()` (koji ispravno poziva Service verzije) **nikad se
   ne poziva** — mrtav kod, superseded View-ovim direktnim SQL-om (potvrđeno postojećim kod-komentarom:
   "VIEW sada sam popunjava... Controller više ne treba da popunjava ovaj dropdown").
5. Dodatno otkriveno: tri Service metode (`load_vrste_prijevoza`, `load_ured_odredista`, `load_isprave`)
   nikad nisu ni bile pozvane od strane bilo kog produkcionog koda (samo u sopstvenim docstring primjerima).
6. Predstavljen nalaz korisniku (AskUserQuestion) — 3 opcije: samo cleanup mrtvog koda / konsolidacija
   šifarnika u Service uz migraciju View-a / bez izmjene. Korisnik izabrao: samo cleanup.
7. Obrisana `ZaglavljeController.load_dropdowns()` (root + dist_client) i tri Service metode
   (root + dist_client).
8. `py_compile` na sva 4 fajla — OK.
9. Puna `pytest tests/ -q` (izuzev DB-zavisnih testova, `dmserver` nedostupan) — identičan baseline (3
   pre-postojeća fail-a + 1 error, nepovezano). Ciljano `pytest tests/ -q -k zaglavlje` — 38 passed, 1
   skipped.
10. `npx gitnexus analyze` + `detect_changes` — risk_level low (čisto brisanje opet nije detektovano u
    `changed_symbols`, isti poznati alat-limit kao ranije ove sesije; nezavisan dokaz jači).
11. Commit `d6dd1ef`.

## Zašto je urađeno
Korisnik je eksplicitno zatražio pregled Zaglavlje taba za isti troslojni standard, dok je ručno testirao
Naimenovanja izmjene iz prethodnog zadatka. Nalaz je pokazao da NIJE potreban veliki refaktor (za razliku
od početnog očekivanja) — arhitektura je već solidna. Jedini realan nalaz (View-ov sirovi SQL) je,
identično obrascu otkrivenom 3x u Naimenovanja sesiji ranije istog dana, uključivao dio koji je izgledao
kao "treba migrirati" ali se pri provjeri pokazao kao mrtav/redundantan kod, ne živ gap. Korisnik je
odlučio (nakon predstavljenih opcija) da se samo taj mrtav kod počisti, a da se View-ov sirovi SQL ostavi
netaknut — isti risk-profil kao Naimenovanja dropdown presedan (read-only, bez draft mutacije), plus
postojeći kod-komentar koji potvrđuje da je View-ovo samostalno popunjavanje već svjesna odluka tima, ne
previd koji čeka ispravku.

## Kako je urađeno
Uklonjen cio metod-blok `load_dropdowns()` iz `ZaglavljeController` (root + dist_client, identičan
sadržaj osim BOM razlike na liniji 1 — potvrđeno prije izmjene) i tri metod-bloka
(`load_vrste_prijevoza`, `load_ured_odredista`, `load_isprave`) iz `ZaglavljeService` (root + dist_client,
identičan sadržaj osim CRLF/LF razlike — potvrđeno byte-level normalizacijom prije izmjene).

## Šta nije dirano
- **View-ov sirovi SQL** (6 mjesta: `_load_vrste_deklaracija_from_db`, `_load_tipovi_deklaracija_from_db`,
  `_load_vrste_prijevoza_from_db`, `_load_ured_odredista_from_db`, `_load_isprave_from_db`,
  `_auto_fill_deklarant`) — namjerno, korisnička odluka.
- `get_vrste_deklaracija()`/`get_vid_unutra()` u Service — NISU dirane, i dalje se koriste (Controller
  `_populate_oznaka_combo` i inicijalni `_populate_oznaka_combo` poziv iz drugog handlera).
- Ostatak Zaglavlje View-a (2579 linija) i Controllera (preostalih ~1160 linija) — nije audit-ovan do
  detalja (nisu pregledani svi `_on_*` handleri metodom kakva je primijenjena na Naimenovanja), samo
  ciljani grep-ovi za poznate red-flag obrasce. Moguće da postoje suptilniji nalazi van dometa ovog kratkog
  pregleda.
- Zatečen nekomitovan WIP drugog agenta/sesije (`AGENTS.md`, `CLAUDE.md`,
  `dist_client/ui/naimenovanja_tab_OPTIMIZED_ui.py`, `dist_client/ui/zaglavlje_tab_ui.py`, `.worktrees/`) —
  nije diran.

## Verifikacija
- `py_compile` na sva 4 izmijenjena fajla — OK.
- Puna `pytest tests/ -q -k "not test_db_ and not test_decision_characterization and not
  tariff_learning_ledger"` — 1650 passed, identično baseline-u utvrđenom ranije istog dana (3 pre-postojeća
  fail-a nepovezana, `dmserver` nedostupan za DB testove).
- Ciljano `pytest tests/ -q -k zaglavlje` — 38 passed, 1 skipped (uklj.
  `tests/test_zaglavlje_service.py`, `tests/unit/test_zaglavlje_controller_import_docs.py`,
  `tests/unit/test_zaglavlje_save_to_draft.py`, `tests/unit/test_zaglavlje_validation.py`,
  `tests/unit/test_zaglavlje_isprava_delegate.py`).
- Repo-wide grep (uklj. sve `.worktrees/`) potvrđuje 0 pozivalaca svih 4 obrisanih metoda prije i poslije
  brisanja.

## Nezavisna provjera
- Checker korišćen: NE
- Razlog: LOW rizik (potpuno nedostupan/nikad pozvan kod, puna test svita zelena, korisnik direktno
  odlučio o scope-u prije izmjene preko AskUserQuestion). Po AGENTS.md kriterijumu, nezavisna provjera nije
  obavezna za ovaj obim.

## Pronađeni problemi
- Isti obrazac kao Naimenovanja sesija ranije istog dana: kod koji "izgleda kao treba migrirati u
  Controller" (View direktan SQL) je pri dubljoj istrazi otkrio da POSTOJI ispravna Controller-orkestrisana
  alternativa (`load_dropdowns()`), ali je ONA mrtva/napuštena, ne View-ov pristup. Četvrti primjer ove
  klase nalaza u istoj sesiji (nakon `_add_history_docs`, `_apply_xml_import_to_zaglavlje` iz Naimenovanje
  audita).
- Root i dist_client kopije NISU bile byte-identične (BOM na `zaglavlje_controller.py`, CRLF/LF na
  `zaglavlje_service.py`) — za razliku od Naimenovanja fajlova koji jesu bili identični. Provjereno
  normalizacijom prije izmjene da je sadržaj funkcionalno identičan (poznat, već dokumentovan obrazac —
  vidi memory `feedback_windows_patterns_2.md`), izmjene primijenjene nezavisno na svaki fajl (ne `cp`)
  da se ne poremeti postojeći encoding/line-ending svakog fajla.

## Odbačene opcije
- Opcija: konsolidovati sve šifarnike (5 View raw-SQL funkcija) u `ZaglavljeService`, View poziva Service
  klasu direktno (isti obrazac kao Naimenovanja tarifni lookup).
- Zašto je razmatrana: ponuđena korisniku kao opcija #2 u AskUserQuestion; bila bi doslovnija primjena
  "View ne smije pozivati DB" pravila iz 3-layer standarda.
- Zašto je odbačena: korisnik je eksplicitno izabrao užu opciju (samo cleanup). Dodatni razlog protiv:
  View-ova i Service-ova verzija `load_ured_odredista` imaju RAZLIČITU logiku parsiranja teksta (View:
  `"CI " + naziv.split(". Carinska ispostava ")[-1]` uz posebno rukovanje "Carinski referat"; Service:
  `naziv.split()[-1]` uz f"{sifra} CI {grad}"), pa bi konsolidacija zahtijevala odluku KOJA verzija je
  tačna — netrivijalno pitanje bez GUI/produkcione provjere, van scope-a "samo cleanup" zadatka.
- Kada odluku ponovo otvoriti: ako se ikad odluči da View treba potpuno DB-free (npr. ako naredna faza
  aplikacije zahtijeva potpuno odvajanje UI procesa od DB pristupa, npr. remote/thin-client scenario).

## Konflikti / kontradiktorni izvori
Nema — nalaz je jednoznačan (0 pozivalaca, potvrđeno sa dva nezavisna grep prolaza, jednim u foreground i
jednim u background procesu sa istim rezultatom).

## Commitovi
| Hash | Poruka |
| --- | --- |
| `d6dd1ef` | `refactor(zaglavlje): ukloni mrtav sifarnik kod iz Controller/Service` |

## Rizici / ograničenja
- Ovaj audit NIJE bio isto tako dubok kao Naimenovanja audit (nisu pregledani svi `_on_*` handleri
  metodom klasifikacije "čist wiring / mješovito-trivijalno / sadrži logiku / visok rizik") — moguće da
  postoje suptilniji nalazi u preostalih 2579 (View) + ~1160 (Controller) linija koje ovaj kratki pregled
  nije uhvatio.
- View-ov sirovi SQL i dalje postoji (namjerno ostavljen) — ako se ikad odluči da se to popravi, dvije
  verzije logike parsiranja teksta (View vs Service za `ured_odredista`) prvo treba uskladiti/potvrditi
  koja je tačna.

## Potreban follow-up
Ako korisnik želi dublji, Naimenovanja-nivoa audit Zaglavlje View-a/Controllera (svi `_on_*` handleri,
svi View↔MainWindow dodirni tačke) — nije urađeno ovom sesijom, samo ciljani grep za poznate red-flag
obrasce.

## Potrebna korisnička potvrda
Nema — brisanje potpuno nedostupnog koda ne mijenja nijedno vidljivo ponašanje, nije potrebna ručna GUI
provjera specifično za ovu izmjenu.
