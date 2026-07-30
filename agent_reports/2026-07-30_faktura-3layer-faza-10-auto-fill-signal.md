# Faktura 3-layer Faza 10 — ručni Auto-popuni signal

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

`FakturaView._on_auto_fill` impact: LOW, direktni pozivalac `FakturaView.auto_fill`, test pokrivenost kroz javni adapter. Ručni klik se uklanja kao direktni pozivalac, ali handler `FakturaTab._on_auto_fill_requested` i dalje delegira na istu metodu.

## Šta je urađeno

- Dugme `Auto-popuni` sada emituje `auto_fill_requested`.
- `FakturaTab._on_auto_fill_requested` ostaje postojeći handler i još delegira na `_on_auto_fill`.
- Root i `dist_client` `faktura_view.py` ostaju ogledani.
- Dodat je test koji potvrđuje da klik emituje signal i ne poziva privatni handler direktno.

## Zašto je urađeno

Faze 5-9 su očistile Agent pipeline od primarnih privatnih poziva. Faza 10 započinje isti obrazac za ručni toolbar tok, ali najmanjim sigurnim rezom: mijenja se samo UI wiring, ne poslovna logika auto-popune.

## Kako je urađeno

`btn_auto_fill.clicked.connect(self._on_auto_fill)` zamijenjeno je signalnim emitovanjem:
`lambda checked=False: self.auto_fill_requested.emit()`. Test patchuje `_on_auto_fill`, klikne dugme i potvrđuje da privatni handler nije pozvan direktno, dok signal jeste emitovan.

## Šta nije dirano

- Nije mijenjan `FakturaTab._on_auto_fill_requested`.
- Nije mijenjana unutrašnja logika `_on_auto_fill`.
- Nije dirana auto-popuna u Agent pipeline-u.
- Nisu dirani `Izračunaj mase` i `Kreiraj Naimenovanja` ručni klikovi.
- Nije uklonjen nijedan privatni fallback.
- Nisu dirane nepovezane lokalne izmjene u radnom stablu.

## Verifikacija

- `python -m py_compile gui/tabs/faktura_view.py dist_client/gui/tabs/faktura_view.py tests/unit/test_faktura_controller.py` — OK
- `python -m pytest tests/unit/test_faktura_controller.py -q` — 28 passed
- Širi Faktura/Agent skup uz `-m "not integration"` — 135 passed, 2 deselected

## Pronađeni problemi

Nije pronađen novi funkcionalni bug. Potvrđeno je da je `Auto-popuni` dugme imalo postojeći signal i handler, ali klik do sada nije koristio signalni put.

## Konflikti / kontradiktorni izvori

Nema kontradikcije. GitNexus nije pokrio Qt `clicked.connect(...)` kao pun execution flow, pa je impact dopunjen direktnim `rg` auditom i testom klika.

Potrebna korisnička potvrda: NE.

## Commitovi

| Hash | Poruka |
| --- | --- |
| a2115e4 | `refactor(faktura): povezi auto popuni dugme preko signala` |

## Rizici / ograničenja

Ovo nije potpuna migracija auto-popune u Controller/Service. Signalni handler za sada namjerno poziva isti legacy View handler, jer taj handler još nosi poslovne i GUI detalje koje treba izdvajati u zasebnim fazama.

## Potreban follow-up

Sljedeći sličan rez može biti `Izračunaj mase` dugme preko `calculate_masses_requested`, jer i za njega već postoji signal i handler koji delegira na postojeći View tok.

## Potrebna korisnička potvrda

Korisnik treba u aplikaciji ručno kliknuti `Auto-popuni` na realnoj fakturi i potvrditi da je vidljivo ponašanje isto kao prije.
