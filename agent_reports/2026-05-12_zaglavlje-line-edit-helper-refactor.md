# ZaglavljeView line edit helper refactor

Datum: 2026-05-12
Agent: Codex

## Zadatak

Po istim pravilima kao prethodni refaktori, uraditi siguran refaktor `gui/tabs/zaglavlje_view.py`, bez promjene javnog interfejsa i bez promjene ponašanja.

## Analiza prije izmjena

1. Komplikovano:
   - `ZaglavljeView` ručno gradi veliki Qt layout i drži mapu widgeta za mnogo carinskih polja.
   - `set_data` ima posebna pravila za editable combo prikaz, a tabela priloženih dokumenata ima posebna import pravila.

2. Duplirano:
   - Isti obrazac privremenog skidanja `readOnly` stanja sa `QLineEdit` prije `setText`/`clear`, zatim vraćanja stanja.

3. Rizično dirati:
   - Rb.1 deklaracija i oznaka combo sinhronizacija.
   - Rb.25/26 prikaz šifre u editable combo poljima.
   - Tabela priloženih dokumenata, `_import_attached_docs` i `clear_refs_on_import`.

4. Plan:
   - Izdvojiti samo helper za `QLineEdit` read-only set/clear.
   - Zamijeniti duplirani blok u `set_data` i `clear_data`.
   - Ne dirati combo pravila, tabelu, signale ni javni interfejs.
   - Pokrenuti compile, diff check, testove i GitNexus detect_changes.

## GitNexus

- Impact `ZaglavljeView`: LOW, 0 direct, 0 affected processes.
- Impact `get_data`: LOW, 0 affected processes.
- Impact `set_data`: LOW, 0 affected processes.
- Impact `clear_data`: LOW, 0 affected processes.
- Detect changes: 1 fajl, risk low, affected processes 0.

## Izmjene

- Dodan `_with_line_edit_writable`.
- Dodan `_set_line_edit_text`.
- Dodan `_clear_line_edit`.
- `set_data` i `clear_data` sada koriste helper umjesto dupliciranog read-only bloka.
- Helper vraća `readOnly` stanje kroz `finally`.

## Provjere

- `python -m py_compile gui/tabs/zaglavlje_view.py` — OK
- `git diff --check` — OK
- `python -m pytest tests/ -q` — 218 passed, 6 skipped
- `gitnexus detect_changes` — LOW, 0 affected processes

## Commiti i memorija

- Kod: `17302be refactor(zaglavlje): izdvoji line edit read only helper`
- Flat memorija: `/home/radovan/.claude/projects/-home-radovan-Desktop-deklarant-pro/memory/2026-05-12_zaglavlje-line-edit-helper-refactor.md`
- MCP memorija: `f6c36d41-a7b6-4572-b54e-dbde3f81c73f`
