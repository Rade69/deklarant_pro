# SifarniciView table helper refactor

Datum: 2026-05-12
Agent: Codex

## Zadatak

Po istim pravilima kao prethodni refaktori, uraditi siguran refaktor `gui/tabs/sifarnici_view.py`, bez promjene javnog interfejsa i bez promjene ponašanja.

## Analiza prije izmjena

1. Komplikovano:
   - `SifarniciView` u jednoj klasi drži navigaciju kategorija, tabele, tree prikaz za carinarnice, forme, pretrage, CRUD akcije i status/pager.
   - Prelaz između `QTableWidget` i `QTreeWidget` je posebno osjetljiv.

2. Duplirano:
   - Osnovno podešavanje `QTableWidget` ponavlja se u `_create_main_area` i `_create_table_widget`.
   - Ponavljaju se selection behavior, selection mode, alternating rows, stylesheet, visina redova i signal konekcije.

3. Rizično dirati:
   - CRUD tokove (`_on_snimi`, `_on_obrisi`, `_on_uredi`).
   - DB pretrage.
   - `QTreeWidget` tok za carinarnice.
   - Inspekcijska pravila i tarifnu hijerarhiju.

4. Plan:
   - Izdvojiti samo helper koji kreira i konfiguriše `QTableWidget`.
   - Zadržati postojeće stylesheet-ove za glavnu i fallback tabelu.
   - Ne dirati CRUD/DB logiku ni tree tok.
   - Pokrenuti compile, diff check, testove i GitNexus detect_changes.

## GitNexus

- Impact `SifarniciView`: LOW, 0 direct, 0 affected processes.
- Impact `_create_main_area`: LOW, 0 affected processes.
- Impact `_create_table_widget`: LOW, 0 affected processes.
- Detect changes: 1 fajl, risk low, affected processes 0.

## Izmjene

- Dodan `_create_configured_table`.
- `_create_main_area` koristi helper za glavnu tabelu.
- `_create_table_widget` koristi helper za restauriranu/fallback tabelu.

## Provjere

- `python -m py_compile gui/tabs/sifarnici_view.py` — OK
- `git diff --check` — OK
- `python -m pytest tests/ -q` — 218 passed, 6 skipped
- `gitnexus detect_changes` — LOW, 0 affected processes

## Commiti i memorija

- Kod: `d72393d refactor(sifarnici): izdvoji konfiguraciju tabele`
- Flat memorija: `/home/radovan/.claude/projects/-home-radovan-Desktop-deklarant-pro/memory/2026-05-12_sifarnici-table-helper-refactor.md`
- MCP memorija: `3435c121-9e50-41db-84a7-2d40cb65d198`
