# Čišćenje dead code-a i technical debt — 26. april 2026

## Obrisani fajlovi (19 fajlova)

Svaki fajl je provjeren sa `grep -rn "from <modul> import"` prije brisanja.
Nula pravih importa = siguran za brisanje.

| Fajl | Razlog brisanja |
|---|---|
| `gui/tabs/faktura_controller.py` | Stub, nikad priključen; FakturaTab koristi FakturaView direktno |
| `gui/tabs/naimenovanja_controller.py` | Isto — stub bez ijednog importa |
| `gui/tabs/demo_tab.py` | Demo widget, 0 importa |
| `core/validation/rules.py` | Validation logika premještena u services; 0 importa |
| `core/mapping/enums.py` | Enum-i premješteni; 0 importa |
| `core/mapping/central_mapper.py` | Importovan samo iz obrisanog `asycuda_xml_exporter.py` |
| `core/draft/prilozi.py` | Zamijenjeno sa `AttachedDocument` u `draft.py` |
| `core/draft/zaglavlje.py` | Zamijenjeno sa inline klasama u `draft.py` |
| `utils/money.py` | Formatiranje novca inline-ovano gdje treba; 0 importa |
| `utils/text.py` | 0 pravih importa (greška pri provjeri: `text` substring dao false pozitive) |
| `utils/weight.py` | 0 pravih importa |
| `exporters/asycuda_xml_exporter.py` | Zamijenjen sa `asycuda_xml_builder.py`; bio zakomentarisan u `__init__.py` |
| `importers/pdf/importer.py` | Zamijenjen sa `smart_pdf_importer.py`; 0 importa |
| `importers/pdf/utils.py` | Utility funkcije inline-ovane; 0 importa |
| `services/agent/hybrid_matching_service.py` | Logika premještena u `tariff_suggestion_service.py`; 0 importa |
| `importers/vendors/leburic/leburic_pekabesko_xml_parser.py` | XML parser zamijenjen PDF parserom; 0 importa |
| `sifrarnici/pakovanja.py` | Podaci premješteni u DB; 0 importa |
| `sifrarnici/povlastice.py` | Isto |
| `sifrarnici/transport.py` | Isto |

## Obrisana prazna direktorija

- `core/mapping/` — ostala prazna nakon brisanja enums.py i central_mapper.py

## Popravljene zavisnosti

### `utils/dependency_injection.py`
Uklonjena `register_services()` funkcija koja je referencirala nepostojeće
`faktura_controller_refactored` i `naimenovanja_controller_refactored` fajlove.
Funkcija nikad nije bila pozvana (importovana ali nekorišćena u `tab_factory.py`).

### `gui/tabs/tab_factory.py`
Uklonjen import `register_services` koji se nikad nije koristio.

### `exporters/__init__.py`
Uklonjena zakomentarisana referenca na obrisani `asycuda_xml_exporter`.

## Popravljeni silent except blokovi

| Fajl | Linija | Izmjena |
|---|---|---|
| `services/import_service.py` | L227, L243 | `except Exception: pass` → `logger.debug(f"...")` |
| `exporters/asycuda_xml_builder.py` | L849 | `except Exception: pass` → `logger.debug(f"...")` |

## Metodologija provjere

Da bi se izbjegli false pozitivi (npr. `utils/text` substring matchuje hiljade linija),
korišten je eksplicitni pattern:
```bash
grep -rn "from utils\.text import\|from utils import text" --include="*.py" .
```
