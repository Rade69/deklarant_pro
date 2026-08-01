## Datum

2026-08-01

## Agent

Codex

## Scope

- `gui/tabs/agent/services/import_pipeline_service.py`
- `dist_client/gui/tabs/agent/services/import_pipeline_service.py`
- `tests/unit/test_puna_auto_pipeline.py`
- `docs/context/history.md`

## Status izvora

- `docs/CONTEXT.md` — aktivan; pročitan prije izmjene.
- `project_rooms/2026-07-30_faktura-cleanup-migracioni-manifest.md` — aktivan; Faza E je završno uklanjanje fallback-a nakon stabilizacije.
- `agent_reports/2026-08-01_faktura-cleanup-stabilizacija-poslije-d3.md` — aktivan; pokazao da javni API put radi i da private `_on_create_naimenovanja` još nije za brisanje.

## GitNexus impact

`gitnexus_context` za `FakturaView._on_create_naimenovanja` pokazao je da metoda još ima stvarne pozivaoce: javni adapter `create_naimenovanja`, `_on_export_pdf` i characterization test. Zbog toga nije brisana sama private View metoda. `impact` alat nije bio izložen u trenutnom tool setu; korišćen je `context` + `rg` inventar pozivalaca kao fallback, a prije commita se koristi `gitnexus_detect_changes(scope="staged")`.

## Reprodukcija prije izmjene

Ovo nije bugfix nego refactor/cleanup. Prije izmjene Agent `_puna_auto_pipeline` je imao četiri private fallback grane: `_on_calculate_masses`, `_on_auto_fill`, `_on_validate_all`, `_on_create_naimenovanja`. Stabilizacioni testovi su već pokazali da javni API put prolazi.

## Šta je urađeno

- Uklonjen Agent fallback na `_on_calculate_masses(auto=True)`.
- Uklonjen Agent fallback na `_on_auto_fill(auto=True)`.
- Uklonjen Agent fallback na `_on_validate_all(auto=True)`.
- Uklonjen Agent fallback na `_on_create_naimenovanja(auto=True)`.
- Test `test_puna_auto_pipeline.py` promijenjen da potvrdi novo pravilo: bez javnog API-ja pipeline kontrolisano staje i ne poziva private metode.
- Root i `dist_client` kopije Agent pipeline servisa su poravnate.

## Zašto je urađeno

Javni API adapteri su uvedeni i stabilizovani kroz ranije Faktura faze. Agent pipeline više ne treba da zaobilazi javni sloj i poziva private View handlere. Ovo smanjuje rizik da budući refaktor privatnih metoda nevidljivo pokvari punu automatizaciju.

## Kako je urađeno

U svakoj od četiri faze pipeline-a ostao je samo javni API poziv. Ako odgovarajući javni API ne postoji, faza vraća postojeći kontrolisani neuspjeh (`False`/`None`/`(-1, -1)`), pa pipeline staje ili daje warning prema postojećim pravilima.

## Šta nije dirano

- Nije brisan `FakturaView._on_create_naimenovanja`.
- Nisu brisani `_on_calculate_masses`, `_on_auto_fill` ni `_on_validate_all`.
- Nije mijenjan ručni toolbar signalni tok.
- Nije mijenjan PDF export helper koji još poziva create workflow.
- Nije mijenjan XML exporter.
- Nisu dirane tuđe WIP izmjene u working tree-u.

## Verifikacija

- `rg -n "hasattr\\(fw, '_on_|fw\\._on_(calculate_masses|auto_fill|validate_all|create_naimenovanja)\\(" gui/tabs/agent/services/import_pipeline_service.py dist_client/gui/tabs/agent/services/import_pipeline_service.py` → nema pogodaka
- `python -m py_compile gui/tabs/agent/services/import_pipeline_service.py dist_client/gui/tabs/agent/services/import_pipeline_service.py tests/unit/test_puna_auto_pipeline.py`
- `python -m pytest tests/unit/test_puna_auto_pipeline.py -q` → 17 passed
- `python -m pytest tests/unit/test_faktura_controller.py tests/unit/test_faktura_create_naimenovanja_workflow_service.py tests/unit/test_faktura_auto_fill_workflow_service.py tests/unit/test_faktura_mass_workflow_service.py tests/unit/test_puna_auto_pipeline.py tests/unit/test_faktura_validation_service_phase3.py tests/unit/test_inline_validation_gui.py tests/unit/test_faktura_service_phase2.py tests/unit/test_faktura_table_roundtrip.py tests/unit/test_faktura_characterization.py tests/unit/test_tariff_mapping_service.py tests/unit/test_faktura_view_validacija_selekcija.py tests/unit/test_faktura_view_provjeri_nakon_uvoza.py tests/unit/test_faktura_view_provjeri_selekcija.py tests/unit/test_agent_controller_provjeri_nakon_uvoza.py tests/unit/test_mass_calculator.py tests/unit/test_weight_guards.py tests/unit/asycuda_item_limit_test.py -q -m "not integration"` → 172 passed
- `python -m pytest tests/unit/test_asycuda_goods_description.py tests/unit/test_asycuda_helpers.py tests/unit/test_safe_xml.py tests/unit/test_parse_naimenovanja_xml.py tests/unit/test_agent_v2_wiring_fixes.py tests/integration/test_decision_xml_preflight.py tests/integration/test_decision_to_naimenovanja.py -q` → 126 passed
- `git diff --no-index -- gui/tabs/agent/services/import_pipeline_service.py dist_client/gui/tabs/agent/services/import_pipeline_service.py` → bez razlika

## Nezavisna provjera

Nije rađena posebna checker sesija. Promjena je uska i testirana, ali prije sljedećeg brisanja samih private View metoda preporučena je nezavisna provjera jer te metode još imaju direktne pozivaoce.

## Pronađeni problemi

- Prvo kopiranje u `dist_client` razotkrilo je BOM razliku na početku fajla. Root fajl već ima BOM, pa je `dist_client` vraćen na isti byte-level paritet umjesto konverzije encodinga.
- `_on_create_naimenovanja` nije mrtav kod; GitNexus context potvrđuje aktivne pozivaoce.

## Odbačene opcije

- Odbačeno: brisati private View metode u ovoj fazi. Razlog: još imaju pozivaoce i brisanje bi bilo behavior change šireg obima.
- Odbačeno: ostaviti legacy fallback test živ. Razlog: novi cilj Faze E je upravo zabrana ulaska Agent pipeline-a u private View handlere.

## Konflikti / kontradiktorni izvori

Nema kontradikcija. Manifest je tražio uklanjanje fallback-a tek nakon stabilizacije; ova faza uklanja samo Agent fallback, ne same legacy metode.

## Commitovi

| Hash | Poruka |
| --- | --- |
| 8f12fca | `refactor(agent): ukloni private fallback iz pune automatizacije` |

## Kontekst korišćen

- `docs/CONTEXT.md` pročitan u cijelosti.
- `docs/context/history.md` pregledan samo na kraju radi numeracije.
- `FakturaView._on_create_naimenovanja` mapiran kroz GitNexus context.
- Agent pipeline i relevantni test otvoreni samo u ciljanim isječcima.

## Rizici / ograničenja

Ako neki budući runtime objekat nema javne Faktura adaptere, puna automatizacija će sada kontrolisano stati umjesto da koristi private fallback. To je namjerno, ali zahtijeva da svi stvarni Faktura tab objekti nastave izlagati javne API-je.

## Potreban follow-up

Preostali cleanup je poseban rez: provjeriti da li se mogu ukloniti private View metode ili ih ostaviti kao interne implementacione detalje javnih adaptera. Ne brisati ih dok GitNexus/rg ne pokažu nula stvarnih pozivalaca.

## Potrebna korisnička potvrda

Korisnik treba ručno potvrditi punu automatizaciju na realnoj fakturi: mase → auto-fill → validacija → deklarantska potvrda → `Kreiraj Naimenovanja` → XML export smoke.
