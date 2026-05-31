---
section: pdf_parse_pipeline
file: importers/smart_pdf_importer.py
---

## Svrha

Centralni entry point za parsiranje bilo kojeg PDF-a. Automatski detektuje format i poziva odgovarajući specijalizovani parser. Sadrži 3 nivoa fallback-a ako primarni parser vrati prazan rezultat.

## Zavisnosti i pretpostavke

- Oslanja se na `_detect_pdf_format()` u istom fajlu
- Specijalizovani parseri su u `importers/` folderu i importuju se lazy (unutar if/elif blokova)
- OCR fallback zahtijeva `pytesseract` i `pdf2image` — opcioni, bez greške ako nisu instalirani

## Pravila i granice

5-koračni pipeline:

| Korak | Opis |
|-------|------|
| 1 | Detekcija formata (`_detect_pdf_format`) |
| 2 | Poziv specijalizovanog parsera za detektovani format |
| 3 | Fallback na `parse_generic_pdf()` ako specijalizovani vrati 0 stavki |
| 4 | OCR fallback ako i generic vrati 0 stavki (samo za skenirane PDF-ove) |
| 5 | Finalni rezultat: uvijek vraća `ImportResult`, nikad `None` |

**Važno**: Evaluacija `if result is not None` umjesto `if result` — `ImportResult` sa 0 stavki je falsy, ali nije `None`.

## Zašto ovako

Jedan ulazni parser smanjuje coupling — GUI i ImportService ne moraju znati koji vendor format koristiti. Fallback lanac osigurava da korisnik uvijek dobije nešto (pa makar i generički rezultat) umjesto greške.
