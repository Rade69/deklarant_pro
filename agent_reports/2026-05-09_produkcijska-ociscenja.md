# Izvještaj sesije — 9. Maj 2026 (III)

## Tema
Produkcijska čišćenja: mrtav kod, bare except, pool timeout, duplikati get_db_connection, graceful shutdown.

---

## Šta je urađeno (redosljed lakše → teže)

### 1. Obrisan mrtav kod — `deklarant_xml_builder.py`
- Fajl nije imao nijednog importa u projektu
- Obrisan `git rm` bez zamjene

### 2. Prazni `except` blokovi — 5 lokacija
| Fajl | Lokacija | Fix |
|------|----------|-----|
| `blagic_importer.py` | red parsing loop | `except Exception as e` + debug log |
| `blagic_attos_importer.py` | packing lista detekcija | `except Exception as e` + debug log |
| `backup_service.py` | PathSettings fallback | bare `except:` → `except Exception as e` |
| `analytics_service.py` | 3 mjesta | `except Exception as e` + debug log |

### 3. Pool timeout za `ThreadedConnectionPool`
- `psycopg2.ThreadedConnectionPool` nema built-in `pool_timeout` parametar
- Implementiran retry loop sa 30s timeout — baca `PoolError` ako konekcija nije dostupna
- Lokacija: `database/db.py` — `get_db_connection()` context manager

### 4. Duplikati `get_db_connection` — 2 lokacije
- `historical_learning_service_safe.py`: `self.get_db_connection()` je čitao `.env` direktno sa hardkodiranim fallback vrijednostima — delegirano na centralni pool
- `exporter_xml_indexer.py`: koristio `get_db_settings()` ali bez `sslmode` i `RealDictCursor` — dodano za konzistentnost

**Napomena:** `exporter_xml_indexer.py` i dalje koristi raw `psycopg2.connect()` (ne pool) jer koristi `conn = f()` pattern bez context managera. Nije refaktorisan da ne bi zahtijevao promjenu 5 call sitova.

### 5. Circular dependency — lažni alarm
GitNexus je označio `ImportService.import_file → _try_combine_with_previous → self.registry.import_file` kao kružnu zavisnost. To je lažni alarm — `self.registry` je `StrategyRegistry` (druga klasa), ne `ImportService`. Nema rizika od rekurzije.

### 6. Graceful shutdown za QThread workere — 3 panela
Pattern uzet iz `learning_panel.py` koji već ima `_stop_worker`:
- `DatabasePanel`: `closeEvent` → quit/wait za `_conn_thread` i `_stats_thread`
- `AnalyticsPanel`: `closeEvent` → quit/wait za `_thread`
- `QuotaPanel`: `closeEvent` → quit/wait za `_worker`

---

## Commitovi

| Hash | Opis |
|------|------|
| `17008ec` | fix(cleanup): ukloni mrtav kod i popravi bare except blokove |
| `70e46a0` | fix(database): pool timeout i uklanjanje duplikata get_db_connection |
| `6b06bef` | fix(gui): dodaj graceful shutdown closeEvent za QThread workere |
