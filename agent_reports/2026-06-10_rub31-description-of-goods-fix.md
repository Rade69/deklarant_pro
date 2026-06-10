# Agent Report: Rub.31 "sadržaj se izgubi" — fix Description_of_goods (2026-06-10)

## Šta je urađeno

Ispravljen bug: nakon uvoza XML-a generisanog u Deklarant Pro u ASYCUDA World i
klika na Rub.31 (editovanje), sadržaj polja "Description of goods" se gubi.

`description_of_goods` se sada skraćuje na `_MAX_LINE` (55 karaktera) umjesto
dosadašnjih `_MAX_DESC` (280 karaktera) u jednoj liniji.

## Kako je urađeno

### Analiza
- Korisnik je dostavio stvarni export `ŠUMA-35.xml` (35 stavki, `Downloads/`).
- Eksterni AI alat (Codex) je predložio hipotezu: ASYCUDA Rub.31 editor "Description
  of goods" prihvata samo kratku jednu liniju (~55 char), dok `Description_of_goods`
  može izaći do 280 char u jednoj liniji.
- Provjera na stvarnom fajlu (Python skripta, parsiranje XML-a) potvrdila je: 7/35
  stavki imalo `Description_of_goods` od 65 do 279 karaktera u jednoj liniji
  (stavke 1, 3, 5, 16, 22, 30, 34) — preostalih 28 stavki (<=55 char) bez problema.
- Provjereno i da `Description_of_goods` MORA ostati single-line (`\n` zabranjen) —
  potvrđeno postojećim commitom `80477f4` ("ASYCUDA World odbija višeredni tekst u
  ovom polju"), pa rješenje NIJE 3-linijski wrap kao kod `Commercial_Description`,
  nego prosto skraćivanje na 55 char.

### Izmjena
- `services/naimenovanja/rub31_builder.py` — `build_asycuda_rub31()`:
  `description_of_goods=description or "."` → `description_of_goods=_clip(description, _MAX_LINE) or "."`
- Identična izmjena u mirror kopiji `dist_client/services/naimenovanja/rub31_builder.py`
  (fajlovi su bili identični prije izmjene).
- `tests/unit/test_asycuda_goods_description.py` — ažurirana 2 testa koja su
  očekivala neskraćeni (>55 char) `description_of_goods`:
  - `test_commercial_description_uses_goods_description_when_tariff_heading_is_generic`
  - `test_choose_tariff_description_not_filtered_when_contains_numbers`
- Svih 35 testova u `test_asycuda_goods_description.py` prolazi (ručni test runner,
  pytest nije instaliran u dostupnom venv-u).

### GitNexus
- `gitnexus_impact(build_asycuda_rub31, upstream)` → risk LOW, 8 pogođenih simbola
  (samo `_build_description_of_goods`/`_build_commercial_description` u oba
  `asycuda_xml_builder.py` — root i `dist_client`).
- `gitnexus_detect_changes(staged)` → risk MEDIUM (XML export logika), bez
  neočekivanih simbola.
- Index je nakon commita prijavljen kao stale — `npx gitnexus analyze` planiran
  nakon ovog izvještaja.

## Zašto

Korisnik: "Ovo je xml generisan našom aplikacijom ali kad ga uvezem u ASYCUDA
aplikaciju i želim da editujem u rub.31 sadržaj se izgubi." `Commercial_Description`
je već imao isti 55-char/3-linije limit (raniji commitovi `c344231`, `4a8dd45`), ali
`description_of_goods` nije bio usklađen — sada su oba polja konzistentna sa istim
ASYCUDA editor ograničenjem.

## Commitovi

| Hash | Opis |
|------|------|
| a42ddba | fix(rub31): skrati Description_of_goods na _MAX_LINE (55 karaktera) |

## Napomene / sljedeći koraci

- Zaseban, već odobren zadatak (mojibake korupcija u 41 fajlu na `windows` grani,
  uneseni greškom tokom ranije cherry-pick sesije) je i dalje PENDING — vidi memoriju
  `2026-06-10_mojibake-korupcija-41-fajlova-pending.md`. `exporters/asycuda_xml_builder.py`
  ima i taj fix primijenjen lokalno (uncommitted), treba ga odvojiti od ovog rub31 fix-a.
- Preporuka: nakon mojibake fix-a, rebuild PyInstaller EXE-a i novi test-export sa
  `ŠUMA-35.xml` podacima da se potvrdi da Rub.31 editor više ne briše sadržaj.
