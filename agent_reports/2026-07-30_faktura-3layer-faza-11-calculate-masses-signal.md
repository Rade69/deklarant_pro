# Faktura 3-layer Faza 11 — ručni Izračunaj mase signal

## Datum

2026-07-30

## Agent

Codex

## Scope

- `gui/tabs/faktura_view.py`
- `dist_client/gui/tabs/faktura_view.py`
- `tests/unit/test_faktura_controller.py`
- `docs/context/history.md`

## Status izvora

- `docs/CONTEXT.md` — aktivan evergreen kontekst, pročitan prije izmjene.
- `docs/context/history.md` — aktivan dated log, korišćen ciljano kroz kraj fajla.
- GitNexus refactoring skill — korišćen jer se mijenja UI wiring u toku 3-layer migracije.

## GitNexus impact

`FakturaView._setup_ui` impact: LOW, 1 direktni pozivalac (`FakturaView.__init__`), 0 pogođenih execution flow-ova.

`FakturaView._on_calculate_masses` impact: LOW, direktni pozivalac `FakturaView.calculate_masses`, test pokrivenost kroz javni adapter. Ručni klik se uklanja kao direktni pozivalac, ali handler `FakturaTab._on_calculate_masses_requested` i dalje delegira na istu metodu.

## Šta je urađeno

- Dugme `Izračunaj mase` sada emituje `calculate_masses_requested`.
- `FakturaTab._on_calculate_masses_requested` ostaje postojeći handler i još delegira na `_on_calculate_masses`.
- Root i `dist_client` `faktura_view.py` ostaju ogledani.
- Dodat je test koji potvrđuje da klik emituje signal i ne poziva privatni handler direktno.

## Zašto je urađeno

Faza 11 nastavlja ručni toolbar migration pattern iz Faze 10. Cilj je ukloniti direktni View-handler wiring iz dugmadi bez mijenjanja poslovne logike raspodjele masa, jer je taj kod osjetljiv i već radi u produkciji.

## Kako je urađeno

`btn_calc_masses.clicked.connect(self._on_calculate_masses)` zamijenjeno je signalnim emitovanjem:
`lambda checked=False: self.calculate_masses_requested.emit()`. Test patchuje `_on_calculate_masses`, klikne dugme i potvrđuje da privatni handler nije pozvan direktno, dok signal jeste emitovan.

## Šta nije dirano

- Nije mijenjan `FakturaTab._on_calculate_masses_requested`.
- Nije mijenjana unutrašnja logika `_on_calculate_masses`.
- Nije dirana per-invoice raspodjela masa.
- Nije diran Agent pipeline.
- Nisu dirani `Auto-popuni` i `Kreiraj Naimenovanja` tokovi.
- Nisu dirane nepovezane lokalne izmjene u radnom stablu.

## Verifikacija

- `python -m py_compile gui/tabs/faktura_view.py dist_client/gui/tabs/faktura_view.py tests/unit/test_faktura_controller.py` — OK
- `python -m pytest tests/unit/test_faktura_controller.py -q` — 29 passed
- Širi Faktura/Agent skup uz `-m "not integration"` — 136 passed, 2 deselected

## Pronađeni problemi

Nije pronađen novi funkcionalni bug. Potvrđeno je da je `Izračunaj mase` dugme imalo postojeći signal i handler, ali klik do sada nije koristio signalni put.

## Konflikti / kontradiktorni izvori

Nema kontradikcije. Qt signalni wiring nije potpuno vidljiv kao GitNexus execution flow, pa je impact dopunjen direktnim `rg`/diff auditom i testom klika.

Potrebna korisnička potvrda: NE.

## Commitovi

| Hash | Poruka |
| --- | --- |
| 0f69fd0 | `refactor(faktura): povezi izracun masa dugme preko signala` |

## Rizici / ograničenja

Ovo nije potpuna migracija masa u Controller/Service. Signalni handler za sada namjerno poziva isti legacy View handler, jer taj handler još nosi poslovne i GUI detalje koje treba izdvajati u zasebnim fazama.

## Potreban follow-up

Sljedeći sličan rez može biti ručno dugme `Kreiraj Naimenovanja`, ali to je rizičnije od masa jer postojeći `FakturaTab._on_create_naimenovanja_requested` ide kroz Controller put koji nije potpuna paritetna zamjena za legacy View tok.

## Potrebna korisnička potvrda

Korisnik treba u aplikaciji ručno kliknuti `Izračunaj mase` na realnoj fakturi i potvrditi da je vidljivo ponašanje isto kao prije.
