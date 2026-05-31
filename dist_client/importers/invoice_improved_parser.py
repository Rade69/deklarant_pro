"""
Invoice Improved Parser - Univerzalni parser za moderne fakture

Parsira fakture sa standardnim tabelarnim formatom:
No. Code Title Measure Quantity Price Value
1.  1071 NAZIV PROIZVODA kom 100,00 5,70 570,00

Radi sa bilo kojim dobavljačem koji koristi ovaj format.
"""

import logging
import re
from typing import List

from core.draft.draft import InvoiceLine, Party
from importers.import_result import ImportResult

logger = logging.getLogger("deklarant_pro.import.invoice_improved")


def parse_invoice_improved(pdf_path: str) -> ImportResult:
    """
    Parsira moderne fakture sa standardnim tabelarnim formatom.

    Args:
        pdf_path: Putanja do PDF fajla

    Returns:
        ImportResult sa stavkama
    """
    logger.info(f"📋 Parsing invoice (improved format): {pdf_path}")

    import pdfplumber

    items: List[InvoiceLine] = []
    invoice_number = ""
    bruto_kg = 0.0
    neto_kg = 0.0
    has_origin_statement = False
    origin_statements = []

    # Pattern za početak nove stavke: Broj., Kod, Ostatak...
    item_start_pattern = re.compile(
        r'^(\d+)\.\s+([A-Z0-9]+)\s+(.+)',
        re.IGNORECASE
    )
    # Pattern za header kolona (svaka stranica ima ponavljajući header)
    col_header_pattern = re.compile(r'No\.\s+Code\s+', re.IGNORECASE)

    current_item_data = None

    with pdfplumber.open(pdf_path) as pdf:
        # Ekstraktuj broj fakture i težine iz prve stranice
        first_text = pdf.pages[0].extract_text() or "" if pdf.pages else ""
        invoice_match = re.search(r'INVOICE\s+no:\s*([^\s]+)', first_text, re.IGNORECASE)
        if invoice_match:
            invoice_number = invoice_match.group(1)
            logger.debug(f"Invoice number: {invoice_number}")

        # Težine su obično na posljednjoj stranici
        full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)
        bruto_match = re.search(r'Bruto\s+težina[:\s]+([\d,\.]+)', full_text, re.IGNORECASE)
        if not bruto_match:
            bruto_match = re.search(r'Gross\s*[Ww]eight[:\s]+([\d,\.]+)', full_text, re.IGNORECASE)
        if bruto_match:
            bruto_kg = _parse_number(bruto_match.group(1))

        neto_match = re.search(r'Neto\s+težina[:\s]+([\d,\.]+)', full_text, re.IGNORECASE)
        if not neto_match:
            neto_match = re.search(r'Net\s*[Ww]eight[:\s]+([\d,\.]+)', full_text, re.IGNORECASE)
        if neto_match:
            neto_kg = _parse_number(neto_match.group(1))

        # Tarifna oznaka iz footera (ako postoji — vrijedi za sve stavke)
        footer_tariff = ""
        tariff_match = re.search(r'Tarifna\s+oznaka[:\s]+([\d\.\s]+)', full_text, re.IGNORECASE)
        if tariff_match:
            raw = tariff_match.group(1).strip()
            digits = re.sub(r'[^\d]', '', raw)
            if len(digits) >= 8:
                footer_tariff = digits[:10]
                logger.info(f"  Tarifna oznaka iz footera: {footer_tariff}")

        # DETEKTUJ SVE izjave o poreklu
        origin_statements = _detect_all_origin_statements(full_text)
        has_origin_statement = len(origin_statements) > 0
        logger.info(f"  Detekcija izjave o poreklu: {has_origin_statement} ({len(origin_statements)} izjava)")

        # Parsiranje stavki — STRANICA PO STRANICA da bi preskočili ponavljajuće headere
        for page in pdf.pages:
            text = page.extract_text() or ""
            page_lines = text.split('\n')

            # Preskoči header stranice (sve do linije "No. Code Title...")
            in_header = True
            skip_footer_continuation = False  # Ako je footer linija višeredna
            for raw_line in page_lines:
                line = raw_line.strip()

                if in_header:
                    if col_header_pattern.match(line):
                        in_header = False  # Sljedeće linije su podaci
                    continue  # Preskoči header linije

                # Skip prazan i footer
                if not line:
                    continue
                if 'Strana:' in line:
                    continue

                is_footer = bool(re.match(
                    r'^(Total|SAY\s*:|VAT\s*:|TOTAL\s+EUR|Neto\s+te|Bruto\s+te|'
                    r'Pakovanje|Tarifna|Naimenovanje|Paritet|Broj\s+komada|Izvoznik)',
                    line, re.IGNORECASE
                ))

                if is_footer:
                    skip_footer_continuation = True
                    continue

                # Novi stavak uvijek prekida footer blok
                if re.match(r'^\d+\.', line):
                    skip_footer_continuation = False
                elif skip_footer_continuation:
                    continue  # Višeredni footer tekst — preskočiti

                match = item_start_pattern.match(line)
                if match:
                    # Sačuvaj prethodnu stavku
                    if current_item_data:
                        item = _parse_item_data(current_item_data)
                        if item:
                            items.append(item)

                    num = int(match.group(1))
                    code = match.group(2).strip()
                    rest = match.group(3).strip()

                    current_item_data = {
                        'num': num,
                        'code': code,
                        'line': rest,
                        'continuation_lines': []
                    }

                elif current_item_data:
                    # Continuation: multi-line naziv (samo ako nije novi red sa brojem)
                    if not re.match(r'^\d+\.', line):
                        current_item_data['continuation_lines'].append(line)

    # Dodaj posljednju stavku
    if current_item_data:
        item = _parse_item_data(current_item_data)
        if item:
            items.append(item)

    logger.info(f"✅ Parsed {len(items)} items")

    # Ako izjava ima zemlju porijekla, dodijeli je stavkama koje nemaju zemlja_porijekla
    if origin_statements and items:
        for stmt in origin_statements:
            if stmt.origin_country:
                for item in items:
                    if not item.zemlja_porijekla:
                        item.zemlja_porijekla = stmt.origin_country
                logger.info(f"  Dodijeljena zemlja '{stmt.origin_country}' stavkama bez zemlja_porijekla")

    # Ako footer ima tarifnu oznaku, dodijeli je svim stavkama koje nemaju tarifni_broj
    if footer_tariff and items:
        count = 0
        for item in items:
            if not item.tarifni_broj:
                item.tarifni_broj = footer_tariff
                count += 1
        if count:
            logger.info(f"  Dodijeljen tarifni '{footer_tariff}' za {count} stavki iz footera")

    # Raspodjeli težine proporcionalno po iznosima (za XML export)
    if items and (bruto_kg > 0 or neto_kg > 0):
        total_amount = sum(item.iznos for item in items)
        if total_amount > 0:
            for item in items:
                proportion = item.iznos / total_amount
                item.bruto_kg = proportion * bruto_kg
                item.neto_kg = proportion * neto_kg
            logger.debug(f"Distributed weights proportionally across {len(items)} items")

    # Pokušaj detektovati naziv exportera iz teksta
    exporter_name = _detect_exporter(full_text)

    return ImportResult(
        items=items,
        bruto_kg=bruto_kg,
        neto_kg=neto_kg,
        invoice_name=invoice_number,
        currency="EUR",
        has_origin_statement=has_origin_statement,
        origin_statements=origin_statements,
        exporter=Party(name=exporter_name) if exporter_name else None,
    )


def _parse_item_data(item_data: dict) -> InvoiceLine:
    """
    Parsira podatke jedne stavke.

    item_data format:
    {
        'num': 1,
        'code': '1071',
        'line': 'GREJAC GPB-2000W 230V GOR, kom 100,00 5,70 570,00',
        'continuation_lines': ['MET']
    }
    """
    num = item_data['num']
    code = item_data['code']
    line = item_data['line']
    continuation = item_data.get('continuation_lines', [])

    # Pattern za kraj linije: jedinica količina cijena iznos
    # kom 100,00 5,70 570,00
    end_pattern = re.compile(
        r'([a-zA-Z]{2,10})\s+([\d,\.]+)\s+([\d,\.]+)\s+([\d,\.]+)$',
        re.IGNORECASE
    )

    match = end_pattern.search(line)
    if not match:
        logger.warning(f"Stavka #{num}: Ne mogu parsirati brojeve: {line}")
        return InvoiceLine(
            line_no=num,
            product_code=code or "",
            naziv_robe=f"Stavka {num}",
            jm="",
            kolicina=0,
            cijena_jed=0,
            iznos=0
        )

    # Ekstraktuj jedinicu, količinu, cijenu, iznos
    unit = match.group(1).lower()
    quantity = _parse_number(match.group(2))
    price = _parse_number(match.group(3))
    amount = _parse_number(match.group(4))

    # Naziv je sve prije jedinice
    naziv_end = match.start()
    naziv = line[:naziv_end].strip()

    # Dodaj continuation lines ako postoje
    if continuation:
        naziv += " " + " ".join(continuation)

    naziv = naziv.strip()

    return InvoiceLine(
        product_code=code,
        naziv_robe=naziv,
        kolicina=quantity,
        jm=unit,
        cijena_jed=price,
        iznos=amount,
        valuta="EUR"
    )


def _parse_number(text: str) -> float:
    """Parsira broj iz teksta."""
    if not text:
        return 0.0

    # Ukloni sve osim cifara, tačke i zareza
    text = re.sub(r'[^\d,.\-]', '', str(text))

    # Zamijeni zarez sa tačkom
    text = text.replace(',', '.')

    # Ako ima više tačaka, prva je separator hiljada
    if text.count('.') > 1:
        parts = text.split('.')
        text = ''.join(parts[:-1]) + '.' + parts[-1]

    try:
        return float(text)
    except ValueError:
        return 0.0


def detect_invoice_improved(pdf_path: str) -> bool:
    """
    Detektuje da li je ovo Invoice Improved format.

    Returns:
        True ako je detektovan format sa karakterističnim poljima (NO. CODE TITLE MEASURE QUANTITY PRICE)
    """
    import pdfplumber

    try:
        with pdfplumber.open(pdf_path) as pdf:
            if not pdf.pages:
                return False

            text = pdf.pages[0].extract_text() or ""
            text_upper = text.upper()

            # Karakteristični header: No. Code Title Measure Quantity Price Value
            if ("NO." in text_upper and "CODE" in text_upper and
                "TITLE" in text_upper and "MEASURE" in text_upper and
                "QUANTITY" in text_upper and "PRICE" in text_upper):
                return True

            return False

    except Exception:
        return False


def _detect_exporter(full_text: str, fallback: str = "") -> str:
    """Try to detect company name from invoice header."""
    lines = [l.strip() for l in full_text.split('\n')[:10] if l.strip()]
    for line in lines:
        for prefix in ['Seller:', 'Vendor:', 'From:', 'FROM:', 'Prodavac:', 'Dobavljač:']:
            if line.startswith(prefix):
                name = line[len(prefix):].strip()
                if name:
                    return name
    return fallback


def _detect_all_origin_statements(text: str) -> list:
    """Detektuj SVE izjave o preferencijalnom poreklu u tekstu."""
    try:
        from services.tariff.origin_statement_detector import OriginStatementDetector
        detector = OriginStatementDetector()
        return detector.detect_all_in_text(text)
    except Exception as e:
        logger.warning(f"  Greška tokom detekcije izjava: {e}")
        return []
