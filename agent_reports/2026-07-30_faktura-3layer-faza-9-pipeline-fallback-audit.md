# Faktura 3-layer Faza 9 — pipeline fallback audit

## Datum

2026-07-30

## Agent

Codex

## Scope

- `gui/tabs/agent/services/import_pipeline_service.py`
- `dist_client/gui/tabs/agent/services/import_pipeline_service.py`
- `tests/unit/test_puna_auto_pipeline.py`

## Status izvora

- `docs/CONTEXT.md` — aktivan evergreen kontekst, pročitan prije rada.
- `docs/context/history.md` — aktivan dated log, korišćen ciljano kroz prethodne Faze 5-8 i `Tail`, nije čitan u cijelosti.
- GitNexus indeks — ažuriran poslije Faze 8; `query` za ovaj konkretan tekstualni obrazac vratio upozorenje da FTS indeks nedostaje, pa je dopunjen `rg` auditom.

## GitNexus impact

Produkcioni simbol nije mijenjan u ovoj fazi. GitNexus kontekst za `_puna_auto_pipeline` pokazao je dvije kopije istog simbola (`gui/` i `dist_client/`). `rg` audit aktivnog pipeline-a potvrdio je da su privatni Faktura pozivi (`_on_calculate_masses`, `_on_auto_fill`, `_on_validate_all`, `_on_create_naimenovanja`) ostali samo kao fallback nakon javnih API-ja.

Rizik izmjene: nizak — dodan je samo zaštitni unit test.

## Šta je urađeno

- Pregledan je `_puna_auto_pipeline` i njegovi pozivi prema Faktura sloju.
- Potvrđeno je da pipeline prvo pokušava javne metode:
  - `calculate_masses(auto=True)`
  - `auto_fill(auto=True)`
  - `validate(auto=True)`
  - `create_naimenovanja(auto=True)`
- Potvrđeno je da privatni `_on_*` pozivi više nisu primarni put, nego kompatibilni fallback.
- Dodat je test koji simulira legacy Faktura objekt bez javnih metoda i potvrđuje da fallback i dalje radi.

## Zašto je urađeno

Faze 5-8 su uklonile glavnu Agent zavisnost od privatnih Faktura View metoda, ali nije bilo eksplicitne stabilizacione kapije koja dokazuje oba uslova: javni API je preferiran, a fallback se još ne smije obrisati jer može pokriti slučajeve gdje Agent dobije stariji/siromašniji objekt.

## Kako je urađeno

U `tests/unit/test_puna_auto_pipeline.py` dodat je `TestJavniApiIFallback::test_legacy_fallback_ostaje_ziv_kad_javni_api_ne_postoji`. Test koristi minimalni legacy objekt koji ima samo privatne `_on_*` metode i nema javne adaptere. Pipeline mora završiti uspješno i pozvati sve fallback metode sa `auto=True`.

## Šta nije dirano

- Nije mijenjan `import_pipeline_service.py`.
- Nije mijenjan `FakturaView` legacy tok.
- Nije uklonjen nijedan privatni fallback.
- Nije prespajan ručni toolbar tok.
- Nije diran XML/export/import tok.
- Nisu dirane postojeće nepovezane lokalne izmjene u radnom stablu.

## Verifikacija

- `python -m py_compile tests/unit/test_puna_auto_pipeline.py` — OK
- `python -m pytest tests/unit/test_puna_auto_pipeline.py tests/unit/test_faktura_controller.py -q` — 43 passed
- Širi Faktura/Agent skup uz `-m "not integration"` — 134 passed, 2 deselected

## Pronađeni problemi

Nema novog funkcionalnog buga. Audit je pokazao da privatni `_on_*` pozivi u Agent pipeline-u još postoje, ali samo kao fallback. To nije regresija; to je namjerna kompatibilnost dok se ne potvrdi da svi runtime putevi uvijek dobijaju `FakturaTab`/`FakturaView` sa javnim adapterima.

## Konflikti / kontradiktorni izvori

GitNexus `query` nije vratio procese za tekstualnu pretragu i prijavio je degradiran FTS indeks. Kao važeći izvor za konkretan audit tretiran je direktni `rg` pregled fajlova i postojeći testovi, uz GitNexus kontekst za disambiguaciju simbola.

Potrebna korisnička potvrda: NE.

## Commitovi

| Hash | Poruka |
| --- | --- |
| 57dc959 | `test(faktura): pokrij legacy fallback agent pipelinea` |

## Rizici / ograničenja

Ovo nije cleanup faza. Fallback metode su namjerno ostavljene jer njihovo brisanje zahtijeva poseban manifest pozivalaca i korisnički E2E test. Sljedeća faza može biti ili aktiviranje ručnog auto-fill signala kroz Controller, ili zaseban cleanup plan kada se potvrdi da više nema runtime zavisnosti od privatnih metoda.

## Potreban follow-up

- Odlučiti da li Faza 10 ide u smjeru ručnog toolbar toka (`Auto-popuni`, `Izračunaj mase`, `Kreiraj Naimenovanja`) kroz signale ili u smjeru cleanup manifesta.
- Ne uklanjati privatne fallback-e prije posebne cleanup grane.

## Potrebna korisnička potvrda

Nema obavezne potvrde za ovu fazu. Za narednu fazu korisnik treba izabrati: nastavak migracije ručnih dugmadi ili priprema cleanup plana.
