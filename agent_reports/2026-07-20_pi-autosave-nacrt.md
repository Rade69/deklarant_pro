# Agent Report: Autosave / recovery nacrta deklaracije

- **Datum**: 2026-07-20
- **Agent**: Pi (Claude Code alternative)
- **Scope**: `services/draft_autosave_service.py` (novi), `gui/main_window.py`, `run.py`, `dist_client/` mirror

## GitNexus impact

- Prije izmjene: `gitnexus impact "Class:gui/main_window.py:MainWindow"` → **LOW** (4 direktna importa, 0 procesa)
- Novi simboli (`draft_autosave_service.py`) nemaju postojeće zavisnike — nema rizika
- Pogođeno: 0 procesa, samo dodavanje novih hookova na postojeće signale

## Šta je urađeno

1. **`services/draft_autosave_service.py`** — novi servis sa:
   - `autosave_path()` — fiksna putanja `~/.autosave/autosave.xml`
   - `save_autosave(draft)` — reuse-uje `DeclarationDraftService.save()`
   - `has_autosave()`, `autosave_timestamp()`, `load_autosave()`, `clear_autosave()`
   - Svi logger ispisi sa emoji (bez direktnog stderr ispisa)

2. **`gui/main_window.py`** — dodato:
   - `_setup_autosave()` — QTimer na 5 minuta, povezan na `_autosave_tick()`
   - `_autosave_tick()` — čuva trenutni draft (iz FakturaView ili MainWindow.draft)
   - `_on_autosave_after_naimenovanja()` — hook na `FakturaView.naimenovanja_created`
   - `clear_autosave()` u `_on_exit_clicked()` — briše autosave pri urednom zatvaranju

3. **`run.py`** — dodato:
   - `_check_autosave_on_startup(parent)` — non-blocking dijalog nakon `window.show()`
   - Poziv: `_check_autosave_on_startup(window)` prije `_check_license_on_startup(window)`
   - Na Yes: učitava autosave u MainWindow.draft (isti obrazac kao `_replace_draft_contents`)
   - Na No: briše autosave fajl

4. **`dist_client/`** — mirror sa ispravnim encodingom (bez BOM)

5. **`tests/unit/test_draft_autosave_service.py`** — 14 testova:
   - Save/load/has/clear/timestamp — osnovne operacije
   - Ne mijenja `_persistent_draft_path` — autosave ne dira ručno save stanje
   - Ne setuje dirty = False — autosave ne maskira prljavštinu
   - Multiple save/load cycles — fajl overwrite
   - Valid XML sa DeklarantProDraft root tagom
   - Naimenovanja se čuvaju kroz autosave
   - Rubne vrijednosti: no file, clear bez fajla
   - Putanja pod default_drafts_directory

## Zašto je urađeno

Korisnik (Radovan) je primijetio da nema zaštite od gubitka rada pri padu
aplikacije, strujnom udaru ili slučajnom zatvaranju. Cilj: automatsko čuvanje
u pozadini + ponuda za oporavak, bez ometanja korisnika dijalozima usred rada.

## Kako je urađeno

- Novi zaseban fajl `services/draft_autosave_service.py` (nije miješano u `DeclarationDraftService`)
- Timer živi u `MainWindow` (gdje već postoji pristup draftu i QTimer import)
- Hook na `naimenovanja_created` signal **umjesto** direktnog diranja `_on_create_naimenovanja`
  — time se izbjegava potpuno diranje `faktura_view.py` (u skladu sa scope lock-om)
- Recovery obrazac preuzet iz `_check_license_on_startup` (non-blocking, nakon `window.show()`)
- Autosave se briše pri urednom zatvaranju (`_on_exit_clicked`) — recovery prikazuje
  samo ako je došlo do neočekivanog prekida

## Šta nije dirano

- `gui/tabs/faktura_view.py` — nije diran (hook preko signala umjesto direktnog poziva)
- `gui/tabs/agent/services/*` — scope lock
- `services/agent/*` — scope lock
- `gui/tabs/agent/widgets/llm_provider.py` — scope lock
- `gui/tabs/agent/agent_controller.py` — nije diran
- `services/declaration_draft_service.py` — nije diran (samo reuse-ovan)
- `drafts/lastDirectory` QSettings — nije diran
- `_persistent_draft_path` — nije diran (ostaje samo za ručno "Sačuvaj nacrt")

## Verifikacija

- [x] `python -m py_compile services/draft_autosave_service.py` — OK
- [x] `python -m py_compile gui/main_window.py` — OK
- [x] `python -m py_compile run.py` — OK
- [x] `python -m py_compile dist_client/services/draft_autosave_service.py` — OK
- [x] `python -m py_compile dist_client/gui/main_window.py` — OK
- [x] `python -m py_compile dist_client/run.py` — OK
- [x] `python -m pytest tests/unit/test_draft_autosave_service.py -v` — 14/14 passed
- [x] `python -m pytest tests/ -q` — samo 4 postojeća faila (nisu povezani)
- [x] Pre-commit hook prošao
- [x] dist_client encoding: root BOM (utf-8-sig), dist_client bez BOM (utf-8)

## Pronađeni problemi

- `_persistent_draft_path` je dinamički atribut (ne postoji u `DeclarationDraft` klasi,
  postavlja ga samo `DeclarationDraftService.load()`). Test mora koristiti
  `hasattr()` umjesto direktnog pristupa.

## Commitovi

| Hash | Poruka |
|------|--------|
| `cfdbe98` | feat(autosave): automatsko čuvanje nacrta i oporavak pri startu |

## Rizici / ograničenja

- **Autosave koristi `DeclarationDraftService.save()`** — isti format kao ručni save.
  Ako se format promijeni, autosave će automatski pratiti. Nema dodatnog održavanja.
- **Timer interval od 5 min** je fiksan. Ako bude potrebe za konfigurabilnim intervalom,
  lako se dodaje QSettings parametar.
- **Sam draft objekat** — autosave čuva ono što je u draftu u trenutku tick-a.
  Ako FakturaView ima lokalni draft (split draft), čuva se taj (preko `faktura_view.draft`).
- **Ako je `DeclarationDraftService.save()` izmijenjen u budućnosti** da dodaje
  nešto što ne želimo u autosave-u (npr. postavlja `_persistent_draft_path`), treba
  dodati wrapper u autosave_service koji to poništava.

## Potreban follow-up

- Nema — zadatak je zatvoren. Grana `feature/draft-autosave-nacrt` čeka spajanje
  sa `windows` nakon što Claude završi Fazu D.

## Potrebna korisnička potvrda

- Ručno testiranje: simulirani "pad" (ubiti proces) dok postoji autosave, pa
  restart — treba se pojaviti recovery dijalog sa tačnim vremenom.
- Autosave se NE smije pojaviti nakon urednog zatvaranja (preko "Izlaz" dugmeta).