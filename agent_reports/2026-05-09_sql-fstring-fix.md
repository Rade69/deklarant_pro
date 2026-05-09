# Izvještaj sesije — 9. Maj 2026 (II)

## Tema
Sigurnosni fix: zamjena f-string SQL upita sa `psycopg2.sql` modulom.

---

## Šta je urađeno

Zamjenjena su 4 mjesta u kodu gdje su SQL upiti građeni f-string interpolacijom umjesto parametrizovanim upitima.

---

## Analiza rizika

Nijedan od 4 slučaja nije bio **aktivni exploit** — nijedan nije direktno umetao korisnički unos u SQL string. Međutim, svi su bili **loša praksa** jer:

- f-string pattern je "zarazan" — novi kod koji se doda u istu funkciju može slučajno naslijediti isti stil i biti ranjiv
- `update_inspection_rule` koristi `ALLOWED` whitelist koji ako se ikad pogrešno proširi → injection
- Svaka buduća refactoring greška (npr. zamjena `filtered.keys()` sa user inputom) → kritična ranjivost

---

## Kako je urađeno

### 1. `sifarnici_service.py` — `count_inspection_rules`

**Prije:**
```python
where = "WHERE is_active = TRUE" if only_active else ""
cur.execute(f"SELECT COUNT(*) FROM catalogs.inspection_rules {where}")
```

**Poslije:** Dvije odvojene statičke query-je bez interpolacije.

---

### 2. `sifarnici_service.py` — `update_inspection_rule`

**Prije:**
```python
set_clause = ", ".join(f"{k} = %s" for k in filtered)
cur.execute(f"UPDATE catalogs.inspection_rules SET {set_clause}...", vals)
```

**Poslije:** `sql.Identifier` za nazive kolona — čak i kad su iz whiteliste, kolone se pravilno escapuju.

---

### 3. `chat_worker.py` — `_search_pg_partners`

**Prije:**
```python
or_clause = " OR ".join(["name ILIKE %s"] * len(patterns))
cur.execute(f"SELECT ... WHERE {or_clause} LIMIT 15", patterns)
```

**Poslije:** `pg_sql.SQL` kompozicija + dodan `from psycopg2 import sql as pg_sql`.

---

### 4. `database_panel.py` — `StatsWorker.run`

**Prije:**
```python
cur.execute(f"SELECT COUNT(*) AS n FROM {tabela}")
```

**Poslije:** `pg_sql.Identifier` za schema i tabelu + dodan import.

---

## Zašto nije korišten alternativni pristup

Razmatrana je whitelist validacija table_name stringova (iz analize), ali `psycopg2.sql` je bolji pristup jer:
- Escapovanje je automatsko i ispravno za sve edge case-ove
- Ne zahtijeva održavanje whiteliste
- Konzistentno sa ostatkom koda (sifarnici_service već koristio `sql` u `search_generic`)

---

## Commitovi

| Hash | Opis |
|------|------|
| `85fc135` | fix(security): zamijeni f-string SQL upite sa psycopg2.sql |
