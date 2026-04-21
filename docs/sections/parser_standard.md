# Parser Standard — Obavezni minimum svakog importera

## Šta svaki parser mora da vrati

Svaki parser mora popuniti `ImportResult.exporter` i `ImportResult.importer`
kao `Party` objekte, i postaviti ista polja na svaku `InvoiceLine`.

```python
from core.draft.draft import Party
from importers.import_result import ImportResult

return ImportResult(
    items=items,
    bruto_kg=...,
    neto_kg=...,
    invoice_name=...,
    currency="EUR",
    exporter=Party(
        name="NAZIV STRANOG DOBAVLJAČA",   # OBAVEZNO
        city="Grad, Zemlja",               # ako postoji u dokumentu
        country="RS",                      # ISO kod ako dostupan
    ),
    importer=Party(
        name="NAZIV DOMAĆE BiH FIRME",     # OBAVEZNO
        vat_or_id="4XXXXXXXXXXX",          # JIB ako postoji u dokumentu
    ),
)
```

I na svakoj stavci:
```python
for item in items:
    item.exporter = exporter
    item.importer = importer
```

## Ko je ko

| Polje | Uloga | Rb. u ASYCUDA | Primjer |
|-------|-------|---------------|---------|
| `exporter` | **STRANI DOBAVLJAČ** koji šalje robu | Rb.2 Izvoznik | PEKABESKO AD, IMAMOGLU, TECHNOGREEN |
| `importer` | **DOMAĆA BiH FIRMA** koja prima robu | Rb.8 Primalac | Leburić Komerc, Šumaprom Commerce |

## Gdje naći podatke u dokumentima

### Fakturu/invoice kao PDF ili XLS
- **Exporter** = kompanija na letterheadu (vrh stranice) ili labela `SELLER/EKSPORTATOR/FROM`
- **Importer** = labela `BUYER/KUPAC/CONSIGNEE` (obično ispod exportera)
- **JIB uvoznika** = labela `JIB`, `PIB`, `Mat.br`, `VAT`, `ID broj` uz ime uvoznika

### XML faktura (Leburić format)
- `<Prodavac><Naziv>` → exporter
- `<Prodavac><PoreskiBroj>` → PDV/porezni broj exportera
- `<Kupac><Naziv>` → importer

### Ako podatak nije u dokumentu
Hardkodiraj poznato ime firme koja koristi taj parser:
```python
# leburic_pekabesko_importer.py — XLS nema header, uvoznik je uvijek isti
importer = Party(name="LEBURIĆ KOMERC D.O.O.")
```

## JIB validacija (opcionalno)

Ako parser izvuče JIB uvoznika, može se provjeriti u PostgreSQL:
```python
from services.partner_lookup_service import find_partner_by_jib
partner = find_partner_by_jib(jib)
if partner and partner['naziv'] != importer.name:
    logger.warning(f"JIB {jib} pripada '{partner['naziv']}', parser kaže '{importer.name}'")
```

## Checklist za novi parser

- [ ] `ImportResult.exporter` popunjen (name obavezan, city/country ako dostupno)
- [ ] `ImportResult.importer` popunjen (name obavezan, vat_or_id ako dostupno u dokumentu)
- [ ] `item.exporter` i `item.importer` postavljeni na svakoj stavci u petlji
- [ ] JIB izvlačen ako postoji u dokumentu
- [ ] `detect_*` funkcija ne vraća True za dokumente drugog dobavljača
