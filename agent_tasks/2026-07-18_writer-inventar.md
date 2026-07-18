# Writer inventar — Faza 0 (dopunjeno)

Datum: 2026-07-18
Svako mjesto gdje se direktno piše `tarifni_broj`, `zemlja_porijekla`, `povlastica` ili `eur1_number`
u `InvoiceLine` objektima.

---

## A. DIREKTNI ASSIGNMENT WRITE-ovi (`obj.polje = vrijednost`)

Ovo su mjesta gdje kod direktno dodjeljuje vrijednost atributu InvoiceLine instance.
To su write operacije koje zaobilaze bilo kakav servis odluka.

### A1. Parser/Deserializer — DOZVOLJEN sirovi unos

Ovi pišu sirove činjenice iz dokumenata (faktura, PDF, XML). To je jedina dozvoljena
granica za direktan upis polja bez prolaska kroz decision servis.

| # | Fajl | Linija(e) | Polja | Tip upisa |
|---|------|-----------|-------|-----------|
| 1 | `core/draft/draft.py` | 170-172 | tarifni_broj, zemlja_porijekla, povlastica | `InvoiceLine.from_any()` constructor |
| 2 | `importers/excel_importer.py` | 460-461 | tarifni_broj, zemlja_porijekla | Assignment iz Excel kolona |
| 3 | `importers/faktura_xml_parser.py` | 221-223 | tarifni_broj, zemlja_porijekla, povlastica | Assignment iz XML fakture |
| 4 | `importers/generic_pdf_importer.py` | 348, 818 | zemlja_porijekla | Assignment iz PDF parsinga |
| 5 | `importers/xml_importer.py` | 346-348 | tarifni_broj, zemlja_porijekla, povlastica | Assignment iz ASYCUDA XML |
| 6 | `importers/xml_importer.py` | 613-615 | tarifni_broj, zemlja_porijekla, povlastica | Assignment iz Pro forma XML |
| 7 | `importers/vendors/sumaprom/sumaprom_pdf_parser.py` | 366-367 | tarifni_broj, zemlja_porijekla | Assignment |
| 8 | `importers/vendors/sumaprom/sumaprom_excel_parser.py` | 641-650 | tarifni_broj, zemlja_porijekla, povlastica | Assignment |
| 9 | `importers/vendors/pip_food/pip_food_parser.py` | 179-180 | tarifni_broj, zemlja_porijekla | Assignment |
| 10 | `importers/proton_system_importer.py` | 211-213 | tarifni_broj, zemlja_porijekla, povlastica | Assignment |
| 11 | `importers/vendors/medicopharm/medicopharm_importer.py` | 935-937, 1075-1076 | tarifni_broj, zemlja_porijekla, povlastica | Assignment |
| 12 | `importers/pdf/ocr_invoice_parser.py` | 311 | tarifni_broj | Assignment iz OCR rezultata |
| 13 | `importers/vendors/blagic/blagic_loren_pdf_parser.py` | 166-167 | tarifni_broj, zemlja_porijekla | Assignment |
| 14 | `importers/vendors/blagic/blagic_loren_importer.py` | 458, 466-476 | tarifni_broj, zemlja_porijekla, povlastica | Assignment iz Excel-a |
| 15 | `importers/vendors/master_frigo/master_frigo_importer.py` | 474-476 | tarifni_broj, zemlja_porijekla, povlastica | Assignment |
| 16 | `importers/vendors/blagic/blagic_importer.py` | 281-282 | tarifni_broj, zemlja_porijekla | Assignment |
| 17 | `importers/vendors/blagic/blagic_attos_importer.py` | 528-529, 561-562, 617-618 | tarifni_broj, zemlja_porijekla | Assignment |
| 18 | `importers/vendors/blagic/blagic_combined_importer.py` | 274-276 | tarifni_broj, zemlja_porijekla, povlastica | Assignment |
| 19 | `importers/vendors/leburic/leburic_pekabesko_pdf_parser.py` | 576-578, 816-818, 1186-1188 | tarifni_broj, zemlja_porijekla, povlastica | Assignment |
| 20 | `importers/vendors/leburic/leburic_pekabesko_importer.py` | 332-334 | tarifni_broj, zemlja_porijekla, povlastica | Assignment |
| 21 | `importers/vendors/kg_fashion/kg_fashion_importer.py` | 222, 371-372 | tarifni_broj, zemlja_porijekla | Assignment |
| 22 | `importers/vendors/cmana/cmana_pdf_parser.py` | 267-268 | tarifni_broj, zemlja_porijekla | Assignment |
| 23 | `importers/vendors/imamoglu/imamoglu_excel_importer.py` | 217-218, 226, 349-350, 358 | tarifni_broj, zemlja_porijekla, povlastica | Assignment |
| 24 | `importers/vendors/imamoglu/imamoglu_pdf_parser.py` | 237-238 | tarifni_broj, zemlja_porijekla | Assignment |
| 25 | `importers/invoice_improved_parser.py` | 165, 173 | zemlja_porijekla, tarifni_broj | Assignment iz parsiranog footera |

### A2. Inferred / Business Logic Writer — MORA BITI MIGRIRAN na decision servis

Ovi pišu izvedene vrijednosti (tarifu iz baze, zemlju iz mappinga, povlasticu iz detekcije).
Ovo su paralelni putevi koji se moraju objediniti u `DeclarationDecisionService`.

| # | Fajl | Linija(e) | Polja | Tip upisa | Problem |
|---|------|-----------|-------|-----------|---------|
| 26 | `services/faktura/auto_fill_service.py` | 96, 101, 112 | tarifni_broj, zemlja_porijekla | Assignment | AutoFillService.fill_tariff_numbers() piše bez decision servisa |
| 27 | `services/tariff/tariff_mapping_service.py` | 234, 240 | tarifni_broj | Assignment | auto_populate_tariffs() piše direktno |
| 28 | `services/tariff/tariff_mapping_service.py` | 260, 268 | zemlja_porijekla | Assignment | merge_country_origin rezultat se direktno upisuje |
| 29 | `services/tariff/product_master_list.py` | 227, 230 | tarifni_broj, zemlja_porijekla | Assignment | Product master direktno upisuje |
| 30 | `services/import_service.py` | 203 | tarifni_broj | Assignment | ImportService direktno normalizuje i upisuje |
| 31 | `services/naimenovanja/declaration_assembly.py` | 66, 70, 81 | tarifni_broj, zemlja_porijekla, povlastica | Assignment | Assembly kopira iz InvoiceLine bez odluke |
| 32 | `services/agent/tariff/hybrid_tariff_agent.py` | 204 | tarifni_broj | Assignment | HybridTariffAgent ekstraktuje i piše |
| 33 | `services/agent/chat/tariff_intent_service.py` | 387, 414 | tarifni_broj | Assignment | Agent direktno piše proposed_tariff |
| 34 | `services/agent/validation/historical_tariff_search_service.py` | 120 | tarifni_broj | Assignment | Istorijski search direktno upisuje |
| 35 | `importers/vendors/kg_fashion/kg_fashion_importer.py` | 453, 464 | zemlja_porijekla, tarifni_broj | Assignment | Mapping iz Customs XML-a se direktno upisuje |
| 36 | `importers/pdf/ocr_invoice_parser.py` | 544, 562 | zemlja_porijekla | Assignment | OCR parser piše zemlju izvedenu iz tarife |

### A3. Manual Edit Adapter — MORA ići kroz decision servis

Ovi pišu na osnovu korisničke akcije u GUI-ju. Nakon migracije,
svi moraju pozivati `confirm_manual_value()` ili `apply_candidate()`.

| # | Fajl | Linija(e) | Polja | Tip upisa | Problem |
|---|------|-----------|-------|-----------|---------|
| 37 | `gui/dialogs/eur1_quick_dialog.py` | 637, 678-679 | zemlja_porijekla, eur1_number, povlastica | Assignment | EUR.1 dijalog piše bez decision servisa |
| 38 | `gui/dialogs/pe2_quick_dialog.py` | 395, 487-488 | zemlja_porijekla, eur1_number, povlastica | Assignment | PE2 dijalog piše bez decision servisa |
| 39 | `gui/dialogs/add_item_dialog.py` | 204, 210-211 | tarifni_broj, zemlja_porijekla, povlastica | Assignment | Dodavanje stavke ručno |
| 40 | `gui/tabs/faktura_view.py` | 1374, 1398, 1400 | tarifni_broj, zemlja_porijekla, povlastica | Assignment | Manual edit u Faktura tabeli |
| 41 | `gui/tabs/faktura_view.py` | 1693, 1707-1708 | tarifni_broj, zemlja_porijekla, povlastica | Assignment | `_read_invoice_lines_from_table` |
| 42 | `gui/tabs/faktura_view.py` | 2435, 3618 | tarifni_broj | Assignment | Auto-fill i batch rezultat |
| 43 | `gui/tabs/naimenovanja_view.py` | 1882-1884, 2506, 2542-2544 | tarifni_broj, zemlja_porijekla, povlastica | Assignment | Promjena tarife u Naimenovanja tabu |
| 44 | `gui/tabs/agent/services/chat_intent_handler.py` | 1964, 2124 | tarifni_broj | Assignment | Agent direktno piše u draft.invoice_lines |

---

## B. SETATTR / DICT / CONSTRUCTOR UPISI

Ovo su mjesta gdje se vrijednosti upisuju kroz `InvoiceLine(**kwargs)` konstruktor
ili kroz dict-based API.

| # | Fajl | Linija(e) | Polja | Tip |
|---|------|-----------|-------|-----|
| B1 | `services/tariff/tariff_mapping_service.py` | 365-368, 422-425, 538-541 | tarifni_broj, zemlja_porijekla, povlastica | `TariffMapping(**row)` — read konstruktor, ne upis u InvoiceLine |
| B2 | `services/tariff/tariff_mapping_service.py` | 674-677, 728-731, 810-813, 952-955 | tarifni_broj, zemlja_porijekla, povlastica | `TariffMapping(...)` konstruktor — read-only struktura |
| B3 | `services/tariff/tariff_mapping_service.py` | 925-927 | tarifni_broj, zemlja_porijekla, povlastica | `INSERT ... ON CONFLICT` — baza znanja (dozvoljeno) |
| B4 | `services/tariff/tariff_mapping_service.py` | 1031 | povlastica | Čitanje iz XML-a, ne upis u InvoiceLine |
| B5 | `services/faktura_service.py` | 114, 122 | tarifni_broj, zemlja_porijekla | `InvoiceLine(...)` konstruktor iz dict-a |
| B6 | `services/tariff_facade.py` | 155-157, 189, 206, 219 | tarifni_broj, zemlja_porijekla, povlastica | Konstruktor TariffSuggestion — read-only |
| B7 | `services/agent/tariff/tariff_suggestion_service.py` | 226-228, 257-259, 316-318 | tarifni_broj, zemlja_porijekla, povlastica | Konstruktor TariffMapping iz DB reda — read-only |
| B8 | `services/naimenovanja/declaration_assembly.py` | 150-152 | tarifni_broj, zemlja_porijekla, povlastica | Konstruktor InvoiceLine iz DB reda — read-only |
| B9 | `services/naimenovanja/create_naimenovanja_service.py` | 211 | eur1_number | Čitanje iz InvoiceLine (ne upis) |
| B10 | `services/naimenovanja/tariff_service.py` | 153 | zemlja_porijekla | Konstruktor TariffSuggestion |

---

## C. READ-ONLY KOMPONENTE KOJE TRENUTNO POGREŠNO PIŠU (BUG!)

| # | Fajl | Linija(e) | Polja | Problem |
|---|------|-----------|-------|---------|
| C1 | `services/validation/preference_validator.py` | 242 | povlastica | **`auto_fix_missing_eur1()` piše `item.povlastica = 'PE1'`** — validator mora biti read-only! |
| C2 | `gui/tabs/naimenovanja_view.py` | 2506 | tarifni_broj | `_on_tariff_changed` piše u `invoice_line.tarifni_broj` — zaobilazi decision servis |

---

## REZIME

| Kategorija | Broj | Status |
|------------|------|--------|
| A1. Parser/Deserializer | 25 | DOZVOLJEN — sirovi unos iz dokumenata |
| A2. Inferred/Business Writer | 11 | **MORA BITI MIGRIRAN** na decision servis |
| A3. Manual Edit Adapter | 8 | **MORA** ići kroz decision servis |
| B. Setattr/Dict/Constructor | 10 | READ-ONLY strukture — nisu direktni writer-i |
| C. Read-only sa bugom | 2 | **BUG** — validator/dialog piše umjesto da samo čita |

**Ukupno direktnih writer-a za migraciju:** 11 (A2) + 8 (A3) + 2 (C) = **21 mjesto**

**Nakon Faze 6, dozvoljeni direktni upisi SAMO u:**
- A1: Parser/Deserializer granici (sirovi unos činjenica iz dokumenata)
- Decision servisu (`apply_candidate()`, `confirm_manual_value()`)
- Draft restore toku (`InvoiceLine.from_any()`)
- Manual edit adapteru koji ODMAH poziva decision servis