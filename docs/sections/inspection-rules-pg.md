# inspection-rules-pg

## Pregled

Modul za upravljanje inspekcijskim pravilima u PostgreSQL bazi.

Zamjenjuje stari SQLite `inspection_rules.db` koji je imao dva strukturna problema:
- `tariff_code_norm` sadržavao markere (`**`, `*`, `+`) iz originalnog dokumenta — prefix matching nije radio
- Nije bilo mogućnosti uređivanja (read-only uvezeni podaci iz 2015. godine)

## Fajlovi

| Fajl | Sekcija | Uloga |
|------|---------|-------|
| `database/migrate_inspection_rules_to_pg.py` | `inspection-rules-pg-migration` | Inicijalni uvoz JSON → PostgreSQL |
| `services/sifarnici_service.py` | `inspection-rules-pg-service` | CRUD i pretraga (PostgreSQL) |
| `services/inspection_service.py` | `inspection-service-pg` | Prefix-matching provjera za agent/import |

## Baza podataka

### Tabela: `catalogs.inspection_rules`

```sql
CREATE TABLE catalogs.inspection_rules (
    id               SERIAL PRIMARY KEY,
    inspection_type  VARCHAR(50) NOT NULL,   -- veterinary, sanitary, phytosanitary, ...
    tariff_code      VARCHAR(40),            -- originalni kod (bez markera)
    tariff_code_norm VARCHAR(20),            -- normalizovani (bez razmaka)
    tariff_len       SMALLINT,               -- dužina norm koda (za prefix matching)
    scope            VARCHAR(30),            -- tariff_code | chapter | prefix
    chapter          VARCHAR(10),            -- dvocifreni broj glave
    description      TEXT,
    marker           VARCHAR(10),            -- **, *, + (odvojen od koda)
    condition_text   TEXT,                   -- uslov (NULL = bezuslovno)
    match_strength   VARCHAR(20),            -- exact | prefix
    can_auto_decide  BOOLEAN DEFAULT TRUE,
    source_dataset   VARCHAR(60),
    source_page      SMALLINT,
    is_active        BOOLEAN DEFAULT TRUE,   -- soft-delete
    notes            TEXT,                   -- korisničke napomene
    updated_at       TIMESTAMP DEFAULT NOW()
);
```

Indeksi: `idx_insp_rules_norm (tariff_code_norm, tariff_len) WHERE is_active`, `idx_insp_rules_type (inspection_type) WHERE is_active`.

## Tipovi inspekcija

| Ključ | Naziv | Izvor JSON |
|-------|-------|-----------|
| `veterinary` | Veterinarska inspekcija | `bih_veterinarska_kontrola_prilog_I_flat.json` |
| `sanitary` | Sanitarna inspekcija | `bih_sanitary_iz_objedinjenog_spiska_flat.json` |
| `quality_control` | Kontrola kvaliteta | `bih_quality_control_iz_objedinjenog_spiska_flat.json` |
| `medicines_agency` | Agencija za lijekove | `bih_medicines_agency_iz_objedinjenog_spiska_flat.json` |
| `phytosanitary` | Fitosanitarna inspekcija | `bih_fitosanitarna_lista_v_flat.json` |

## Prefix matching

`InspectionService.check("1601009900")` izvodi:

```sql
SELECT DISTINCT ON (inspection_type) ...
FROM catalogs.inspection_rules
WHERE is_active = TRUE
  AND tariff_code_norm = substr('1601009900', 1, tariff_len)
ORDER BY inspection_type, tariff_len DESC
```

Vraća najspecifičniji pogodak po tipu inspekcije.

## Migracija

Pokretanje (idempotentno — briše i ponovo kreira sve redove):

```bash
python database/migrate_inspection_rules_to_pg.py
```

### Veterinarska inspekcija — markeri

Prilog I sadrži kodove sa prefiksima `**`, `*`, `+` koji označavaju posebne uslove
(dvostruka kontrola, granični prijelaz, itd.). Parser `_strip_marker()` odvaja marker
od koda i sprema ga u zasebnu `marker` kolonu, tako da `tariff_code_norm` ostaje čist.

### Fitosanitarna lista

Lista ne sadrži tarifne kodove nego kategorije robe. Mapiranje kategorija na prefikse
je hardkodirano u `_parse_phytosanitary()` (npr. `bilje_namijenjeno_sadnji` → `0601`, `0602`, ...).

## SifarniciService metode

| Metoda | Opis |
|--------|------|
| `load_inspection_rules(search, insp_type, only_active, limit)` | Dohvat s filterima |
| `count_inspection_rules(only_active)` | Ukupan broj za status bar |
| `get_inspection_rule(rule_id)` | Jedno pravilo po ID-u |
| `update_inspection_rule(rule_id, updates)` | Ažuriranje (ograničene kolone) |
| `deactivate_inspection_rule(rule_id)` | Soft-delete (`is_active = FALSE`) |
| `activate_inspection_rule(rule_id)` | Reaktivacija |
| `add_inspection_rule(data)` | Novi red, vraća ID |
