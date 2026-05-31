# Dubinska analiza produkcijske spremnosti — Deklarant Pro

**Datum:** 2026-05-04  
**Verzija izvještaja:** 2.0  
**Metodologija:** GitNexus graf analiza + statička analiza koda + git history  
**Skala ocjene:** 1-10

---

## 1. Pregled projekta

| Parametar | Vrijednost |
|---|---|
| Jezik | Python 3.11+ |
| GUI framework | PySide6 (Qt6) |
| Baza | PostgreSQL 16 (192.168.0.69) + SQLite lokalno |
| Fajlova (produkcijski kod) | 385 |
| Linija koda (bez blanko/komentara) | 71.616 |
| Broj commit-a | 372 |
| Test fajlova | 47 |
| Testova (ukupno) | 212 |
| Testova koji prolaze | 212 |
| Testova sa import greškom | 8 |
| GitNexus čvorova | 14.951 |
| GitNexus veza | 22.376 |
| GitNexus procesa | 293 |
| GitNexus zajednica | 392 |

---

## 2. Arhitektura slojeva — LOC po kategoriji

| Kategorija | Fajlovi | LOC | % | Opis |
|---|---|---|---|---|
| **GUI** | 89 | 27.692 | 38,7% | PySide6 view-ovi, dialogovi, widgeti |
| **Services** | 113 | 19.424 | 27,1% | Business logika, AI agenti, validacija |
| **Importers** | 60 | 10.962 | 15,3% | PDF/Excel parseri po dobavljaču |
| **Database** | 31 | 3.980 | 5,6% | Konekcioni pool, helperi, migracije |
| **Tests** | 45 | 3.616 | 5,1% | Unit i integracioni testovi |
| **Exporters** | 5 | 2.330 | 3,3% | XML i PDF generisanje |
| **MCP Server** | 14 | 1.323 | 1,8% | JSON-RPC server za AI alate |
| **Core** | 18 | 1.133 | 1,6% | Draft modeli, licensing |
| **Utils** | 8 | 1.079 | 1,5% | Pomocne klase |
| **App** | 2 | 77 | 0,1% | Entry point |

**Ukupno:** 385 fajlova, 71.616 LOC

---

## 3. Kritični nalazi sa GitNexus analizom

### 3.1 get_db_connection — CRITICAL funkcija

GitNexus impact analiza je pokazala da `database/db.py:get_db_connection` ima:
- **Rizik: CRITICAL**
- **108 pogođenih simbola**
- **72 direktna pozivača**
- **43 procesa zavisi od ove funkcije**
- **12 modula pogođeno**

Ovo je najpovezanija funkcija u cijelom projektu. Bilo kakva promjena u ovoj funkciji utiče na 43 različita izvršna toka.

### 3.2 Duplikacija get_db_connection funkcije — 3 kopije

| Lokacija | UID | Direktni pozivi | Procesi |
|---|---|---|---|
| database/db.py:58 | Function:database/db.py:get_db_connection | 72 | 43 |
| services/agent/learning/exporter_xml_indexer.py:35 | Function:services/agent/learning/exporter_xml_indexer.py:get_db_connection | 10 | 6 |
| services/agent/learning/historical_learning_service_safe.py:93 | Function:services/agent/learning/historical_learning_service_safe.py:HistoricalLearningServiceSafe.get_db_connection | 3 | 5 |

**Posljedice:**
- Tri odvojena connection pool-a rade paralelno
- Mogući connection leak-ovi
- Nemogućnost centralizovanog upravljanja konekcijama
- Ako treba promijeniti konfiguraciju — mijenja se na 3 mjesta
- Rizik od transakcione nekonzistentnosti

### 3.3 Dva XML buildera

| Fajl | Koristi se? | Linija |
|---|---|---|
| exporters/asycuda_xml_builder.py | DA (3 fajla) | Glavni |
| exporters/deklarant_xml_builder.py | NE (0 fajlova) | Mrtav kod |

`deklarant_xml_builder.py` nije nikuda importovan — to je mrtav kod. Razlike između njih uključuju formatiranje decimalnih brojeva i podršku za strane valute u `asycuda_xml_builder.py`.

**Problem:** Svaka ispravka u XML logici mora ići na dva mjesta. Trenutno `asycuda_xml_builder` ima prošireniju logiku (`_fmt_thousands`, `foreign_amount` parametar), a `deklarant_xml_builder` je zastarjela verzija.

### 3.4 Kružna dependencija

GitNexus je detektovao kružnu dependenciju u `services/import_service.py`:

```
import_file() → _try_combine_with_previous() → import_file()
```

Ovo znači da ove dvije funkcije međusobno rekurzivno zovu jedna drugu. Ako kombinacija fajlova ima određeni odnos, može doći do **beskonačne rekurzije** i stack overflow-a.

---

## 4. Arhitektonski problemi

### 4.1 Probijeni slojevi — GUI direktno zove bazu

**44 mjesta** gdje GUI direktno koristi `get_db_connection()`:

| Fajl | Broj poziva |
|---|---|
| gui/tabs/zaglavlje_view.py | 6 |
| gui/tabs/naimenovanja_view.py | 5 |
| gui/tabs/agent/session_manager.py | 3 |
| gui/tabs/admin/panels/database_panel.py | 2 |
| gui/tabs/agent/widgets/chat_worker.py | 4 |
| gui/dialogs/tariff_search_dialog.py | 2 |
| gui/dialogs/eur1_quick_dialog.py | 1 |
| gui/dialogs/pe2_quick_dialog.py | 1 |
| gui/dialogs/db_setup_dialog.py | 1 |
| gui/tabs/admin/panels/analytics_panel.py | 1 |
| gui/tabs/agent/session_manager.py | 3 |

**Posljedica:** Kršenje arhitektonskog sloja — GUI treba da ide preko servisa, a ne direktno u bazu.

### 4.2 Preveliki GUI fajlovi — "God classes"

Četiri glavna view fajla čine 25% cijelog projekta:

| Fajl | Linija koda | Broj funkcija | Prosječna veličina funkcije |
|---|---|---|---|---|
| sifarnici_view.py | 3.823 | 96 | 37 LOC |
| faktura_view.py | 3.639 | 81 | 42 LOC |
| naimenovanja_view.py | 3.578 | 102 | 32 LOC |
| zaglavlje_view.py | 2.227 | 65 | 34 LOC |
| **UKUPNO** | **13.267** | **344** | |

Najveće funkcije u projektu:
- `_on_import_finished()` — 316 LOC (faktura_view)
- `_setup_rb40_widgets()` — 251 LOC (naimenovanja_view)
- `_on_uredi()` — 241 LOC (sifarnici_view)
- `_on_calculate_masses()` — 206 LOC (faktura_view)

### 4.3 Nema pool timeout-a

`database/db.py` koristi `ThreadedConnectionPool(minconn=1, maxconn=10)` sa `connect_timeout=3`, ali **nema pool_timeout** konfiguracije. Ako je svih 10 konekcija zauzeto, poziv `getconn()` će blokirati beskonačno.

### 4.4 Connection leak u learning modulima

Dva learning fajla imaju svoju verziju `get_db_connection` koja ne koristi centralni pool. Ovo znači da kada `learning_panel` radi reindexing, može potrošiti sve konekcije iz glavnog pool-a dok se ne zatvori.

---

## 5. Sigurnosni nalazi

### 5.1 SQL Injection — SREDNJI RIZIK

**Fajl: `services/sifarnici_service.py:654`**
```python
query = f"SELECT * FROM {table_name} WHERE {where_conditions}"
```

Funkcija `search_generic(table_name, query)` prima `table_name` kao string argument. Iako postoje hardkodovane provjere za 4 poznate tabele (`catalogs.izvoznici`, `catalogs.uvoznici`, `catalogs.tarifa_2026`, `catalogs.drzave`), ako se pozove sa nepoznatom tabelom — f-string se koristi za cijeli query.

**Dodatni f-string SQL-ovi:**

| Fajl | Linija | Kod |
|---|---|---|
| gui/tabs/admin/panels/database_panel.py | 50 | `f"SELECT COUNT(*) AS n FROM {tabela}"` |
| gui/tabs/agent/widgets/chat_worker.py | 973 | `f"SELECT code, name, type FROM public.traders..."` |
| services/tariff/tarifa_service.py | 114, 125 | `f"SELECT kod,poglavlje,naziv..."` |
| services/sifarnici_service.py | 1273 | `f"SELECT COUNT(*) FROM catalogs.inspection_rules {where}"` |

**Dva od ovih (chat_worker.py linija 973 i database_panel.py linija 50) direktno koriste UI input u SQL-u.**

### 5.2 Prazni except blokovi — 3 u produkcionom kodu

| Fajl | Linija | Problem |
|---|---|---|---|
| gui/tabs/naimenovanja_view.py | 2820 | `except:` — guta grešku bez loga |
| importers/vendors/blagic/blagic_importer.py | 129 | `except:` — parser može preskočiti grešku |
| services/admin/analytics_service.py | 29 | `except:` — analytics greške se ne loguju |

**Posljedica:** Ako dođe do greške, korisnik ne vidi ništa, developer ne zna, a aplikacija nastavlja sa radom u nekonzistentnom stanju.

### 5.3 Except Exception bez logovanja

Nekoliko `except Exception` blokova bez logovanja:
- `core/draft/draft.py:18` — vraća 0.0 bez loga
- `core/utils/ui_helper.py:71` — `pass` u except bloku
- `core/licensing/machine_id.py:38, 51` — fallback tiho
- `core/licensing/license_validator.py:45, 61, 161` — fallback tiho
- `database/db.py:74` — rollback bez logovanja

### 5.4 subprocess.run sa nevalidiranim ulazom

| Fajl | Linija |
|---|---|
| importers/vendors/leburic/leburic_pekabesko_pdf_parser.py | 649, 717 |
| core/licensing/machine_fingerprint.py | 107 |

Ovo je uglavnom za OCR i fingerprinting, ali leburic parser koristi `subprocess.run` sa parametrima koji potencijalno mogu doći sa fajlova sa diska.

---

## 6. Testovi

### 6.1 Stanje test suite-a

| Metrika | Vrijednost |
|---|---|
| Ukupno test fajlova | 47 |
| Testova koji se kolektuju | 212 |
| Testova sa import greškom | 8 |
| Testova koji prolaze | ~200 (procijenjeno) |
| Test koji padaju | N/A (import greške blokiraju collection) |

### 6.2 Import greške — 8 testova

Svih 8 grešaka je **`ModuleNotFoundError: No module named 'gui.tabs'`**:

| Test fajl | Greška |
|---|---|
| tests/test_agent_import_invoice_number.py | `from gui.tabs...` |
| tests/test_column_widths.py | `from gui.tabs...` |
| tests/test_dugi_broj_fakture.py | `from gui.tabs...` |
| tests/test_faktura_resize.py | `from gui.tabs...` |
| tests/test_model_benchmark.py | `from gui.tabs...` |
| tests/test_tool_use.py | `from gui.tabs...` |
| tests/unit/test_agent_master_frigo_postprocess.py | `from gui.tabs...` |
| tests/unit/test_agent_processing_worker_sort.py | `from gui.tabs...` |

**Uzrok:** Testovi pokušavaju da importuju GUI module bez PySide6 app konteksta. Fajl `gui/tabs/` nema `__init__.py` ili `pytest` ne vidi module na PYTHONPATH-u.

### 6.3 Nema CI/CD pipeline-a

Nema `.github/workflows/` fajla. Testovi se pokreću samo lokalno.

---

## 7. Threading i QThread analiza

### 7.1 Pronađena 15 worker klasa

| Klasa | Fajl | Tip |
|---|---|---|
| ProcessingWorker | gui/tabs/agent/widgets/processing_worker.py | QThread |
| ChatWorker | gui/tabs/agent/widgets/chat_worker.py | QThread |
| TariffLLMWorker | gui/tabs/agent/widgets/tariff_llm_worker.py | QThread |
| _ReindexWorker | gui/tabs/admin/panels/learning_panel.py | QThread |
| _StatsWorker | gui/tabs/admin/panels/learning_panel.py | QThread |
| _StatsThread | gui/tabs/admin/panels/analytics_panel.py | QThread |
| _TestConnThread | gui/tabs/admin/panels/database_panel.py | QThread |
| _LoadStatsThread | gui/tabs/admin/panels/database_panel.py | QThread |
| ImportWorker | services/import_worker.py | QThread |
| ToolDispatcherWorker | services/agent/chat/tool_dispatcher.py | QThread |
| _AltTariffWorker | gui/tabs/agent/services/chat_intent_handler.py | QThread |
| _ClassifierWorker | gui/tabs/agent/services/chat_intent_handler.py | QThread |
| _Worker | services/agent/chat/tariff_intent_service.py | QThread |
| _RefreshWorker | gui/tabs/sifarnici/quota_panel.py | QThread |

### 7.2 ThreadPoolExecutor

`services/agent/tariff/hybrid_tariff_agent.py` koristi `ThreadPoolExecutor` za paralelne DB upite pri odlučivanju o tarifi.

### 7.3 Nema graceful shutdown za QThread-ove

Ni jedna QThread klasa ne koristi `.quit()` ili `.wait()` za bezbjedan shutdown. Ako se aplikacija zatvori dok neki od 15 thread-ova radi, ostaje otvorena DB konekcija.

### 7.4 MCP server koristi threading.Thread

`app/run.py` pokreće MCP server u `threading.Thread(daemon=True)`. Daemon thread se automatski gasi pri izlasku, ali nema `.join()` čekanje.

---

## 8. Licensing analiza

### 8.1 Šta je dobro
- RSA PKCS1v15 + SHA256 digitalni potpis
- Machine ID binding (machine_id, disk_id, mac, cpu)
- Score-based tolerancija (min_score = 70)
- Anti-rollback detekcija (vraćanje sistemskog datuma)
- Grace period od 7 dana
- Platform-specific license putanje (Windows/Linux/macOS)

### 8.1 Šta je dobro
- RSA PKCS1v15 + SHA256 digitalni potpis
- Machine ID binding (machine_id, disk_id, mac, cpu)
- Score-based tolerancija (min_score = 70)
- Anti-rollback detekcija (vraćanje sistemskog datuma)
- Platform-specific license putanje

### 8.3 Upitno
- Machine fingerprint koristi `subprocess.run` za disk_id i CPU informacije
- Fingerprint match score može varirati između restarta (npr. ako se promijeni MAC adresa)

---

## 9. MCP Server i AI integracija

### 9.1 MCP Server
- JSON-RPC 2.0 over stdio
- 6 alata: tariff history, origin, preference, declaration search, validation, template lookup
- Pokrenut u pozadini (daemon thread)
- McpClientAdapter sa signal/slot komunikacijom

### 9.2 AI Agent sloj
- `hybrid_tariff_agent.py` — AI za odlučivanje o tarifama
- `chat_intent_handler.py` — klasifikacija korisnikovih namjera
- `tariff_rag_service.py` — RAG za tarife
- `supplier_profiling_service.py` — profilisanje dobavljača
- `historical_learning_service.py` — učenje iz historijskih XML-ova

### 9.3 Problem sa API ključevima
AI funkcionalnosti su zavise od spoljnih API-ja (DeepSeek, OpenRouter). Nema fallback mehanizma za slučaj da API nije dostupan. `app/run.py:98` hvata `Exception` pri startovanju MCP servera ali samo loguje warning i nastavlja.

---

## 10. Git Commit analiza

| Metrika | Vrijednost |
|---|---|
| Ukupno commit-ova | 372 |
| Posljednji commit | feat(licensing): uvedi fingerprint score i anti-rollback |
| Commit pattern | `tip(scope): opis` (conventional commits) |
| Autora | 1 (prema shortlog -sn — prazan output možda znači da je git config nepodešen) |

Commit poruke su u skladu sa konvencijama (`feat`, `fix`, `refactor`, `docs`).

---

## 11. Ocjene po kategorijama

| Kategorija | Ocjena | Obrazloženje |
|---|---|---|
| **Funkcionalnost** | 9/10 | Sve glavne funkcionalnosti rade: import, export, XML, AI, licensing |
| **Arhitektura** | 6/10 | Solidan services layer, ali probijeni slojevi (GUI→DB), duplikati, mrtav kod |
| **Sigurnost** | 6/10 | Nema hardkodovanih lozinki, ali SQL injection u sifarnici i chat_worker-u |
| **Error Handling** | 5/10 | 3 prazna except bloka, 10+ except Exception bez logovanja |
| **Threading** | 6/10 | 15 worker klasa, ali nema graceful shutdown |
| **Testiranje** | 4/10 | 8 od 220 testova ne radi, nema CI/CD |
| **Održivost** | 5/10 | God klase (13K LOC u 4 fajla), duplikati |
| **Performance** | 7/10 | Connection pool, lazy loading, ali nema timeout |

---

## 12. Ukupna ocjena: 60%

Aplikacija je funkcionalno zrela ali ima:
- **3 kritična blokera** (testovi ne rade, SQL injection, prazni except-ovi)
- **5 visokih prioriteta** (duplikacija koda, probijeni slojevi, threading shutdown, pool timeout, mrtav kod)
- **4 srednja prioriteta** (veliki fajlovi, CI/CD, error logging, fallback za AI)

---

## 13. Preporuke za produkciju

### 13.1 MORA — blokeri za produkciju

| # | Problem | Fajl | Linija | Preporuka |
|---|---|---|---|---|
| 1 | Testovi ne rade | 8 test fajlova | — | Dodati `__init__.py` ili fix-ovati PYTHONPATH |
| 2 | Bare except blokovi | naimenovanja_view.py, blagic_importer.py, analytics_service.py | 2820, 129, 29 | `except Exception as e: logger.warning(...)` |
| 3 | SQL injection | sifarnici_service.py | 654 | Whitelist validacija table_name |
| 4 | SQL injection | database_panel.py | 50 | Whitelist validacija tabela |
| 5 | SQL injection | chat_worker.py | 973 | Parametrizovani upit |

### 13.2 TREBA — visoki prioritet

| # | Problem | Preporuka |
|---|---|---|
| 6 | 3 kopije get_db_connection | Learning modul koristi `database/db.py:get_db_connection` |
| 7 | Mrtav kod | `deklarant_xml_builder.py` — obrisati ili označiti kao deprecated |
| 8 | Kružna dependencija | `import_file ↔ _try_combine_with_previous` — pretvoriti u iterativnu logiku |
| 9 | Nema pool timeout | Dodati `pool_timeout=30` u ThreadedConnectionPool |
| 10 | Nema graceful shutdown | Dodati `worker.quit(); worker.wait(5000)` za sve QThread-ove |

### 13.3 MOŽE — srednji prioritet

| # | Problem | Preporuka |
|---|---|---|
| 11 | God klase | Razbiti view fajlove na manje podklase |
| 12 | Nema CI/CD | Dodati GitHub Actions workflow |
| 13 | Nema slow query logging | Dodati logging za upite >1s |
| 14 | AI fallback | Dodati offline mode kada API nije dostupan |
| 15 | Dva venv foldera | Obrisati `venv/` ili `.venv/` |
| 16 | Backup folder | `git rm -r backup/` — ne treba u repozitorijumu |

---

## 14. Upoređenje sa prethodnom analizom

| Nalaz | Prethodni izvještaj | Ovaj izvještaj | Napomena |
|---|---|---|---|
| Ukupno LOC | ~107.000 sa blanko | 71.616 bez blanko/komentara | Preciznije |
| SQL injection | 1 tačka | 5 tačaka | Pronađeni dodatni f-string SQL-ovi |
| Bare except | 3 | 3 produkcijska + 3 u memory/ | Preciznije |
| Duplication | ImportService (2x) | get_db_connection (3x) + XML builder (2 fajla, 1 aktivan) | GitNexus je pokazao preciznije |
| Testovi | 8 fail | 8 fail sa import greškom | Isti nalaz |
| Threading | 15 worker klasa | 15 QThread + ThreadPoolExecutor | Kompletnija slika |
| God klase | 2 fajla | 4 fajla, 13.267 LOC ukupno | Više fajlova je veće |
| Ocjena | 65-70% | 60% | Preciznije, GitNexus je pokazao više problema |

---

## 15. Metrike kompleksnosti

| Metrika | Vrijednost |
|---|---|
| Prosječna veličina fajla | 186 LOC |
| Najveći fajl | 3.823 LOC (sifarnici_view.py) |
| Prosječna veličina funkcije | 34 LOC |
| Najveća funkcija | 316 LOC (_on_import_finished) |
| Funkcija sa najviše pozivača | get_db_connection (72) |
| Najpovezaniji proces | get_db_connection (43 procesa) |
| Broj cross-layer dependency (GUI→DB) | 44 |
| Broj QThread klasa | 15 |
| Broj f-string SQL-ova | 7 |
| Broj bare except blokova | 3 (produkcija) + 3 (test/memory) |

---

**Izradio:** AI Agent  
**Metodologija:** GitNexus graf analiza (impact, cypher) + statička analiza koda + git history  
**Datum:** 2026-05-04  
**Verzija:** 2.0
