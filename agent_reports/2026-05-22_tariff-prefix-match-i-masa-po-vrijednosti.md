# Agent Report: Tariff Prefix Match + Masa po Vrijednosti

**Datum:** 2026-05-22  
**Sesija:** 64a5abd3 (nastavak)

---

## Šta je urađeno

### 1. Raspodjela masa po vrijednosti (iznos) — `MassCalculator`
- SCENARIJ 1 promijenjen: ako stavke imaju `iznos > 0`, masa se raspoređuje proporcionalno po vrijednosti umjesto po količini
- Fallback na `kolicina` kada `iznos` nije dostupan (backward compatible)
- Dodano 4 nova testa u `TestMassCalculatorValueDistribution`

### 2. Kreiranje naimenovanja za sve split deklaracije odjednom
- `_on_create_naimenovanja` u `FakturaView` detektuje `_multi_drafts` (> 1 draft)
- Prikazuje confirmation dialog sa listom svih deklaracija
- Kreira naimenovanja za svaki split draft u petlji
- Prikazuje breakdown po deklaraciji u success poruci

### 3. KG Fashion baza znanja iz PRET A PORTER XML fajlova
- Uvezeno 20 mapiranja iz 6 XML fajlova (PRET-1 do PRET-5, PRET-RS)
- Seed unosi za Bueno obuću: `26WG0703 → 64039198`, `26WG2803 → 64039198` itd.
- Seed unosi za Jagger odjeću: `JG8622 → 61103099`, `JG5760 → 62044400` itd.

### 4. Prefix match za product_code — `find_mapping()`
- Problem: `26WG0703-TAUPE` ne pronalazi seed `26WG0703` (tačan match ne prolazi)
- Rješenje: SQL query proširen — tražimo i gdje je DB kod prefiks traženog koda
- Tačan match ima prioritet (ORDER BY CASE), prefix match je fallback
- Obrisano 13 pogrešnih zapisa `26WG*-BOJA → kriva_tarifa` koji su blokirali seed unose

---

## Kako je urađeno

### `find_mapping()` — prefix match query
```python
cursor.execute("""
    SELECT product_code, naziv_robe, commodity_code, precision_1,
           zemlja_porijekla, povlastica, usage_count
    FROM catalogs.product_tariff_mapping
    WHERE product_code ILIKE %s
       OR (%s ILIKE product_code || '%%' AND product_code != '')
    ORDER BY
        CASE WHEN product_code ILIKE %s THEN 0 ELSE 1 END,
        usage_count DESC
    LIMIT 1
""", (product_code.strip(), product_code.strip(), product_code.strip()))
```

### DB cleanup — pogrešni zapisi sa sufiksima boja
```sql
DELETE FROM catalogs.product_tariff_mapping
WHERE product_code ~ '^[0-9]{2}W[A-Z][0-9]+-[A-Z]'
```
Obrisano 13 redova (`26WG0703-TAUPE`, `26WG2803-PEACH`, `26WG2804-GREEN`, itd.)

---

## Zašto

- KG Fashion fakture imaju product_code sa sufiksom boje (npr. `26WG0703-TAUPE`)
- PRET A PORTER XML deklaracije imaju iste kodove bez sufiksa (npr. `26WG0703`)
- Seed unosi trebaju pokriti sve varijante boja — prefiks match to rješava generički
- 13 pogrešnih zapisa nastalo prethodnim auto-popunjavanjem koje je koristilo netačne tarife

---

## Commitovi

| Hash | Opis |
|------|------|
| `91bd4de` | fix(tariff): prefix match za product_code sa sufiksima boja |
| (prethodna sesija) | feat: mass distribution by value, multi-draft naimenovanja, PRET XML seed |

---

## Testovi

- 459 unit testova — svi prolaze
- Manualni test `find_mapping`: `26WG0703-TAUPE → 64039198` ✅, `JG8622 → 61103099` ✅
