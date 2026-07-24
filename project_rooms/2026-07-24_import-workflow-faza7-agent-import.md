# Jedinstveni import workflow — Faza 7 Agent import

## Cilj

Povezati Agent import na isti neutralni import workflow koji koristi ručni pojedinačni import nakon Faze 6.

## Pogođeno

- `gui/tabs/agent/agent_controller.py::AgentController._on_all_completed`
- `dist_client/gui/tabs/agent/agent_controller.py::AgentController._on_all_completed`
- testovi pariteta Agent/ručni import

GitNexus impact za root metodu je MEDIUM: pogođeni su prvenstveno postojeći unit testovi Agent import grane, bez registrovanih runtime execution-flow veza u indeksu.

## Plan

1. Pretvoriti `FileItem` rezultate u `ImportCandidate`.
2. Pozvati `prepare_import()` sa postojećim invoice ključevima i očekivanim partnerima.
3. Prikupiti partner/valuta/origin odluke kroz postojeće FakturaView dijaloge.
4. Primijeniti `apply_import_plan()` na draft.
5. Ostaviti Agent-specifičan chat rezime, prebacivanje na Faktura tab i historijsku provjeru.
6. Mirror u `dist_client`.

## Šta NE dirati

- Analiza mod Agent-a.
- Puna automatizacija poslije uvoza.
- Parseri i `ProcessingWorker`.
- Ručni import koji je završen u Fazi 6.

## Konflikti

Stari parity testovi su dokumentovali razlike između ručnog i Agent uvoza. Nakon faze 7 ti testovi se tretiraju kao zastarjeli i ažuriraju se da dokazuju paritet kroz ponašanje, ne kroz stare interne helper pozive.
