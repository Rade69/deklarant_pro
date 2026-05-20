# Agent report — Fix: tariff_description1/2 ne filtrirati kroz product_names

Datum: 2026-05-20

## Šta je urađeno

Ispravljen bug u `_choose_tariff_description` (`rub31_builder.py`) gdje su autorizovana tarifna polja (`tariff_description1`, `tariff_description2`) pogrešno filtrirana kao nazivi proizvoda, rezultirajući praznim L1 u Rub.31 `Commercial_Description`.

## Problem

Stavke 10, 22, 25 u BLAGIC-LOREN-3-3-ASY.xml nemaju tarifni opis u L1.

**Root cause (lanac):**

1. `goods_trade_name` prve linije za kod 39173100 = "– – savitljive cijevi...27,6 Mpa ili veći"
2. `_looks_like_product("...27,6 Mpa...")` → **True** (sadrži cifre) → tekst ide u `product_names`
3. `tariff_description2` = isti tekst → `_candidate_is_product_text(tariff_desc2, product_names)` → **True** → filtrirano
4. Svi kandidati filtrirani → `description_of_goods = "."`

**Pogođeni kodovi:** 39173100 ("27,6 Mpa"), 85322500, 85168020, 73102990 ("0,5 mm") i slični.

## Kako je urađeno

### Izmjena `_choose_tariff_description` u `rub31_builder.py`

**Stara logika:** Svi kandidati prolaze kroz `_candidate_is_product_text` filter.

**Nova logika:** `tariff_description1` i `tariff_description2` su označeni kao `_TARIFF_FIELDS` i **isključeni** iz filtera. Redosljed kandidata nije promijenjen:

```
1. tariff_description1  ← tariff field, bez filtera
2. goods_description    ← filter se primjenjuje
3. trade candidates     ← filter se primjenjuje
4. tariff_description2  ← tariff field, bez filtera
5. tariff_heading       ← filter se primjenjuje
```

Ovo znači: `goods_description` i dalje ima prioritet nad `tariff_description2` (čuva staro ponašanje), ali ni jedno od tarifnih polja ne može biti eliminisano filter-om.

### Zašto ovaj pristup, ne promjena redosljeda

Alternativa bi bila staviti `tariff_description2` na početak liste. To bi slomilo test koji provjerava da `goods_description` (korisnikov unos) ima prioritet — npr. stavka sa `goods_description="brtve, podlošci..."` i `tariff_description2="- - zaptivci..."` bi dobila pogrešan opis.

## Testovi dodani (3 nova)

| Test | Šta pokriva |
|------|-------------|
| `test_choose_tariff_description_not_filtered_when_contains_numbers` | tariff_description2 s "27,6 Mpa" nije filtriran |
| `test_choose_tariff_description_not_filtered_when_description1_contains_numbers` | tariff_description1 s "0,5 mm" nije filtriran |
| `test_choose_tariff_description_returns_description2_when_description1_absent` | tariff_description2 se koristi kad description1 nije postavljen |

Ukupno: 29 testova, svi prolaze.

## Commitovi

| Hash | Opis |
|------|------|
| `f91eda8` | fix(rub31): ne filtriraj tariff_description1/2 kroz product_names filter |
