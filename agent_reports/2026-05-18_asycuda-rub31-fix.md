# Agent Report: ASYCUDA Rub.31 — Commercial_Description i normalizacija tarife

**Datum:** 2026-05-18
**Grana:** dev

---

## Šta je urađeno

Dva odvojena buga koji su zajedno uzrokovali da ASYCUDA World "briše" opis robe (Rub.31) pri importu XML-a:

1. **Newline bug** — `Commercial_Description` generisan bez `\n` znakova; ASYCUDA Word ignoriše single-line sadržaj
2. **Encoding bug** — tarifni opisi iz baze sadrže `–` (U+2013) i `−` (U+2212) koji se u ASYCUDA prikazuju kao `â` artefakti

---

## Kako je urađeno

### Bug 1: Newline u Commercial_Description

**Korijen problema:** `asycuda_xml_builder.py`, stara linija 992:
```python
result = " ".join(result.splitlines()).strip()
```
Ova linija je eksplicitno uklanjala sve newline karaktere. ASYCUDA World (Java) čita `Commercial_Description` kao multi-line polje — single-line sadržaj odbacuje/briše.

**Fix:** `_build_commercial_description()` repisana da gradi sadržaj sa stvarnim `\n` separatorima:
```
Tarifni heading
Naziv proizvoda 1
Naziv proizvoda 2
Faktura: 893/26 (rb. 58)
```

Faktura info vraćen na zahtjev korisnika — "to nam treba da znamo koje stavke idu u koji tarifni broj".

### Bug 2: En-dash → â artefakti

**Korijen problema:** Tarifna baza (`database/deklarant_sistem.db`, tabela `tarifa_2026`) čuva `–` (U+2013, en-dash) i `−` (U+2212, minus sign) kao hijerarhijske indentatore:
```
– ljepljivi zavoji...
– – vata i proizvodi od vate
– – – – ostalo
```
ASYCUDA koristi `- ` (obična crtica). Java aplikacija ne prikazuje ispravno ove Unicode karaktere → `â` u Rub.31.

**Fix:** Dodat statički helper `_normalize_tariff_text()` koji se poziva na kraju `_tariff_heading()`:
```python
@staticmethod
def _normalize_tariff_text(text: str) -> str:
    return text.replace("–", "-").replace("−", "-")
```

---

## Zašto

ASYCUDA World je Java aplikacija koja koristi vlastiti XML parser. Testiranjem utvrđeno (poređenjem `2203.xml` koji je pripremio ASYCUDA ekspert i `MEDIKOFARM-185-3.xml` iz naše aplikacije):
- ASYCUDA referentni fajl: `- - ostalo`
- Naš fajl: `â â ostalo`

---

## Commitovi

| Hash | Opis |
|------|------|
| `d9bd409` | fix(asycuda): normalizuj en-dash i minus-znak u tarifnim opisima |
| (prethodni) | fix(asycuda): Commercial_Description multi-line format za Rub.31 |

---

## Bug 3: "Nestane sve" pri kliku na opis robe (naknadni)

**Simptom:** Kolega testira importovani XML — čim klikne na "opis robe" u ASYCUDA World, sadržaj nestane.

**Korijen problema:** ASYCUDA World ima fiksni 3-linijski widget (~55 karaktera po liniji) za `Commercial_Description`. Stara implementacija (`_fit_parts`) stavljala je svaki naziv proizvoda na zasebnu liniju — za naimenovanje s 3+ artikla to je 5-6 linija. ASYCUDA odbacuje sadržaj koji ne stane u 3×55 pri prelasku u edit mode.

**Fix:** `_build_commercial_description()` repisana da uvijek gradi tačno 3 linije:

1. Tarifni heading (clipovan na 55 char)
2. Svi nazivi proizvoda comma-separated (clipovani na 55 char)
3. Faktura: X/26 (rb. N) (clipovana na 55 char)

Dodat novi test: `test_commercial_description_never_exceeds_3_lines_or_55_chars_per_line`

---

## Fajlovi promijenjeni

- `exporters/asycuda_xml_builder.py` — `_normalize_tariff_text()`, `_tariff_heading()`, `_build_commercial_description()`, `_build_description_of_goods()`
- `tests/unit/test_asycuda_goods_description.py` — 17 testova, svi prolaze
