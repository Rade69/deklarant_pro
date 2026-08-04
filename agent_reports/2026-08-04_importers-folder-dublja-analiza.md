## Datum
2026-08-04

## Agent
Claude Code (Sonnet 5)

## Scope
Audit: cio `importers/` folder (57 .py fajlova). Izmjena: `importers/pdf/{base,blagic_strategy,
generic_strategy,master_frigo_strategy,ocr_strategy}.py`, `importers/vendors/blagic/blagic_importer.py`,
`importers/vendors/blagic/__init__.py`, `importers/pip_food_parser.py` + `dist_client/` kopije.
`docs/importers/IMPORTERS_BUG_REPORT.md` (status napomena).

## Impact analiza
Repo-wide grep (0 vanjskih referenci prije brisanja, provjereno za svaki obrisani fajl) + puna
test svita poslije. GitNexus `impact`/`detect_changes` file-level lookup nije uspio (poznat alat-limit
iz ranijih krugova ove sesije za pure-deletion promjene) — nezavisan dokaz jači. Risk: LOW.

## Šta je urađeno
1. Mapiran dispatch mehanizam: `strategy_registry.py` → `importers/strategies/` (generic PDF/Excel/XML,
   AKTIVNO registrovano) vs `importers/pdf/*_strategy.py` (per-vendor Strategy obrazac, NIKAD registrovan).
2. Potvrđeno orphaned: `importers/pdf/base.py`+4 strategy fajla (422 linije, `__all__ = []`, 0 referenci
   bilo gdje uklj. testove) — abandoned pokušaj da zamijeni if/elif dispatch u `smart_pdf_importer.py`,
   pokrivao samo 3 od 9 dobavljača.
3. Potvrđeno orphaned: `importers/vendors/blagic/blagic_importer.py` (jedini pozivalac bio dead
   `blagic_strategy.py`). Sadržavao 2 poznata bug-a iz `IMPORTERS_BUG_REPORT.md` — bezopasni jer
   nedostižni.
4. Otkriveno usput (nakon prvog brisanja test suite je pukao): `vendors/blagic/__init__.py`
   unconditionally re-eksportuje simbole iz `blagic_importer.py` u `__all__` — Python izvršava
   `__init__.py` pri BILO KOM submodule importu, pa je brisanje bez fixa lomilo cio `blagic` paket.
   Popravljeno (uklonjena re-export linija + 3 imena iz `__all__`, potvrđeno da nisu spoljno korišćena).
5. Potvrđeno orphaned: `importers/pip_food_parser.py` (7-linijski shim, niko ga ne koristi — svi idu
   direktno na `importers.vendors.pip_food.pip_food_parser`).
6. Unakrsno provjeren `docs/importers/IMPORTERS_BUG_REPORT.md` (2026-04-03, 17 stavki) sa trenutnim
   kodom — 5 spot-checked kritičnih/major bugova (#1, #5, #7, #8, #9) VEĆ POPRAVLJENI; #2/#3 MOOT
   (fajl obrisan); recomendacija #1 (9 dupliranih `_parse_number` implementacija) I DALJE VAŽI.
   Dodata status napomena na vrh dokumenta.
7. Korisnik pitan (AskUserQuestion, 2 pitanja) — odobrio brisanje sva 3 dead-code nalaza; odbio
   (za sada) konsolidaciju `_parse_number` duplikata kao veći/rizičniji follow-up posao.
8. py_compile + puna `pytest tests/ -q` (bez DB-zavisnih testova) — nakon `__init__.py` fixa identično
   baseline-u, nema regresije. Ciljano: `test_blagic_attos_dedup`, `test_blagic_loren_agent_import`,
   `test_pip_food_parser`, `test_pdf_plumber_only` — svi prolaze.
9. `npx gitnexus analyze` + `detect_changes` — risk low.
10. Commit `b9ee4bb`.

## Šta nije dirano
- Živi OCR moduli u `importers/pdf/` (`ocr_utils.py`, `ocr_invoice_parser.py`) — koristi ih
  `smart_pdf_importer.py`.
- `blagic_loren_importer.py`/`blagic_attos_importer.py`/`blagic_combined_importer.py` — živi, koriste se.
- 9 dupliranih `_parse_number`-stil funkcija po dobavljačima — follow-up, veći/rizičniji posao
  (zahtijeva karakterizacione testove po dobavljaču na realnim fakturama prije konsolidacije).
- Ostatak `IMPORTERS_BUG_REPORT.md` stavki (#4, #6, #10-16) — nisu provjeravane ovom sesijom.

## Verifikacija
py_compile OK (root + dist_client). Puna `pytest tests/ -q -k "not test_db_..."` — identičan baseline
(3 pre-postojeća fail-a nepovezana). Ciljani vendor testovi (26 passed, 24 skipped zbog nedostupnih
test-fajlova/pytesseract — okruženje, ne regresija).

## Pronađeni problemi
`__init__.py` re-export gotcha (vidi #4 iznad) — vrijedna, ponovljena pouka: prije brisanja bilo kog
Python modula unutar paketa, provjeriti da li ga paketov `__init__.py` re-eksportuje, ne samo direktne
pozivaoce po punom putu.

## Commitovi
| Hash | Poruka |
| --- | --- |
| `b9ee4bb` | `refactor(importers): ukloni orphaned PDF strategy podstablo i mrtve shim-ove` |

## Potreban follow-up
Konsolidacija 9 dupliranih `_parse_number` implementacija u `invoice_line_utils.parse_eu_number()` —
korisnik svjesno odgodio, zahtijeva karakterizacione testove po dobavljaču prije izmjene.

## Potrebna korisnička potvrda
Nema — sve izmjene su brisanje dokazano nedostupnog koda, testovi zeleni.
