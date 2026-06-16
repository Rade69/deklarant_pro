# 003 — Prilagodba aplikacije za više špediterskih kuća

**Datum:** 2026-05-01  
**Status:** Analiza i preporuke  
**Kontekst:** Aplikacija razvijena za jednu špeditersku kuću; pitanje šta treba za drugu

---

## Trenutno stanje — single-tenant

Aplikacija je razvijena za jednu konkretnu špeditersku kuću. Svi slojevi su
ispravni, ali neki sadrže podatke ili putanje specifične za tu kuću:

| Sloj | Šta je specifično |
|------|-------------------|
| **XML indeks** | `docs/NOVA ASIKUDA` — 2500+ XML fajlova iz njihove istorije |
| **SQLite indeks** | `declaration_index.db` — izgrađen iz njihovih XML fajlova |
| **PostgreSQL** | `exporter_xml_index`, `declaration_items`, `declarations` — njihovi podaci |
| **Baza znanja** | `catalogs.tarifa_nazivi`, `product_tariff_mapping` — izgrađeno iz njihove istorije |
| **Importeri** | `importers/` — pisani za njihove dobavljače i formate faktura |
| **Historijsko učenje** | `HistoricalLearningServiceSafe` — uči iz njihovih podataka |
| **Šifrarnici** | Partneri, deklarant, carinarnice — njihovi podaci |
| **Hardkodovane putanje** | `XML_DIR` u `declaration_search_service.py`, `XML_FOLDER` u `exporter_xml_indexer.py` |

---

## Šta je već generičko i ne treba dirati

Ovi slojevi su potpuno nezavisni od konkretne špedicije:

- **GUI** — svi tabovi, forme, tabele, dialogi. Samo prikazuju podatke iz baze.
- **Agent Tool Use** — 8 alata, DeepSeek routing, intent classifier. Ne zavise od podataka.
- **MCP server** — 6 read-only alata. Čitaju iz PostgreSQL baze, potpuno generički.
- **XML builder** — ASYCUDA format je standardizovan za sve špedicije u BiH.
- **Validacija** — carinska pravila (limit 99, tarifni lookup, inspekcijska pravila) su ista za sve.
- **Zaglavlje** — auto-popunjavanje rubrike 14 iz baze, generički mehanizam.

---

## Šta se mora uraditi za svaku novu špediciju

### Obavezni koraci (svaka instalacija)

| # | Korak | Vrijeme | Opis |
|---|-------|---------|------|
| 1 | **Nova PostgreSQL baza** | 15 min | Kreirati bazu, pokrenuti `setup_db.py`, sve migracije. Prazna šema, bez tuđih podataka. |
| 2 | **XML reindeksiranje** | 30-60 min | Postaviti njihove XML fajlove, pokrenuti `exporter_xml_indexer --reindex`. |
| 3 | **Unos deklaranta** | 5 min | U šifrarnike unijeti njihove podatke (JIB, Naziv, Adresa, Grad). |
| 4 | **Unos partnera** | 1-2 h | Unijeti izvoznike, uvoznike, primaoce iz njihove dokumentacije. |
| 5 | **`.env` konfiguracija** | 5 min | `DB_NAME`, `DB_HOST`, kredencijali za novu bazu. |

### Vjerovatni koraci (zavisi od špedicije)

| # | Korak | Vrijeme | Opis |
|---|-------|---------|------|
| 6 | **Novi importeri** | 1-5 dana | Ako imaju drugačije formate faktura (PDF layout, Excel struktura). |
| 7 | **Specifična pravila** | varira | Drugačije povlastice, carinski postupci, način grupisanja. |

---

## Šta treba poboljšati za lakšu prilagodbu

### 1. Hardkodovane putanje → `.env` varijable

**Trenutno:**
```python
# services/agent/chat/declaration_search_service.py
XML_DIR = Path(...) / "data" / "knowledge_base" / "NOVA ASIKUDA"

# services/agent/learning/exporter_xml_indexer.py
XML_FOLDER = Path(...) / "docs" / "NOVA ASIKUDA"
```

**Treba:**
```env
# .env
XML_ARCHIVE_DIR=docs/spedicija_xyz_xml
DECLARATION_INDEX_DB=docs/spedicija_xyz_xml/declaration_index.db
```

Ovo omogućava da svaka špedicija ima svoj folder sa XML fajlovima i svoj SQLite indeks, bez mijenjanja koda.

### 2. Profilisanje baze znanja

Tarifna mapiranja (`product_tariff_mapping`) i baza znanja su izgrađeni iz historije jedne špedicije. Za novu špediciju, ove tabele treba da počnu prazne i da se pune iz njihove sopstvene istorije. Treba razmisliti da li da se ove tabele:
- Ostave prazne za novu špediciju (čist početak)
- Ili da se napravi opšta baza znanja koja se dijeli (zajedničke tarife, carinski postupci)

### 3. Instalacioni skript

Napraviti `setup_new_spedition.sh` koji automatizuje korake 1-5:

```bash
#!/bin/bash
# setup_new_spedition.sh <ime_spedicije> <xml_folder>
# 1. Kreira novu PostgreSQL bazu
# 2. Pokreće setup_db.py i migracije
# 3. Postavlja .env sa imenom baze
# 4. Pokreće reindeksiranje XML fajlova
```

---

## Arhitektonska odluka: profil vs. zasebna baza

Dva pristupa za više špedicija:

### Opcija A: Zasebna baza po špediciji (preporučeno)

```
deklarant_pro_spedicija1  → aplikacija instanca 1
deklarant_pro_spedicija2  → aplikacija instanca 2
```

**Prednosti:** Potpuna izolacija podataka, nema curenja između špedicija, jednostavno.  
**Mane:** Više baza za održavanje, migracije se moraju pokretati za svaku.

### Opcija B: Jedna baza sa `tenant_id` kolonom

```sql
ALTER TABLE catalogs.declarations ADD COLUMN tenant_id INT;
```

**Prednosti:** Jedna baza, lakše održavanje.  
**Mane:** Rizik curenja podataka, svaki upit mora filtrirati po `tenant_id`, kompleksnije.

**Preporuka:** Opcija A za sada. Jednostavnije je, sigurnije, i broj špedicija neće biti veliki (5-10). Ako ikad dođe do 20+ špedicija, tad razmotriti Opciju B.

---

## Procjena truda za drugu špediciju

| Faza | Vrijeme |
|------|---------|
| Infrastruktura (baza, XML indeks, konfiguracija) | 1-2 h |
| Unos podataka (deklarant, partneri) | 2-4 h |
| Eventualni novi importeri | 1-5 dana |
| Testiranje sa njihovim podacima | 1 dan |
| **Ukupno (bez novih importera)** | **~1 dan** |
| **Ukupno (sa 2-3 nova importera)** | **~3-5 dana** |

Prva nova špedicija će tražiti najviše vremena jer će se otkriti sve tačke koje treba parametrizovati. Svaka sljedeća — sve manje.

---

## Šta NE raditi

- **Ne pokušavaj multi-tenant arhitekturu odmah.** Single-tenant sa zasebnim bazama je dovoljan za 5-10 špedicija.
- **Ne briši postojeće importere.** Oni su biblioteka. Nova špedicija možda ima istog dobavljača.
- **Ne diraj MCP server.** On je već generički — čita iz bilo koje baze.
- **Ne komplikuj instalaciju.** Za sad, ručni setup sa 5 koraka je prihvatljiv. Instalacioni skript može doći kasnije.
