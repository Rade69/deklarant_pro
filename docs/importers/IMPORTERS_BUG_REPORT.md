# Importers Bug Report

Datum: 2026-04-03

---

## CRITICAL BUGS

### 1. `importers/xml_importer.py` — Shadowing built-in `ImportError`

**Linije:** 1 (top), `_parse_items` error handling, `_parse_pro_items` error handling

**Problem:** Fajl koristi `logger.debug(f"Warning: ...")` unutar `except Exception` bloka u `_parse_items` i `_parse_pro_items`. Kada dođe do greške pri parsiranju stavke, ona se tiho preskače sa `continue`. Ovo znači da se greške pri parsiranju XML stavki **nikad ne prijavljuju** korisniku — stavke se samo tiho gube.

**Rizik:** Korisnik misli da je XML validan, a zapravo mu fale stavke bez ikakvog upozorenja.

**Fix:** Koristiti `logger.warning` ili `logger.error` umjesto `logger.debug`. Dodatno, sakupiti sve greške i vratiti ih u result dictionary.

---

### 2. `importers/blagic_importer.py` — `validate_import_result` koristi nepostojeće atribute

**Linije:** ~260-285

```python
for i, line in enumerate(lines):
    if line.quantity <= 0:
        stats["errors"].append(f"Stavka {line.position_number}: količina <= 0")
    if line.cijena_jed <= 0:
        stats["errors"].append(f"Stavka {line.position_number}: cijena <= 0")
```

**Problem:** `InvoiceLine` nema atribute `position_number`, `tariff_code`, `origin_country`, `unit`. Koristi se: `line_no`, `tarifni_broj`, `zemlja_porijekla`, `jm`, `kolicina`, `cijena_jed`.

**Fix:** Zamijeniti:
- `line.position_number` → `line.line_no`
- `line.tariff_code` → `line.tarifni_broj`
- `line.origin_country` → `line.zemlja_porijekla`
- `line.unit` → `line.jm`

---

### 3. `importers/blagic_importer.py` — `_safe_float` hendluje slova pogrešno

**Linije:** ~40-55

```python
if any(c.isalpha() for c in s if c.lower() not in ["e", ".", ","]):
    return 0.0
```

**Problem:** Ovaj check sprječava parsiranje naučne notacije sa minusom (npr. `1.5E-10` — minus se ne provjerava). Takođe, `€` se uklanja na početku ali se provjera za slova vrši poslije, što znači da valjani iznosi sa valutom (npr. `100EUR`) bivaju odbijeni jer `€` je već uklonjen ali `EUR` slova ostaju.

**Fix:** Ukloniti sve alpha karaktere osim `e` za naučnu notaciju, ili jednostavnije — pokušati `float()` direktno i hvatati `ValueError`.

---

### 4. `importers/strategy_registry.py` — Circular imports pri importovanju

**Linije:** ~185-190

```python
def _register_default_strategies(registry: StrategyRegistry) -> None:
    from importers.strategies.pdf_strategy import PDFImportStrategy
    from importers.strategies.excel_strategy import ExcelImportStrategy
    from importers.strategies.xml_strategy import XMLImportStrategy
```

**Problem:** `XMLImportStrategy` radi `from importers.xml_importer import XMLImporter` na top-level (line 15). Ako se `strategy_registry` učita prije nego što su `core.draft` moduli dostupni, dolazi do circular import greške.

**Rizik:** Aplikacija može pasti pri startu ako se registry inicijalizuje prerano.

**Fix:** Lazy import svih tri strategije unutar `_register_default_strategies`, plus lazy import `XMLImporter` unutar `XMLImportStrategy.__init__`.

---

## MAJOR BUGS

### 5. `importers/blagic_combined_importer.py` — `Dict[str, any]` treba `Dict[str, Any]`

**Linije:** ~143

```python
) -> Tuple[List[InvoiceLine], Dict[str, any]]:
```

**Problem:** `any` (lowercase) nije validan tip hint u Pythonu. Treba `Any` (importovan iz `typing`). Ovo pyright/type checker prijavljuje kao grešku.

**Fix:** `Dict[str, Any]`

---

### 6. `importers/generic_pdf_importer.py` — `_parse_number` ne hendluje EU format ispravno

**Linije:** ~248-263

```python
def _parse_number(text: str) -> float:
    text = re.sub(r'[^\d,.\-]', '', str(text))
    text = text.replace(',', '.')
    if text.count('.') > 1:
        parts = text.split('.')
        text = ''.join(parts[:-1]) + '.' + parts[-1]
```

**Problem:** Za EU format `1.234,56`:
1. `re.sub` zadrži sve: `1.234,56`
2. `.replace(',', '.')` → `1.234.56`
3. `text.count('.') > 1` → True (2 tačke)
4. Result: `1234.56` ✅ — OVO RADI za ovaj slučaj

Ali za `1234,56`:
1. `re.sub` → `1234,56`
2. `.replace(',', '.')` → `1234.56` ✅

Ali za `1.234.567,89`:
1. `re.sub` → `1.234.567,89`
2. `.replace(',', '.')` → `1.234.567.89`
3. 4 tačke → `1234567.89` ✅

Ovo zapravo radi, ali je problematično za brojeve sa razmacima: `1 234,56` — razmak se ukloni, ali onda `1234,56` postane `1234.56`. OK je.

**NAPOMENA:** Ovo nije bug za većinu slučajeva, ali `invoice_line_utils.parse_eu_number()` ima ispravniju logiku sa `rfind` provjerom. Preporučuje se korištenje te funkcije umjesto dupliciranja logike.

---

### 7. `importers/blagic_loren_importer.py` — Neto težina se postavlja na 0.0

**Linije:** ~360

```python
item = InvoiceLine(
    ...
    bruto_kg=tezina_ukupno,  # VAŽNO: "Težina ukupno" u Excel-u je BRUTO težina!
    neto_kg=0.0,  # Neto nije dostupno u Excel-u
    ...
)
```

**Problem:** U `_parse_item_row`, `bruto_kg` se postavlja na `tezina_ukupno`, ali `neto_kg` je uvijek `0.0`. Komentar kaže "Neto nije dostupno" — ali u Excel fajlu kolona F je "Težina po komadu kg", što je zapravo neto težina po komadu. Neto bi se mogao izračunati kao `tezina_po_komadu * kolicina`.

**Fix:** Postaviti `neto_kg=tezina_po_komadu * kolicina` umjesto `0.0`.

---

### 8. `importers/invoice_improved_parser.py` — `_parse_item_data` koristi pogrešne nazive parametara

**Linije:** ~160-177

```python
return InvoiceLine(
    ordinal=num,
    code=code or "",
    naziv=f"Stavka {num}",
    unit="",
    quantity=0,
    unit_price=0,
    amount=0
)
```

**Problem:** `InvoiceLine` nema atribute `ordinal`, `code`, `naziv`, `unit`, `quantity`, `unit_price`, `amount`. Ispravni nazivi su: `line_no`, `product_code`, `naziv_robe`, `jm`, `kolicina`, `cijena_jed`, `iznos`.

**Fix:** Koristiti ispravne nazive polja.

---

### 9. `importers/smart_pdf_importer.py` — `_parse_sumaprom` koristi generic fallback

**Linije:** ~147-151

```python
def _parse_sumaprom(pdf_path: str) -> ImportResult:
    logger.warning("⚠️  ŠUMAPROM PDF parser još nije implementiran - koristi se generic parser")
    return parse_generic_pdf(pdf_path)
```

**Problem:** Postoji `sumaprom_pdf_parser.py` fajl u `importers/pdf/` direktorijumu, ali se ne koristi. Umjesto toga, koristi se generic parser koji može dati lošije rezultate.

**Fix:** Provjeriti da li `sumaprom_pdf_parser.py` postoji i iskoristiti ga.

---

## MINOR BUGS

### 10. `importers/excel_importer.py` — `.xls` fajlovi se ne zatvaraju eksplicitno

**Linije:** ~150-160

```python
if ext == '.xls':
    import xlrd
    wb = xlrd.open_workbook(filepath)
else:
    wb = openpyxl.load_workbook(filepath, data_only=True)
...
if ext == '.xlsx':
    wb.close()
```

**Problem:** `.xls` fajlovi otvoreni sa `xlrd` se nikad ne zatvaraju. Iako `xlrd` nema `.close()` metodu, dobro je imati konzistentan kod. Takođe, `xlrd` se importuje unutar try bloka — ako import fail-uje, greška se ne hendluje čisto.

---

### 11. `importers/strategy_registry.py` — `reset_registry` ne resetuje automatski registrovane strategije

**Linije:** ~205-215

```python
def reset_registry() -> None:
    global _registry
    _registry = None
```

**Problem:** `reset_registry()` postavlja `_registry = None`, ali sledeći poziv `get_registry()` će ponovo registrovati default strategije. Ako su korisnici ručno registrovali custom strategije prije reset-a, one će biti izgubljene bez upozorenja.

**Preporuka:** Dodati warning logging ili vratiti listu izgubljenih custom strategija.

---

### 12. `importers/blagic_attos_importer.py` — `find_matching_packing_list` koristi glob koji može matchovati više fajlova

**Linije:** ~80-95

```python
packing_list_pattern = f"Lista pakovanja {invoice_number}*.pdf"
for file in folder.glob(packing_list_pattern):
    logger.info(f"Pronađena lista pakovanja: {file.name}")
    return str(file)
```

**Problem:** Ako postoje više packing lista sa istim brojem (npr. "Lista pakovanja 3940 Blagić.pdf" i "Lista pakovanja 3940 Blagić (kopija).pdf"), vrati se prva nađena koja ne mora biti ispravna.

**Preporuka:** Sortirati rezultate i preferirati fajlove bez "(kopija)" u imenu.

---

### 13. `importers/generic_pdf_importer.py` — `_detect_columns` preskače UNIT_PRICE kolone sa "NET" u imenu

**Linije:** ~130-135

```python
elif re.search(r'\bUNIT.*PRICE\b|\bPRICE\b|\bCIJENA\b|\bCENA\b', cell) \
        and 'TOTAL' not in cell and 'AMOUNT' not in cell \
        and 'NETO' not in cell and 'NET' not in cell \
        and mapping.unit_price is None:
```

**Problem:** Ako fajl ima kolonu "Unit Price (Net)" ili "NET UNIT PRICE", ona će biti preskočena. Ovo može dovesti do toga da cijena ne bude detektovana.

**Fix:** Provjeriti da li je "NET" dio cijene (što je često slučaj) ili je kolona zapravo "Net Amount" (što nije cijena).

---

### 14. `importers/packing_list_parser.py` — `_fuzzy_match` koristi jednostavnu metriku

**Linije:** ~450-480

```python
def _fuzzy_match(text1: str, text2: str) -> float:
    ...
    if t1 in t2 or t2 in t1:
        return 0.90
    tokens1 = set(t1.split())
    tokens2 = set(t2.split())
    ...
    return len(intersection) / len(union) if union else 0.0
```

**Problem:** Ova funkcija ne koristi `difflib.SequenceMatcher` kao što komentari navode, već jednostavnu token-based Jaccard sličnost. Za kratke nazive proizvoda (npr. "GREJAC GPB-2000W" vs "GREJAC GPB-2000"), ovo može dati nisku sličnost jer je jedan token različit.

**Preporuka:** Koristiti `difflib.SequenceMatcher` za bolje rezultate.

---

## POTENCIJALNI PROBLEMI

### 15. Svi importer fajlovi — Nedostaju type hint-ovi za return type

Mnoge funkcije nemaju return type hint-ove, što otežava static type checking (pyright).

### 16. `importers/__init__.py` — Samo eksportuje `ImportResult`

Ostale klase (`ImportStrategy`, `StrategyRegistry`, `ImportResult`, exception klase) se ne eksportuju iz `__init__.py`, što znači da se moraju importovati sa punim path-om.

### 17. `importers/blagic_combined_importer.py` — Hardkodovani test path

**Linije:** ~305

```python
excel_file = "najavauvoza/blagic-loren/702VP-2025 BLAGIC.xlsx"
pdf_file = "najavauvoza/blagic-attos/Faktura 3940 Blagić.pdf"
```

Test path-ovi u `__main__` bloku koriste relativne path-ove koji možda ne postoje na svim sistemima.

---

## PREPORUKE

1. **Konsolidovati `_parse_number` funkcije** — Postoji 6+ duplikata ove funkcije u različitim importerima. Kreirati zajedničku funkciju u `invoice_line_utils.py`.

2. **Dodati unit testove** za svaki importer sa poznatim input/output parovima.

3. **Standardizovati logging** — Neki importeri koriste `logger.debug`, drugi `logger.info` za iste operacije.

4. **Dodati error reporting** — Trenutno se greške loguju ali se ne vraćaju korisniku na način koji omogućava akciju.

5. **Kreirati zajednički test dataset** — Folder sa poznatim PDF/Excel/XML fajlovima i očekivanim rezultatima za regresiono testiranje.
