# Agent report — Fix: overflow marker i heading fragment u Rub.31

Datum: 2026-05-21

## Šta je urađeno

Ispravljena 2 buga u `_choose_tariff_description` (`rub31_builder.py`) koja su zajedno uzrokovala pogrešan `description_of_goods` i `Commercial_Description` za stavke 6, 10, 22, 25 (nazivi robe umjesto tarifnog opisa) i kratke opise bez konteksta (stavke 8, 17, 19, 21 i dr.).

---

## Bug 1 — goods_description s "; ... (+N više)" prolazio product filter

### Problem

`create_naimenovanja_service.py` gradi `goods_description` za naimenovanja s >3 robe ovako:

```python
goods_description = "; ".join(descriptions[:3])
if len(descriptions) > 3:
    goods_description += f"; ... (+{len(descriptions)-3} više)"
```

Sufiks `"... (+2 više)"` nije u `product_keys` → `_candidate_is_product_text` vraćao False → `goods_description` (produkt nazivi!) prolazio kao tarifni opis.

### Pogođene stavke (BLAGIC-LOREN)

| Stavka | Tarifni kod | Roba | Pogrešan opis |
|--------|-------------|------|---------------|
| 6  | 40169300 | 5 tunelnih guma Hisense | TUNEL GUMA HISENSE HK...; TUNEL GUMA HISENSE HK...; ... (+2 više) |
| 10 | 39173100 | 4 creva | DOVODNO CREVO VES MASINE...; CREVO 4x6mm...; ... (+1 više) |
| 22 | 85322500 | 4 kondenzatora | KONDENZATOR 14mf...; KONDENZATOR 40mf...; ... (+1 više) |
| 25 | 85168020 | 4 ringla | RINGLA F 145 S...; RINGLA F 145 E...; ... (+1 više) |

### Rješenje

`_candidate_is_product_text` sada ignorira tokene koji počinju s `"..."`:

```python
_OVERFLOW_MARKER = re.compile(r"^\.\.\.")

def _candidate_is_product_text(...) -> bool:
    ...
    raw_parts = [p.strip(" ,;") for p in re.split(r"[;\n]+", candidate) if p.strip(" ,;")]
    # Skip overflow markers like "... (+2 više)"
    parts = [_key(p) for p in raw_parts if not _OVERFLOW_MARKER.match(p)]
    return bool(parts) and all(part in product_keys for part in parts)
```

---

## Bug 2 — kratki fragment opisi bez parent heading konteksta

### Problem

Sub-tarifni opisi poput `"- šarke"`, `"- dijelovi"`, `"- - bez pribora"` su tehnički ispravni ali bez parent headinga izgledaju "okrnjeno" u Rub.31. `_choose_tariff_description` ih vraćao odmah bez traženja bogatijeg opisa (4-cifreni heading).

### Primjeri

| Stavka | Tarifni kod | Stari opis | Novi opis |
|--------|-------------|------------|-----------|
| 8, 19  | 83021000 | - šarke | Šarke, zglobovi i sl. pribor od prostih metala |
| 17     | 82054000 | - odvijači | (4-cifreni heading iz DB) |
| 21, 31 | 84509000/85087000 | - dijelovi | (4-cifreni heading iz DB) |
| 14     | 90329000 | - dijelovi i pribor | (4-cifreni heading iz DB) |

### Rješenje

Nova funkcija `is_heading_fragment`:

```python
def is_heading_fragment(text: str) -> bool:
    if not re.match(r"^[\s–-]", text):
        return False
    content = re.sub(r"^[\s–-]+", "", text).strip()
    return len(content) <= 25
```

Prag 25 znakova za sadržaj (bez vodećih crtica):
- `"- šarke"` → content = "šarke" (5) → **fragment** ← fallback
- `"- električni otpornici za grijanje:"` → content = "električni..." (33) → **nije fragment** ← koristi se
- `"- - savitljive cijevi i crijeva, što mogu podnijeti..."` → nije fragment ← koristi se

Izmjene u kodu:
1. `_choose_tariff_description` — fragment se ne vraća odmah nego se čeka bogatiji kandidat
2. `_tariff_heading` (asycuda_xml_builder.py) — fragment triggera DB fallback prema 4-cifri
3. `is_heading_fragment` eksportovana i importovana u oba fajla

---

## Testovi dodani (4 nova)

| Test | Šta pokriva |
|------|-------------|
| `test_overflow_marker_in_goods_description_is_filtered_as_product` | goods_description s "(+N više)" ispravno filtriran |
| `test_heading_fragment_yields_to_richer_tariff_heading` | "- šarke" zamijenjeno 4-cifrenim headingom |
| `test_long_specific_description_not_treated_as_fragment` | Dugi opis ne biva zamijenjen kraćim headingom |
| `test_fragment_fallback_when_no_tariff_heading` | Fragment vraćen kao fallback kad nema bogatijeg opisa |

Ukupno: 33 testova, svi prolaze.

## Commitovi

| Hash | Opis |
|------|------|
| `960bba2` | fix(rub31): ispravi 2 buga u _choose_tariff_description |
