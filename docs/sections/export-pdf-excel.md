# PDF/Excel izvoz iz Faktura taba — dokumentacija izmjena

> **Link**: `docs/sections/export-pdf-excel.md`
> **Commit**: `f1f29cb` feat(export): PDF/Excel izvoz sa Faktura/Stavka/Naim. kolonama + Pregled faktura
> **Datum**: 2026-04-23

---

## Svrha

Omogućiti dva načina izvoza fakturnih stavki iz Faktura taba:
1. **PDF/Excel** — grupisanje po naimenovanjima (za internu upotrebu, pregled po naimenovanjima)
2. **Pregled** (PDF) — grupisanje po fakturi (za carinika, da vidi koja stavka iz koje fakture ide u koje naimenovanje)

Dodatno: rubrika 31 (trgovački naziv) u Naimenovanja tabu sada prikazuje koje fakture i koje stavke iz tih faktura ulaze u to naimenovanje.

---

## Zavisnosti

- **ReportLab** (`reportlab`) — PDF generisanje
- **openpyxl** — Excel generisanje
- **PySide6** — Qt file dialog i toolbar dugmad
- `core/draft/draft.py` — `InvoiceLine` model sa poljima `invoice_number`, `assigned_naimenovanje_ordinal`, `line_no`
- `services/export_service.py` — `ExportService` klasa

---

## Promjene

### 1. `exporters/pdf_invoice_exporter.py` — PDF izvoz (dugme PDF)

**Šta**: Prepravljena tabela u `_create_naimenovanja_table()`

**Promjene u headeru:**
```
PRIJE:  RB | Faktura | Šifra | Naziv robe | ... | Cijena | ...
POSLIJE: RB | Faktura | Stavka | Naim. | Naziv robe | ... | (bez Cijene) | ...
```

**Promjene u kolonama:**
- `Šifra` → `Stavka` (vrijednost: `line.line_no` umjesto `line.product_code`)
- Dodata kolona `Naim.` (vrijednost: `line.assigned_naimenovanje_ordinal`)
- Izbrisana kolona `Cijena` (cijena_jed)
- Širine kolona podešene: Faktura=3.8cm, Stavka=1.0cm, Naim.=1.1cm

### 2. `services/export_service.py` — Excel izvoz (dugme Excel)

**Šta**: Potpuno prepravljena metoda `export_to_excel()`

**Promjene:**
- Dodat opcioni parametar `draft: Optional[DeclarationDraft] = None`
- Grupisanje po naimenovanjima (isto kao PDF):
  - Plavi merged header red za svako naimenovanje: `NAIMENOVANJE X | Tarifa: YYY | Broj stavki: Z`
  - Header red sa istim kolonama kao PDF
  - Sivi total red sa sumama (Količina, Vrijednost, Bruto, Neto)
  - Prazan red između grupa
- Fiksne širine kolona (RB=5, Faktura=22, Stavka=6, Naim.=6, Naziv=40...)
- Izbrisane kolone: "Cijena", "Red.br." → "RB"
- Dodate kolone: "Faktura", "Stavka", "Naim."

### 3. `exporters/pdf_faktura_pregled.py` — NOV FAJL — Pregled faktura (dugme Pregled)

**Šta**: Potpuno novi exporter za pregled grupisan po fakturi

**Karakteristike:**
- Grupisanje po `invoice_number`
- Kolone: RB | Naimen. | Tarifa | Naziv robe | Količina | JM | Iznos (EUR) | Bruto kg | Neto kg
- Bez kolone Šifra (eksplicitno traženo)
- Tarifa proširena na 3.0cm
- Zbir po fakturi (subtotal)
- Grand total za cijelu deklaraciju
- Napomena na dnu: "Naimen. = redni broj naimenovanja u deklaraciji"
- Stilovi sa jedinstvenim imenima (PregledTitle, PregledSubTitle, itd.) da ne bi došlo do conflikta

### 4. `gui/tabs/faktura_view.py` — UI promjene

**Šta**: Dodato dugme "Pregled" u Izvezi toolbar

**Promjene:**
- Otkomentarisan `from exporters.pdf_invoice_exporter import export_invoice_to_pdf` (linija 64)
- Dodat import `from exporters.pdf_faktura_pregled import export_faktura_pregled`
- Dodato dugme "Pregled" sa ikonicom `fa5s.eye` i tooltipom
- Nova metoda `_on_export_pregled_faktura()`:
  - Provjera da li postoje invoice_lines i items
  - File dialog za čuvanje
  - Poziv `export_faktura_pregled(self.draft, filepath)`
  - Prikaz poruke sa brojem faktura i stavki
- Ažuriran poziv `ExportService.export_to_excel()` da prosljeđuje `self.draft`

### 5. `gui/tabs/naimenovanja_view.py` — Rubrika 31

**Šta**: `_format_trading_names()` sada dodaje info o fakturi

**Promjene:**
- Umjesto samo "proizvod1, proizvod2, ..." sada:
  ```
  proizvod1, proizvod2
  
  Faktura: FAKT-001 (rb. 1, 2), FAKT-002 (rb. 4)
  ```
- Pri skraćivanju (max 550 karaktera): prvo se skraćuju nazivi proizvoda, footer sa fakturarna ostaje netaknut
- Ako nema proizvoda, prikazuje se samo footer

---

## Zašto ovako

1. **Dva izvoza** — carinik zahtijeva pregled po fakturi, dok je interno potrebno grupisanje po naimenovanjima
2. **Bez Šifre** — eksplicitno traženje korisnika (nije potrebna u izvozu)
3. **Bez Cijene** — eksplicitno traženje korisnika (vrijednost je dovoljna)
4. **Stavka kolona** — omogućava cariniku da vidi koji redni broj na fakturi ima koji proizvod
5. **Excel grupisanje** — prati istu strukturu kao PDF radi konzistentnosti
6. **Rubrika 31 footer** — cariniku je bitno da u trgovačkom nazivu vidi iz koje fakture potiču proizvodi

---

## Linkovi u kodu

Sljedeći fajlovi imaju komentar `# docs/sections/export-pdf-excel.md`:
- `exporters/pdf_invoice_exporter.py` — kod `_create_naimenovanja_table()`
- `services/export_service.py` — kod `export_to_excel()`
- `exporters/pdf_faktura_pregled.py` — na početku fajla
- `gui/tabs/faktura_view.py` — kod dugmeta Pregled i Excel handlera
- `gui/tabs/naimenovanja_view.py` — kod `_format_trading_names()`
