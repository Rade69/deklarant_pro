## Datum

2026-07-24

## Agent

OpenAI Codex

## Scope

- `gui/main_window.py`
- `dist_client/gui/main_window.py`
- `styles/main_tabs.qss`
- `dist_client/styles/main_tabs.qss`
- `tests/unit/test_main_window_exit_button.py`

## GitNexus impact

LOW, pet povezanih metoda u GUI modulu i bez pogođenih poslovnih procesa.

## Šta je urađeno

Dugme `Izlaz` dobilo je garantovan vertikalni razmak od trake sadržaja, kompaktnu
visinu i zaseban stil sa zaobljenjem, obrubom, hoverom i pressed stanjem.

## Zašto je urađeno

Donji rub dugmeta vizuelno se naslanjao na sadržaj ispod glavne trake kartica.

## Kako je urađeno

Visina se ograničava prema stvarnoj visini `QTabBar`, uz najmanje četiri piksela
vertikalne margine. Stil je skopovan isključivo na `btnExitApp`.

## Šta nije dirano

Nisu mijenjani položaj tabova, funkcija zatvaranja, potvrda aktivnog Agent workera
ni ostala dugmad.

## Verifikacija

- Pet ciljanih offscreen testova je prošlo.
- `py_compile` je prošao.
- QSS je uspješno učitan kroz Qt parser.
- `git diff --check` i pre-commit provjera su prošli.

## Pronađeni problemi

Nema.

## Konflikti / kontradiktorni izvori

Nema.

## Commitovi

| Hash | Poruka |
|---|---|
| `b96fac0` | `fix(gui): odmakni i stilizuj dugme izlaz` |

## Rizici / ograničenja

Potrebna je vizuelna provjera na korisnikovom stvarnom Windows skaliranju.

## Potreban follow-up

Nije potreban ako je razmak vizuelno odgovarajući.

## Potrebna korisnička potvrda

Provjeriti da dugme više ne dodiruje donji sadržaj pri uobičajenoj veličini
prozora.
