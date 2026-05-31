# NaimenovanjaView package helper refactor

Datum: 2026-05-12
Agent: Codex

## Zadatak

Po istim pravilima kao prethodni refaktori, uraditi siguran refaktor `gui/tabs/naimenovanja_view.py`, bez promjene javnog interfejsa i bez promjene ponašanja.

## Analiza prije izmjena

1. Komplikovano:
   - `NaimenovanjaView` je veliki PySide view koji u jednoj klasi drži UI binding, signal handlere, auto-popunu, tarifni lookup i dokument pravila.
   - `_load_current_item` je naročito osjetljiv jer radi više nezavisnih poslova u jednom toku.

2. Duplirano:
   - Postavljanje naziva pakovanja iz šifre bilo je ponovljeno u `_on_package_code_changed`, `_update_package_naziv` i `_load_current_item`.

3. Rizično dirati:
   - Rb.40/Rb.44/PE pravila.
   - Tarifni lookup i fallback SQLite/PostgreSQL tokovi.
   - XML import i sinhronizacija sa izvorom.
   - `le_r31_trg_naziv` pravilo o svim komercijalnim nazivima.

4. Plan:
   - Izdvojiti samo privatni helper za naziv pakovanja.
   - Zadržati postojeće signal handler uslove i model update ponašanje.
   - Ne mijenjati javni interfejs.
   - Pokrenuti compile, diff check, testove i GitNexus detect_changes.

## GitNexus

- Impact `NaimenovanjaView`: LOW, 0 direct, 0 affected processes.
- Impact `_on_package_code_changed`: LOW, 0 affected processes.
- Impact `_update_package_naziv`: LOW, 0 affected processes.
- Impact `_load_current_item`: LOW, 0 affected processes.
- Detect changes: 1 fajl, risk low, affected processes 0.

## Izmjene

- Dodan `_set_package_name_from_code`.
- `_on_package_code_changed` koristi helper sa `clear_missing=False`, čime je sačuvano staro ponašanje da ne briše UI tekst kada nema naziva u katalogu.
- `_update_package_naziv` koristi isti helper.
- `_load_current_item` koristi helper sa `update_model=False`, čime učitavanje forme ne prepisuje model.

## Provjere

- `python -m py_compile gui/tabs/naimenovanja_view.py` — OK
- `git diff --check` — OK
- `python -m pytest tests/ -q` — 218 passed, 6 skipped
- `gitnexus detect_changes` — LOW, 0 affected processes

## Commiti i memorija

- Kod: `5751649 refactor(naimenovanja): izdvoji helper za naziv pakovanja`
- Flat memorija: `/home/radovan/.claude/projects/-home-radovan-Desktop-deklarant-pro/memory/2026-05-12_naimenovanja-package-helper-refactor.md`
- MCP memorija: `f9e7ced3-b6f6-438d-84fb-90c61634d943`
