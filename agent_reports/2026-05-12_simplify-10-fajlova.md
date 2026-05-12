# Agent Report — /simplify na 10 najvećih Python fajlova

**Datum:** 2026-05-12  
**Zadatak:** Primijeniti `/simplify` skill na 10 najvećih Python fajlova bez narušavanja funkcionalnosti  
**Rezultat:** -707 linija kroz 6 commita, svi fajlovi sintaksno ispravni

---

## Šta je urađeno

Svakom fajlu prethodila je analiza 3 paralelna agenta (Code Reuse, Code Quality, Efficiency). Na osnovu nalaza primijenjene su isključivo **sigurne** izmjene: mrtav kod, duplikati, debug ostaci — bez strukturnih refaktora koji bi mogli promijeniti ponašanje.

| Fajl | Prije | Poslije | Delta |
|------|-------|---------|-------|
| `gui/tabs/sifarnici_view.py` | 3,823 | 3,652 | -171 |
| `gui/tabs/faktura_view.py` | 3,639 | 3,528 | -111 |
| `gui/tabs/naimenovanja_view.py` | 3,592 | 3,500 | -92 |
| `services/zaglavlje_service.py` | 1,917 | 1,834 | -83 |
| `gui/tabs/zaglavlje_view.py` | 2,227 | 2,186 | -41 |
| `gui/tabs/agent/services/chat_intent_handler.py` | 1,649 | 1,641 | -8 |
| `services/agent/validation/declaration_validator_service.py` | 1,154 | 979 | **-175** |
| `services/sifarnici_service.py` | 1,425 | 1,413 | -12 |
| `exporters/asycuda_xml_builder.py` | 1,142 | 1,129 | -13 |
| `importers/vendors/leburic/leburic_pekabesko_pdf_parser.py` | 1,501 | 1,500 | -1 |
| **UKUPNO** | **21,069** | **20,362** | **-707** |

---

## Kako je urađeno

### Tehničke intervencije po tipu

**Mrtav kod (nikad pozvan):**
- `sifarnici_view.py`: `PosiljalacData` dataclass, `_on_table_cell_clicked`, `_create_action_buttons`
- `zaglavlje_view.py`: `_add_carinska_ispostava_autocomplete` (pass placeholder), `_clear_all_fields` (alias)
- `zaglavlje_service.py`: `load_zaglavlje`, `delete_zaglavlje`, `get_tipovi_deklaracija` (nema callera)
- `declaration_validator_service.py`: `_validate_contextual` (vraća `[]`), `_analyze_product_categories`, `_detect_product_category`, `_detect_supplier_category`, `_check_origin_statement`, `test_agent_validation` (test funkcija u prod kodu)

**Duplikati:**
- `sifarnici_service.py`: dva `_log_error` u istoj klasi — drugi (linija 677) tihо overriduje prvi (linija 209)
- `leburic_pekabesko_pdf_parser.py`: `OriginStatementDetector` importovan i instanciran dva puta unutar iste funkcije
- `sifarnici_view.py`: `_reload_current_category()` helper eliminisao duplirane tree-restore blokove

**Debug/print ostaci → logger:**
- `declaration_validator_service.py`: 10+ `print()` poziva zamijenjena sa `logger.debug/warning`
- `naimenovanja_view.py`: `traceback.print_exc()` → `logger.exception()`
- `zaglavlje_view.py`, `faktura_view.py`: `except: pass` → `logger.warning`

**Lokalni importi → module nivo:**
- `sifarnici_service.py`: `import logging` unutar metoda × 2 → module nivo
- `zaglavlje_view.py`: 6 lokalnih importa unutar metoda premješteno na vrh fajla

**Performansni fix (O(n²) → O(1)):**
- `asycuda_xml_builder.py`: `total_items_value_ref = sum(...)` računata unutar `_fill_item_valuation` koji se poziva jednom po stavci. Parametar `total_items_value` već postoji i prosljeđuje se iz vanjske petlje — zamijenjen direktno.

**Predkompajlirani regex:**
- `leburic_pekabesko_pdf_parser.py`: 16 OCR fix pattern-a kompajlirani jednom kao `_PRODUCT_NAME_FIXES` module-level konstanta umjesto na svakom pozivu funkcije

**Klasa konstante umjesto inline dict/set:**
- `faktura_view.py`: `_CONFIDENCE_COLORS`, `_CONFIDENCE_ICONS`
- `naimenovanja_view.py`: `_FLOAT_FIELDS = frozenset({...})`
- `sifarnici_view.py`: `_CATEGORY_PLURAL`

---

## Zašto

Akumulirani dug iz perioda brzog razvoja (MVP → produkcija). Fajlovi su narasli na 1000–3800 linija. Nije mijenjana funkcionalnost — isključivo površinska čišćenja koja olakšavaju buduće izmjene.

**Odluka: Ne diramo `_on_import_finished` (315 linija u faktura_view.py)** — prevelik rizik, monolitna metoda sa kompleksnim state menadzmentom.

**Odluka: Ne diramo Pro XML granu u asycuda_xml_builder.py** — nije aktivna ali sadrži biznis logiku; brisanje bi zahtijevalo dublje razumijevanje.

---

## Commiti

| Hash | Poruka |
|------|--------|
| `f2b3885` | refactor(faktura_view): ukloni duplikate i mrtav kod (-111 linija) |
| `1dc46c2` | refactor(naimenovanja_view): mrtav kod, duplikati, debug cleanup (-92 linija) |
| `402b313` | refactor(zaglavlje_view): lokalni importi, mrtav kod (-41 linija) |
| `19c56b7` | refactor(zaglavlje_service, chat_intent_handler): mrtav kod i duplikati |
| `25ae9d2` | refactor(services,exporters,importers): mrtav kod, print→logger, O(n²) fix (-201 linija) |
| *(sifarnici_view commit iz prethodne sesije)* | refactor(sifarnici_view): ukloni mrtav kod i duplikate (-171 linija) |
