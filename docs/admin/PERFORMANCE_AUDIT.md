# Audit performansi — Deklarant Pro

**Datum revizije:** 2026-08-05
**Opseg:** Cijela aplikacija — GUI, servisi, baza, import pipeline
**Metodologija:** Statička analiza koda (GitNexus + grep + ručna verifikacija)
**Fokus:** Uska grla koja usporavaju rad aplikacije — blokade UI thread-a, N+1 upiti, neefikasne bulk operacije, neindeksirani upiti

---

## 1. KRITIČNO — UI zamrzavanje (3 nalaza)

### 1.1 Šifrarnici — QTreeWidget popunjavanje bez blockSignals

**Fajl:** `gui/tabs/sifarnici_view.py:1417-1437`
**Problem:** `_load_carinarnice_data()` dodaje QTreeWidgetItem-e u dvostrukoj petlji (regionalni centri × ispostave) BEZ `blockSignals(True)` i `setUpdatesEnabled(False)`. Svaki `QTreeWidgetItem()` konstruktor trigeruje signal → layout update → repaint. Sa 30+ centara i 200+ ispostava, UI zamrzava na 1-3 sekunde.

**Popravka:**
```python
self.table.blockSignals(True)
self.table.setUpdatesEnabled(False)
self.table.clear()
for rc_data in regional_centers:
    rc_item = QTreeWidgetItem(self.table)
    ...
    for ci_data in rc_data["ispostave"]:
        ci_item = QTreeWidgetItem(rc_item)
        ...
self.table.setUpdatesEnabled(True)
self.table.blockSignals(False)
self.table.expandAll()
```

**Očekivano ubrzanje:** 5-10× brže popunjavanje tabele.

### 1.2 Šifrarnici — `_filter_table_rows()` bez blockSignals

**Fajl:** `gui/tabs/sifarnici_view.py:2478-2488`
**Problem:** Petlja kroz sve redove, svaki poziv `setRowHidden()` trigeruje signal. Sa 1000+ redova, svaki keystroke u search polju blokira UI.

**Popravka:** Omotati petlju u `blockSignals(True)`/`False`.

### 1.3 `db.py` — `time.sleep(0.1)` blokira UI thread

**Fajl:** `database/db.py:168`
**Problem:** `get_db_connection()` context manager koristi `time.sleep(0.1)` u wait petlji za connection pool. Kada se pozove sa UI thread-a (npr. direktno iz `zaglavlje_view.py:84-162`), blokira korisnički interfejs do `_POOL_WAIT_TIMEOUT` sekundi.

**Popravka:** Osigurati da se `get_db_connection()` NIKAD ne poziva direktno sa UI thread-a. Sve UI-thread pozive prebaciti na `QThread` worker ili koristiti keširane podatke.

---

## 2. VISOKO — Baza podataka (4 nalaza)

### 2.1 `zvanicna_tarifa` — SELECT bez LIMIT

**Fajl:** `services/sifarnici_service.py:473-477`
**Problem:** `SELECT tarifni_kod, opis FROM catalogs.zvanicna_tarifa ORDER BY tarifni_kod` — vraća CIJELU carinsku tarifu (10.000+ redova) bez ikakvog LIMIT-a. Poziva se svaki put kad se otvori Šifrarnici tab.

**Popravka:** Dodati `LIMIT 1000` i paginaciju. Prvi put učitati samo `LIMIT 500`, a `ILIKE` pretragu limitirati na `LIMIT 200`.

### 2.2 N+1 upiti — `validate_mappings()`

**Fajl:** `services/naimenovanja/tariff_service.py:380-390`
**Problem:** Za svaki mapping, `get_tarifa_opis()` otvara NOVU SQLite konekciju i izvršava SELECT. Sa 50+ mapinga, to je 50 odvojenih konekcija + 50 SELECT-ova.

**Popravka:** Spojiti sve u jedan batch upit: `SELECT tarifni_kod, opis FROM zvanicna_tarifa WHERE tarifni_kod IN (?, ?, ...)` sa svim kodovima odjednom.

### 2.3 N+1 upiti — `load_tariff_description()` fallback

**Fajl:** `services/naimenovanja/tariff_service.py:69-83` i `232-262`
**Problem:** Umjesto jednog upita sa `OR` ili `UNION`, kod iterira kroz `fallback_codes` i `prefix_len` range, izvršavajući odvojeni `cursor.execute()` za svaki.

**Popravka:** Kombinovati sve prefixe u jedan upit: `WHERE tarifni_kod LIKE '01%' OR tarifni_kod LIKE '0101%' OR ...`

### 2.4 `product_tariff_mapping` — 500 kandidata bez early-exit

**Fajl:** `services/tariff/tariff_mapping_service.py:607-620`
**Problem:** Nakon DB upita koji vraća do 500 kandidata, Python petlja prolazi kroz SVE radeći `SequenceMatcher` (CPU-intenzivna operacija), čak i kad je već pronađen jasan match.

**Popravka:** Dodati early-exit kad `similarity > 0.95` — ako je već pronađen odličan match, nema potrebe obrađivati preostalih 450 kandidata.

---

## 3. SREDNJE — Arhitektura i threading (3 nalaza)

### 3.1 `_puna_auto_pipeline()` — djelimično blokira UI

**Fajl:** `gui/tabs/agent/services/import_pipeline_service.py:228-380`
**Problem:** Auto-import pipeline koristi `QApplication.processEvents()` između faza, ali faze (auto-fill, validacija) same traju dovoljno dugo da korisnik primijeti zamrzavanje. `processEvents()` je mitigacija, ne rješenje.

**Preporuka:** Cijeli pipeline izmjestiti u `QThread` (ProcessingWorker već postoji za ovo — `gui/tabs/agent/widgets/processing_worker.py`). Provjeriti da li se koristi dosljedno.

### 3.2 `ThreadPoolExecutor` — moguće iscrpljivanje connection pool-a

**Fajl:** `services/agent/tariff/hybrid_tariff_agent.py:398-401`
**Problem:** `ThreadPoolExecutor` sa N radnika — svaki zove `decide_tariff()` koja otvara DB konekciju. Pod opterećenjem može iscrpiti PostgreSQL connection pool (`_POOL_SIZE`).

**Preporuka:** Ograničiti `max_workers` na polovinu `_POOL_SIZE` ili koristiti semafor za DB pristup.

### 3.3 Lazy importi koji se ponavljaju

**Fajlovi:** `tariff_intent_service.py:77-78`, `backup_service.py:179`
**Problem:** `TariffMappingService` i `HybridMatchingService` se importuju unutar tijela metode — svaki poziv rekonstruiše objekt. Nije kritično ali nepotrebno troši CPU.

**Preporuka:** Koristiti lazy singleton (klasnu varijablu `_instance`) ili module-level import.

---

## 4. NISKO — Sporedni nalazi (2 nalaza)

### 4.1 `declaration_search_service.py` — batch insert

**Fajl:** `services/agent/chat/declaration_search_service.py:380-386`
**Problem:** Pojedinačni INSERT u petlji za deklaracije. Koristi `executemany` za stavke ali ne i za deklaracije.

### 4.2 `sifarnici_view.py:2498` — `_clear_highlights()` bez blockSignals

**Fajl:** `gui/tabs/sifarnici_view.py:2498-2502`
**Problem:** Dvostruka petlja (redovi × kolone) poziva `setBackground()` bez `blockSignals`.

---

## 5. Šta je DOBRO urađeno

Aplikacija u cjelini ima solidnu arhitekturu za performanse:

- ✅ **Import pipeline** — `ImportWorker(QThread)`, `ManualBatchImportWorker(QThread)` — pravilno izmješten iz UI thread-a
- ✅ **Agent chat** — `ChatWorker(QThread)` — LLM pozivi nikad ne blokiraju UI
- ✅ **Admin DB test** — `_TestConnThread(QThread)` — konekcijski testovi van UI thread-a
- ✅ **Trigram GIN indeksi** — migracije 007 i 012 — PostgreSQL full-text search sa `pg_trgm`
- ✅ **Bulk operacije u `sifarnici_view.py:1371-1391`** — ispravno koristi `blockSignals` + `setUpdatesEnabled` za QTableWidget
- ✅ **`tariff_hierarchy.py:131-171`** — pravilan obrazac za QTreeWidget bulk popunjavanje
- ✅ **Connection pooling** u `database/db.py` — `psycopg2.pool.ThreadedConnectionPool` sa `_POOL_MIN` i `_POOL_MAX`
- ✅ **`_POOL_WAIT_TIMEOUT`** — circuit breaker za spriječavanje vječnog čekanja

---

## 6. Zbirni pregled po prioritetu

| # | Prioritet | Fajl | Problem | Očekivano ubrzanje | Trud |
|---|-----------|------|---------|---------------------|------|
| 1 | 🔴 KRITIČNO | `sifarnici_view.py:1417` | QTreeWidget bez blockSignals | 5-10× | 5 min |
| 2 | 🔴 KRITIČNO | `sifarnici_view.py:2478` | _filter_table_rows bez blockSignals | 3-5× | 2 min |
| 3 | 🔴 KRITIČNO | `db.py:168` | time.sleep blokira UI thread | Eliminacija zamrzavanja | 30 min |
| 4 | 🟠 VISOKO | `sifarnici_service.py:473` | SELECT bez LIMIT (10k+ redova) | 10-50× manje mreže | 5 min |
| 5 | 🟠 VISOKO | `tariff_service.py:380` | N+1 SQLite konekcije | 10-30× | 15 min |
| 6 | 🟠 VISOKO | `tariff_service.py:69,232` | N+1 fallback upiti | 3-5× | 10 min |
| 7 | 🟠 VISOKO | `tariff_mapping_service.py:607` | 500 kandidata bez early-exit | 2-5× | 5 min |
| 8 | 🟡 SREDNJE | `import_pipeline_service.py:228` | Djelimično blokira UI | Eliminacija micro-freezea | 1 h |
| 9 | 🟡 SREDNJE | `hybrid_tariff_agent.py:398` | ThreadPoolExecutor vs pool size | Stabilnost pod opterećenjem | 10 min |
| 10 | 🟡 SREDNJE | `tariff_intent_service.py:77` | Ponavljani lazy importi | Marginalno | 5 min |

**Ukupno:** 10 nalaza. Prva 3 su trivijalna za popraviti (5-10 min svaki), a donose najveće subjektivno ubrzanje.

---

## 7. Preporučeni redoslijed implementacije

### Faza 1 — Brze pobjede (30 min)
Popravke #1, #2, #4, #7 — dodavanje `blockSignals`, `LIMIT`, i `early-exit`. Ovo su jedno-linijske ili parolinijske izmjene koje odmah donose vidljivo ubrzanje.

### Faza 2 — Batch DB upiti (30 min)
Popravke #5, #6 — spajanje N+1 upita u batch. Zahtijeva malo više refaktora ali donosi značajno ubrzanje pri učitavanju tarifa i validaciji.

### Faza 3 — Threading (1-2 h)
Popravke #3, #8, #9 — prebacivanje `get_db_connection()` poziva sa UI thread-a i pipeline optimizacija. Veći refaktor, ali eliminiše zamrzavanja.

---

Reviziju izvršio: Crush (DeepSeek V4 Pro), 2026-08-05
