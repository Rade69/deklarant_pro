# importers/sumaprom_pdf_parser.py

"""
ŠUMAPROM PDF Parser
Parser za skenirane ŠUMAPROM PDF fakture (Technogreen dobavljač).

Format fakture (OCR):
  [rb] product_code naziv_robe [jm_noise] [kolicina] cijena_jed iznos ZEMLJA/NAZIV

Pouzdani ankeri za parsiranje:
  - Zemlja uvijek na kraju: XX/NAZIV (npr. DE/NEMACKA, SER/SRBIJA)
  - Iznos i cijena su zadnji brojevi prije zemlje
  - product_code je prvi token (može imati crtice, tačke)
"""

import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

import pdfplumber

from core.draft.draft import InvoiceLine
from importers.import_result import ImportResult
from utils.country_normalizer import normalize_country_name

logger = logging.getLogger("deklarant_pro.import.sumaprom_pdf")

# Tokeni koje OCR generiše za JM/kolicinu — treba ih preskočiti
_JM_NOISE = re.compile(
    r'\b(?:Net|Nrt|Nr|Ne|Nev|Nes|Ned|Nesh|Nev|Lush|doaed|kom|set|hom|'
    r'met|Mot|Set|Sot|Sot\/set|Set\/set|set\/set|BBT|WILL|LON|CPT|EURO|AIP|ALP|'
    r'PLATT|PLAST|WAL|TILL|ZAMA|ERGO|DUPLA)\b',
    re.IGNORECASE,
)

# Zemlja pattern: XX/ ili XX / (2-3 velika slova + kosa crta)
_COUNTRY_RE = re.compile(r'\b([A-Z]{2,3})\s*/\s*[A-Z]{2,}', re.IGNORECASE)

# Broj sa zarezom ili tačkom
_NUMBER_RE = re.compile(r'^\d+(?:[,\.]\d+)?$')


def detect_sumaprom_pdf(filepath: str) -> bool:
    """Detektuje ŠUMAPROM PDF — radi i za skenirane PDFove (OCR)."""
    try:
        with pdfplumber.open(filepath) as pdf:
            text = "".join(p.extract_text() or "" for p in pdf.pages[:2])

        if len(text.strip()) < 50:
            # Skenirani — probaj OCR na prvoj stranici
            from importers.pdf.ocr_utils import ocr_pdf_to_text_no_lines
            pages = ocr_pdf_to_text_no_lines(filepath, dpi=300)
            text = pages[0] if pages else ""

        t = text.upper()
        # Detektuj ŠUMAPROM po: nazivu firme, ili po karakteristikama (R.br., Item Code, itd)
        if ("SUMAPROM" in t or "ŠUMAPROM" in t) and ("FAKTURA" in t or "INVOICE" in t):
            return True
        # Ako nema SUMAPROM ali format fakture odgovara (TECHNOGREEN + faktura)
        if "TECHNOGREEN" in t and ("FAKTURA" in t or "INVOICE" in t):
            return True
        return False

    except Exception as e:
        logger.debug(f"detect_sumaprom_pdf error: {e}")
        return False


def parse_sumaprom_pdf(pdf_path: str) -> ImportResult:
    """Parsira ŠUMAPROM PDF fakturu (tekstualni ili skenirani)."""
    logger.info(f"ŠUMAPROM PDF parser: {Path(pdf_path).name}")

    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = "".join(p.extract_text() or "" for p in pdf.pages)

        if len(text.strip()) > 100:
            logger.info("  Tekstualni PDF")
        else:
            logger.info("  Skenirani PDF — koristim OCR sa uklanjanjem linija")
            from importers.pdf.ocr_utils import ocr_pdf_to_text_no_lines
            pages = ocr_pdf_to_text_no_lines(pdf_path, dpi=300)
            text = "\n".join(pages)

    except Exception as e:
        logger.error(f"  Greška pri čitanju PDF-a: {e}")
        return ImportResult(items=[], bruto_kg=0.0, neto_kg=0.0,
                            invoice_name=Path(pdf_path).stem, currency="EUR")

    header = _extract_header(text)
    items  = _parse_items(text)

    logger.info(f"  Parsed {len(items)} stavki | bruto={header['bruto_kg']} kg | faktura={header['invoice_name']}")
    logger.info(f"  Izvoznik: {header['exporter_name']} | Uvoznik: {header['importer_name']}")

    from core.draft.draft import Party
    exporter = Party(
        name=header['exporter_name'],
        city=header['exporter_city'],
        country=header['exporter_country'],
    ) if header['exporter_name'] else None

    importer = Party(
        name=header['importer_name'],
        city=header['importer_city'],
        country=header['importer_country'],
    ) if header['importer_name'] else None

    for item in items:
        if exporter:
            item.exporter = exporter
        if importer:
            item.importer = importer

    return ImportResult(
        items=items,
        bruto_kg=header['bruto_kg'],
        neto_kg=header['neto_kg'],
        invoice_name=header['invoice_name'] or Path(pdf_path).stem,
        currency="EUR",
        exporter=exporter,
        importer=importer,
    )


# ── Header ekstrakcija ────────────────────────────────────────────────────────

def _extract_header(text: str) -> Dict[str, Any]:
    h = {
        'invoice_name': '', 'invoice_date': '',
        'bruto_kg': 0.0, 'neto_kg': 0.0,
        'exporter_name': '', 'exporter_city': '', 'exporter_country': '',
        'importer_name': '', 'importer_city': '', 'importer_country': '',
    }

    m = re.search(r'(?:Invoice\s*No|FAKTURA\s*BR)[.\s|]*(\d+\s*/\s*\d+)', text, re.IGNORECASE)
    if m:
        h['invoice_name'] = m.group(1).replace(' ', '')

    m = re.search(r'(\d{1,2}\.\d{1,2}\.\d{4})', text)
    if m:
        h['invoice_date'] = m.group(1)

    m = re.search(r'(?:BRUTO\s*TEZINA|Gross\s*weight)[:\s|]*([\d,\.]+)\s*KG', text, re.IGNORECASE)
    if m:
        try:
            h['bruto_kg'] = float(m.group(1).replace(',', '.'))
        except ValueError:
            pass

    m = re.search(r'(?:NETO|Net\s*weight)[:\s]*([\d,\.]+)\s*KG', text, re.IGNORECASE)
    if m:
        try:
            h['neto_kg'] = float(m.group(1).replace(',', '.'))
        except ValueError:
            pass

    # ── Izvoznik (exporter) — pojavljuje se na vrhu fakture prije BUYER/KUPAC ──
    # OCR vidi: "TECHNOGREEN d.o.o.\n... Beograd - Surčin, SRBIJA\n..."
    # Uzimamo sve redove PRIJE prve pojave BUYER/KUPAC kao blok izvoznika
    buyer_pos = re.search(r'\b(?:BUYER|KUPAC)\b', text, re.IGNORECASE)
    header_block = text[:buyer_pos.start()] if buyer_pos else text[:400]

    lines = [l.strip() for l in header_block.splitlines() if l.strip()]
    # Filtriraj OCR šum (kratki tokeni, samo interpunkcija, www/email/tel)
    company_lines = [
        l for l in lines
        if len(l) > 4
        and not re.match(r'^[\W\d]+$', l)
        and not re.search(r'www\.|e-mail|Tel\.|fax|^\s*[=\-]+\s*$|\+\d{3}', l, re.IGNORECASE)
        and not re.match(r'^Page\s+\d', l, re.IGNORECASE)
    ]
    if company_lines:
        h['exporter_name'] = company_lines[0]
        # Grad i zemlja — red koji sadrži poznate indikatore
        for line in company_lines[1:]:
            if re.search(r'SRBIJA|HRVATSKA|SLOVENIJA|NJEMA|GERMAN|ITALY|ITALIA|'
                         r'BOSN|AUSTRIA|FRANCE|CHINA|KINA|TURSKA|TURKEY', line, re.IGNORECASE):
                # Ukloni OCR šum s početka (=, |, cifre, razmaci)
                clean = re.sub(r'^[\s=|>~\-\d]+', '', line).strip()
                h['exporter_city'] = clean
                break

    # ── Uvoznik (importer/buyer) — iza BUYER/KUPAC labele ───────────────────
    _BUYER_KW = re.compile(r'^\s*[\|\-\s]*(?:BUYER|KUPAC|IMPORTER|UVOZNIK|CONSIGNEE)\s*[\|\-\s]*$', re.IGNORECASE)
    if buyer_pos:
        after_buyer = text[buyer_pos.end():]
        buyer_lines = [l.strip() for l in after_buyer.splitlines() if l.strip()]
        # Prva smislena linija (nije BUYER/KUPAC keyword)
        for line in buyer_lines:
            if _BUYER_KW.match(line):
                continue
            if len(line) > 4 and not re.match(r'^[\W\d]+$', line):
                h['importer_name'] = line
                break
        # Grad/adresa uvoznika
        started = False
        for line in buyer_lines:
            if _BUYER_KW.match(line):
                continue
            if line == h['importer_name']:
                started = True
                continue
            if started and len(line) > 3:
                h['importer_city'] = line
                break

    return h


# ── Parsiranje stavki ─────────────────────────────────────────────────────────

# Redovi koje treba preskočiti
_SKIP_RE = re.compile(
    r'(?:BUYER|KUPAC|SUMAPROM|TECHNOGREEN|forest|garden|equipment|'
    r'www\.|e-mail|Tel\.|fax|BEOGRAD|Beograd|BIJELJINA|Dvorovi|'
    r'Karad|Puskinova|Page\s+\d|FAKTURA\s+BR|Invoice\s+No|'
    r'UKUPNO|TOTAL|OSLOBOD|PRICE\s+TERM|VALUTA|DELIVERY|PARITET|'
    r'BANK|BANCA|SWIFT|ACC\s+NO|IBAN|Gross\s+weight|BRUTO\s+TEZINA|'
    r'Box\s+No|KOLETA|Reg\.br|Mati|Sifra\s+del|upisani|Total\s+Invoice|'
    r'eightthous|slovima|osamhilj|ISSUED|Ljubig|Mat\.br|Due\s+date|'
    r'Invoice\s+date|Comments|NAPOMENE|Number\s+of)',
    re.IGNORECASE,
)


def _parse_number(s: str) -> float:
    """Parsira broj sa zarezom ili tačkom."""
    try:
        return float(s.replace(',', '.'))
    except ValueError:
        return 0.0


def _normalize_country(raw: str) -> str:
    """XX/NAZIV → dvoslovni ISO kod."""
    m = re.match(r'^([A-Z]{2,3})', raw.strip().upper())
    if not m:
        return normalize_country_name(raw)
    code = m.group(1)
    mapping = {'SER': 'RS', 'SLO': 'SI', 'BRA': 'BR', 'ITA': 'IT',
               'IND': 'IN', 'CHN': 'CN', 'IRE': 'IE', 'IRN': 'IR'}
    return mapping.get(code, code[:2] if len(code) == 3 else code)


def _clean_token(tok: str) -> str:
    """Ukloni OCR šum iz tokena (|, ", ', ~, _)."""
    return re.sub(r'[|"\'~_`]', '', tok).strip()


def _parse_line(line: str, line_no: int) -> Optional[InvoiceLine]:
    """
    Parsira jednu liniju Šumaprom fakture (OCR).

    Strategija:
    1. Nađi zemlju (XX/NAZIV) na kraju — pouzdani anker
    2. Ukloni | znakove (ostaci tabela linija), očisti OCR šum
    3. Skupi sve brojeve zdesna, preskačući jednoznačni OCR šum
    4. Zadnja 2 broja = cijena_jed, iznos
    5. Ukloni JM noise i kolicinu
    6. Rb? product_code naziv_robe
    """
    line = line.strip()
    if len(line) < 15:
        return None
    if _SKIP_RE.search(line):
        return None

    # 1. Nađi zemlju na kraju
    country_m = _COUNTRY_RE.search(line)
    if not country_m:
        return None

    zemlja = _normalize_country(country_m.group(0))
    # Ukloni | znakove (OCR ostatak tabela linija) i višestruke razmake
    before_country = re.sub(r'\|', ' ', line[:country_m.start()])
    before_country = re.sub(r'\s+', ' ', before_country).strip()

    # 2. Tokenizuj i očisti
    tokens = [t for t in before_country.split() if _clean_token(t)]
    if not tokens:
        return None

    # 3. Skupi do 4 broja zdesna, preskačući jednoznačne šum-tokene
    numbers: List[Tuple[int, float]] = []
    skipped = 0
    for i in range(len(tokens) - 1, -1, -1):
        tok = _clean_token(tokens[i])
        if not tok:
            continue
        if _NUMBER_RE.match(tok):
            numbers.insert(0, (i, _parse_number(tok)))
            skipped = 0
            if len(numbers) == 4:
                break
        else:
            skipped += 1
            if skipped > 2:  # prestani kad preskočiš 2+ ne-broja
                break

    # Odaberi cijena_jed i iznos od zadnja 2 u listi
    cijena_jed = 0.0
    iznos      = 0.0
    cut_idx    = len(tokens)

    if len(numbers) >= 2:
        cut_idx    = numbers[-2][0]
        cijena_jed = numbers[-2][1]
        iznos      = numbers[-1][1]
    elif len(numbers) == 1:
        cut_idx = numbers[-1][0]
        iznos   = numbers[-1][1]

    left_tokens = [_clean_token(t) for t in tokens[:cut_idx]]
    left_tokens = [t for t in left_tokens if t]  # ukloni prazne nakon clean

    # 4. Ukloni JM noise s desna
    while left_tokens and _JM_NOISE.fullmatch(left_tokens[-1]):
        left_tokens.pop()

    # 5. Ukloni kolicinu (cijeli broj na desnom kraju)
    kolicina = 0.0
    if left_tokens:
        last = left_tokens[-1]
        if re.match(r'^\d+$', last):
            kolicina = float(last)
            left_tokens.pop()

    # Ukloni JM noise ponovo
    while left_tokens and _JM_NOISE.fullmatch(left_tokens[-1]):
        left_tokens.pop()

    # Ukloni jednoznačne OCR šum tokene s kraja (-, ., ,, =)
    while left_tokens and re.match(r'^[-.,=]+$', left_tokens[-1]):
        left_tokens.pop()

    if not left_tokens:
        return None

    # 6. Rb. broj na početku? (1-3 cifre, ili garbled karakter + cifre)
    first = left_tokens[0]
    if re.match(r'^[^\w]*\d{1,3}$', first) and len(left_tokens) > 1:
        left_tokens.pop(0)

    if not left_tokens:
        return None

    # Očisti product_code od vodećih OCR znakova
    product_code = re.sub(r'^["\'\s]+', '', left_tokens[0])
    if not product_code:
        product_code = left_tokens[0]

    naziv_robe = ' '.join(left_tokens[1:]) if len(left_tokens) > 1 else product_code

    # Osnovna provjera kvalitete
    if len(naziv_robe) < 3:
        return None
    if re.match(r'^[\d\s,\.]+$', naziv_robe):
        return None

    return InvoiceLine(
        line_no=line_no,
        naziv_robe=naziv_robe,
        product_code=product_code,
        tarifni_broj='',
        zemlja_porijekla=zemlja,
        kolicina=kolicina,
        cijena_jed=cijena_jed,
        iznos=iznos,
        valuta="EUR",
        bruto_kg=0.0,
        neto_kg=0.0,
        jm='kom',
    )


def _parse_items(text: str) -> List[InvoiceLine]:
    """Parsira sve stavke iz OCR teksta."""
    items = []
    line_counter = 1

    for raw_line in text.splitlines():
        item = _parse_line(raw_line, line_counter)
        if item:
            items.append(item)
            line_counter += 1

    return items
