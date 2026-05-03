# Style Refactor - Faza Plan

## Faza 1 - Inventar i stabilizacija kriticnih konflikata

- `TASK-001`: Inventar svih stil izvora i konflikata.
- `TASK-002`: Dropdown strelice - uklanjanje fallback artefakata (kvadrat/minus).

## Faza 2 - Uklanjanje haosa iz inline sloja

- `TASK-003`: Audit i klasifikacija svih `setStyleSheet(...)` poziva.
- `TASK-004`: Migracija baznih stilova iz inline u QSS (samo Naimenovanja tab).

## Faza 3 - Konsolidacija i pravila

- `TASK-005`: Uvesti style governance dokument + linter skriptu za anti-patterne.

## Gate kriteriji po fazi

- Nema vizuelne regresije u kriticnim tabovima (`Zaglavlje`, `Naimenovanja`, `Faktura`).
- Svaki task ima dokaz verifikacije.
- Diff ostaje u scope-u taska.
