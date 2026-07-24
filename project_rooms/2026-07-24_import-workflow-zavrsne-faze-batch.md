# Jedinstveni import workflow — završne faze batch/runtime

## Cilj

Završiti preostali aktivni ulaz u zajednički import workflow: ručni grupni import na Faktura tabu.

## Pogođeno

- `FakturaView._process_batch_records` — GitNexus impact MEDIUM, direktni pozivaoci su `_on_batch_done` i testovi.
- `dist_client` kopija iste metode — GitNexus impact LOW.
- `_expected_import_partners` — GitNexus impact LOW.

## Plan

1. Prebaciti batch record-e na `ImportCandidate`.
2. Pripremiti `ImportPlan` za sve ispravne fakture u batchu.
3. Koristiti postojeće UI odluke za partnere, valutu i PE2/PE3/EUR1.
4. Primijeniti plan preko `apply_import_plan`.
5. Ostaviti legacy fallback za Assembly/Master-list režim.
6. Mirror-ovati samo potvrđene runtime promjene u `dist_client`.
7. Ažurirati testove, `docs/CONTEXT.md` i agent report.

## Šta NE dirati

- Parser worker i QThread lifecycle.
- Assembly/Master-list posebni režim.
- Stil/UI razlike u `dist_client/faktura_view.py`.
- Poznata dva nevezana pada punog test suite-a.

## Konflikti

Kanonski plan traži uklanjanje duplirane logike tek kad su svi aktivni pozivaoci migrirani. Legacy batch i legacy single import nisu uklonjeni jer i dalje štite Assembly/Master-list fallback.
