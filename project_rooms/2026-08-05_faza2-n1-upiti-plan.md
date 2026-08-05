# Faza 2 — Plan refaktora N+1 upita

**Datum:** 2026-08-05
**Status:** Analiza završena — ČEKA ODOBRENJE

---

## Mapa zavisnosti

```
                    ┌──────────────────────────────┐
                    │     database/db.py:270        │
                    │     get_tarifa_opis(code)     │ ← OTVARA NOVU KONEKCIJU svaki put
                    │     (1 kod → 1 konekcija)     │
                    └──────────┬───────────────────┘
                               │
              ┌────────────────┼──────────────────┐
              │                │                   │
              ▼                ▼                   ▼
  tariff_service.py:397  tariff_service.py:382  db_widgets.py:84
  validate_tariff()      validate_mappings()    (pojedinačno)
  (1 poziv, OK)          ★ N POZIVA U PETLJI   (1 poziv, OK)
                               │
                    ┌──────────┴───────────┐
                    │                      │
                    ▼                      ▼
         naimenovanja_view.py    naimenovanja_controller.py
         :2857                    :317
```

```
  tariff_service.py:23
  load_tariff_description(code)
  ★ 1-15 SELECT-ova u petlji unutar 1 konekcije
                    │
                    ▼
         naimenovanja_service.py:160
         (pojedinačni poziv za 1 tarifni kod)
```

```
  tariff_service.py:195
  load_tariff_description_from_postgres(code, nivo)
  ★ 3-8 SELECT-ova u petlji unutar 1 konekcije
                    │
         ┌──────────┴───────────┐
         │                      │
         ▼                      ▼
  naimenovanja_service.py  naimenovanja_view.py
  :446, :450               :1223
```

---

## Planirani zahvati

### Popravka 5 — `validate_mappings()` N+1 konekcija

**Fajl:** `database/db.py` + `services/naimenovanja/tariff_service.py`

**Problem:** `validate_mappings()` zove `get_tarifa_opis()` za svaki mapping u petlji (linija 382). Svaki poziv otvara NOVU PostgreSQL konekciju (`with get_db_connection()`). Za 30 mappinga = 30 konekcija + 30 SELECT-ova.

**Rješenje:**
1. Dodati novu funkciju `get_tarifa_opis_batch(codes: list)` u `database/db.py`:
   - Otvori JEDNU konekciju
   - `SELECT tarifni_kod, opis FROM catalogs.zvanicna_tarifa WHERE tarifni_kod = ANY(%s) ORDER BY LENGTH(tarifni_kod) DESC`
   - Vrati `{code: opis}` dict
2. `validate_mappings()` koristi batch verziju umjesto petlje

**NE DIRATI:** Postojeću `get_tarifa_opis()` — ostaje za:
- `validate_tariff()` (tariff_service.py:397) — pojedinačni poziv
- `db_widgets.py:84` — pojedinačni poziv

**Rizik:** 🟢 NIZAK — nova funkcija, postojeća netaknuta. Samo 1 pozivalac se mijenja.

---

### Popravka 6a — `load_tariff_description()` fallback petlja

**Fajl:** `services/naimenovanja/tariff_service.py:23-94`

**Problem:** Nakon što exact match ne uspije, petlja kroz `generate_fallback_codes()` izvršava 1-15 pojedinačnih `SELECT ... WHERE tarifni_kod LIKE 'XX%' LIMIT 1`.

**Rješenje:** 
- Generisati sve fallback kodove u Pythonu
- Jedan SQL upit: `WHERE tarifni_kod LIKE 'XX%' OR tarifni_kod LIKE 'YY%' OR ... ORDER BY LENGTH(tarifni_kod) DESC LIMIT 1`
- Isti rezultat, 1 SELECT umjesto N

**Pozivaoci:** `naimenovanja_service.py:160` — ne mijenja se interfejs

**Rizik:** 🟢 NIZAK — samo interna implementacija. Isti rezultat.

---

### Popravka 6b — `load_tariff_description_from_postgres()` prefix_len petlja

**Fajl:** `services/naimenovanja/tariff_service.py:195-296`

**Problem:** Za `nivo='podbroj'`: 2-3 candidate upita + 3 prefix_len upita = 5-6 SELECT-ova. Za `nivo='glava'`: glava + podglava = 2 SELECT-a.

**Rješenje:** 
- Spojiti SVE kandidate (exact codes + LIKE prefixe) u JEDAN upit:
  ```sql
  WHERE (tarifni_kod IN ('code1', 'code2', 'code3') OR tarifni_kod LIKE '123456%' OR ...)
    AND nivo = 'podbroj'
  ORDER BY LENGTH(tarifni_kod) DESC LIMIT 1
  ```
- Za `nivo='glava'`: spojiti glava + podglava u jedan upit

**Pozivaoci:**
- `naimenovanja_service.py:446,450`
- `naimenovanja_view.py:1223`
- Interfejs se NE mijenja — isti potpis, isti rezultat

**Rizik:** 🟡 SREDNJI — kompleksniji refaktor. Logika se sažima ali MORA dati identičan rezultat. Potrebno testiranje sa stvarnim tarifnim kodovima.

---

## Šta NE DIRATI

- `get_tarifa_opis()` u `database/db.py` — ostaje netaknuta
- `validate_tariff()` — pojedinačni poziv, ne treba batch
- `db_widgets.py:84` — pojedinačni poziv
- `naimenovanja_service.py` — ne mijenja se interfejs servisa
- `_clean_tariff_description()` — čista logika, ne dira se

## Redoslijed implementacije

1. **Prvo #5** (najjednostavnije, najveći efekat) — `get_tarifa_opis_batch()`
2. **Onda #6a** — `load_tariff_description()` LIKE spajanje
3. **Na kraju #6b** — `load_tariff_description_from_postgres()` kompletan refaktor

## Očekivano ubrzanje

| Popravka | Prije | Poslije | Ubrzanje |
|----------|-------|---------|----------|
| #5 (30 mappinga) | 30 konekcija + 30 SELECT | 1 konekcija + 1 SELECT | **15-30×** |
| #6a (10 fallback kodova) | 10 SELECT-ova u petlji | 1 SELECT sa OR | **5-10×** |
| #6b (podbroj) | 6 SELECT-ova u petlji | 1 SELECT | **3-5×** |
