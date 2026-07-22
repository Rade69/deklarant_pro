# Agent Report — 2026-07-22: PDF dugme — vidljiv indikator padajućeg menija

## Datum
2026-07-22

## Agent
Claude Sonnet 5

## Scope
- `styles/button_system.qss` + `dist_client` kopija
- `docs/CONTEXT.md` (§36)

## Status izvora

Direktan nastavak merge-a Codex grane (`agent_reports/2026-07-22_merge-codex-faktura-toolbar.md`).
Korisnik testirao novu funkcionalnost PDF menija (§32-34 u CONTEXT.md, Codexova
`feat(faktura): dodaj izbor PDF izvještaja u meni`) i primijetio da dugme nema vizuelni
indikator (trokutić) da je padajući meni.

## GitNexus impact

Nema — čisto QSS izmjena, ne dira `gui/tabs/faktura_view.py` niti bilo koji Python kod.
`_populate_toolbar_section`/`_create_button` (gdje se `btnPDF` objectName postavlja i
`setMenu()` poziva) su netaknuti.

## Šta je urađeno

Provjereno: `menu-indicator` se nigdje u repou nije koristio prije ove izmjene (grep preko
svih `.qss`/`.py` fajlova) — `QPushButton#btnPDF` je imao samo `background-color`/`color`/
`border` pravila (u `unified_color_system.qss` i `button_system.qss`), bez ijedne definicije
za sam indikator padajućeg menija. Dodato u `styles/button_system.qss` (+ `dist_client`
kopija): `QPushButton#btnPDF { padding-right: 18px; }` (mjesto za strelicu) i
`QPushButton#btnPDF::menu-indicator { subcontrol-origin: padding; subcontrol-position: right
center; right: 6px; width: 8px; height: 8px; }`.

## Zašto je urađeno

`btn_export_pdf.setMenu(pdf_export_menu)` (dodato Codexovim `bc00a1a` commitom) čini cijelo
dugme okidačem za padajući meni s dvije opcije ("Spisak naimenovanja" / "Pregled po
fakturama") — bez vizuelnog signala korisnik ne zna da je to meni, a ne obična akcija koja
odmah izvozi PDF.

## Kako je urađeno

Dvije nove QSS deklaracije dodate ODMAH nakon postojećeg `#btnPDF:pressed` bloka, u oba
identična fajla (`styles/` i `dist_client/styles/`) — čisto dodatna izmjena, ne mijenja
nijedno postojeće pravilo.

## Šta nije dirano

- `gui/tabs/faktura_view.py` — `_populate_toolbar_section`, `_create_button`,
  `_on_export_pdf`, `_on_export_pregled_faktura` — nula izmjena.
- Boje, hover/pressed stanja, ostala dugmad u "Izvezi" sekciji.

## Verifikacija

```
python -m pytest tests/ -k "faktura and (toolbar or button or pdf)" -q
  → 1 passed, 4 skipped, 942 deselected (ništa specifično za btnPDF postoji kao pytest,
    Codexova verifikacija bila je offscreen smoke test van pytest suite-a)
```

QSS sintaksa vizuelno provjerena (par zagrada, validni selektori) — Qt tiho ignoriše
nevalidan QSS bez izuzetka, pa formalna python-nivo provjera nije primjenjiva; potrebna je
vizuelna potvrda nakon rebuild-a.

## Pronađeni problemi

Nema novih.

## Konflikti / kontradiktorni izvori

Nema.

## Commitovi

| Hash | Poruka |
|------|--------|
| (pending) | style(faktura): dodaj indikator padajućeg menija na PDF dugme |

## Rizici / ograničenja

- Nisam mogao vizuelno potvrditi izgled bez pokretanja aplikacije (offscreen Qt test bi
  mogao provjeriti postojanje `menu-indicator` u efektivnom stylesheet-u, ali ne i stvaran
  render) — korisnička vizuelna potvrda potrebna nakon rebuild-a.
- `padding-right: 18px` je procjena — ako se u praksi pokaže da strelica i dalje nije
  dovoljno vidljiva ili da tekst djeluje pomjeren, vrijednost treba fino podesiti.

## Potreban follow-up

- Rebuild `.exe`-a i vizuelna potvrda da se trokutić sad vidi na PDF dugmetu.

## Potrebna korisnička potvrda

- Da li se mali trokutić (indikator padajućeg menija) sad jasno vidi na PDF dugmetu u
  Faktura tabu.
