# Istraga: Naimenovanja i Faktura tab — kompletni tok

**Datum**: 2026-07-25
**Agent**: Pi
**Scope**: Naimenovanja tab (view, controller, servisi, widgeti, delegate), Faktura tab, ručni/grupni/agent import, services.import_workflow, parseri, draft modeli, root vs dist_client, testovi

---

## Sažetak

Istraženo 8.840 linija View koda (FakturaView 6.133 + NaimenovanjaView 3.888 − preklapanje), 14 servisa, 3 workera, root/dist_client drift i test coverage. Pronađeno **16 potvrđenih nalaza** u 7 kategorija. Svi su dokazani kroz kod — nema nagađanja.

---

## 1. KRITIČNI PROBLEMI I RIZICI ZA PODATKE

### 1a) `services/import_service.py` — shipped build fabrikuje POGREŠNE tarifne brojeve ⚠️ KRITIČNO

- **Fajl:Linija**: `services/import_service.py` (root vs dist_client)
- **Opis**: Root je UKLONIO `zfill(8)` za 4-7 cifrene tarifne brojeve jer je fabrikovao nepostojeća poglavlja (npr. `"3304990"` → `"03304990"` = nepostojeće poglavlje 03). **Dist_client (shipped .exe runtime) još uvijek ima `zfill(8)`** — proizvodi pogrešne tarifne brojeve.
- **Dokaz**: `diff -u dist_client/services/import_service.py services/import_service.py` pokazuje uklonjen `zfill(8)` + komentar u root-u koji referencira `project_rooms/2026-07-25_ukloni-lijevu-dopunu-kratkih-tarifa.md`.
- **Da li je aktivan kod**: DA — `normalize_tariff_numbers()` se poziva pri svakom importu fakture.
- **Rizik**: PRAVNI — pogrešna carinska tarifa u shipped build-u = finansijski/pravni problem za deklaranta.
- **Predlog**: Mirrorati root izmjenu u dist_client ODMAH (Faza 10 plana).

### 1b) `FakturaView._get_tariff_description` — `__file__` putanja bez `sys.frozen` (bug §44) ⚠️ KRITIČNO

- **Fajl:Linija**: `gui/tabs/faktura_view.py:5379`
- **Opis**: Direktan `sqlite3.connect(Path(__file__).parent.../"database"/"deklarant_sistem.db")` bez `sys.frozen` provjere. U .exe build-u `__file__` pokazuje unutar `_internal/` bundle-a, baza živi pokraj .exe-a — konekcija tiho napravi PRAZNU bazu.
- **Dokaz**: Isti obrazac kao §44 (`tariff_hierarchy.py`), već popravljeno u 3 fajla (`tarifa_service.py`, `tariff_tree_service.py`, `tariff_history_analysis_service.py`).
- **Da li je aktivan kod**: DA — poziva se iz `_show_tariff_preview_dialog` (l.5526).
- **Rizik**: Tiho prazan opis tarife u shipped build-u + N+1 (otvara konekciju u petlji).
- **Predlog**: Premjestiti u `TariffService` (koji već ima pravilan `_resolve_db_path`).

---

## 2. NAJVEĆA USKA GRLA

### 2a) `_get_tariff_description` — N+1 SQLite konekcija u petlji

- **Fajl:Linija**: `gui/tabs/faktura_view.py:5526` (poziv u petlji)
- **Opis**: Za svaki predlog tarife u preview dijalogu otvara NOVU SQLite konekciju, radi upit, zatvara. Za 50 predloga = 50 konekcija.
- **Dokaz**: `for i, proposal in enumerate(proposals): opis = self._get_tariff_description(tarif)`.
- **Predlog**: Batch lookup (jedan upit za sve kodove) ili cache.

### 2b) `_run_historical_tariff_validation` — DB upiti na UI threadu

- **Fajl:Linija**: `gui/tabs/faktura_view.py:4622`
- **Opis**: `HistoricalTariffSearchService().validate_lines()` radi DB upite za SVAKU stavku na UI threadu. Poziva se nakon svakog importa (l.2620, 2740, 3825, 4147).
- **Dokaz**: Poziva se direktno iz `_on_import_finished` i `_process_batch_records` — nema QThread.
- **Predlog**: Premjestiti u worker thread (kao `ProcessingWorker`).

### 2c) `_load_current_item` — DB upiti pri svakoj navigaciji

- **Fajl:Linija**: `gui/tabs/naimenovanja_view.py:2359`
- **Opis**: Pri svakom prelasku na novo naimenovanje radi `_load_tariff_descriptions_sqlite` + `_load_tariff_description_from_db` (PostgreSQL). Postoji djelimični cache (draft polja), ali samo za PRVI prolaz.
- **Predlog**: Cache tarifnih opisa po tariff_code (ne po naimenovanju).

---

## 3. ARHITEKTURNI I ODRŽAVAČKI DUG

### 3a) Naimenovanja NEMA controller — sve u View (krši 3-layer pattern)

- **Opis**: `gui/tabs/naimenovanja_tab.py` (41 linija) je tanak wrapper oko `NaimenovanjaView` (3.888 linija). Ne postoji `naimenovanja_controller.py`. AGENTS.md zahtijeva 3-layer (View/Controller/Service).
- **Dokaz**: `find gui/tabs -name "*naimenovanja*"` — samo `naimenovanja_tab.py` i `naimenovanja_view.py`. Za poređenje: `zaglavlje_controller.py` (1.154 linije) postoji za Zaglavlje.
- **Predlog**: Izdvojiti `NaimenovanjaController` (orchestration) iz View-a.

### 3b) 4+ direktna DB upita u NaimenovanjaView (krši 3-layer)

- **Fajl:Linija**: `gui/tabs/naimenovanja_view.py` — l.838, 1078, 1268, 1890, 2556
- **Opis**: View direktno: (1) učitava pakovanja iz DB, (2) učitava prethodne dokumente iz DB, (3) učitava tarifne opise iz PostgreSQL, (4) briše stare tarifne mape (DELETE ×2).
- **Predlog**: Sve DB operacije u `NaimenovanjaService`.

### 3c) Duplikat logike u NaimenovanjaView — DELETE + learn tarifa

- **Fajl:Linija**: `gui/tabs/naimenovanja_view.py:1890` i `2556`
- **Opis**: ISTA logika (DELETE starih tarifa + `TariffFacade.get_instance().learn()`) duplicirana na dva mjesta.
- **Predlog**: Izdvojiti u jednu metodu ili `TariffFacade.sync_mapping()`.

### 3d) `_suggest_tariff_impl` — STOP_WORDS poslovna logika u View

- **Fajl:Linija**: `gui/tabs/naimenovanja_view.py:3403`
- **Opis**: STOP_WORDS set ({"goods", "material", ...}) i edge-case provjere su u View-u, mogle bi biti u servisu.
- **Predlog**: Premjestiti u `TariffService.suggest_tariff()`.

### 3e) `TariffService.load_tariff_description()` ZASTARIO — View ima bolju verziju

- **Fajl:Linija**: `services/naimenovanja/tariff_service.py:19` vs `gui/tabs/naimenovanja_view.py:1239`
- **Opis**: Servis ima jednostavnu verziju (bez `nivo` parametra). View ima naprednu (sa `nivo="podbroj"/"glava"` i boljim prefix fallback). Paradoks — servis zaostao, View napredovao.
- **Predlog**: Premjestiti logiku iz View-a u servis (sa `nivo` parametrom).

---

## 4. MRTAV ILI DUPLIRAN KOD

### 4a) Legacy metode u FakturaView — aktivne ali zbunjujuće

- **Fajl:Linija**: `gui/tabs/faktura_view.py:3833` (`_on_import_finished_legacy`, 324 linije) i `2627` (`_process_batch_records_legacy`, 116 linija)
- **Opis**: `_on_import_finished` (l.3788) i `_process_batch_records` (l.2555) su TANKE fasade koje provjeravaju `_can_use_unified_manual_import` i padaju na legacy. Legacy je AKTIVAN fallback, ali naziv "legacy" je zbunjujuć.
- **Napomena**: Ovo je Codexov rad na Fazi 6 — unified put koristi naš `ImportPlan`. Legacy ostaje dok se ne migrira agent tok.
- **Predlog**: Nakon Faze 8 (agent migracija), obrisati legacy.

### 4b) `__main__` test blok u `naimenovanja_view.py` (l.3871-3888)

- **Opis**: `if __name__ == "__main__":` blok za standalone UI testiranje. Nije mrtav kod (koristi se za ručno testiranje), ali ~18 linija u produkcionom fajlu.
- **Predlog**: Prihvatljivo, samo napomena.

---

## 5. UX TOKOVI KOJE JE MOGUĆE POJEDNOSTAVITI

### 5a) `_on_import_xml` u NaimenovanjaView — parsiranje na UI threadu

- **Fajl:Linija**: `gui/tabs/naimenovanja_view.py:3302`
- **Opis**: `ZaglavljeService().parse_naimenovanja_from_xml(filename)` (324 linije) radi na UI threadu. Za velike ASYCUDA XML-ove (do 99 naimenovanja) može zamrznuti UI na par sekundi.
- **Predlog**: Premjestiti u worker thread.

### 5b) Često reloadovanje tabele — `_load_data_from_draft` na ~20 mjesta

- **Fajl:Linija**: `gui/tabs/faktura_view.py` — 20 poziva `_load_data_from_draft`
- **Opis**: Postoji PASS 1/PASS 2 optimizacija i `_validation_generation` counter koji otkazuje starije pozive (dobro). Ali broj poziva ukazuje na moguće nepotrebna osvježavanja.
- **Predlog**: Debounce reload (kumulativni QTimer 50ms) umjesto direktnih poziva.

---

## 6. QTHREAD ŽIVOTNI CIKLUS

### 6a) ChatWorker i TariffLLMWorker nemaju `cancel()`

- **Fajl**: `gui/tabs/agent/widgets/chat_worker.py` i `tariff_llm_worker.py`
- **Opis**: Samo `ProcessingWorker` ima `cancel()` + `_cancelled` flag. ChatWorker i TariffLLMWorker nemaju — LLM poziv se ne može prekinuti.
- **Predlog**: Dodati `cancel()` sa `requestInterruption()`.

### 6b) MainWindow.closeEvent — nema `quit()/wait()`

- **Fajl:Linija**: `gui/main_window.py:582`
- **Opis**: closeEvent pita korisnika ako worker radi, ali ako kaže "Da, zatvori" — nema `worker.quit()` + `worker.wait()`. Thread se gasi nasilno (Qt warning).
- **Predlog**: Dodati graceful shutdown.

---

## 7. TEST COVERAGE — nepokriveni kritični tokovi

| Metoda | Fajl | Testova | Problem |
|--------|------|---------|---------|
| `_load_tariff_description_from_db` | naimenovanja_view:1239 | 0 | Direktan DB u View |
| `_on_import_xml` | naimenovanja_view:3302 | 0 | XML parsiranje na UI thread |
| `_suggest_tariff_impl` | naimenovanja_view:3403 | 0 | STOP_WORDS u View |
| `_load_current_item` | naimenovanja_view:2359 | 0 | DB pri navigaciji |
| `_get_tariff_description` | faktura_view:5379 | 0 | sqlite + bug §44 + N+1 |

Sve ove metode sadrže poslovnu logiku u View-u i nemaju testove jer su teško testabilne (ovise o Qt/DB). **Ovo je glavni razlog zašto se bugovi kriju** — kad se logika premjesti u servise, postaju testabilni.

---

## 8. ROOT/DIST_CLIENT DRIFT — sažetak

| Fajl | Tip razlike | Rizik |
|------|-------------|-------|
| `services/import_service.py` | `zfill(8)` uklonjen u root | **KRITIČAN** — pogrešne tarife u shipped |
| `gui/tabs/faktura_view.py` | UI redizajn (PDF/Pregled dugmad) | Nizak — kozmetika |
| `exporters/asycuda_xml_builder.py` | Namjerno (poznato) | — |
| `importers/packing_list_parser.py` | Reordering (poznato) | — |
| ostali | BOM/CRLF/frozen-patch | — |

---

## PREPORUČENI REDOSLIJED IMPLEMENTACIJE

| # | Šta | Korist | Rizik | Testovi |
|---|-----|--------|-------|---------|
| 1 | **Mirror `zfill(8)` fix u dist_client** | Uklanja pravni rizik (pogrešne tarife) | Nizak | Postojeći tarifni testovi |
| 2 | **Premjestiti `_get_tariff_description` u TariffService** (sa `_resolve_db_path`) | Uklanja §44 bug + N+1 | Nizak | Novi test za TariffService |
| 3 | **Premjestiti `_load_tariff_description_from_db` u TariffService** (sa `nivo`) | Uklanja duplikat + 3-layer kršenje | Srednji | Novi test sa nivo parametrom |
| 4 | **Izdvojiti NaimenovanjaController** | 3-layer compliance, testabilnost | Srednji | Karakterizacioni testovi |
| 5 | **Premjestiti `_run_historical_tariff_validation` u worker** | Ne blokira UI | Srednji | QThread test |
| 6 | **`_on_import_xml` u worker** | Ne blokira UI | Nizak | XML test |
| 7 | **`cancel()` za ChatWorker/TariffLLMWorker** | Prekidivost | Nizak | Worker lifecycle test |
| 8 | **`quit()/wait()` u closeEvent** | Graceful shutdown | Nizak | closeEvent test |
| 9 | **Obrisati legacy metode** (nakon Faze 8) | Čist kod | Nizak | Paritet testovi |

---

## ŠTA NIJE POTVRĐENO (negativni rezultati)

- **Signalne petlje**: `_validation_generation` counter i `is_loading` guard pravilno sprečavaju petlje. PASS 1/PASS 2 optimizacija je dobra.
- **`disconnect()` except blokovi**: Opravdani Qt pattern (TypeError ako nije konektovano).
- **`blockSignals` u FakturaView**: Pravilno korišćeno na svim bulk mjestima.
- **`naimenovanja_view.py` drift**: Identičan root/dist_client (nema problema).
- **Mrtav kod u NaimenovanjaView**: `__main__` blok je za standalone test (prihvatljivo).

---

## OČEKIVANA KORIST ZA SVAKU IZMJENU

1. **zfill fix**: Uklanja PRAVNI RIZIK — shipped build više ne proizvodi pogrešne tarife.
2. **TariffService migracija**: Uklanja §44 bug + N+1 + omogućava testiranje.
3. **NaimenovanjaController**: Omogućava testiranje poslovne logike bez Qt.
4. **Worker migracija**: UI se ne zamrzava pri validaciji/importu.
5. **cancel()**: Korisnik može prekinuti dugotrajne LLM pozive.
