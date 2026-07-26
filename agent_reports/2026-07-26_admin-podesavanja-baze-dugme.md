# Dugme "Podešavanja" u Admin → Baza podataka

## Datum
2026-07-26

## Agent
Claude (Sonnet 5)

## Scope
- `gui/tabs/admin/panels/database_panel.py` — novo dugme + `_on_settings()`
- `dist_client/gui/tabs/admin/panels/database_panel.py` — ista izmjena, mirror
- `tests/unit/test_database_panel_settings_button.py` — nov test fajl
- `docs/CONTEXT.md` — §68
- `gui/dialogs/db_setup_dialog.py` — NIJE mijenjan, samo povezan (postojao
  gotov, nikad pozvan)

## Status izvora
Korisnik je poslao screenshot Admin panela (status konekcije, "Testiraj
konekciju" dugme, broj zapisa po tabeli) i primijetio da nema načina da se
promijene parametri konekcije iz aplikacije. Nije bilo ranijeg
agent_report/memorije o ovoj konkretnoj primjedbi. Vezano za raniju
(istu sesiju) raspravu o auto-provjeri konekcije pri startu — korisnik je
tu raspravu eksplicitno odgodio do dodjele statične IP adrese serveru, ali
je zatražio ovo dugme odmah ("Uradi").

## GitNexus impact
`DatabasePanel` upstream: LOW (8 impacted — samo import lanac kroz
`admin_view.py` → `admin_controller.py`/`admin_tab.py` → `main_window.py`,
0 affected_processes, 0 affected_modules). Prijavljeno korisniku prije
izmjene (bezbjedno, samo dodavanje dugmeta i privatnog handlera — javni
API klase nepromijenjen). `detect_changes(scope=all)` poslije potvrdio
LOW/0 affected_processes.

## Šta je urađeno
1. Dodato dugme "Podešavanja" (`self.btn_settings`) pored "Testiraj
   konekciju" u grid layout-u "Status konekcije" grupe (podijeljen red 3
   na dvije kolone umjesto jedne koja je spanning).
2. Nov handler `_on_settings()`: otvara `DbSetupDialog(parent=self)`
   (već ima `_load_existing_env()` — predpopuni iz `.env` automatski). Ako
   korisnik potvrdi (`Accepted`): poziva `_reload_settings()` (isti helper
   koji `check_and_setup_db()` koristi pri startu — resetuje
   `config.settings._db_settings` singleton i zatvara stari connection
   pool), ažurira `lbl_server` prikaz i automatski ponovo pokreće test
   konekcije (`_on_test_conn()`), da korisnik odmah vidi da li nove
   postavke rade.
3. Identična izmjena u `dist_client` mirroru (fajl bio bajt-identičan
   prije izmjene, potvrđeno `git diff --no-index --ignore-cr-at-eol`).

## Zašto je urađeno
`DatabasePanel` je do sad bio čisto read-only prikaz (status + broj zapisa
po tabeli) — jedini način da se promijeni host/port/baza/korisnik/lozinka
bio je ručno uređivanje `.env` fajla van aplikacije. `DbSetupDialog` je već
postojao kao potpuno gotov ekran za baš ovu namjenu (čak i sa
`check_and_setup_db()` helper funkcijom predviđenom za poziv iz `run.py`),
ali nigdje nije bio povezan — potvrđeno grep-om preko `gui/`, `services/`,
`core/` da se `DbSetupDialog(` ne poziva nigdje osim u vlastitom fajlu.

## Kako je urađeno
Handler direktno u `DatabasePanel` (View), bez posebnog Controller/Service
sloja — ovo je isti postojeći obrazac u ovom konkretnom fajlu
(`_on_test_conn`/`_on_refresh` već pokreću QThread-ove direktno iz View-a,
`admin_controller.py` samo sluša `refresh_requested` signal). Nova metoda
ne krši ništa novo u tom pogledu, samo prati zatečen stil ove panele.
`_reload_settings()` je "privatna" (`_` prefiks) funkcija u
`db_setup_dialog.py`, ali je namjenski jedini mehanizam koji modul nudi za
ovu svrhu (i sam `check_and_setup_db()` je koristi) — uvezena direktno,
bez duplikacije njene logike u `database_panel.py`.

## Šta nije dirano
- `gui/dialogs/db_setup_dialog.py` — nula izmjena, samo povezan iz novog
  mjesta.
- Startup auto-provjera konekcije (`check_and_setup_db()` poziv iz
  `run.py`) — eksplicitno odgođeno od strane korisnika do static IP-a,
  van scope-a ovog zadatka.
- `admin_controller.py` / `admin_view.py` — nema promjene wiring-a, panel
  se i dalje konstruiše na isti način.

## Verifikacija
- `python -m py_compile` na oba fajla (root + dist_client) — čisto.
- `git diff --no-index --ignore-cr-at-eol` root vs dist_client — 0 razlika
  nakon sinhronizacije.
- Offscreen konstrukcija stvarnog `DatabasePanel` widgeta
  (`QT_QPA_PLATFORM=offscreen`) — potvrđeno da se panel konstruiše bez
  greške, oba dugmeta imaju ispravan tekst (UTF-8 provjeren direktno,
  terminal prikaz ima cp1252 artefakt na Windowsu — poznat, nevezan za kod).
- `pytest tests/unit/test_database_panel_settings_button.py -q` — 2 passed.
- Pun test suite `pytest tests/ -q` — 1180 passed, 57 skipped, 5 xfailed,
  ista 2 pre-postojeća nepovezana problema
  (`test_xml_parser_fix.py`, `test_model_benchmark.py`).
- `gitnexus_detect_changes(scope=all)` — LOW risk, 0 affected_processes.

## Pronađeni problemi
Nema novih — ovo JE nalaz sam po sebi (orfan `DbSetupDialog`), sad
riješeno povezivanjem.

## Konflikti / kontradiktorni izvori
Nema.

## Commitovi
| Hash | Poruka |
| --- | --- |
| (sljedeći commit) | `feat(admin): poveži DbSetupDialog kroz dugme Podešavanja u Bazi podataka` |

## Rizici / ograničenja
- `DbSetupDialog` snima lozinku u `.env` kao plain-text (postojeće
  ponašanje dijaloga, ne nova izmjena — dijalog to i sam napominje
  korisniku u UI tekstu).
- Vizuelni izgled (raspored dva dugmeta umjesto jednog) nije potvrđen
  uživo u aplikaciji, samo offscreen konstrukcijom.

## Potreban follow-up
- Startup auto-provjera konekcije (`check_and_setup_db()` iz `run.py`) —
  korisnik je rekao da to rješava dodjelom statične IP adrese serveru;
  ako se predomisli, infrastruktura (`DbSetupDialog`, `check_and_setup_db`)
  je već spremna, samo treba poziv na startu.

## Potrebna korisnička potvrda
Da — vizuelni izgled dva dugmeta jedno pored drugog u Admin → Baza
podataka, i funkcionalna provjera da "Podešavanja" → izmjena → "Snimi i
nastavi" stvarno promijeni na koji server se aplikacija spaja (bez
restarta).
