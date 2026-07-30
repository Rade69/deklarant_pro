# Datum

2026-07-30

## Agent

Codex

## Scope

- `gui/tabs/faktura_tab.py`
- `gui/tabs/faktura_view.py`
- `gui/tabs/agent/services/import_pipeline_service.py`
- `dist_client/gui/tabs/faktura_tab.py`
- `dist_client/gui/tabs/faktura_view.py`
- `dist_client/gui/tabs/agent/services/import_pipeline_service.py`
- `tests/unit/test_faktura_controller.py`
- `tests/unit/test_puna_auto_pipeline.py`
- `docs/context/history.md`

## Status izvora

- `docs/CONTEXT.md` — aktivno; fazni zapisi idu u `docs/context/history.md`.
- `docs/context/history.md` §102 — aktivno; prethodna faza je uvela isti javni-adapter obrazac za mase.
- `project_rooms/2026-07-29_faktura-stvarna-3layer-migracija-i-ciscenje-plan.md` — aktivan kao širi plan; ova faza je mali adapter rez za auto-popunu tarifa.

## GitNexus impact

- `FakturaView._on_auto_fill` — LOW, bez direktnih indeksiranih pozivalaca.
- Ručna `rg` provjera našla je dinamički Agent poziv u `_puna_auto_pipeline` i test očekivanja u `test_puna_auto_pipeline.py`.

## Šta je urađeno

- Uveden javni `auto_fill(auto: bool = False)` adapter na `FakturaTab`.
- Uveden kompatibilni javni adapter istog imena na `FakturaView`.
- `_puna_auto_pipeline` prvo koristi `fw.auto_fill(auto=True)`.
- Privatni `_on_auto_fill(auto=True)` ostaje fallback.
- Testovi Puna automatizacija pipeline-a sada potvrđuju da se koristi javni `auto_fill(auto=True)`, a ne privatni `_on_auto_fill`.
- Root i `dist_client` su usklađeni.

## Zašto je urađeno

Nakon Faza 5-7 Agent više ne zavisi od privatnih metoda za validaciju, kreiranje naimenovanja i mase, ali je i dalje direktno pozivao privatnu auto-popunu tarifa. Ovaj rez uvodi javni API za tu fazu bez promjene poslovnog ponašanja i bez diranja tariff logike.

## Kako je urađeno

`FakturaTab.auto_fill(auto=True)` i `FakturaView.auto_fill(auto=True)` delegiraju na postojeći `_on_auto_fill(auto=True)`. Agent pipeline preferira javni adapter, a fallback na privatni naziv ostaje radi kompatibilnosti.

## Šta nije dirano

- Nije mijenjana unutrašnja logika `_on_auto_fill`.
- Nisu premještani undo snapshot, osnovna polja, TariffFacade preview/commit, selekcija, dijalozi ni render/status semantika.
- Ručno dugme `Auto-popuni` nije prespojeno na signal.
- Nisu dirani import, XML ni export.
- Nepovezane lokalne izmjene u worktree-u nisu dirane.

## Verifikacija

- `python -m pytest tests/unit/test_faktura_controller.py tests/unit/test_puna_auto_pipeline.py -q` — 42/42 passed.
- Širi Faktura/Agent/tariff skup bez integration testova — 133/133 passed, 2 deselected.

## Pronađeni problemi

Nije pronađena nova regresija.

## Konflikti / kontradiktorni izvori

Veliki plan predviđa potpunu migraciju auto-popune tarifa u zasebnoj fazi. Važeća odluka za ovaj zadatak: javni adapter je uveden sada, ali stvarna migracija auto-popune ostaje poseban kasniji rez.

## Commitovi

| Hash | Poruka |
| --- | --- |
| ccfb923 | `refactor(faktura): uvedi javni auto fill api za agent` |

## Rizici / ograničenja

Ovo je adapter faza. Agent više koristi javno ime, ali stvarni poslovni vlasnik za auto-popunu tarifa je i dalje legacy View tok. Privatni fallback se ne smije ukloniti dok se ručni i Agent tokovi paritetno ne prebace na Controller/Service.

## Potreban follow-up

- Posebno migrirati ručni `Auto-popuni` signal i Controller/Service rezultat.
- Nastaviti smanjivanje Agent/MainWindow zavisnosti od privatnih Faktura View metoda.
- U kasnijoj fazi prebaciti Agent da dobija `FakturaTab`, ne direktno `FakturaView`.

## Potrebna korisnička potvrda

Pokrenuti Punu automatizaciju na stvarnoj fakturi sa stavkama bez tarife i potvrditi da se auto-popuna ponaša kao ranije.
