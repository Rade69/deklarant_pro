# Datum

2026-07-29

## Agent

Codex

## Scope

- `gui/tabs/faktura_view.py`
- `gui/tabs/faktura_tab.py`
- `gui/tabs/faktura_controller.py`
- `dist_client/gui/tabs/faktura_view.py`
- `dist_client/gui/tabs/faktura_tab.py`
- `dist_client/gui/tabs/faktura_controller.py`
- `tests/unit/test_faktura_controller.py`
- `docs/CONTEXT.md`

## Status izvora

- `docs/CONTEXT.md` §91, §94-98 — aktivno; definiše da su signali bili pasivna infrastruktura i da se migracija radi malim vertikalnim rezovima.
- Faza 3 report — aktivno; osnovna validaciona boja je već bila premještena u servis, što omogućava Fazu 4.

## GitNexus impact

- `FakturaView._on_validate_all` — LOW, 0 direktnih indeksiranih pozivalaca/procesa.
- `FakturaController` — LOW, 2 direktna importera (`gui/tabs/faktura_tab.py`, `dist_client/gui/tabs/faktura_tab.py`), dalje `tab_factory` i `main_window`.
- `FakturaController.validate_and_color_rows` — LOW, 1 test pozivalac u indeksu.

## Šta je urađeno

- Dugme `Provjeri` sada emituje `validate_requested` umjesto direktnog poziva stare View metode.
- `FakturaTab._on_validate_requested` postao je aktivni ručni validacioni tok:
  - sinhronizuje tabelu u draft,
  - poziva `FakturaController.validate_and_color_rows`,
  - primjenjuje boje i tooltip-e na Qt tabelu,
  - puni `validation_cache`,
  - ažurira status bar,
  - prikazuje korisniku ručni sažetak validacije,
  - pokreće istorijsku tarifnu provjeru.
- `FakturaController.validate_and_color_rows` proširen je tako da, pored starog `color_map` ugovora, vraća `style_map`, `valid_count` i `target_rows`.
- Testovi su dopunjeni da dokažu da dugme emituje signal i da signalni handler koristi `blockSignals` bez `itemChanged` spama.
- Root i `dist_client` su ogledani za dotaknute fajlove.

## Zašto je urađeno

Ovo je prvi stvarni View -> Controller -> Service vertikalni rez Faktura taba. Faza 3 je pripremila servisnu validacionu logiku, ali ručna akcija korisnika je i dalje išla direktno kroz View handler. Aktiviranjem samo dugmeta `Provjeri` dobija se stvarna migracija bez diranja import pipeline-a, pune automatizacije ili XML toka.

## Kako je urađeno

`FakturaView` dobija `_emit_validate_requested`, koji čita selektovane redove iz Qt tabele i emituje `validate_requested("rows", rows)` ili `validate_requested("all", [])`. `FakturaTab` preuzima orkestraciju i koristi `FakturaController`, dok View ostaje zadužen samo za UI objekte, postojeće helper metode za status/modal i istorijski worker.

## Šta nije dirano

- Automatski `_on_validate_all(auto=True)` put nije prebačen.
- Import, puna automatizacija, kreiranje naimenovanja i XML export nisu mijenjani.
- Country/preference confidence logika nije premještena iz View-a.
- Ostali Faktura signali nisu aktivirani.
- Nepovezane lokalne izmjene u worktree-u nisu dirane.

## Verifikacija

- `python -m pytest tests/unit/test_faktura_controller.py -q` — 19/19 passed.
- `python -m pytest tests/unit/test_faktura_validation_service_phase3.py tests/unit/test_inline_validation_gui.py -q` — 10/10 passed.
- `python -m pytest tests/unit/test_faktura_controller.py tests/unit/test_faktura_validation_service_phase3.py tests/unit/test_inline_validation_gui.py tests/unit/test_faktura_service_phase2.py tests/unit/test_faktura_table_roundtrip.py tests/unit/test_faktura_characterization.py tests/unit/test_tariff_learning_ledger.py -q` — 69/69 passed.

## Pronađeni problemi

Postojeći testovi koji direktno emituju `validate_requested` ranije nisu patchovali modale jer signal nije bio pravi korisnički tok. Nakon aktiviranja ručne validacije testovi su morali patchovati `SafeMessageBox.information/warning`; produkciono ponašanje modala je ostalo.

## Konflikti / kontradiktorni izvori

Komentar u `FakturaTab` govorio je da View još ne emituje signale. To je bilo tačno prije Faze 4, ali je sada zastarjelo za `validate_requested`; komentar i `docs/CONTEXT.md` su ažurirani.

## Commitovi

| Hash | Poruka |
| --- | --- |
| 7d3b402 | `refactor(faktura): aktiviraj rucnu validaciju kroz controller` |

## Rizici / ograničenja

Automatski validacioni tok još nije migriran. To je namjerno ograničenje jer je vezan za import, punu automatizaciju i istorijsku validaciju, pa zahtijeva posebnu fazu i karakterizacione testove.

## Potreban follow-up

Faza 5 treba izabrati naredni mali vertikalni rez. Najprirodniji kandidati su ili automatska validacija/fallback `_on_validate_all(auto=True)` ili jedan jednostavniji handler koji ne otvara dodatne modale.

## Potrebna korisnička potvrda

Ručno kliknuti `Provjeri` u Faktura tabu na fakturi sa:

- svim stavkama,
- selektovanim jednim/dva reda,
- redom bez tarife ili zemlje,

i potvrditi da su modal, boje i istorijska tarifna provjera isti kao prije.
