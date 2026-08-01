# Faktura 3-layer Faza 3 — Controller-owned validator i assembly

## Datum

2026-08-01

## Agent

Codex

## Scope

- `gui/tabs/faktura_controller.py`
- `gui/tabs/faktura_tab.py`
- `gui/tabs/faktura_view.py`
- `dist_client/gui/tabs/faktura_controller.py`
- `dist_client/gui/tabs/faktura_tab.py`
- `dist_client/gui/tabs/faktura_view.py`
- `tests/unit/test_faktura_controller.py`
- `tests/unit/test_faktura_view_status_bar.py`
- `dist_client/tests/unit/test_faktura_view_status_bar.py`
- `project_rooms/2026-08-01_faktura-3layer-refaktor-fazni-plan.md`
- `docs/context/history.md`

## Status izvora

Aktivni izvori:

- `project_rooms/2026-08-01_faktura-3layer-refaktor-fazni-plan.md` — Faza 3.
- `docs/CONTEXT.md` — 3-layer pravila, GUI/status pravila i XML/validaciona ograničenja.
- Trenutni worktree: `.worktrees/faktura-faza3-codex`, grana `refactor/faktura-3layer-codex`, polazni commit `115d673`.

Paralelni rad:

- Pi/Claude rade Faze 1-2 na `refactor/faktura-3layer-claude`.
- Ovaj rad je izolovan u posebnom worktree-u i nije dirao Pi/Claude WIP.

## GitNexus impact

- `FakturaItemValidator` root UID: MEDIUM, 30 pogođenih, 14 direktnih.
- `DeclarationAssembly` root UID: LOW, 6 pogođenih, 2 direktna.
- `FakturaView._validation_issue_counts`: HIGH, 23 pogođena, 2 direktna, proces `auto_fill`.
- `FakturaView._update_status_bar`: HIGH, 30 pogođenih, 21 direktan, procesi `calculate_masses` i `auto_fill`.
- `FakturaController`: LOW, 4 pogođena, 2 direktna.

Zbog HIGH metoda scope je zaključan na minimalan migracioni most i testove. Nije mijenjana validaciona semantika, assembly semantika, legacy import ili master-list ponašanje.

## Reprodukcija prije izmjene

Ovo nije bugfix nego arhitektonski refactor. Prije izmjene potvrđeno je:

- `FakturaView.__init__` direktno instancira `FakturaItemValidator` i `DeclarationAssembly`;
- `_validation_issue_counts()` direktno zove `self.validator.validate(line)`;
- `_update_status_bar()` direktno čita `self.assembly.master_list_loaded` i `self.assembly.get_completion_status()`;
- legacy/master-list grane i dalje koriste `self.assembly` i namjerno nisu scope Faze 3.

## Šta je urađeno

- `FakturaController` sada kreira i posjeduje `validator` i `assembly`.
- Dodati su mali Controller adapteri:
  - `validate_line(line)`;
  - `assembly_completion_status()`;
  - `reset_assembly()`.
- `FakturaTab` poslije kreiranja controllera poziva `view.set_controller(self.controller)`.
- `FakturaView` više nema top-level import niti direktnu instancijaciju `FakturaItemValidator`/`DeclarationAssembly` u `__init__`.
- `_validation_issue_counts()` ide kroz Controller adapter kada je Controller prisutan.
- `_update_status_bar()` assembly status dobija kroz Controller adapter.
- `_on_clear_all()` resetuje assembly kroz Controller kada je Controller prisutan.
- Root i `dist_client` produkcioni fajlovi su poravnati.

## Zašto je urađeno

Faza 3 iz plana traži da View prestane direktno instancirati i koristiti validator/assembly za male status/validacione tokove. Time se smanjuje View → Service sprega i pomjera vlasništvo u Controller, bez otvaranja velikog legacy import refaktora.

## Kako je urađeno

Primijenjen je migracioni most:

- aplikacioni put (`FakturaTab`) uvijek povezuje View sa Controllerom;
- View čuva `self.assembly` kao privremeni alias na Controller-owned assembly zbog legacy/master-list grana koje ostaju za Fazu 6/7;
- standalone View testovi imaju lokalni fallback za validacioni helper, ali normalan runtime koristi Controller.

## Šta nije dirano

- Nije dirana validaciona logika `FakturaItemValidator`.
- Nije dirana logika `DeclarationAssembly`.
- Nisu dirani legacy/master-list uvoz putevi.
- Nisu dirani `_on_load_master_list`, `_finish_import_legacy_path`, `_process_batch_records_legacy`.
- Nisu dirani Pi/Claude WIP fajlovi.
- Nisu stage-ovani generisani UI fajlovi koji su bili dirty u worktree-u.

## Verifikacija

Prošlo:

- `python -m py_compile gui/tabs/faktura_controller.py gui/tabs/faktura_tab.py gui/tabs/faktura_view.py dist_client/gui/tabs/faktura_controller.py dist_client/gui/tabs/faktura_tab.py dist_client/gui/tabs/faktura_view.py`
- `python -m pytest tests/unit/test_faktura_controller.py tests/unit/test_faktura_view_status_bar.py -q` → 44/44 passed
- `python -m pytest dist_client/tests/unit/test_faktura_view_status_bar.py -q` → 8/8 passed
- `python -m pytest tests/unit/test_faktura_characterization.py tests/unit/test_faktura_view_provjeri_nakon_uvoza.py tests/unit/test_import_workflow_parity.py tests/unit/test_puna_auto_pipeline.py tests/unit/test_faktura_view_provjeri_selekcija.py tests/unit/test_faktura_view_validacija_selekcija.py -q` → 71/71 passed

Širi unit set:

- `python -m pytest tests/unit -q -m "not integration"` → 1398 passed, 21 failed, 71 skipped, 2 deselected, 5 xfailed.
- Failovi su postojeći DB/env problemi u worktree okruženju: nedostaje `tarifa_2026`, nedostaje `DB_PASSWORD`, `DEBUG=release` nije validan bool za jedan test. Faktura ciljane i import/pipeline kapije su prošle.

GitNexus:

- `detect_changes` za staged scope nije mogao mapirati novi worktree path; indeks poznaje osnovni repo path i jedan stari worktree, ali ne `.worktrees/faktura-faza3-codex`.
- Scope je zato potvrđen sa `git diff --cached --name-only` i ciljanim testovima.

## Nezavisna provjera

Obavezna prije spajanja zbog HIGH impact metoda. Predloženi checker: Claude Code. Checker treba provjeriti:

- da View više ne posjeduje validator/assembly u Fazi 3 scope-u;
- da legacy/master-list `self.assembly` grane nisu slučajno promijenjene;
- da root/dist promjene ostaju paritetne;
- da testovi za status/validaciju pokrivaju stvarni novi tok.

## Pronađeni problemi

- Novi worktree je odmah pokazao dirty generisane UI fajlove (`ui/...`, `dist_client/ui/...`). Nisu dio ovog rada i nisu stage-ovani.
- GitNexus `detect_changes` ne mapira ovaj novi worktree path, pa je staged scope provjeren git diff-om.
- Širi unit set u ovom worktree-u zavisi od lokalne DB/env konfiguracije i zato nije potpuno zelen.

## Odbačene opcije

- Potpuno uklanjanje `self.assembly` iz View-a je odbačeno jer Faza 6/7 tek treba da obradi aktivne legacy/master-list puteve.
- Prebacivanje legacy import logike u ovoj fazi je odbačeno jer bi pomiješalo Fazu 3 sa najvećom i najrizičnijom Fazom 6.

## Konflikti / kontradiktorni izvori

Plan kaže da View treba prestati direktno instancirati `validator`/`assembly`, ali isti plan upozorava da legacy/master-list `self.assembly` grane nisu mrtve i ne smiju se dirati do Faze 6. Rješenje je migracioni alias: Controller posjeduje assembly, View privremeno drži referencu zbog legacy grana.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `603da5e` | `refactor(faktura): Faza 3 - prebaci validator i assembly u controller` |
| pending | `docs(faktura): dokumentuj Fazu 3 controller owned servise` |

## Kontekst korišćen

- `docs/CONTEXT.md` — pročitan relevantni početni dio sa 3-layer i GUI pravilima.
- `project_rooms/2026-08-01_faktura-3layer-refaktor-fazni-plan.md` — pročitan cijeli prije početka.
- `gui/tabs/faktura_controller.py`, `faktura_tab.py`, relevantni dijelovi `faktura_view.py`.
- Testovi za Faktura controller/status/import pipeline.

## Rizici / ograničenja

- View je privremeno porastao za nekoliko linija jer Faza 3 uvodi adaptere; pravo stanjenje dolazi kroz Faze 4-6.
- Legacy `self.assembly` grane ostaju tehnički dug, ali namjerno van scope-a.
- Potreban je nezavisan checker prije merge-a.

## Potreban follow-up

- Claude Code review/checker za Fazu 3.
- Nakon Pi Faza 1/2 i Codex Faza 3 treba koordinisati merge redoslijed da se ne pregaze paralelne izmjene u `faktura_view.py`.

## Potrebna korisnička potvrda

Nema poslovne odluke za ovu fazu. Potrebna je samo odluka kada da Claude Code pregleda i kojim redoslijedom će se spajati Pi i Codex grane.
