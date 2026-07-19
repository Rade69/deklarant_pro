# Agent Report — 2026-07-19: MCP historijska pretraga — pravi ASYCUDA XML podaci

## Datum
2026-07-19

## Agent
Claude Sonnet 5

## Scope
- `database/migrate_declarations_from_xml.py` (nov fajl) + `dist_client/` mirror
- PostgreSQL `catalogs.declarations` / `catalogs.declaration_items` — puni podaci

---

## Status izvora

- `agent_reports/2026-07-19_baza-podataka-audit-katalog.md` — audit istog dana,
  identifikovao `declarations`/`declaration_items` kao "kod postoji, tabela
  prazna". Korišten kao polazna tačka, ali **korigovan tokom ovog zadatka**
  (vidi ispod) — audit nije provjerio da li je izvorna migraciona skripta
  (`migrate_mappings.py`) uopšte davala vrijednu vrstu podataka.

---

## GitNexus impact

Nova samostalna skripta, bez postojećih pozivalaca — `gitnexus_impact` nije
primjenjivo (GitNexus indeks je nezavisno utvrđen kao degradiran za ovaj repo,
vidi `docs/CONTEXT.md` §16). Ručna provjera: skripta ne mijenja nijedan
postojeći Python simbol, samo poziva `DeclarationSearchService._parse_xml`
(read-only poziv, metoda ne referencira `self`).

---

## Šta je urađeno

1. **Otkrivena i ispravljena pogrešna pretpostavka** (moja, iz prethodne
   poruke korisniku): tvrdio sam da `declarations`/`declaration_items` čuvaju
   "stvarno prihvaćene ASYCUDA deklaracije" — netačno. Postojeća
   `database/migrate_mappings.py` je samo omotavala
   `catalogs.product_tariff_mapping` u lažne `"MIGRATED_{product_code}"`
   deklaracije (isti podaci, druga šema, `LIMIT 1000`) — nula dodane
   evidentne vrijednosti.
2. Otkriven **već postojeći, dokazani** servis
   `services/agent/chat/declaration_search_service.py` — parsira stvarnih
   2503 ASYCUDA XML fajla iz `data/knowledge_base/NOVA ASIKUDA/` u SQLite
   (`declaration_index.db`), koristi ga agent chat. Ima čak i prošli bugfix
   (`agent_reports/2026-07-03_declaration-search-fts-item-id-fix.md`).
3. Utvrđeno **zašto MCP server ne može prosto koristiti taj SQLite servis**:
   `docs/sections/mcp-server-architecture.md` — MCP server je namjerno
   dizajniran da radi samostalno na Ubuntu serveru sa SAMO PostgreSQL
   pristupom (bez lokalnih XML fajlova) — otuda originalni izbor
   PostgreSQL tabela za MCP alate.
4. Napisana nova skripta `database/migrate_declarations_from_xml.py` koja
   **reuse-uje** `DeclarationSearchService._parse_xml()` (ista, dokazana
   logika parsiranja — ne nova reimplementacija) i upisuje stvarne podatke u
   `catalogs.declarations`/`catalogs.declaration_items` (PostgreSQL).
5. Testirano prvo na uzorku od 20 fajlova, zatim pun backfill svih 2503.
6. Verifikovano uživo: sva 4 relevantna MCP alata
   (`suggest_tariff_from_history`, `find_product_origin`, `suggest_preference`,
   `search_historical_declarations`) vraćaju smislene, stvarne rezultate sa
   pravim tarifnim brojevima, zemljama porijekla i povlasticama (npr. CEFTAP).

---

## Zašto je urađeno

Korisnik je tražio da se MCP istorijska pretraga "završi do kraja" nakon što
sam je ranije preporučio kao najvredniju od 4 "upitne" tabele iz audita.
Dublje čitanje `migrate_mappings.py` je otkrilo da bi puko pokretanje te
postojeće skripte samo duplirao `product_tariff_mapping` u drugoj šemi — bez
prave dodane vrijednosti. Korisnik je odabran "jednokratni backfill" (ne
inkrementalni sync) kad sam predstavio ispravljen, veći obim posla.

---

## Kako je urađeno

- `database/migrate_declarations_from_xml.py`:
  - `ensure_schema()` — identična DDL kao stara `migrate_mappings.py`
    (`CREATE TABLE IF NOT EXISTS`, isti indeksi uklj. GIN FTS na `naziv_robe`)
  - `DELETE FROM` oba tabele prije punjenja (idempotentno, čisti stare lažne
    redove ako ih ima)
  - Za svaki XML fajl: `DeclarationSearchService()._parse_xml(path)` →
    `(filename, decl_type, exporter, consignee, jib)` + lista stavki
    `(hs_code, commercial, description, country, preference)`
  - `naziv_robe` = spoj `commercial` + `description` (oba polja, radi bolje
    FTS pokrivenosti — ista logika kao SQLite verzija koja indeksira oba
    polja odvojeno)
  - `invoice_number` = ime XML fajla (isti izbor kao `DeclarationSearchService`
    — `filename TEXT UNIQUE` u njenoj SQLite šemi)
  - Batch commit na svakih 200 deklaracija

---

## Šta nije dirano

- `database/migrate_mappings.py` — namjerno netaknuta (ostaje u
  `setup_all_migrations.py` pipeline-u za nove instalacije; van scope-a je
  odlučivati da li je ukloniti/zamijeniti tamo — poseban follow-up).
- `services/agent/chat/declaration_search_service.py` (SQLite verzija) — u
  potpunosti netaknuta, samo pozvana njena `_parse_xml` metoda.
- `mcp_server/tools/*.py` — logika upita nepromijenjena. Postoji poznato
  ograničenje (vidi "Pronađeni problemi") koje NISAM popravljao jer je van
  scope-a "popuni podatke".
- Inkrementalni sync mehanizam — korisnikova eksplicitna odluka da ostane
  jednokratni backfill.

---

## Verifikacija

```
python database/migrate_declarations_from_xml.py --limit 20
→ 20 deklaracija, 97 stavki, 0 preskoceno

python database/migrate_declarations_from_xml.py   (pun run)
→ 2496 deklaracija, 9798 stavki, 7 preskoceno

python -m pytest mcp_server/tests/ -q
→ 31 passed

python -m pytest tests/unit tests/integration -q
→ 689 passed, 44 skipped, 5 xfailed, 2 failed (identicno kao PRIJE ovog
  zadatka — vidi agent_reports/2026-07-19_baza-cleanup-drop-6-tabela.md,
  isti pretpostojeći Pi/Codex regresija, nepromijenjen brojem)
```

Live poziv sva 4 alata sa realnim upitima ("kobasice", "slanina", "čvarci",
zemlja "RS" + izvoznik) — svi vraćaju stvarne, smislene podatke sa pravim
tarifnim brojevima/zemljama/povlasticama iz stvarnih XML deklaracija.

---

## Pronađeni problemi

- **`search_historical_declarations` nije dijakritik-neosjetljiva** —
  `ILIKE '%cvarci%'` NE pronalazi `'Čvarci'` (mora se tražiti tačno
  `'čvarci'`). SQLite verzija (`DeclarationSearchService`) ovo rješava
  `unicode61 remove_diacritics 2` FTS5 tokenizatorom; MCP verzija koristi
  prostu `ILIKE`. Ovo je **postojeće ograničenje u `mcp_server/tools/*.py`
  SQL-u**, ne nešto što je moja migracija unijela — nisam ga popravljao
  (van scope-a "popuni podatke stvarnim vrijednostima"). Follow-up: dodati
  PostgreSQL `unaccent` extension + `unaccent(di.naziv_robe) ILIKE
  unaccent(...)` u sve upite.
- **Manji artefakt u sirovim podacima**: pronađen jedan `hs_code` sa zarezom
  na kraju (`'2301100000,'`) — potiče iz same XML datoteke (netačan unos u
  originalnoj deklaraciji), ne iz mog parsiranja. Nije popravljano — vjerno
  odražava izvorne podatke, isto bi se pojavilo i u SQLite indeksu.
- `suggest_tariff_from_history` ponekad vraća duplirane prijedloge (isti
  `hs_code` više puta sa istim `confidence`) zbog `GROUP BY tarifni_broj,
  naziv_robe` u postojećem MCP alatu — pretpostojeća logika u
  `mcp_server/tools/tariff_history.py`, nisam mijenjao.

---

## Konflikti / kontradiktorni izvori

Moja ranija tvrdnja korisniku (prethodna poruka u sesiji) da MCP pretraga
koristi "stvarno prihvaćene ASYCUDA deklaracije" je bila netačna u tom
trenutku (stara skripta je davala samo prepakovan `product_tariff_mapping`).
Ispravljeno tokom ovog zadatka — sada tvrdnja tačno odražava stanje. Nema
drugih kontradiktornih izvora.

---

## Commitovi

| Hash | Poruka |
|------|--------|
| `6de3e0e` | feat(mcp): popuni declarations/declaration_items pravim ASYCUDA XML podacima |
| `4b37021` | docs(report): audit catalogs seme - 36 tabela (subagent istraga) |

---

## Rizici / ograničenja

- Podaci su **statični snapshot** (jednokratni backfill) — novi XML fajlovi
  dodani u `data/knowledge_base/NOVA ASIKUDA/` nakon danas neće biti vidljivi
  MCP alatima dok se skripta ručno ne ponovi (isti obrazac kao
  `product_similarity_memory` sync).
- Skripta zavisi od lokalne XML arhive (`data/knowledge_base/NOVA ASIKUDA/`,
  2503 fajla) — nije uključena u `setup_all_migrations.py` jer ta arhiva
  možda nije prisutna/prenosiva na svaku instalaciju.

---

## Potreban follow-up

1. Diakritik-neosjetljiva pretraga u `mcp_server/tools/*.py` (PostgreSQL
   `unaccent` extension) — poznato ograničenje, nije popravljeno.
2. Odluka: da li `migrate_mappings.py` treba ukloniti/zamijeniti u
   `setup_all_migrations.py` pipeline-u za buduće instalacije, ili ostaviti
   kao istorijski artefakt.
3. Ako se poželi trajna sinhronizacija — dodati inkrementalni mehanizam
   (korisnik je eksplicitno odabrao da to NIJE dio ovog zadatka).

---

## Potrebna korisnička potvrda

- Isprobati MCP alate iz stvarnog agent-chat toka (ne samo direktan Python
  poziv kao u ovoj verifikaciji) da se potvrdi krajnja integracija.
- Odlučiti prioritet za dijakritik-fix i `migrate_mappings.py` pitanje
  (follow-up stavke gore).
