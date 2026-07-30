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
- `docs/CONTEXT.md`

## Status izvora

- `docs/CONTEXT.md` §101 — aktivno; prethodna faza je uvela isti javni-adapter obrazac za kreiranje naimenovanja.
- `project_rooms/2026-07-29_faktura-stvarna-3layer-migracija-i-ciscenje-plan.md` — aktivan kao širi plan; ova faza je mali adapter rez za mase.

## GitNexus impact

- `FakturaView._on_calculate_masses` — LOW, bez direktnih indeksiranih pozivalaca.
- Ručna `rg` provjera našla je dinamički Agent poziv u `_puna_auto_pipeline` i test očekivanja u `test_puna_auto_pipeline.py`.

## Šta je urađeno

- Uveden javni `calculate_masses(auto: bool = False) -> bool` adapter na `FakturaTab`.
- Uveden kompatibilni javni adapter istog imena na `FakturaView`.
- `_puna_auto_pipeline` prvo koristi `fw.calculate_masses(auto=True)`.
- Privatni `_on_calculate_masses(auto=True)` ostaje fallback.
- Testovi Puna automatizacija pipeline-a sada potvrđuju da se koristi javni `calculate_masses(auto=True)`, a ne privatni `_on_calculate_masses`.
- Root i `dist_client` su usklađeni.

## Zašto je urađeno

Nakon Faza 5 i 6 Agent više ne zavisi od privatnih metoda za validaciju i kreiranje naimenovanja, ali je i dalje direktno pozivao privatni izračun masa. Ovaj rez uvodi javni API za tu fazu bez promjene poslovnog ponašanja.

## Kako je urađeno

`FakturaTab.calculate_masses(auto=True)` i `FakturaView.calculate_masses(auto=True)` delegiraju na postojeći `_on_calculate_masses(auto=True)`. Agent pipeline preferira javni adapter, a fallback na privatni naziv ostaje radi kompatibilnosti.

## Šta nije dirano

- Nije mijenjana unutrašnja logika `_on_calculate_masses`.
- Nisu premještani toolbar parsing, per-invoice težine, fallback guard, reload tabele ni dirty/data_changed semantika.
- Ručno dugme `Izračunaj mase` nije prespojeno na signal.
- Nisu dirani auto-popuna tarifa, import, XML ni export.
- Nepovezane lokalne izmjene u worktree-u nisu dirane.

## Verifikacija

- `python -m pytest tests/unit/test_faktura_controller.py tests/unit/test_puna_auto_pipeline.py -q` — 40/40 passed.
- Širi Faktura/Agent/mase skup bez integration testova — 131/131 passed, 2 deselected.

## Pronađeni problemi

Nije pronađena nova regresija.

## Konflikti / kontradiktorni izvori

Veliki plan predviđa potpunu migraciju masa u zasebnoj fazi. Važeća odluka za ovaj zadatak: javni adapter je uveden sada, ali stvarna migracija masa ostaje poseban kasniji rez.

## Commitovi

| Hash | Poruka |
| --- | --- |
| 7716d81 | `refactor(faktura): uvedi javni calculate masses api za agent` |

## Rizici / ograničenja

Ovo je adapter faza. Agent više koristi javno ime, ali stvarni poslovni vlasnik za auto izračun masa je i dalje legacy View tok. Privatni fallback se ne smije ukloniti dok se ručni i Agent tokovi paritetno ne prebace na Controller/Service.

## Potreban follow-up

- Posebno migrirati ručni `Izračunaj mase` signal i Controller/Service rezultat.
- Nastaviti adaptere za preostale privatne Agent pozive, najvjerovatnije auto-popunu tarifa.
- U kasnijoj fazi prebaciti Agent da dobija `FakturaTab`, ne direktno `FakturaView`.

## Potrebna korisnička potvrda

Pokrenuti Punu automatizaciju na stvarnoj fakturi gdje bar jedna stavka nema masu i potvrditi da se mase izračunaju kao ranije.
