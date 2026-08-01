## Datum

2026-08-01

## Agent

Codex

## Scope

- `gui/tabs/faktura_view.py`
- `dist_client/gui/tabs/faktura_view.py`
- `gui/tabs/agent/services/import_pipeline_service.py`
- `dist_client/gui/tabs/agent/services/import_pipeline_service.py`
- `tests/unit/test_faktura_controller.py`
- `tests/unit/test_faktura_view_validacija_selekcija.py`
- `dist_client/tests/unit/test_faktura_view_validacija_selekcija.py`
- `tests/unit/test_agent_controller_provjeri_nakon_uvoza.py`
- `dist_client/tests/unit/test_agent_controller_provjeri_nakon_uvoza.py`
- `tests/unit/test_faktura_view_provjeri_nakon_uvoza.py`
- `dist_client/tests/unit/test_faktura_view_provjeri_nakon_uvoza.py`
- `tests/unit/test_puna_auto_pipeline.py`
- `dist_client/tests/unit/test_puna_auto_pipeline.py`
- `docs/context/history.md`

## Status izvora

- `docs/CONTEXT.md` — aktivan; pročitan prije izmjene.
- `agent_reports/2026-08-01_faktura-cleanup-faza-e2-dead-code-audit.md` — aktivan; utvrdio da validaciona metoda nije za brisanje.
- `agent_reports/2026-08-01_faktura-cleanup-faza-e4-validation-adapter.md` — aktivan; E5 je predložen tek nakon prebacivanja Tab sloja na javni adapter.

## GitNexus impact

Korišćen je `gitnexus-refactoring` workflow. Direktni `impact` alat nije bio izložen, pa je urađen fallback:

- `rg` inventar svih `def validate`, `_on_validate_all`, `_validate_all_items` i `validate_requested` referenci
- ciljano čitanje aktivne validacione implementacije i selekcijskih testova
- `gitnexus_detect_changes` prije commita

Rizik je LOW/MEDIUM po prirodi simbola: metoda je aktivna, ali javni API nije promijenjen i svi poznati direktni test pozivaoci su ažurirani.

## Reprodukcija prije izmjene

Ovo je cleanup/refactor. Prije izmjene je potvrđeno da:

- `FakturaView.validate()` delegira na `_on_validate_all`
- selekcijski testovi direktno pozivaju `_on_validate_all`
- produkcioni Tab sloj od E4 više ne poziva `_on_validate_all` direktno

## Šta je urađeno

- `FakturaView._on_validate_all` preimenovan u `FakturaView._validate_all_items`.
- `FakturaView.validate()` sada delegira na `_validate_all_items`.
- Ista produkciona izmjena preslikana u `dist_client`.
- Selekcijski testovi u root/dist kopiji prebačeni na novo interno ime.
- Test i komentari koji opisuju javni auto-validacioni tok ažurirani sa starog `_on_validate_all` naziva na `validate(auto=True)`.
- Dopunjen `docs/context/history.md`.

## Zašto je urađeno

`_on_validate_all` ime je izgledalo kao GUI event handler, iako je nakon E4 ostalo samo interna implementacija javnog `validate()` adaptera. Novo ime jasnije govori šta metoda radi i smanjuje konfuziju za sljedeće faze cleanup-a.

## Kako je urađeno

Preimenovanje je urađeno minimalno i bez mijenjanja tijela metode. Javni ugovor ostaje `validate(auto: bool) -> tuple[bool, int, int]`.

## Šta nije dirano

- Nije mijenjana logika validacije.
- Nije mijenjan `validate_requested` signalni tok.
- Nije mijenjana istorijska tarifna validacija ni čekanje workera.
- Nije mijenjan Agent pipeline osim komentara.
- Nije diran legacy `_on_validate_all` stub u pipeline testu jer namjerno simulira staru klasu bez javnog API-ja.
- Nisu dirane postojeće tuđe/WIP izmjene u `dist_client/ui/...`.

## Verifikacija

- `python -m py_compile gui/tabs/faktura_view.py dist_client/gui/tabs/faktura_view.py gui/tabs/agent/services/import_pipeline_service.py dist_client/gui/tabs/agent/services/import_pipeline_service.py tests/unit/test_faktura_controller.py tests/unit/test_faktura_view_validacija_selekcija.py tests/unit/test_puna_auto_pipeline.py dist_client/tests/unit/test_faktura_view_validacija_selekcija.py dist_client/tests/unit/test_puna_auto_pipeline.py`
- `python -m pytest tests/unit/test_faktura_controller.py tests/unit/test_faktura_view_validacija_selekcija.py tests/unit/test_puna_auto_pipeline.py tests/unit/test_agent_controller_provjeri_nakon_uvoza.py tests/unit/test_faktura_view_provjeri_nakon_uvoza.py -q` → 64/64 passed
- `python -m pytest dist_client/tests/unit/test_faktura_view_validacija_selekcija.py dist_client/tests/unit/test_puna_auto_pipeline.py dist_client/tests/unit/test_agent_controller_provjeri_nakon_uvoza.py dist_client/tests/unit/test_faktura_view_provjeri_nakon_uvoza.py -q` → 30/30 passed
- `rg` potvrda: nema `def _on_validate_all` u root/dist produkcionom kodu.

## Nezavisna provjera

Nije rađena posebna checker sesija jer je tijelo metode ostalo isto i testovi direktnih pozivalaca prolaze. Za sljedeću fazu koja dira tijelo validacije potreban je poseban review.

## Pronađeni problemi

Preostale `_on_validate_all` reference postoje samo u legacy pipeline test stubu/assertima. To nije produkcioni dug nego namjeran test dokaza da se private fallback ne poziva kad javni API ne postoji.

## Odbačene opcije

- Odbačeno: potpuno ukloniti direktne selekcijske testove interne metode. Razlog: oni su jeftina i precizna zaštita za scoped validation behavior.
- Odbačeno: mijenjati tijelo validacije u E5. Razlog: E5 je rename-only cleanup.

## Konflikti / kontradiktorni izvori

Nema konflikta u produkcionom kodu. E2 tvrdnja da metoda nije za brisanje je zadržana: metoda nije obrisana, samo je preimenovana.

## Commitovi

| Hash | Poruka |
| --- | --- |
| pending | `refactor(faktura): preimenuj internu validaciju` |

## Kontekst korišćen

- `docs/CONTEXT.md` pročitan u cijelosti.
- `gitnexus-refactoring` skill pročitan u cijelosti.
- `docs/context/history.md` nije čitan cijeli; dodat je append-only zapis.
- `faktura_view.py`, selekcijski testovi i pipeline komentari čitani su ciljano.

## Rizici / ograničenja

Rename ne mijenja ponašanje, ali metoda je aktivna i ostaje interna zaštitna tačka za validaciju. Nije rađen ručni GUI E2E.

## Potreban follow-up

Sljedeći cleanup može biti E6: audit preostalih private metoda u Faktura View-u koje su još aktivni implementation path (`_on_create_naimenovanja`, `_on_import_finished_legacy`) i odluka da li ih samo dokumentovati ili pripremiti adapter-preimenovanje.

## Potrebna korisnička potvrda

Za brisanje ili preimenovanje `_on_create_naimenovanja` treba posebna potvrda i audit, jer ga još koriste javni adapter, PDF export helper i characterization test.
