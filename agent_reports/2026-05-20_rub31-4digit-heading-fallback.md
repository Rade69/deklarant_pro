# Agent report — Rub.31 fallback na 4-cifreni tarifni heading

Datum: 2026-05-20

## Šta je urađeno

Implementiran fallback u `_tariff_heading` koji, kada pod-tarifni opis bude generički ("ostali/ostale/ostalo"), nastavlja pretraživati tarifnu bazu sve dok ne nađe bogatiji opis — ili koristi 4-cifreni heading kao ultimativni fallback.

## Problem

Analiza `BLAGIC-LOREN.xml` (39 stavki) pokazala da 11 stavki ima generičke opise poput "-- ostali" u Rub.31 `Description_of_goods`. To se dešava jer:

1. `_tariff_heading` je stajao na prvom nepraznom DB rezultatu — čak i kad je "-- ostali"
2. Pod-tarifni nivo u bazi BiH carinske tarife često je samo "-- ostali" za različite grupacije
3. 4-cifreni heading (npr. 8516 = "Električni bojleri, grijači prostorija...") uvijek je bogatiji

## Kako je urađeno

### Izmjena `_tariff_heading` u `asycuda_xml_builder.py`

**Stara logika:**
- Ako item fields (`tariff_description1/2`) postavljeni → vrati ih odmah (čak i ako su "ostali")
- DB lookup: stani na prvom nepraznom rezultatu (čak i generičkom)

**Nova logika:**
1. Provjeri item fields — ako non-generički, vrati odmah (bez DB lookupa)
2. Ako item fields prazni ILI generički → DB lookup od specifičnog prema 4-cifrenom
3. Prvu non-generičku vrijednost iz DB-a vrati
4. Ako su SVI DB kandidati generički → vrati zadnji (= 4-cifreni = najširi/najbogatiji)

### Redosljed pretraživanja DB-a

Za kod "85168080":
1. `trazi_po_kodu("85168080")` → "-- ostali" (generički, nastavi)
2. `trazi_po_kodu("851680")` → "- ostali" (generički, nastavi)
3. `trazi_po_kodu("8516")` → "Električni bojleri, grijači prostorija i tla" ✅

Za kod "84821090":
1. "-- ostali" (generički)
2. "- ostali" (generički)
3. "8482" → "Ležišta sa kuglicama ili valjcima..." ✅

### Import dodan u xml_builder

```python
from services.naimenovanja.rub31_builder import (
    build_asycuda_rub31,
    is_generic_tariff_text,  # novo
    normalize_tariff_text,
)
```

## Testovi dodani (4 nova)

| Test | Šta pokriva |
|------|-------------|
| `test_tariff_heading_falls_back_to_4digit_when_specific_is_generic` | Osnovna logika fallbacka |
| `test_tariff_heading_prefers_non_generic_over_4digit` | Non-generički specifičan opis → ne zamjenjuj 4-cifrenim |
| `test_tariff_heading_uses_non_generic_from_item_fields_without_db` | Non-generički item field → nema DB poziva |
| `test_tariff_heading_triggers_db_lookup_when_item_field_is_generic` | Generički item field → DB lookup se pokreće |

## Commitovi

| Hash | Opis |
|------|------|
| `cee1709` | fix(rub31): koristi 4-cifreni heading kad je specifičan opis generički |
