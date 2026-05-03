# XML Import — zaštita priloženih dokumenata (add-only)

Datum: 2026-04-28

## Problem
Pri XML uvozu u Zaglavlje, postojeći podaci u tabeli "Priloženi dokumenti" su se prepisivali
novim vrijednostima iz XML-a (npr. OST/PE3 reference), što je dovodilo do gubitka ručnog unosa
i podataka koji su već potvrđeni kroz Naimenovanja.

## Nova logika
Implementiran je "add-only" merge:

1. Prije uvoza uzima se snapshot trenutno upisanih dokumenata iz UI tabele.
2. Ti dokumenti se tretiraju kao zaključani i ostaju nepromijenjeni.
3. XML import i `draft.header_attached_documents` mogu dodati samo šifre koje nedostaju.
4. Ne postoji prepisivanje postojećeg reda drugim izvorom podataka.

## Implementacija
Fajl: `gui/tabs/zaglavlje_controller.py`

Dodano:
- `_merge_import_docs_add_only_missing(existing_docs, draft_header_docs, imported_docs)`
  - održava redoslijed i deduplikaciju po šifri (case-insensitive)
  - prvo zadržava postojeće, zatim dodaje nedostajuće iz drafta i XML-a
- `_sanitize_attached_documents_after_import(..., protected_codes=...)`
  - poštuje `protected_codes` (šifre koje su već postojale prije importa)
  - sigurnosno čisti konfliktne reference (npr. PE prefiks na ne-PE kodu)
  - za novododane `N730/PZT/DV1` ostavlja praznu referencu (ako nije bila zaštićena)

## Posljedica
- OST iz Rub.40.3 i PE unosi iz Naimenovanja ostaju sačuvani ako su već bili u tabeli.
- XML više ne može pregaziti postojeći red u "Priloženim dokumentima".
- XML i dalje dopunjava nedostajuće dokumente.
