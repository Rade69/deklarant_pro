# Agent report — ASYCUDA Rub.31 tarifni opis i deduplikacija robe

Datum: 2026-05-20

## Problem

Korisnik je uporedio XML koji izvozi Deklarant Pro, isti XML nakon obrade u ASYCUDA
aplikaciji i snimke ekrana Rub.31 za Blagic-Loren pošiljku.

Uocena su dva problema:

- Opis tarife mora biti automatizovan u Rub.31, ali ponekad je prva linija
  `Commercial_Description` bila naziv robe umjesto tarifnog opisa.
- ASYCUDA je prikazivala naziv robe dva puta jer je aplikacija vec izvezla
  dupliranu prvu i drugu liniju komercijalnog opisa.

Primjer neispravnog izlaza:

```text
GREJAC RERNE GORENJE 1100W PERLA 616021 (GP1127) UZI...
GREJAC RERNE GORENJE 1100W PERLA 616021 (GP1127) UZI...
Faktura: 266VP-2026 (rb. 2)
```

## Urađeno

- `AsycudaXMLBuilder._build_commercial_description()` sada poredi kandidate za
  tarifni opis sa nazivima fakturnih stavki.
- Ako se kandidat za tarifni opis poklapa sa nazivom robe, preskace se kao
  tarifni opis i koristi se sljedeci kandidat, najcesce `tariff_description2`.
- Nazivi robe se normalizuju prije deduplikacije, tako da razlike samo u visku
  razmaka ne prave duple linije.
- Zadrzan je namjerni format Rub.31:
  1. opis tarife
  2. naziv robe ili skraceni spisak naziva robe
  3. broj fakture i redni brojevi stavki

Primjer popravljenog izlaza:

```text
- - ostali
GREJAC RERNE GORENJE 1100W PERLA 616021 (GP1127) UZI
Faktura: 266VP-2026 (rb. 2)
```

## Testovi

Pokrenuto:

```bash
python -m pytest tests/unit/test_asycuda_goods_description.py tests/unit/test_parse_naimenovanja_xml.py tests/unit/test_pe_rub44_consistency.py tests/unit/test_naimenovanja_view_display_values.py -q
python -m py_compile exporters/asycuda_xml_builder.py
```

Rezultat:

```text
39 passed
py_compile OK
```

## GitNexus

- Impact analiza za `_build_commercial_description`: LOW
- `detect_changes`: risk level LOW, bez pogodjenih execution flow-ova

## Napomena

`AGENTS.md` i `CLAUDE.md` su imali nevezane lokalne izmjene i nisu dio ove
promjene.
