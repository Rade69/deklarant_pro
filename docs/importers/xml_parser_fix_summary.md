# XML Parser Fix - Količine iz ASYCUDA XML fajlova

## Problem
XML parser je hardkodirao količinu na "1" za sve stavke u ASYCUDA XML fajlovima (npr. 1.xml) umjesto da uzima stvarne količine iz XML-a.

## Rješenje
Ispravljeno parsiranje količina i dodato product_code parsiranje.

### Ključne promjene u `importers/xml_importer.py`:

1. **Količine** - dodan prioritet za `<Number_of_packages>`:
```python
quantity = self._get_float(item_elem, [
    'Packages/Number_of_packages',  # NOVO: prvi prioritet
    'Supplementary_unit/Suppplementary_unit_quantity',
    'Supplementary_quantity',
    'TariffQuantity',
    'Commodity/GoodsMeasure/TariffQuantity'
], default=1.0)
```

2. **Product code** - parsiranje iz `Commercial_Description`:
```python
# Uzmi prvi dio opisa (do zareza, tačke-zareza ili novog reda)
cleaned = product_code.replace('\n', ' ').replace('\r', ' ').strip()
for sep in [';', ',', '.', '-']:
    if sep in cleaned:
        product_code = cleaned.split(sep)[0].strip()
        break
else:
    # Ako nema separatora, uzmi prvu riječ
    parts = cleaned.split()
    product_code = parts[0].strip() if parts else cleaned.strip()
```

3. **Dodavanje u InvoiceLine**:
```python
invoice_line = InvoiceLine(
    line_no=int(item_number) if item_number.isdigit() else idx,
    product_code=product_code,  # NOVO
    ...
)
```

## Test rezultati
**Fajl**: `1.xml`
**Prije**: Sve količine = 1.0
**Poslije**: Količine = [100.0, 157.0, 10196.0, 20.0]

## Važno za buduće parsere
- ASYCUDA XML koristi `<Number_of_packages>` za količinu u komadima
- `<Supplementary_unit_quantity/>` tagovi su često prazni
- `Commercial_Description` sadrži detaljan opis za product_code

## Commit
`ee76416 fix(xml-importer): ispravi parsiranje količina i dodaj product_code`

## Datum
20. april 2026