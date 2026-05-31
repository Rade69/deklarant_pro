# ZaglavljeService attached document helper refactor

Datum: 2026-05-12
Agent: Codex

## Zadatak

Po istim pravilima kao prethodni refaktori, uraditi siguran refaktor `services/zaglavlje_service.py`, bez promjene javnog interfejsa i bez promjene ponašanja.

## Analiza prije izmjena

1. Komplikovano:
   - `ZaglavljeService` u jednom fajlu drži draft mapiranje, XML import/export, katalog lookup i export validaciju.
   - `validate` i XML parsing imaju dosta poslovnih pravila i nisu dobar kandidat za usputni refaktor.

2. Duplirano:
   - Konstrukcija dict-a za priložene dokumente (`code`, `name`, `number`, `from_rule`) ponavlja se u draft mapiranju.
   - Provjera da li lista dokumenata već ima određenu šifru ponavlja se za N380/PZT/N730.

3. Rizično dirati:
   - XML tag parsing i namespace logika.
   - Rb.22 iznos/valuta sinhronizacija.
   - Pravila za obavezne dokumente, VOZ, DIS, DV1 i PE dokumente.

4. Plan:
   - Izdvojiti samo helper za standardni dict priloženog dokumenta.
   - Izdvojiti samo helper za provjeru prisutnosti šifre dokumenta.
   - Zamijeniti očigledna ponavljanja u `load_from_draft` i `save_to_draft`.
   - Pokrenuti compile, diff check, testove i GitNexus detect_changes.

## GitNexus

- Impact `ZaglavljeService`: LOW, 0 direct, 0 affected processes.
- Impact `load_from_draft`: LOW, 0 affected processes.
- Impact `save_to_draft`: LOW, 0 affected processes.
- Detect changes: 1 fajl, risk low, affected processes 0.

## Izmjene

- Dodan `_attached_doc_dict`.
- Dodan `_has_attached_doc_code`.
- `load_from_draft` koristi helper za postojeće header dokumente, automatski N380, PZT i N730.
- `save_to_draft` koristi helper kada vraća očuvane dokumente iz prethodnog drafta.

## Provjere

- `python -m py_compile services/zaglavlje_service.py` — OK
- `git diff --check` — OK
- `python -m pytest tests/ -q` — 218 passed, 6 skipped
- `gitnexus detect_changes` — LOW, 0 affected processes

## Commiti i memorija

- Kod: `615357b refactor(zaglavlje): izdvoji helper za prilozene dokumente`
- Flat memorija: `/home/radovan/.claude/projects/-home-radovan-Desktop-deklarant-pro/memory/2026-05-12_zaglavlje-service-attached-doc-helper-refactor.md`
- MCP memorija: `c5e174ab-6a1f-4f04-a593-533bd9e242c5`
