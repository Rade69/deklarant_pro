# Faktura 3-layer stabilizacija toolbar signala

## Datum

2026-07-30

## Agent

Codex

## Scope

- `gui/tabs/faktura_tab.py`
- `dist_client/gui/tabs/faktura_tab.py`
- `tests/unit/test_faktura_controller.py`
- `docs/context/history.md`

## Status izvora

- `docs/CONTEXT.md` — aktivan evergreen kontekst, pročitan prije izmjene.
- `docs/context/history.md` — aktivan dated log, korišćen ciljano kroz kraj fajla.
- GitNexus refactoring skill — korišćen jer stabilizacija provjerava posljedice refaktor wiring-a.

## GitNexus impact

Produkciona izmjena je mala i ograničena na `FakturaTab` signal handler-e. `gitnexus_detect_changes` prije commita vratio je LOW rizik i 0 affected execution flow-ova, uz postojeći šum iz nepovezanih lokalnih fajlova.

## Šta je urađeno

- Napravljen je stabilizacioni audit ručnog toolbar toka:
  - `Provjeri` → `validate_requested` → aktivni Controller/Service tok.
  - `Auto-popuni` → `auto_fill_requested` → javni legacy adapter.
  - `Izračunaj mase` → `calculate_masses_requested` → javni legacy adapter.
  - `Kreiraj Naimenovanja` → `create_naimenovanja_requested(False)` → javni legacy adapter.
- `FakturaTab._on_auto_fill_requested` sada delegira na `self.auto_fill(auto=False)`.
- `FakturaTab._on_calculate_masses_requested` sada delegira na `self.calculate_masses(auto=False)`.
- Dodan je stabilizacioni test koji potvrđuje mapu tri legacy-delegirajuća signala prema javnim adapterima.
- Root/dist_client paritet potvrđen za `faktura_tab.py` i `faktura_view.py`.

## Zašto je urađeno

Faze 10-12 prespojile su ručna dugmad preko signala, ali `auto_fill` i `calculate_masses` handleri su i dalje direktno zvali privatne View metode. Funkcionalno je to radilo, ali arhitekturno nije bilo ujednačeno sa javnim adapter patternom iz Faza 5-8 i Faze 12. Stabilizaciona faza zatvara taj mali nesklad bez promjene poslovnog ponašanja.

## Kako je urađeno

Handleri su promijenjeni ovako:

- `_on_auto_fill_requested()` → `return self.auto_fill(auto=False)`
- `_on_calculate_masses_requested()` → `return self.calculate_masses(auto=False)`

Time signalni put ide kroz javni `FakturaTab` API, a javni adapter i dalje delegira na autoritativni legacy View handler.

## Šta nije dirano

- Nije mijenjana validaciona logika.
- Nije mijenjana unutrašnja logika `_on_auto_fill`, `_on_calculate_masses` ili `_on_create_naimenovanja`.
- Nije aktiviran Controller create put za kreiranje naimenovanja.
- Nije diran Agent pipeline.
- Nije diran import/export/XML tok.
- Nisu dirane nepovezane lokalne izmjene u radnom stablu.

## Verifikacija

- `python -m pytest tests/unit/test_faktura_controller.py -q` — 32 passed
- Širi Faktura/Agent skup uz `-m "not integration"` — 139 passed, 2 deselected
- `python -m py_compile gui/tabs/faktura_tab.py dist_client/gui/tabs/faktura_tab.py tests/unit/test_faktura_controller.py` — OK
- Root/dist_client paritet:
  - `gui/tabs/faktura_tab.py` — OK
  - `gui/tabs/faktura_view.py` — OK

## Pronađeni problemi

Nije pronađen funkcionalni bug. Pronađen je arhitekturni nesklad: dva signal handlera su preskakala javne adaptere i direktno zvala privatne View metode. To je sada ujednačeno.

## Konflikti / kontradiktorni izvori

Nema kontradikcije. GitNexus ne vidi u potpunosti Qt signal wiring kao execution flow, pa je audit dopunjen `rg` pregledom connect linija i testom klika/signal mape.

Potrebna korisnička potvrda: NE.

## Commitovi

| Hash | Poruka |
| --- | --- |
| pending | `refactor(faktura): stabilizuj toolbar signalne adaptere` |

## Rizici / ograničenja

Ovo nije cleanup faza. Privatni legacy handleri ostaju ispod javnih adaptera. Dublja migracija u Controller/Service mora ići zasebno po funkcionalnosti, uz paritet testove i korisnički E2E.

## Potreban follow-up

Preporuka za sljedeći korak: napraviti kratak cleanup/migracioni manifest sa tri kolone za svaki legacy handler:

- trenutni javni ulaz;
- šta legacy handler još radi;
- šta mora biti izdvojeno u Service/Controller prije brisanja.

## Potrebna korisnička potvrda

Korisnik treba ručno provjeriti na realnoj fakturi: `Provjeri`, `Auto-popuni`, `Izračunaj mase`, `Kreiraj Naimenovanja`.
