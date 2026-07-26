# Boja dugmadi u DbSetupDialog

## Datum
2026-07-26

## Agent
Claude (Sonnet 5)

## Scope
- `gui/dialogs/db_setup_dialog.py` — `_build_ui()`, dugmad `_btn_test`/`_btn_save`
- `dist_client/gui/dialogs/db_setup_dialog.py` — ista izmjena, mirror
- `tests/unit/test_db_setup_dialog_button_visibility.py` — nov test fajl
- `docs/CONTEXT.md` — §69

## Status izvora
Direktan nastavak §68 (isti dan) — korisnik je uživo isprobao novo dugme
"Podešavanja" i poslao screenshot sa vizuelnim bugom. Nema ranijeg
agent_report o ovom problemu.

## GitNexus impact
`DbSetupDialog` upstream: LOW (20 impacted — svi import lanci kroz
`app/run.py`, `database_panel.py`, `admin_view.py`, `admin_controller.py`,
`__main__.py`, `chat_intent_handler.py`; 0 affected_processes,
0 affected_modules). `detect_changes(scope=all)` poslije potvrdio LOW/0
affected_processes.

## Šta je urađeno
1. `_btn_test` ("Testiraj konekciju") je dobio eksplicitan
   `setStyleSheet()` — prije nije imao nijedan lokalni stil.
2. `_btn_save` ("Snimi i nastavi") zadržao je identičan stil (izdvojen u
   lokalnu varijablu `_btn_style` da oba dugmeta garantovano ostanu
   sinhronizovana ubuduće).
3. Stil: plava `#2980b9`/bijeli tekst kad enabled, siva
   `#bdc3c7`/`#7f8c8d` kad disabled, hover `#3498db`.
4. Ista izmjena u `dist_client` mirroru (fajl bio bajt-identičan prije
   izmjene).

## Zašto je urađeno
Screenshot je pokazao da "Testiraj konekciju" renderuje bijela slova na
svijetloj/bijeloj pozadini — potpuno nečitljivo. "Snimi i nastavi" (već je
imao lokalni stylesheet) je ispravno vidljivo (sivi tekst na sivoj
pozadini u disabled stanju, kako i treba jer je test konekcije upravo
neuspio). Korisnik je eksplicitno tražio da boje budu "u skladu sa drugim
dugmadima".

Root cause globalne QSS kaskade (`styles/unified_color_system.qss` ima
`QPushButton { background-color: #3D6A8A; color: #FFFFFF; }` kao osnovno
pravilo koje bi TEORETSKI trebalo da pokrije `_btn_test`) NIJE do kraja
utvrđen — kaskada ide kroz 9 QSS fajlova učitanih redom u
`MainWindow.load_stylesheet()`, i puna ručna analiza specifičnosti/reda
učitavanja za ovaj specifičan slučaj (modalni QDialog otvoren iz Admin
panela) nije isplativa u odnosu na jednostavan i dokazano ispravan fix:
dati dugmetu eksplicitan lokalni stylesheet, isti obrazac koji već radi
za susjedno dugme u ISTOM dijalogu.

## Kako je urađeno
Minimalna izmjena — izdvojen `_btn_style` string prije oba dugmeta,
primijenjen na oba `setStyleSheet()` poziva. Bez promjene javnog API-ja
klase, bez promjene layout-a (isti `btn_row` raspored).

## Šta nije dirano
- Root cause globalne QSS kaskade — nije istražen do kraja (vidi "Zašto").
  Ako se u budućnosti pojavi isti problem na DRUGOM dugmetu bez lokalnog
  stila (u bilo kom dijelu app-a), vrijedi tada uraditi punu QSS cascade
  analizu umjesto opet lokalno zakrpiti.
- `app/run.py::main()` — usput otkriveno da POSTOJI poziv
  `check_and_setup_db()` tamo, ali taj entry point NIJE onaj koji
  PyInstaller spec (`deklarant_pro.spec:137`) koristi za produkcioni build
  (koji koristi `run.py` iz korijena). Zabilježeno u docs/CONTEXT.md §69
  kao follow-up napomena, ništa promijenjeno — van scope-a ovog zadatka i
  van scope-a ranije odluke korisnika da odgodi startup-proveru do static
  IP-a.

## Verifikacija
- `python -m py_compile` na oba fajla (root + dist_client) — čisto.
- Offscreen provjera (`QT_QPA_PLATFORM=offscreen`): oba dugmeta imaju
  postavljen, međusobno identičan `styleSheet()` string.
- `git diff --no-index --ignore-cr-at-eol` root vs dist_client — 0 razlika
  nakon sinhronizacije.
- `pytest tests/unit/test_db_setup_dialog_button_visibility.py -q` — 1
  passed (nov test).
- Pun test suite `pytest tests/ -q` — 1181 passed, 57 skipped, 5 xfailed,
  ista 2 pre-postojeća nepovezana problema.
- `gitnexus_detect_changes(scope=all)` — LOW risk, 0 affected_processes.

## Pronađeni problemi
Usputni nalaz: `app/run.py::main()` (mrtav kod za produkciju, vidi "Šta
nije dirano") — zabilježeno, nije popravljano jer nije bilo traženo i van
je scope-a ove sesije.

## Konflikti / kontradiktorni izvori
Nema.

## Commitovi
| Hash | Poruka |
| --- | --- |
| (sljedeći commit) | `fix(admin): popravi nevidljivo dugme Testiraj konekciju u DbSetupDialog` |

## Rizici / ograničenja
Fix nije potvrđen pixel-tačno (test provjerava da su stringovi postavljeni
i identični, ne stvaran render) — potreban je vizuelni pregled uživo.
Root cause globalne kaskade ostaje nepoznat, pa je moguće (mada
malo vjerovatno) da se isti simptom pojavi na nekom DRUGOM
neopremljenom dugmetu negdje drugo u app-u.

## Potreban follow-up
- Vizuelna potvrda korisnika da su oba dugmeta sad čitljiva i vizuelno
  konzistentna.
- Ako se predomisli o startup auto-provjeri konekcije: `app/run.py` već
  ima referentnu implementaciju (`check_and_setup_db()` poziv) koja se
  može prenijeti/pozvati iz `run.py::main()` umjesto pisanja iznova.

## Potrebna korisnička potvrda
Da — vizuelni izgled oba dugmeta u živoj aplikaciji.
