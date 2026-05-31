# Agent report: CMANA parser i EUR1 tok

## Kontekst
CMANA PDF fakture u `najavauvoza/CMANA/` su se parsirale sa ispravnim EUR iznosima, ali bez tarifnih brojeva i zemlje porijekla. Zbog toga kasnije grupisanje nije moglo dati iste vrijednosti kao stari XML fajlovi.

## Uradjeno
- Dodan CMANA vendor parser paket u `importers/vendors/cmana/`.
- `smart_pdf_importer.py` detektuje CMANA racun i poziva CMANA parser.
- `services/import_service.py` tretira `cmana` kao poznat vendor format, da PDF ne ode kroz packing-list fallback.
- CMANA parser mapira poznate sifre artikala na tarife:
  - `120002` -> `02071450`
  - `120009` -> `02071360`
  - `120028` -> `02071391`
  - `120031` -> `02071340`
  - `120036` -> `02071110`
  - `120052` -> `02071360`
  - `120056` -> `02071330`
- CMANA stavkama se postavlja porijeklo `RS` i `raw["eur1_suggested"] = True`, pa postojeci `Eur1QuickDialog` ima podatke da se otvori i predlozi unos EUR1 obrasca.

## Verifikacija
- `python -m pytest tests/unit/test_parser_regression.py -q` -> 28 passed
- `python -m pytest tests/ -q` -> 581 passed, 6 skipped, 1 failed

## Napomena o padu kompletnog suite-a
Pad nije vezan za CMANA:
`tests/test_tool_use_offline.py::TestToolSchema::test_ima_tacno_10_alata`
ocekuje 10 alata, a trenutna definicija vraca 12.

## Rizici
- Mapiranje CMANA sifara je eksplicitno za trenutno vidjene artikle. Ako CMANA uvede nove sifre artikala, parser ce ih procitati, ali im nece automatski dodijeliti tarifu dok se mapa ne prosiri.
