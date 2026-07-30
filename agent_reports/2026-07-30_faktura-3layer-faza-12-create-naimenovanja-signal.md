# Faktura 3-layer Faza 12 — ručni Kreiraj Naimenovanja signal

## Datum

2026-07-30

## Agent

Codex

## Scope

- `gui/tabs/faktura_tab.py`
- `dist_client/gui/tabs/faktura_tab.py`
- `gui/tabs/faktura_view.py`
- `dist_client/gui/tabs/faktura_view.py`
- `tests/unit/test_faktura_controller.py`
- `docs/context/history.md`

## Status izvora

- `docs/CONTEXT.md` — aktivan evergreen kontekst, pročitan prije izmjene.
- `docs/context/history.md` — aktivan dated log, korišćen ciljano kroz kraj fajla.
- GitNexus refactoring skill — korišćen jer se mijenja UI wiring u toku 3-layer migracije.

## GitNexus impact

`FakturaView._on_create_naimenovanja` impact: LOW, 3 direktna pozivaoca u root kodu/testovima (`FakturaView.create_naimenovanja`, `_on_export_pdf`, characterization test), 0 pogođenih execution flow-ova.

`FakturaTab._on_create_naimenovanja_requested` impact: LOW, GitNexus ne vidi direktne pozivaoce jer je Qt signalni wiring dinamičan. Ručni `rg` audit potvrdio je da signal već postoji i da je povezan u `FakturaTab.__init__`.

## Šta je urađeno

- Dugme `Kreiraj Naimenovanja` sada emituje `create_naimenovanja_requested(False)`.
- `FakturaTab._on_create_naimenovanja_requested` više ne koristi parcijalni Controller create put.
- Handler sada delegira na javni `create_naimenovanja(auto=auto)` adapter, koji čuva postojeći legacy View tok.
- Root i `dist_client` fajlovi ostaju ogledani.
- Dodani su testovi:
  - klik dugmeta emituje signal i ne poziva privatni handler direktno;
  - signal handler koristi javni legacy adapter.

## Zašto je urađeno

Kod `Auto-popuni` i `Izračunaj mase` signal handleri su već delegirali na legacy View metode, pa je bilo bezbjedno samo prespojiti dugmad. Kod `Kreiraj Naimenovanja` handler je bio rizičniji jer je išao kroz Controller, koji još nije paritetna zamjena za produkcioni View tok. Da ne izgubimo funkcionalnost, prvo je handler vraćen na javni legacy adapter, pa je tek onda dugme prespojeno na signal.

## Kako je urađeno

`btn_create_naimenovanja.clicked.connect(self._on_create_naimenovanja)` zamijenjeno je signalnim emitovanjem:
`lambda checked=False: self.create_naimenovanja_requested.emit(False)`.

`FakturaTab._on_create_naimenovanja_requested(auto)` sada radi `return self.create_naimenovanja(auto=auto)`.

## Šta nije dirano

- Nije mijenjana unutrašnja logika `_on_create_naimenovanja`.
- Nije aktiviran parcijalni Controller create put za ručni klik.
- Nije mijenjan Agent pipeline.
- Nije diran XML/export/import tok.
- Nije uklonjen nijedan privatni fallback.
- Nisu dirane nepovezane lokalne izmjene u radnom stablu.

## Verifikacija

- `python -m py_compile gui/tabs/faktura_tab.py dist_client/gui/tabs/faktura_tab.py gui/tabs/faktura_view.py dist_client/gui/tabs/faktura_view.py tests/unit/test_faktura_controller.py` — OK
- `python -m pytest tests/unit/test_faktura_controller.py -q` — 31 passed
- Širi Faktura/Agent skup uz `-m "not integration"` — 138 passed, 2 deselected

## Pronađeni problemi

Postojeći `FakturaTab._on_create_naimenovanja_requested` nije bio bezbjedan za aktiviranje ručnim dugmetom jer je zaobilazio bogatiji legacy View tok. Ovo je ispravljeno prije prespajanja dugmeta.

## Konflikti / kontradiktorni izvori

Nema kontradikcije između koda i plana; plan je zahtijevao oprez jer Controller create put još nije paritetan. Kao važeći izvor tretiran je legacy View tok, jer je to produkcioni put koji su do sada koristili korisnici.

Potrebna korisnička potvrda: NE.

## Commitovi

| Hash | Poruka |
| --- | --- |
| pending | `refactor(faktura): povezi kreiraj naimenovanja dugme preko signala` |

## Rizici / ograničenja

Ovo nije potpuna migracija kreiranja naimenovanja u Controller/Service. Signalni handler namjerno zadržava legacy paritet preko javnog adaptera. Brisanje `_on_create_naimenovanja` ili aktiviranje Controller create puta zahtijeva posebnu fazu sa E2E testom.

## Potreban follow-up

Sljedeći logičan korak je stabilizacioni audit ručnih toolbar signala: `Provjeri`, `Auto-popuni`, `Izračunaj mase` i `Kreiraj Naimenovanja` sada idu preko signala, ali samo validacija ima pravi Controller tok. Ostali su signalni wiring sa legacy delegacijom.

## Potrebna korisnička potvrda

Korisnik treba u aplikaciji ručno kliknuti `Kreiraj Naimenovanja` na realnoj fakturi i potvrditi da je ponašanje identično prethodnom produkcionom toku.
