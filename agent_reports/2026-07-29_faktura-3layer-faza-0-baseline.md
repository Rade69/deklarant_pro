## Datum

2026-07-29

## Agent

Codex

## Scope

- `tests/unit/test_faktura_table_roundtrip.py`
- `tests/unit/test_faktura_characterization.py`
- `docs/CONTEXT.md`

## Status izvora

- `docs/CONTEXT.md` — aktivan, pročitan prije rada.
- `project_rooms/2026-07-27_faktura-3layer-refaktor-detaljni-plan.md` — aktivan plan Faze 0, ali dio testova je već postojao i dopunjen je umjesto dupliranja.
- `docs/CONTEXT.md` §93 — aktivna ledger invarijanta nakon migracije 013.
- `docs/CONTEXT.md` §94 — aktivan okvir: migracija i cleanup su odvojeni checkpointi.

## GitNexus impact

- `FakturaView` (`gui/tabs/faktura_view.py`) — HIGH, 23 direktna / 32 ukupno pogođena simbola.
- `_load_data_from_draft` — HIGH, 17 direktnih / 43 ukupno pogođena simbola.
- `TariffMappingService.learn_with_dedup` — HIGH, 3 direktna / 12 ukupno pogođenih simbola.

Zaključak: produkcioni tok nije mijenjan; Faza 0 je ograničena na karakterizacione testove i dokumentaciju.

## Šta je urađeno

- Dopunjen table roundtrip test za sva editabilna Faktura polja.
- Zaključano postojeće ponašanje parsiranja EU brojeva iz tabele u draft.
- Zaključano čitanje čiste zemlje iz `Qt.UserRole`, da emoji prikaz ne uđe u podatak.
- Zaključano pravilo da se kodovi kraći od 8 cifara ne dopunjavaju nagađanjem.
- Dodan karakterizacioni test da `_on_create_naimenovanja(auto=True)` prosljeđuje `draft_uid` u `TariffFacade.learn_from_draft()`.

## Zašto je urađeno

Faktura 3-layer migracija ima HIGH blast radius i mora krenuti od stabilnog baseline-a. Posebno je važno da buduće premještanje logike ne prekine ledger deduplikaciju koja je tek aktivirana u produkciji.

## Kako je urađeno

Testovi koriste postojeći `FakturaView` i `DeclarationDraft` gdje je korisno imati stvarni Qt widget, a `MagicMock` samo za izolovanu orkestraciju `_on_create_naimenovanja` bez modala i bez DB upisa.

## Šta nije dirano

- Nije mijenjan `gui/tabs/faktura_view.py`.
- Nije mijenjan `services/tariff/tariff_mapping_service.py`.
- Nije mijenjan import workflow.
- Nije diran `dist_client`.
- Nisu dirane postojeće nepovezane izmjene u worktree-u.

## Verifikacija

- `python -m pytest tests/unit/test_faktura_table_roundtrip.py tests/unit/test_faktura_characterization.py tests/unit/test_tariff_learning_ledger.py -q` — 29 passed.
- `python -m pytest tests/unit/test_faktura_controller.py tests/unit/test_import_workflow_parity.py tests/unit/test_faktura_view_provjeri_nakon_uvoza.py tests/unit/test_faktura_view_validacija_selekcija.py tests/unit/test_faktura_view_provjeri_selekcija.py -q` — 59 passed.
- `python -m pytest tests/ -q` — 1517 passed, 85 skipped, 5 xfailed, 4 failed, 1 error.

## Pronađeni problemi

Postojeći `test_faktura_table_roundtrip.py` je ranije više provjeravao da objekti postoje nego stvarni roundtrip. To je dopunjeno bez izmjene produkcionog koda.

Puna suite i dalje ima nepovezane baseline probleme: `test_model_benchmark.py::test_model` traži nepostojeći fixture `model_name`, tool schema testovi očekuju stari broj/nazive alata, `test_xml_parser_fix.py` koristi hardkodovanu `/home/radovan/Documents/Računi/1.xml` putanju, a `test_penetration.py::TestKillSwitch::test_check_agent_v2_default_is_false` pada jer lokalni `.env` ima `DEBUG=release`, što nije Pydantic boolean.

## Konflikti / kontradiktorni izvori

Nema novih konflikata. Worktree je već imao nepovezane izmjene prije ovog rada; ostavljene su netaknute.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `194a793` | `test(faktura): zakljucaj faza 0 baseline` |

## Rizici / ograničenja

Faza 0 još nije potpuna zamjena za ručni E2E test stvarne fakture. Ona samo zaključava nekoliko najvažnijih ponašanja prije refaktora. Puna suite nije zelena zbog pre-postojećih nepovezanih baseline padova.

## Potreban follow-up

- Očistiti ili formalno markirati pre-postojeće baseline padove pune suite, odvojeno od Faktura refaktora.
- U narednoj fazi ne dirati cleanup; prvo Faza 1 composition root bez promjene toka.

## Potrebna korisnička potvrda

Nakon Faze 0 korisnik treba potvrditi osnovni ručni tok u aplikaciji prije prelaska na aktivne vertikalne rezove, ako želi maksimalno konzervativan ritam.
