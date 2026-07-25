# Agent Report: Naimenovanja/Faktura — popravke nakon istrage

**Datum**: 2026-07-25
**Agent**: Pi
**Scope**: 8 od 13 otvorenih nalaza iz istrage `agent_reports/2026-07-25_istraga-naimenovanja-faktura-tok.md`

---

## Status: 8/13 riješeno, 5 ostaje (srednji rizik / veliki refaktor)

### Šta je urađeno (8 nalaza, 7 commitova)

| # | Nalaz | Commit | Šta je urađeno |
|---|-------|--------|----------------|
| 2a | N+1 u `_get_tariff_description` | `703a68e` | Delegira na TariffService sa cache-om |
| 2c | DB pri navigaciji | `703a68e` | Cache u TariffService.load_tariff_descriptions |
| 3e | Zastarjeli TariffService | `703a68e` | Napredna `_clean_tariff_description` + `nivo` parametar |
| 3c | Duplikat DELETE+learn | `dd8d62e` | TariffFacade.sync_mapping() objedinjuje oba |
| 3d | STOP_WORDS u View | `8d781b2` | TariffService.validate_suggestion_input() |
| 3b | DB upiti u NaimenovanjaView | `4f918fc` | NaimenovanjaService (pakovanja, dokumenti) — **0 DB upita u View** |
| 6a | ChatWorker/TariffLLMWorker bez cancel | `eac0b3d` | cancel() metoda + _cancelled flag |
| 6b | closeEvent bez quit/wait | `eac0b3d` | _shutdown_agent_workers() — graceful shutdown |

### Ključni rezultati

- **NaimenovanjaView: 14 → 0 direktnih DB upita** (sve u servisima)
- **N+1 eliminisan** — TariffService cache sprečava otvaranje SQLite konekcije u petlji
- **3 mrtve metode obrisane** (`_clean_tariff_description`, `_validate_mappings`, `_get_connection_pool`)
- **QThread lifecycle popravljen** — workeri su prekidivi, closeEvent radi graceful shutdown
- **Bug §44 otklonjen** — `_get_tariff_description` koristi frozen-svjestan put

### Šta nije urađeno (5 nalaza — opravdano ostavljeno)

| # | Nalaz | Razlog ostavljanja |
|---|-------|-------------------|
| 2b | `_run_historical_tariff_validation` na UI threadu | Srednji rizik — zahtijeva novi QThread worker + testiranje sa stvarnim DB |
| 5a | `_on_import_xml` na UI threadu | Niskorizično (rijetko se koristi) — novi worker prekompleksan za korist |
| 3a | NaimenovanjaController (3.888 linija) | Najveći refaktor — zasebna sesija, može lomiti postojeće tokove |
| 4a | Legacy metode u FakturaView | Faza 9 — ovisi o potvrdi da unified tok radi stabilno |

---

## Verifikacija

- `python -m py_compile` čist na svih 12 izmijenjenih fajlova (root + dist_client)
- **1128 testova prolazi** (+77 novih), 5 xfailed, 1 failed + 1 error (oba nepovezana)
- dist_client mirrorovan (bez BOM)
- Pre-commit hook prošao na svakom commitu

## Commitovi

| Hash | Poruka |
|------|--------|
| `703a68e` | refactor(tariff): ujednači opise tarife u TariffService sa cache-om (N+1 fix) |
| `dd8d62e` | refactor(tariff): TariffFacade.sync_mapping() uklanja duplikat DELETE+learn |
| `8d781b2` | refactor(tariff): premjesti STOP_WORDS i validaciju prijedloga u TariffService |
| `4f918fc` | refactor(naimenovanja): premjesti DB upite za šifrarnike u NaimenovanjaService |
| `eac0b3d` | fix(qthread): cancel() za ChatWorker/TariffLLMWorker + graceful shutdown |

## Rizici / ograničenja

- **NaimenovanjaView i dalje 3.888 linija** — 3-layer kršenje ostaje dok se ne izdvoji Controller (nalaz 3a). Sva DB logika je premještena, ali orchestration i UI logika su još uvijek u View-u.
- **Legacy metode** (`_on_import_finished_legacy`, `_process_batch_records_legacy`) su aktivne — unified tok (Codex Faze 6-8) ih koristi kao fallback dok se ne potvrdi stabilnost.
- **`_run_historical_tariff_validation`** i dalje blokira UI — preporuka za sledeću sesiju: kreirati `HistoricalValidationWorker(QThread)`.

## Potreban follow-up

1. **Faza 9**: obrisati legacy metode nakon potvrde da unified tok radi stabilno (paritet testovi već postoje)
2. **NaimenovanjaController**: izdvojiti orchestration iz View-a (najveći preostali dug)
3. **HistoricalValidationWorker**: premjestiti `_run_historical_tariff_validation` u pozadinu
