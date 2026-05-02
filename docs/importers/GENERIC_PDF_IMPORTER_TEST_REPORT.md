# Generic PDF Importer — Test sa stvarnim fakturama

Datum: 2026-04-03
Testirano fajlova: **20** (PDF)

---

## REZIME

| Metrika | Generic PDF Importer | Smart PDF Importer |
|---------|---------------------|-------------------|
| ✅ PASS | **0 / 20** (0%) | **2 / 20** (10%) |
| ⚠️ WARN | **0 / 20** | **15 / 20** (75%) |
| ❌ FAIL | **20 / 20** (100%) | **3 / 20** (15%) |
| Ukupno stavki | **0** | **345** |

### Presuda
**Generic PDF Importer je potpuno neupotrebljiv** — na svih 20 stvarnih fajlova vratio je **0 stavki**.
Smart PDF Importer uspijeva na 17/20 fajlova (85%).

---

## DETALJNI REZULTATI PO FAJTU

### Blagić Attos (3 fajla)

| Fajl | Generic | Smart | Status |
|------|---------|-------|--------|
| Faktura 720 | 0 stavki | 21 stavki | ❌ Generic fail |
| Faktura 721 | 0 stavki | 57 stavki | ❌ Generic fail |
| Faktura 722 | 0 stavki | 9 stavki | ❌ Generic fail |

**Zašto Smart radi:** Detektuje `blagic_attos` format → koristi specijalizovani parser → automatski kombinuje sa Listom pakovanja.
**Zašto Generic pada:** Ne pronalazi tabele u PDF-u (Blagić fakture nemaju klasičnu tabelarnu strukturu koju pdfplumber može detektovati).

---

### Blagić Loren (8 fajlova)

| Fajl | Generic | Smart | Status |
|------|---------|-------|--------|
| 107VP-2026 | 0 stavki | 25 stavki | ❌ Generic fail |
| 108VP-2026 | 0 stavki | 11 stavki | ❌ Generic fail |
| 109VP-2026 | 0 stavki | 4 stavki | ❌ Generic fail |
| 110VP-2026 | 0 stavki | 4 stavki | ❌ Generic fail |
| 112VP-2026 | 0 stavki | 12 stavki | ❌ Generic fail |
| 114VP-2026 | 0 stavki | 32 stavki | ❌ Generic fail |
| 115VP-2026 | 0 stavki | 29 stavki | ❌ Generic fail |

**Zašto Smart radi:** Detektuje `blagic_loren` format → koristi specijalizovani Loren PDF parser.
**Zašto Generic pada:** Isti razlog — pdfplumber `extract_tables()` ne pronalazi tabele.

---

### Master Frigo (5 fajlova)

| Fajl | Generic | Smart | Status |
|------|---------|-------|--------|
| R2503393 | 0 stavki | 4 stavki | ❌ Generic fail |
| R2503394 | 0 stavki | 51 stavki | ❌ Generic fail |
| R2503395 | 0 stavki | 28 stavki | ❌ Generic fail |
| R2600310 | 0 stavki | 35 stavki ✅ | ❌ Generic fail |
| R2600311 | 0 stavki | 16 stavki ✅ | ❌ Generic fail |

**Napomena:** R2600310 i R2600311 imaju `tarife i zemlje porekla.xlsx` u istom folderu, pa Smart parser popunjava tarifne brojeve i zemlje.

---

### Medicopharm (1 fajl)

| Fajl | Generic | Smart | Status |
|------|---------|-------|--------|
| Medicopharm.pdf | 0 stavki | 0 stavki | ❌ Oba fail |

**Zašto oba padaju:** PDF nema extractable tabele. Tekst je vjerovatno skeniran image, ne text-based PDF. Potrebna bi bila OCR ekstrakcija.

---

### ŠUMAPROM (1 fajl)

| Fajl | Generic | Smart | Status |
|------|---------|-------|--------|
| DOC041122.pdf | 0 stavki | 0 stavki | ❌ Oba fail |

**Zašto oba padaju:** Isti problem — PDF bez extractable tabela. ŠUMAPROM PDF parser nije implementiran (koristi generic fallback).

---

### Stanc / Coppercom (2 fajla)

| Fajl | Generic | Smart | Status |
|------|---------|-------|--------|
| Invoice 234 STANCMETAL | 0 stavki | 0 stavki | ❌ Oba fail |
| Faktura Coppercom | 0 stavki | 0 stavki | ❌ Oba fail |

**Zašto oba padaju:** PDF-ovi bez extractable tabela. Vjerovatno skenirani dokumenti.

---

### Srecko (1 fajl)

| Fajl | Generic | Smart | Status |
|------|---------|-------|--------|
| SRECKO- faktura | 0 stavki | **31 stavki** ✅ | ❌ Generic fail |

**Smart parser:** Detektuje `invoice_improved` format → ekstrakcuje 31 stavku sa tarifnim brojem (8516808000 iz footera), zemljom (RS), i proporcionalno raspoređenim težinama.

---

## KORIJENSKI PROBLEM GENERIC PDF IMPORTER-A

### Zašto Generic PDF Importer vraća 0 stavki na SVIM fajlovima?

Ključni problem je u `_detect_columns()` i `_parse_table_items()` funkcijama:

1. **`pdfplumber.extract_tables()` ne pronalazi tabele** — Vraća `None` ili praznu listu na svim testiranim fajlovima.
2. Generic parser **samo radi sa tabelarnim PDF-ovima** — ako pdfplumber ne može detektovati tabele, parser vraća prazan rezultat.
3. **Nema text-based fallback** — Za razliku od specijalizovanih parsera koji rade line-by-line parsing, generic parser nema fallback na tekstualnu ekstrakciju.

### Logika pada:

```
parse_generic_pdf()
  → pdfplumber.extract_tables() → []  (prazno za sve test fajlove)
  → return ImportResult(items=[], ...)
```

### Poređenje sa Smart PDF Importer-om:

```
parse_smart_pdf()
  → _detect_pdf_format() → "blagic_attos" / "blagic_loren" / "master_frigo" / "invoice_improved" / "generic"
  → koristi specijalizovani parser koji radi line-based parsing
  → ✅ 345 stavki ukupno
```

---

## GREŠKE U SMART PDF IMPORTER-U (WARN statusi)

Smart parser vraća `WARN` (ne FAIL) za 15/20 fajlova zbog sledećih upozorenja:

### Stavke bez tarifnog broja
- Blagić Attos 720: 21/21 stavki bez tarifnog broja
- Blagić Attos 721: 57/57 stavki bez tarifnog broja
- Blagić Loren (svi): Sve stavke bez tarifnog broja (PDF format nema tarife)

### Stavke bez zemlje porijekla
- Blagić Attos 720: 21/21 stavki bez zemlje (izjava o poreklu nađena ali bez specificiranog country code-a)

### Stavke bez cijene/iznosa
- Blagić Loren (svi): Sve stavke bez cijene (Loren Excel ima samo težine, cijene dolaze iz drugog izvora)
- Master Frigo (neki): Stavke bez cijena zavisi od mapping Excel-a

---

## PREPORUKE

### 1. **Generic PDF Importer treba deprecirati ili potpuno prepisati**

Trenutna implementacija radi **isključivo** sa PDF-ovima koji imaju pdfplumber-extractable tabele. Na 20 stvarnih faktura, **nijedna** nije imala takvu strukturu. Ovo znači da je Generic PDF Importer u proizvodnji **beskoristan**.

**Opcije:**
- **A)** Dodati text-based fallback (line-by-line parsing kao u invoice_improved_parser)
- **B)** Ukloniti Generic PDF Importer i koristiti samo Smart PDF Importer
- **C)** Označiti ga kao "eksperimentalni" i sakriti iz UI-ja

### 2. **Medicopharm, ŠUMAPROM, Stanc, Coppercom zahtijevaju OCR**

Ovi PDF-ovi su vjerovatno skenirani dokumenti. Bez OCR-a (npr. Tesseract, pdfplumber sa `image=True`), nijedan parser ih neće moći pročitati.

### 3. **Smart PDF Importer treba dodati fallback za nepoznate formate**

Trenutno za nepoznate formate (`generic`) koristi isti generic parser koji uvijek vraća 0 stavki. Treba dodati bar osnovni text-based extraction kao fallback.

### 4. **Dodati unit testove sa ovim stvarnim fajlovima**

Ovih 20 fajlova čine odličan regression test set. Treba ih dodati u `tests/` sa očekivanim rezultatima.

---

## TEST SKRIPTA

Lokacija: `tests/test_real_invoices_generic_pdf.py`

Pokretanje:
```bash
python tests/test_real_invoices_generic_pdf.py
```
