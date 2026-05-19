# Agent Report: Import Validator — Pouzdanost parsera

**Datum:** 2026-05-19
**Grana:** dev
**Commit:** `9b7c5c5`

---

## Problem

Parser može uspješno završiti bez Python exceptiona, ali vratiti fizički neispravne
podatke: 0 stavki, negativne cijene, neto > bruto. Oba moda (manuelni i agentski)
prihvatala su takve rezultate bez provjere — korisnik bi uvezao praznu deklaraciju.

---

## Arhitektura rješenja

```
import_service.import_file()
        │
        ▼
ImportResult (items, bruto_kg, neto_kg, currency, warnings...)
        │
        ▼ ← NOVO
ImportResult.validate()   ← parser-level, bez DB poziva
        │
   ┌────┴────┐
   │         │
errors    warnings
(blokira) (nastavlja)
        │
        ▼
validate_import_result()  ← ImportValidator servis
        │
   ┌────┴──────────────┐
   │                   │
faktura_view       processing_worker
(manuelni mod)     (agentski mod)
```

---

## Šta validate() provjerava

### Greške (blokiraju uvoz)
| Provjera | Poruka |
|----------|--------|
| `len(items) == 0` | "Parser nije pronašao nijednu stavku (0 stavki)" |
| `bruto_kg < 0` | "Negativna bruto težina: X kg" |
| `neto_kg < 0` | "Negativna neto težina: X kg" |
| `neto_kg > bruto_kg` | "Neto (X) > Bruto (Y) — fizički nemoguće" |
| `cijena_jed < 0` | "Stavka N: negativna cijena X" |
| `iznos < 0` | "Stavka N: negativan iznos X" |

### Upozorenja (ne blokiraju)
| Provjera | Poruka |
|----------|--------|
| `naziv_robe` prazan | "Stavka N: prazan naziv robe" |
| `kolicina <= 0` | "Stavka N: količina = X" |
| Nepoznata valuta | "Nepoznata valuta: 'XYZ'" |
| Stavka neto > bruto | "Stavka N: neto > bruto (X > Y)" |

---

## Novi fajlovi

- `importers/import_result.py` — dodata metoda `validate()`
- `services/import_validator.py` — `validate_import_result()`, `format_validation_summary()`
- `tests/unit/test_import_validator.py` — 21 unit test
- `tests/unit/test_parser_regression.py` — 25 regression testova sa realnim fajlovima

## Izmijenjeni fajlovi

- `gui/tabs/faktura_view.py` — validator pozvan u `_import_multiple_files()`
- `gui/tabs/agent/widgets/processing_worker.py` — validator pozvan u processing loopu

---

## Regression testovi (realni fajlovi)

| Vendor | Fajl | Stavke | Provjera |
|--------|------|--------|----------|
| Leburic Excel | 20-00015.xlsx | 4 | bruto=5323kg, neto=3876.76kg |
| Leburic PDF | 00021.pdf | 8 | iznos=17904.35 EUR, bruto=4909kg |
| Leburic PDF | 00022.pdf | 12 | iznos=52071.06 EUR, bruto=10166kg |
| Imamoglu | PACKING LIST.xlsx | 42 | bruto=2383kg, sve stavke imaju naziv i kolicinu>0 |
| Medicopharm | medicopharm-421.pdf | >0 | validate() prolazi |
| Šumaprom | mock | — | detect=False za nepostojeći fajl |

---

## Ukupan broj testova: 292 (svi prolaze)
