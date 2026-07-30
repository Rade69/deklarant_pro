# Faktura Cleanup Faza A — characterization testovi

## Datum

2026-07-30

## Agent

Codex

## Scope

- `tests/unit/test_faktura_controller.py`
- `tests/unit/test_puna_auto_pipeline.py`
- `docs/context/history.md`

## Status izvora

- `docs/CONTEXT.md` — aktivan evergreen kontekst, pročitan prije rada.
- `project_rooms/2026-07-30_faktura-cleanup-migracioni-manifest.md` — aktivan manifest koji definiše Cleanup Fazu A.
- `tests/unit/test_faktura_controller.py` i `tests/unit/test_puna_auto_pipeline.py` — postojeći characterization testovi prošireni umjesto dodavanja paralelne test strukture.

## GitNexus impact

Produkciona funkcija nije mijenjana. Pre-change impact za `_puna_auto_pipeline` je MEDIUM zbog 14 direktnih test pozivalaca, 0 affected execution flow-ova. Izmjene su test-only, pa je stvarni runtime rizik nizak.

`gitnexus_detect_changes` prije commita: LOW, 0 affected execution flow-ova. Detektovan je i postojeći šum iz nepovezanih lokalnih fajlova.

## Šta je urađeno

- Dodan je characterization test koji zaključava da Agent pipeline koristi javne metode za sve četiri faze prije privatnih fallback-a:
  - `calculate_masses(auto=True)`
  - `auto_fill(auto=True)`
  - `validate(auto=True)`
  - `create_naimenovanja(auto=True)`
- Postojeći legacy fallback test ostaje aktivan i potvrđuje da fallback nije prerano uklonjen.
- Root/dist_client paritet test proširen je na `gui/tabs/agent/services/import_pipeline_service.py`.
- Paritet test sada normalizuje samo UTF-8 BOM razliku prije poređenja teksta.

## Zašto je urađeno

Manifest traži da se prije dublje migracije i bilo kakvog brisanja zaključa trenutno ponašanje. Najvažnija invarijanta za Agent pipeline je da javni API ima prednost, ali da privatni fallback ostaje živ dok svi runtime putevi nisu potvrđeni.

BOM normalizacija je dodana zato što root `import_pipeline_service.py` sadrži BOM, a `dist_client` kopija ne. To nije semantička razlika i ne treba mijenjati encoding fajlova samo radi testa.

## Kako je urađeno

U `test_puna_auto_pipeline.py` dodat je test javnog API redoslijeda. U `test_faktura_controller.py` paritetna parametrize lista dobila je Agent `import_pipeline_service.py`, a poređenje teksta radi `.lstrip("\ufeff")` prije newline normalizacije.

## Šta nije dirano

- Nije mijenjan produkcioni kod.
- Nisu mijenjani `gui/` ni `dist_client/gui/` runtime fajlovi.
- Nije uklonjen nijedan fallback.
- Nije diran Agent pipeline.
- Nije diran XML/import/export tok.
- Nisu dirane nepovezane lokalne izmjene u radnom stablu.

## Verifikacija

- `python -m py_compile tests/unit/test_faktura_controller.py tests/unit/test_puna_auto_pipeline.py` — OK
- `python -m pytest tests/unit/test_faktura_controller.py tests/unit/test_puna_auto_pipeline.py -q` — 50 passed
- Širi Faktura/Agent skup uz `-m "not integration"` — 141 passed, 2 deselected

## Pronađeni problemi

Prvi prolaz paritet testa je pokazao BOM-only razliku između root i `dist_client` Agent pipeline fajla. To je tretirano kao encoding razlika, ne kao stvarni paritet bug. Test sada normalizuje BOM bez mijenjanja fajlova.

## Konflikti / kontradiktorni izvori

Nema konflikta. Manifest je tretiran kao važeći plan; kod/testovi su korišćeni kao izvor stvarnog stanja.

Potrebna korisnička potvrda: NE.

## Commitovi

| Hash | Poruka |
| --- | --- |
| pending | `test(faktura): zakljucaj cleanup faza a javne ulaze` |

## Rizici / ograničenja

Cleanup Faza A ne dokazuje poslovni paritet dublje migracije; ona samo zaključava trenutni javni/fallback ugovor. Sljedeće faze i dalje moraju imati zasebne paritet testove po funkcionalnosti.

## Potreban follow-up

Sljedeći korak po manifestu je Cleanup Faza B: priprema migracije `Izračunaj mase` u Service/Controller, vjerovatno prvo kroz request/result modele i characterization testove postojeće per-invoice raspodjele.

## Potrebna korisnička potvrda

Nema obavezne potvrde za test-only fazu.
