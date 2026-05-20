# Agent report — Univerzalni Rub.31 format i proizvodni tekst kao lazni tarifni opis

Datum: 2026-05-20

## Problem

Korisnik je testirao Blagic-Loren XML u ASYCUDA aplikaciji i pokazao razliku izmedju
12. i 13. naimenovanja:

- 12. naimenovanje je imalo tarifni opis i naziv robe u pravilnom rasporedu.
- 13. naimenovanje je i dalje dupliralo naziv robe jer je `tariff_description1`
  bio sastavljen od vise naziva robe spojenih tacka-zarezom.

Primjer neispravnog obrasca:

```text
TUNEL GUMA CANDY 117CY22 GSK016CY CY3035; TUNEL GUMA...
TUNEL GUMA CANDY 117CY22 GSK016CY CY3035, TUNEL GUMA...
Faktura: 266VP-2026 (rb. 10, 11)
```

## Pravilo

Rub.31 mora univerzalno imati ovaj raspored:

```text
opis tarife
naziv robe ili skraceni spisak naziva robe
Faktura: broj (rb. ...)
```

To vazi bez obzira da li naimenovanje ima jednu ili vise fakturnih stavki.

## Urađeno

- Kandidat za tarifni opis se odbacuje ako je zapravo naziv jedne robe.
- Kandidat za tarifni opis se odbacuje i ako je sastavljen od vise naziva robe
  razdvojenih `;` ili novim redom.
- Tada se koristi stvarni tarifni opis iz `tariff_description2`, a nazivi robe idu
  u drugi red.
- Dodan regresioni test za 13. Blagic-Loren slucaj sa dvije TUNEL GUMA stavke.

Ocekivani izlaz:

```text
- - zaptivci, podlosci i ostali proizvodi za zaptivanje
TUNEL GUMA CANDY 117CY22 GSK016CY CY3035, TUNEL GUMA...
Faktura: 266VP-2026 (rb. 10, 11)
```

## Testovi

Pokrenuto:

```bash
python -m pytest tests/unit/test_asycuda_goods_description.py tests/unit/test_parse_naimenovanja_xml.py tests/unit/test_pe_rub44_consistency.py tests/unit/test_naimenovanja_view_display_values.py -q
python -m py_compile exporters/asycuda_xml_builder.py
```

Rezultat:

```text
42 passed
py_compile OK
```

## GitNexus

- `impact(_build_commercial_description)`: LOW
- `impact(_build_description_of_goods)`: LOW
- `detect_changes`: LOW, bez pogodjenih execution flow-ova

## Napomena

`AGENTS.md` i `CLAUDE.md` su imali nevezane lokalne izmjene i nisu dio ove
promjene.
