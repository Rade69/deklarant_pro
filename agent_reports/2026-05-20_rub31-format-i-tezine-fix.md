# Agent report — Rub.31 format i težine XML fix

Datum: 2026-05-20

## Šta je urađeno

Tri nezavisna fixa u ASYCUDA XML exportu, plus refaktor:

1. **Težine uvijek sa 2 decimale** (`_fmt_weight`)
2. **Commercial_Description: strogo 3 linije** — tarifni opis + roba + faktura
3. **Inline logika premještena u `rub31_builder` servis**

## Kako je urađeno

### Fix 1 — Težine (commit `06b66cf`)
`_fmt_weight` u `asycuda_xml_builder.py` mijenjano iz "strip trailing zeros" u `f"{round(v, 2):.2f}"`.
Uzrok: ASYCUDA interno čuva i prikazuje decimalne vrijednosti; pri ponovnom uvozu XML-a
`516` postaje `516.0`, što stvara neslaganje između naših i ASYCUDA generisanih fajlova.

### Fix 2 — Rub.31 format (commit `c344231`)
`_commercial_lines` u `rub31_builder.py`:
- `_MAX_LINES = 3` (vraćeno sa 4)
- Description se prepend-uje kao L1: inspektori traže tarifni opis u polju
- L2: svi nazivi roba comma-joined (1 linija — jedino što stane uz L1 i L3)
- L3: Faktura referenca

**Ključno ograničenje ASYCUDA**: editabilno polje Rub.31 prihvata maksimalno 3 linije
po 55 karaktera. Sadržaj koji prekorači ove granice se izgubi pri kliku na polje.

`Description_of_goods` (automatski popunjen od ASYCUDA na osnovu tarifnog broja) je
reduciran prikaz — inspektori traže puni opis u `Commercial_Description`.

### Fix 3 — Refaktor (commit `d9501b7`)
`_build_description_of_goods` i `_build_commercial_description` u `AsycudaXMLBuilder`
sada delegiraju na `build_asycuda_rub31()` — uklonjeno ~100 linija duplikata.

## Zašto

- ASYCUDA GUI gubi sadržaj Rub.31 pri kliku ako ima >3 linije ili liniju >55 karaktera
- Carinski inspektori traže tarifni opis u editabilnom polju, ne samo u Description_of_goods
- Težine bez decimala stvaraju neslaganje pri ponovnom uvozu u ASYCUDA

## Commitovi

| Hash | Opis |
|------|------|
| `06b66cf` | fix(xml): težine u XML-u uvijek sa 2 decimale |
| `dc97790` | fix(rub31): tarifni opis kao 1. linija, max 4 linije — REVERTOVANO |
| `c344231` | fix(rub31): commercial_description strogo 3 linije |
| `d9501b7` | refactor(rub31): premjesti inline logiku u build_asycuda_rub31 servis |
| `944a95b` | chore(gitnexus): ažuriraj statistike indeksa |
