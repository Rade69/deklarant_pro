## Datum

2026-08-01

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

- `docs/CONTEXT.md` — aktivan; pročitan prije izmjene.
- `agent_reports/2026-08-01_faktura-cleanup-faza-e2-dead-code-audit.md` — aktivan; `_on_create_naimenovanja` i `_on_import_finished_legacy` nisu bili kandidati za brisanje.
- `agent_reports/2026-08-01_faktura-cleanup-faza-e5-validate-rename.md` — aktivan; predložio E6 audit preostalih aktivnih private metoda.

## GitNexus impact

Korišćen je `gitnexus-refactoring` workflow. Direktni `impact` alat nije bio izložen, pa je urađen fallback:

- `rg` inventar `_on_create_naimenovanja`, `_on_import_finished_legacy`, `create_naimenovanja()`, `_on_import_finished()` i relevantnih testova
- ciljano čitanje `FakturaTab.create_naimenovanja`, `FakturaView.create_naimenovanja`, `_on_export_pdf` i testova
- `gitnexus_detect_changes` prije commita

Rizik je LOW: promijenjeni su samo adapter pozivi; tijelo kreiranja naimenovanja i import legacy put nisu mijenjani.

## Reprodukcija prije izmjene

Ovo je cleanup/refactor. Prije izmjene je potvrđeno:

- `FakturaTab.create_naimenovanja(auto=True)` direktno poziva `self.view._on_create_naimenovanja(auto=True)`
- `_on_export_pdf` direktno poziva `self._on_create_naimenovanja()`
- `FakturaView.create_naimenovanja()` već postoji kao javni adapter
- `_on_import_finished` još delegira na `_on_import_finished_legacy`

## Šta je urađeno

- `FakturaTab.create_naimenovanja()` sada koristi `self.view.create_naimenovanja(auto=auto)`.
- `_on_export_pdf` fallback sada koristi `self.create_naimenovanja()`.
- Ista izmjena preslikana u `dist_client`.
- Test `test_faktura_tab_create_naimenovanja_uses_view_adapter` sada monkeypatchuje javni `view.create_naimenovanja`.
- Dopunjen `docs/context/history.md`.

## Zašto je urađeno

Ovo uklanja dvije nepotrebne direktne zavisnosti od private View implementacije, a ne dira osjetljivu poslovnu logiku grupiranja naimenovanja.

## Kako je urađeno

Minimalna zamjena poziva:

- `self.view._on_create_naimenovanja(auto=auto)` → `self.view.create_naimenovanja(auto=auto)`
- `self._on_create_naimenovanja()` → `self.create_naimenovanja()`

## Šta nije dirano

- Nije brisan niti preimenovan `FakturaView._on_create_naimenovanja`.
- Nije dirana logika `CreateNaimenovanjaWorkflowService`.
- Nije diran `CreateNaimenovanjaService.create_smart_group()`.
- Nije diran `_on_import_finished_legacy`.
- Nije diran unified import workflow.
- Nisu dirane postojeće tuđe/WIP izmjene u `dist_client/ui/...`.

## Verifikacija

- `python -m py_compile gui/tabs/faktura_tab.py dist_client/gui/tabs/faktura_tab.py gui/tabs/faktura_view.py dist_client/gui/tabs/faktura_view.py tests/unit/test_faktura_controller.py`
- `python -m pytest tests/unit/test_faktura_controller.py tests/unit/test_faktura_characterization.py tests/unit/test_puna_auto_pipeline.py -q` → 64/64 passed
- `python -m pytest dist_client/tests/unit/test_puna_auto_pipeline.py -q` → 17/17 passed
- `rg` potvrda: produkcioni direktni pozivaoci iz Tab/PDF toka sada idu preko javnog adaptera.

## Nezavisna provjera

Nije rađena posebna checker sesija jer je izmjena LOW risk i ne dira tijelo poslovne logike. Za preimenovanje `_on_create_naimenovanja` preporučujem poseban audit/checker.

## Pronađeni problemi

`_on_import_finished_legacy` je i dalje aktivan fallback put. Nije kandidat za E6 izmjenu jer `_on_import_finished` delegira na njega kada unified manual import nije dostupan.

## Odbačene opcije

- Odbačeno: preimenovati `_on_create_naimenovanja` u E6. Razlog: to je aktivna implementacija sa characterization testom i treba poseban E7 audit.
- Odbačeno: dirati `_on_import_finished_legacy`. Razlog: još je stvarni fallback path i vezan je za import workflow parity testove.

## Konflikti / kontradiktorni izvori

Nema konflikata u produkcionom kodu. E2 nalaz da se ove metode ne smiju brisati ostaje važeći.

## Commitovi

| Hash | Poruka |
| --- | --- |
| 79fcce5 | `refactor(faktura): koristi javni adapter za kreiranje naimenovanja` |

## Kontekst korišćen

- `docs/CONTEXT.md` pročitan u cijelosti.
- `gitnexus-refactoring` skill pročitan u cijelosti.
- `docs/context/history.md` nije čitan cijeli; dodat je append-only zapis.
- `faktura_tab.py`, relevantni dijelovi `faktura_view.py` i testovi čitani su ciljano.

## Rizici / ograničenja

Nije rađen ručni GUI E2E PDF export. Testovi pokrivaju adapter i pipeline ponašanje, ali ne render PDF-a.

## Potreban follow-up

Sljedeći mogući korak je E7: zaseban audit da li `_on_create_naimenovanja` treba preimenovati u neutralnije interno ime, uz očuvanje karakterizacionog testa i PDF/Agent tokova.

## Potrebna korisnička potvrda

Za E7 treba potvrditi da je cilj samo preimenovanje interne metode, ne promjena logike kreiranja naimenovanja.
