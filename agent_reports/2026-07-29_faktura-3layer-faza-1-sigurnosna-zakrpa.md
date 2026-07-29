## Datum

2026-07-29

## Agent

Codex

## Scope

- `gui/tabs/faktura_controller.py`
- `dist_client/gui/tabs/faktura_controller.py`
- `tests/unit/test_faktura_controller.py`
- `docs/CONTEXT.md`

## Status izvora

- `docs/CONTEXT.md` §91 — aktivno pravilo: Faktura Controller signali su pasivna infrastruktura.
- `docs/CONTEXT.md` §93 — aktivno pravilo: dedup ledger koristi `draft_uid`.
- `docs/CONTEXT.md` §95 — aktivna Faza 0 baseline kapija.
- `project_rooms/2026-07-27_faktura-3layer-refaktor-detaljni-plan.md` — aktivan fazni plan.

## GitNexus impact

`FakturaController.create_naimenovanja` u root controlleru: LOW, 0 direktnih pozivalaca u statičkom grafu. Ručna provjera pokazuje pasivni signalni handler u `FakturaTab`, pa je promjena tretirana kao sigurnosna zakrpa za buduće aktiviranje tog puta.

## Šta je urađeno

- `FakturaController.create_naimenovanja()` sada prosljeđuje `draft_uid` u `TariffFacade.learn_from_draft()`.
- Ista izmjena ogledana je u `dist_client`.
- Dodan test koji zaključava Controller → TariffFacade ugovor.

## Zašto je urađeno

Aktivni stari View handler već čuva ledger invarijantu, ali pasivni Controller put nije. Da se kasnije ne aktivira signal koji zaobilazi dedup ledger, Faza 1 mora biti zatvorena istim ugovorom.

## Kako je urađeno

Minimalna izmjena u controlleru koristi postojeći `draft` argument i čita `draft_uid` bez uvođenja novog stanja u controller. Test koristi `monkeypatch` za `CreateNaimenovanjaService` i `TariffFacade`, bez DB upisa.

## Šta nije dirano

- Nisu aktivirani novi signalni tokovi.
- Nije mijenjan `FakturaView`.
- Nije mijenjan import workflow.
- Nije rađen cleanup starog koda.
- Nisu dirane nepovezane postojeće izmjene u worktree-u.

## Verifikacija

`python -m pytest tests/unit/test_faktura_controller.py tests/unit/test_faktura_characterization.py tests/unit/test_tariff_learning_ledger.py -q` — 40 passed.

## Pronađeni problemi

Prije zakrpe Controller put za kreiranje naimenovanja nije prosljeđivao `draft_uid`, iako aktivni View put jeste. To nije trenutna produkciona regresija, ali jeste opasan gap za naredne faze.

## Konflikti / kontradiktorni izvori

Nema konflikta: §91 kaže da je signalni tok pasivan, a ova zakrpa ga samo čini bezbjednim ako bude aktiviran kasnije.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `6230522` | `fix(faktura): sacuvaj ledger ugovor u controlleru` |

## Rizici / ograničenja

Faza 1 i dalje ne znači da je Faktura migrirana u 3-layer. Ona samo zatvara composition root i pasivni controller ugovor bez promjene aktivnog ponašanja.

## Potreban follow-up

Sljedeća faza je Faza 2: čiste kalkulacije i read-only lookupi, uz oprez da se ne aktivira nijedan signalni tok prije vertikalnog reza.

## Potrebna korisnička potvrda

Nije potrebna za ovu zakrpu; korisnička E2E potvrda postaje važna prije aktivnih vertikalnih rezova.
