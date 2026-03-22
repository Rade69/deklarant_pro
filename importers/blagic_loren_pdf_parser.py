# importers/blagic_loren_pdf_parser.py

"""
Blagić Loren PDF Parser

Parsira Blagić Loren PDF fakture (dobavljač iz Beograda).
Format: tabela sa kolonama: Num, Code, Article, U.N., QTY, Price, Amount
"""

import logging
import re
from typing import List, Dict, Any, Optional
import pdfplumber

from core.draft.draft import InvoiceLine
from importers.import_result import ImportResult

logger = logging.getLogger("asycuda_pro.import.blagic_loren_pdf")


def parse_blagic_loren_pdf(pdf_path: str) -> ImportResult:
    """
    Parsira Blagić Loren PDF fakturu.

    Format tabele:
    Num. | Code | ARTICLE | U.N. | QTY | Price (EURO) | Amount (EURO)

    Args:
        pdf_path: Putanja do PDF fajla

    Returns:
        ImportResult sa stavkama
    """
    logger.info(f"Parsing Blagić Loren PDF: {pdf_path}")

    items: List[InvoiceLine] = []
    invoice_number = ""
    invoice_date = ""
    total_amount = 0.0

    with pdfplumber.open(pdf_path) as pdf:
        full_text = ""

        # Extract text from all pages
        for page in pdf.pages:
            text = page.extract_text() or ""
            full_text += text + "\n"

        # Extract invoice number
        invoice_match = re.search(r'Invoice:\s*(\S+)', full_text)
        if invoice_match:
            invoice_number = invoice_match.group(1)
            logger.debug(f"Invoice number: {invoice_number}")

        # Extract invoice date
        date_match = re.search(r'Invoice date:\s*([0-9]+\.[a-z]+\.[0-9]+)', full_text, re.IGNORECASE)
        if date_match:
            invoice_date = date_match.group(1)
            logger.debug(f"Invoice date: {invoice_date}")

        # Parse items from text
        lines = full_text.split('\n')

        # Pattern za redove sa stavkama:
        # Num Code Article... U.N. QTY Price Amount
        # 1 611FR100 TERMO EKSPANZIONI... pcs 20,00 21,77 435,40

        current_item = None
        # Pattern: Num Code Description Unit Qty Price Amount
        # Unit može biti bilo koja riječ (1-10 karaktera) - fleksibilno za sve varijacije pakovanja
        item_pattern = re.compile(
            r'^(\d+)\s+([A-Z0-9]+)\s+(.+?)\s+([a-zA-Z]{1,10})\s+([\d,\.]+)\s+([\d,\.]+)\s+([\d,\.]+)',
            re.IGNORECASE
        )

        for line in lines:
            line = line.strip()

            # Skip header i prazne linije
            if not line or 'Code A R T I C A L' in line or line.startswith('Num.'):
                continue

            # Check if this is a new item line
            match = item_pattern.match(line)

            if match:
                # Save previous item if exists
                if current_item:
                    items.append(current_item)

                # Parse new item
                num = int(match.group(1))
                code = match.group(2).strip()
                article = match.group(3).strip()
                unit = match.group(4).lower()
                qty = _parse_number(match.group(5))
                price = _parse_number(match.group(6))
                amount = _parse_number(match.group(7))

                # Preskoči troškove koji nisu roba (špedicija, transport, itd.)
                if any(kw in article.upper() for kw in ['SPEDICIJ', 'FREIGHT COST', 'TRANSPORT COST', 'SHIPPING COST']):
                    logger.debug(f"Preskačem non-product stavku {num}: {article[:50]}")
                    current_item = None
                    continue

                current_item = InvoiceLine(
                    line_no=num,
                    product_code=code,
                    naziv_robe=article,
                    jm=unit,
                    kolicina=qty,
                    cijena_jed=price,
                    iznos=amount,
                    valuta="EUR",
                    tarifni_broj="",  # Iz Excel-a
                    zemlja_porijekla="",  # Iz Excel-a
                    bruto_kg=0.0,
                    neto_kg=0.0,
                )

                logger.debug(f"Parsed item {num}: {code} - {article[:40]}")

            elif current_item and line:
                # Multi-line description continuation
                # Skip footer redove i redove koji liče na zbir
                _skip_kw = [
                    'TOTAL', 'SUBTOTAL', 'VAT', 'NET', 'GROSS',
                    'AMOUNT:', 'STRANA ', 'PHONE:', 'FAX:', 'WWW.',
                    'EMAIL:', 'IDN:', 'B4K-',
                ]
                if not any(keyword in line.upper() for keyword in _skip_kw):
                    current_item.naziv_robe += " " + line

        # Add last item
        if current_item:
            items.append(current_item)

        # Extract total
        total_match = re.search(r'Total.*?(\d+[,\.]\d+)', full_text, re.IGNORECASE)
        if total_match:
            total_amount = _parse_number(total_match.group(1))

        # Extract weights (bruto i neto)
        bruto_kg = 0.0
        neto_kg = 0.0

        # Gross weight
        gross_match = re.search(r'Gross\s+weight:\s*([\d,\.]+)\s*kg', full_text, re.IGNORECASE)
        if gross_match:
            bruto_kg = _parse_number(gross_match.group(1))
            logger.debug(f"Extracted Gross weight: {bruto_kg} kg")

        # Net weight
        net_match = re.search(r'Net\s+weight:\s*([\d,\.]+)\s*kg', full_text, re.IGNORECASE)
        if net_match:
            neto_kg = _parse_number(net_match.group(1))
            logger.debug(f"Extracted Net weight: {neto_kg} kg")

        # DETEKTUJ SVE izjave o poreklu
        origin_statements = _detect_all_origin_statements(full_text)
        has_origin_statement = len(origin_statements) > 0
        logger.info(f"  ✅ Detekcija izjave o poreklu: {has_origin_statement} ({len(origin_statements)} izjava)")

        # Raspodjeli težine proporcionalno po iznosima (za XML export)
        if items and (bruto_kg > 0 or neto_kg > 0):
            total_amount = sum(item.iznos for item in items)
            if total_amount > 0:
                for item in items:
                    proportion = item.iznos / total_amount
                    item.bruto_kg = proportion * bruto_kg
                    item.neto_kg = proportion * neto_kg
                logger.debug(f"Distributed weights proportionally across {len(items)} items")

    logger.info(f"Parsed {len(items)} items from Loren PDF")
    logger.info(f"Weights: Gross={bruto_kg} kg, Net={neto_kg} kg")

    return ImportResult(
        items=items,
        bruto_kg=bruto_kg,
        neto_kg=neto_kg,
        invoice_name=invoice_number or pdf_path.split('/')[-1].replace('.pdf', ''),
        currency="EUR",
        import_type='loren_pdf',
        has_origin_statement=has_origin_statement,
        origin_statements=origin_statements,
    )


def _parse_number(s: str) -> float:
    """
    Parse number from string (handles both European and US formats).

    Formats:
    - European: "1.920,00" (dot=thousands, comma=decimal)
    - US: "1,920.00" (comma=thousands, dot=decimal)
    - Simple: "1920,00" or "1920.00"
    """
    if not s:
        return 0.0

    # Remove spaces
    s = s.replace(' ', '')

    # Determine format based on LAST separator (= decimal point)
    if ',' in s and '.' in s:
        # Both present - check which is decimal (last one in string)
        last_comma = s.rfind(',')
        last_dot = s.rfind('.')

        if last_comma > last_dot:
            # European format: "1.920,00" (comma is decimal)
            s = s.replace('.', '')  # Remove thousands separator (dots)
            s = s.replace(',', '.')  # Replace decimal comma with dot
        else:
            # US format: "1,920.00" (dot is decimal)
            s = s.replace(',', '')  # Remove thousands separator (commas)
    elif ',' in s:
        # Only comma - assume European decimal: "1920,00"
        s = s.replace(',', '.')
    # else: only dot or no separator - already correct format

    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def detect_blagic_loren_pdf(filepath: str) -> bool:
    """
    Detektuje da li je PDF Blagić Loren format.

    Kriteriji:
    - Sadrži "LOREN, DOO, Beograd"
    - Sadrži "Invoice:" i broj fakture

    Args:
        filepath: Putanja do PDF fajla

    Returns:
        True ako je Blagić Loren PDF
    """
    try:
        with pdfplumber.open(filepath) as pdf:
            if not pdf.pages:
                return False

            # Check first page
            text = pdf.pages[0].extract_text() or ""

            # Debug: Print first 500 chars
            logger.debug(f"PDF text sample: {text[:500]}")

            # Check for Loren signature (više varijanti)
            has_loren = ("LOREN, DOO, Beograd" in text or
                        "LOREN DOO" in text or
                        "LOREN, D.O.O" in text or
                        "Loren" in text)

            # Check for invoice format (više varijanti)
            has_invoice = ("Invoice:" in text or "INVOICE" in text or "invoice" in text)
            has_table = ("Code" in text or "CODE" in text or "A R T I C" in text or "ARTICLE" in text)

            # Check for filename pattern (broj VP u imenu)
            import os
            filename = os.path.basename(filepath)
            has_vp_number = "VP" in filename.upper() and "BLAGIC" in filename.upper()

            # RELAXED DETECTION: Loren + (invoice ILI VP broj) + (table ILI Gross/Net weight)
            # Ovo hvata i fakture koje nemaju sve standardne markere
            has_weight_fields = ("Gross weight" in text or "Net weight" in text or
                                "GROSS" in text.upper() and "NET" in text.upper())

            if has_loren and (has_invoice or has_vp_number) and (has_table or has_weight_fields):
                logger.debug(f"✅ Loren PDF detected: loren={has_loren}, invoice={has_invoice}, vp_num={has_vp_number}, table={has_table}, weights={has_weight_fields}")
                return True

        logger.debug(f"❌ Not Loren PDF: loren={has_loren}, invoice={has_invoice}, table={has_table}")
        return False

    except Exception as e:
        logger.warning(f"Error detecting Blagić Loren PDF: {e}")
        return False


def _detect_all_origin_statements(text: str) -> List:
    """
    Detektuj SVE izjave o preferencijalnom poreklu u tekstu.

    Args:
        text: Tekst PDF fakture

    Returns:
        Lista OriginStatementMatch objekata
    """
    try:
        from services.origin_statement_detector import OriginStatementDetector

        detector = OriginStatementDetector()
        statements = detector.detect_all_in_text(text)

        return statements

    except Exception as e:
        logger.warning(f"  ⚠️  Greška tokom detekcije izjava: {e}")
        return []


def _detect_origin_statement(text: str) -> bool:
    """
    Detektuj da li PDF sadrži izjavu o preferencijalnom poreklu.

    Koristi OriginStatementDetector servis.

    Args:
        text: Tekst PDF fakture

    Returns:
        True ako je nađena izjava, False inače
    """
    try:
        from services.origin_statement_detector import OriginStatementDetector

        detector = OriginStatementDetector()
        result = detector.detect_in_text(text)

        if result:
            logger.info(f"  ✅ Nađena izjava o poreklu: {result.jezik} / {result.tip_izjave} / origin={result.origin_country}")
            return True
        else:
            logger.debug("  ℹ️  Nije nađena izjava o poreklu")
            return False

    except Exception as e:
        logger.warning(f"  ⚠️  Greška tokom detekcije izjave: {e}")
        return False


# ============================================================
# USAGE EXAMPLE
# ============================================================

if __name__ == "__main__":
    import sys
    from pathlib import Path

    # Add project root to path
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))

    # Test
    test_file = "najavauvoza/blagic-loren/702VP-2025 BLAGIC.pdf"

    logger.debug("\n" + "=" * 70)
    logger.debug("BLAGIĆ LOREN PDF PARSER - Test")
    logger.debug("=" * 70 + "\n")

    try:
        # Test detection
        is_loren = detect_blagic_loren_pdf(test_file)
        logger.debug(f"Detection: {is_loren}")

        if is_loren:
            # Test parsing
            result = parse_blagic_loren_pdf(test_file)

            logger.info(f"\n✅ Parsed: {len(result.items)} items")
            logger.debug(f"Invoice: {result.invoice_name}")
            logger.debug(f"Currency: {result.currency}")

            logger.debug(f"\nPrvih 5 stavki:")
            for i, item in enumerate(result.items[:5], 1):
                logger.debug(f"\n{i}. Code: {item.product_code}")
                logger.debug(f"   Naziv: {item.naziv_robe[:60]}")
                logger.debug(f"   Qty: {item.kolicina} {item.jm}, Price: {item.cijena_jed} EUR, Amount: {item.iznos} EUR")

    except Exception as e:
        logger.error(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
