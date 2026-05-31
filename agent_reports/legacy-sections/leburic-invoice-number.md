---
section: leburic_invoice_number
files:
  - importers/vendors/leburic/leburic_pekabesko_importer.py
  - gui/tabs/agent/agent_controller.py
  - gui/tabs/agent/services/import_pipeline_service.py
  - services/zaglavlje_service.py
  - gui/tabs/zaglavlje_controller.py
---

## Svrha

Ispravan izvor broja fakture za N380 (priloženi dokument u zaglavlju) kod Leburić/Pekabesko uvoza. Leburić šalje dva Excel fajla uz dva PDF-a za istu pošiljku. Excel "Invoice" kolona sadrži Leburić interni nalog broj (26-Ф15-...) — taj broj NE ide u carinarsku deklaraciju. Pravi komercijalni broj fakture (dobavljača Pekabesko) nalazi se u PDF headeru.

## Zavisnosti i pretpostavke

- Svaki Excel (`2000-00015.xlsx`, `20-00015.xlsx`) ima odgovarajući PDF u istom folderu
- `_find_pdf_for_excel()` nalazi PDF čiji OCR tekst sadrži Excel stem (npr. "2000-00015")
- PDF headeri imaju prepoznatljive linije: `Nalog br 0504-3-2000-00015` ili `FAKTURA: 0504-3-20-00015`
- OCR kvalitet je slab ali Nalog/FAKTURA linije su uglavnom čitljive

## Pravila i granice

### Prioritet izvora broja fakture (Excel+PDF kombinacija)

| Izvor | Sadržaj | Koristi se za |
|-------|---------|---------------|
| PDF `Nalog br` linija | `0504-3-2000-00015` (Pekabesko komercijalni) | N380 u zaglavlje — **PRIMARNO** |
| PDF `FAKTURA:` linija | `0504-3-20-00015` (Pekabesko komercijalni) | N380 — fallback ako nema Nalog linije |
| Excel `Invoice` kolona | `26-Ф15-2000-00015` (Leburić interni nalog) | Samo za log/debug — **NE ide u deklaraciju** |

Implementirano u `leburic_pekabesko_importer._extract_from_pdf()` — vraća `(bruto, neto, zemlja, invoice_number)`.

### Zabrana filename stem fallbacka

`file_item.invoice_number or Path(filepath).stem` bio je izvor problema: ako PDF parser ne uspije (npr. ćirilica u broju), stem fajla bi ušao u N380 kao lažni broj fakture.

**Pravilo:** stem fajla smije se koristiti SAMO za prikaz u chat aktivnostima, NIKAD za:
- `line.invoice_number` na stavkama
- `draft.ref_br` akumulaciju
- `brojevi_faktura` listu u import pipeline-u

### Višestruke fakture u jednoj deklaraciji

Kad deklaracija ima N faktura (npr. 2 Leburić fakture), N380 sadrži sve Pekabesko komercijalne brojeve spojene sa ` | `:

```
N380 number = "0504-3-2000-00015 | 0504-3-20-00015"
```

`zaglavlje_service` i `zaglavlje_controller` skupljaju sve unikatne `line.invoice_number` vrijednosti sa svih stavki (bez duplikata).

## Zašto ovako

Leburić Komerc (BiH uvoznik) i Pekabesko AD (MK dobavljač) imaju odvojene numeracije:
- Pekabesko numeracija: `0504-3-YYYY-NNNNN` (serija-tip-god-rbr) — ovo je komercijalna faktura
- Leburić nalog: `YY-Ф15-YYYY-NNNNN` (sadrži ćirilicu Ф) — interni nalog kupca

PDF parser regex `[0-9\-\./ ]{4,}` ne može uhvatiti ćirilično slovo Ф, pa bi broj u potpunosti failao bez ove logike. Excel "Invoice" kolona eksplicitno sadrži Leburić nalog broj koji izgleda kao broj fakture ali nije komercijalna faktura u smislu carinarenja.

## Regexovi za ekstrakciju iz PDF-a

```python
_NALOG_RE = re.compile(r"nalog\s+br[\s:.]*([0-9][0-9\-\./ ]{4,})", re.IGNORECASE)
_FAKTURA_RE = re.compile(r"faktura[:\s]+([0-9][0-9\-\./ ]{4,})", re.IGNORECASE)
```

`_NALOG_RE` ima prioritet — linija "Nalog br 0504-3-2000-00015" je čistija od OCR garble-a nego "FAKTURA: 0504.3.2000.0001 5" (koji može imati artefakte poput apostrofa i razmaka unutar broja).
