# Writer inventar — Faza 0

Datum: 2026-07-18
Svako mjesto gdje se direktno piše `tarifni_broj`, `zemlja_porijekla`, `povlastica` ili `eur1_number`.

## 1. Parser/Deserializer — dozvoljen sirovi unos

| Fajl | Linija | Polje | Napomena |
|------|--------|-------|----------|
| `core/draft/draft.py` | 170-172 | sva 3 | `InvoiceLine.from_any()` — deserializacija iz dict-a |
| `importers/excel_importer.py` | 460-461 | tarifni, zemlja | Excel import |
| `importers/faktura_xml_parser.py` | 221-223 | sva 3 | XML faktura parser |
| `importers/generic_pdf_importer.py` | 348, 818 | zemlja | PDF import |
| `importers/xml_importer.py` | 346-348, 613-615 | sva 3 | ASYCUDA/Pro forma XML |
| `importers/vendors/sumaprom/sumaprom_pdf_parser.py` | 366-367 | tarifni, zemlja | Šumaprom PDF |
| `importers/vendors/sumaprom/sumaprom_excel_parser.py` | 641-650 | sva 3 | Šumaprom Excel |
| `importers/vendors/pip_food/pip_food_parser.py` | 179-180 | tarifni, zemlja | PIP Food |
| `importers/proton_system_importer.py` | 211-213 | sva 3 | Proton System |
| `importers/vendors/medicopharm/medicopharm_importer.py` | 935-937, 1075-1076 | sva 3 | Medicopharm |
| `importers/pdf/ocr_invoice_parser.py` | 311 | tarifni | OCR parser |
| `importers/vendors/blagic/blagic_loren_pdf_parser.py` | 166-167 | tarifni, zemlja | Blagić Loren PDF |
| `importers/vendors/blagic/blagic_loren_importer.py` | 458, 466-476 | sva 3 | Blagić Loren Excel |
| `importers/vendors/master_frigo/master_frigo_importer.py` | 474-476 | sva 3 | Master Frigo |
| `importers/vendors/blagic/blagic_importer.py` | 281-282 | tarifni, zemlja | Blagić |
| `importers/vendors/blagic/blagic_attos_importer.py` | 528-529, 561-562, 617-618 | sva 3 | Blagić Attos |
| `importers/vendors/blagic/blagic_combined_importer.py` | 274-276 | sva 3 | Blagić kombinovani |
| `importers/vendors/leburic/leburic_pekabesko_pdf_parser.py` | 576-578, 816-818, 1186-1188 | sva 3 | Leburic PDF |
| `importers/vendors/leburic/leburic_pekabesko_importer.py` | 332-334 | sva 3 | Leburic Excel |
| `importers/vendors/kg_fashion/kg_fashion_importer.py` | 222, 371-372 | tarifni, zemlja | KG Fashion |
| `importers/vendors/cmana/cmana_pdf_parser.py` | 267-268 | tarifni, zemlja | Cmana |
| `importers/vendors/imamoglu/imamoglu_excel_importer.py` | 217-218, 226, 349-350, 358 | sva 3 | Imamoglu Excel |
| `importers/vendors/imamoglu/imamoglu_pdf_parser.py` | 237-238 | tarifni, zemlja | Imamoglu PDF |

## 2. Manual edit adapter — mora ići kroz decision servis nakon migracije

| Fajl | Linija | Polje | Napomena |
|------|--------|-------|----------|
| `gui/dialogs/eur1_quick_dialog.py` | 637, 678-679 | zemlja, eur1, povlastica | EUR.1 dijalog |
| `gui/dialogs/pe2_quick_dialog.py` | 395, 487-488 | zemlja, eur1, povlastica | PE2 dijalog |
| `gui/dialogs/add_item_dialog.py` | 204, 210-211 | tarifni, zemlja, povlastica | Dodavanje stavke |
| `gui/tabs/faktura_view.py` | 1374, 1398, 1400 | sva 3 | Manual edit u Faktura tabeli |
| `gui/tabs/faktura_view.py` | 1693, 1707-1708 | sva 3 | Čitanje iz tabele nazad u objekat |
| `gui/tabs/faktura_view.py` | 2435, 3618 | tarifni | Auto-fill rezultat i batch operacije |
| `gui/tabs/naimenovanja_view.py` | 1882-1884, 2506, 2542-2544 | sva 3 | Promjena tarife u Naimenovanja tabu |
| `gui/tabs/agent/services/chat_intent_handler.py` | 1964, 2124 | tarifni | Agent direktno piše tarifu |

## 3. Inferred writer — MORA biti migriran na decision servis

| Fajl | Linija | Polje | Napomena |
|------|--------|-------|----------|
| `services/faktura/auto_fill_service.py` | 96, 101, 112 | tarifni, zemlja | AutoFillService — piše direktno |
| `services/tariff/tariff_mapping_service.py` | 234, 240, 260, 268 | tarifni, zemlja | TariffMappingService — piše direktno |
| `services/tariff/product_master_list.py` | 227, 230 | tarifni, zemlja | ProductMasterList — piše direktno |
| `services/import_service.py` | 203 | tarifni | ImportService — piše direktno |
| `services/naimenovanja/declaration_assembly.py` | 66, 70, 81 | tarifni, zemlja, povlastica | DeclarationAssembly |
| `services/agent/tariff/hybrid_tariff_agent.py` | 204 | tarifni | HybridTariffAgent |
| `services/agent/chat/tariff_intent_service.py` | 387, 414 | tarifni | TariffIntentService — piše direktno |
| `services/agent/validation/historical_tariff_search_service.py` | 120 | tarifni | Historical — piše direktno |
| `importers/vendors/kg_fashion/kg_fashion_importer.py` | 453, 464 | zemlja, tarifni | KG Fashion — piše mapping |
| `importers/invoice_improved_parser.py` | 165, 173 | zemlja, tarifni | Parser — piše footer vrijednosti |
| `importers/pdf/ocr_invoice_parser.py` | 544, 562 | zemlja | OCR parser — piše zemlju po tarifi |

## 4. Exporter/Validator — upis nije dozvoljen (BUG!)

| Fajl | Linija | Polje | Napomena |
|------|--------|-------|----------|
| `services/validation/preference_validator.py` | 242 | povlastica | **BUG!** Validator piše `PE1` povlasticu — mora biti read-only |

## 5. Testni kod (OK)

| Fajl | Linija | Polje | Napomena |
|------|--------|-------|----------|
| `services/naimenovanja/create_naimenovanja_service.py` | 535-550 | sva 3 | Testni kod u `__main__` |
| `services/validation/preference_validator.py` | 262-296 | sva 3 | Testni kod u `__main__` |

---

**Ukupno direktnih writer-a:** 11 inferred + 8 manual + 25 parser/deserializer = 44 mjesta
**Nakon migracije (Faza 6), dozvoljeni direktni upisi samo u:**
- Parser/deserializer granici (sirovi unos)
- Decision servisu (izvedene/primijenjene odluke)
- Draft restore toku
- Manual edit adapteru koji odmah poziva decision servis