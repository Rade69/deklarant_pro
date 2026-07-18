# Agent Report — 2026-07-18: VARCHAR(10) fix + Medicopharm debug cleanup

## Datum
2026-07-18

## Agent
Claude Sonnet 4.6

## Scope
- `services/tariff/tariff_mapping_service.py`
- `database/migrations/008_fix_tariff_mapping_column_types.sql` (novi fajl)
- `importers/vendors/medicopharm/medicopharm_importer.py` + dist_client mirror

---

## GitNexus impact
LOW — sve promjene su defanzivne ili cleanup. Nijedan potpis funkcije se nije promijenio.

---

## Šta je urađeno

### 1. VARCHAR(10) greška u `save_mapping` (commit `b8e77a4`)

**Simptom**: `value too long for type character varying(10)` pri uvozu Medicopharm fakture.

**Uzrok**: Kolone `product_code`, `zemlja_porijekla`, `povlastica`, `precision_1`, `supplier`
u tabeli `catalogs.product_tariff_mapping` imaju `CHARACTER VARYING(10)` — naknadno dodavane
s kratkim tipom. Farmaceutski kodovi (npr. `EAN3838989010099`) prelaze 10 karaktera.

**Fix 1 — defanzivna truncacija** u `save_mapping`:
```python
pc  = (product_code    or "")[:200]
zp  = (zemlja_porijekla or "")[:10]
pov = (povlastica       or "")[:20]
pr1 = (precision_1      or "000")[:10]
```
Spriječava pad aplikacije dok migracija nije puštena.

**Fix 2 — migracija 008** (`database/migrations/008_fix_tariff_mapping_column_types.sql`):
```sql
ALTER TABLE catalogs.product_tariff_mapping
    ALTER COLUMN product_code    TYPE TEXT,
    ALTER COLUMN zemlja_porijekla TYPE TEXT,
    ALTER COLUMN povlastica      TYPE TEXT,
    ALTER COLUMN precision_1     TYPE TEXT,
    ALTER COLUMN supplier        TYPE TEXT;
```
Nakon migracije truncacija u kodu ostaje kao sigurnosna mreža ali ne kranji kod.

### 2. Medicopharm debug print cleanup (commit `c8ac48a`)

4 `print()` poziva u `_extract_origin_statement_item_set` zamijenjeni `logger` pozivima:
- `print("⚠️  regex nije pronašao...")` → `logger.warning(...)`
- `print("🔍 Izjava segment: ...")` → uklonjen (segment-level debug suvišan u produkciji)
- `print("✅ Pokrivene stavke: ...")` → `logger.info(...)`
- `print("⚠️  BEZ povlastice: ...")` → spojen u jedan `logger.info` sa prethodnim

---

## Šta nije dirano

- Logika parsiranja izjave o porijeklu (`_extract_origin_statement_item_set`) — ista
- `correct_mapping` metoda u `tariff_mapping_service.py` — nepromjenjena
- Ostali debug printovi u medicopharm importeru koji su još korisni

---

## Verifikacija

- `py_compile` OK za sva 3 Python fajla (root i dist_client mirror)
- `logger` varijabla postoji u medicopharm importeru: `logging.getLogger("deklarant_pro.import.medicopharm")`

---

## Potreban follow-up

- **Pokrenuti migraciju 008 na serveru**:
  ```bash
  psql -h 192.168.0.41 -U deklarant_user -d deklarant_sistem \
       -f database/migrations/008_fix_tariff_mapping_column_types.sql
  ```
  Do tada defanzivna truncacija u kodu sprječava pad, ali `product_code > 10 char`
  se tiho odbacuje.

---

## Commitovi

| Hash | Poruka |
|------|--------|
| `b8e77a4` | fix(tariff): defensive truncation u save_mapping + migracija 008 za VARCHAR(10) |
| `c8ac48a` | fix(medicopharm): ukloni debug print, koristi logger u _extract_origin_statement_item_set |

---

## Potrebna korisnička potvrda

- Pokrenuti migraciju 008 na PostgreSQL serveru (vidi gore)
- Nakon migracije: uvesti Medicopharm fakturu i provjeriti da nema `value too long` u logu
