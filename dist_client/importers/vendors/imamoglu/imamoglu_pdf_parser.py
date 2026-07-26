# importers/imamoglu_pdf_parser.py

"""
IMAMOGLU PDF Parser

Parsira IMAMOGLU (Turkey) PDF fakture.
Format: ITEM | CODE NO | PRODUCT DESCRIPTION | QTY | UNIT | UNIT PRICE | TOTAL
"""

import logging
import re
from typing import List, Optional
import pdfplumber

from core.draft.draft import InvoiceLine, Party
from importers.import_result import ImportResult
from importers.incoterm_utils import detect_incoterm

logger = logging.getLogger("deklarant_pro.import.imamoglu_pdf")


def parse_imamoglu_pdf(pdf_path: str) -> ImportResult:
    """
    Parsira IMAMOGLU PDF fakturu.

    Format tabele:
    ITEM | CODE NO | PRODUCT DESCRIPTION | QTY | UNIT | UNIT PRICE | TOTAL

    Args:
        pdf_path: Putanja do PDF fajla

    Returns:
        ImportResult sa stavkama
    """
    logger.info(f"Parsing IMAMOGLU PDF: {pdf_path}")

    items: List[InvoiceLine] = []
    invoice_number = ""
    gross_kg = 0.0
    net_kg = 0.0

    with pdfplumber.open(pdf_path) as pdf:
        full_text = ""

        # Extract text from all pages
        for page in pdf.pages:
            text = page.extract_text() or ""
            full_text += text + "\n"

        # Extract invoice number
        invoice_match = re.search(r'INV\.\s*NO:\s*(\S+)', full_text)
        if invoice_match:
            invoice_number = invoice_match.group(1)
            logger.debug(f"Invoice number: {invoice_number}")

        # Extract weights (fleksibilno za typo-ove u PDF-u)
        # Pattern hvata: WEIGHT, WEIHGT, WEIGT, WEHGT, itd.
        gross_pattern = r'GROSS\s+WE(?:IGHT|IHGT|IHT|IGT|IHG|HT|GT|T)\s*[:=]?\s*([\d,\.]+)\s*KG'
        gross_match = re.search(gross_pattern, full_text, re.IGNORECASE)
        if gross_match:
            gross_kg = _parse_number(gross_match.group(1))
            logger.debug(f"Gross weight: {gross_kg} kg")
        else:
            logger.warning(f"⚠️  GROSS weight NOT found in PDF")

        net_pattern = r'NET\s+WE(?:IGHT|IHGT|IHT|IGT|IHG|HT|GT|T)\s*[:=]?\s*([\d,\.]+)\s*KG'
        net_match = re.search(net_pattern, full_text, re.IGNORECASE)
        if net_match:
            net_kg = _parse_number(net_match.group(1))
            logger.debug(f"Net weight: {net_kg} kg")
        else:
            logger.warning(f"⚠️  NET weight NOT found in PDF")

        # DETEKTUJ SVE izjave o poreklu
        origin_statements = _detect_all_origin_statements(full_text)
        has_origin_statement = len(origin_statements) > 0
        logger.info(f"  ✅ Detekcija izjave o poreklu: {has_origin_statement} ({len(origin_statements)} izjava)")

        # Parse items - IMAMOGLU ima 2 sekcije:
        # 1. Strane 1-2: ITEM | CODE NO | PRODUCT DESCRIPTION (bez cijena)
        # 2. Strane 4-5: QTY | UNIT | UNIT PRICE | TOTAL (bez kodova)

        lines = full_text.split('\n')

        # FAZA 1: Parsiranje kodova i opisa (strane 1-2)
        items_dict = {}  # item_no -> {code, description}

        current_item_no = None
        current_code = None
        current_desc = ""
        in_items_table = False

        for line in lines:
            line = line.strip()

            # Detect items table start
            if 'ITEM' in line and 'CODE NO' in line and 'PRODUCT DESCRIPTION' in line:
                in_items_table = True
                continue

            # Detect items table end
            if in_items_table and ('TERMS OF PAYMENT' in line or 'TERMS OF DELIVERY' in line):
                # Save last item
                if current_item_no is not None:
                    items_dict[current_item_no] = {
                        'code': current_code or "",
                        'description': current_desc.strip()
                    }
                break

            if not in_items_table or not line:
                continue

            # Try to match item line: "1 I-31-B BASE FOOT..."
            item_match = re.match(r'^(\d+)\s+([A-Z0-9\-/]+)\s+(.+)$', line, re.IGNORECASE)
            if item_match:
                # Save previous item
                if current_item_no is not None:
                    items_dict[current_item_no] = {
                        'code': current_code or "",
                        'description': current_desc.strip()
                    }

                # Start new item
                current_item_no = int(item_match.group(1))
                current_code = item_match.group(2).strip()
                current_desc = item_match.group(3).strip()
                
                # Validiraj kod - ne smije biti previše kratak ili opšta riječ
                invalid_codes = ['STATIC', 'GKE', 'GYE', 'RESISTANCE', 'FF', 'MODEL', 'TYPE', 'SERIES']
                if current_code in invalid_codes or len(current_code) < 3:
                    logger.debug(f"  ⚠️  Ignorisan invalidan kod '{current_code}' za stavku {current_item_no}")
                    current_code = ""  # Resetuj kod, ali zadrži opis
                
                logger.debug(f"Found item {current_item_no}: {current_code}")

            # Try to match item without code: "7  COLD ROOM LOCK..."
            # PAŽNJA: Preskoči "Item X" pattern - to su placeholderi, ne prave stavke
            elif re.match(r'^(\d+)\s+([A-Z\s].+)$', line):
                item_match2 = re.match(r'^(\d+)\s+(.+)$', line)
                if item_match2:
                    desc_candidate = item_match2.group(2).strip()
                    
                    # IGNORIŠI "Item X" pattern - to nisu prave stavke
                    if re.match(r'^Item\s+\d+$', desc_candidate, re.IGNORECASE):
                        logger.debug(f"  ⚠️  Ignorisan 'Item X' placeholder: {desc_candidate}")
                        continue  # Preskoči ovu liniju
                    
                    # Save previous item
                    if current_item_no is not None:
                        items_dict[current_item_no] = {
                            'code': current_code or "",
                            'description': current_desc.strip()
                        }

                    current_item_no = int(item_match2.group(1))
                    current_code = ""
                    current_desc = desc_candidate
                    logger.debug(f"Found item {current_item_no}: (no code) {current_desc[:40]}")

            # Multi-line description continuation
            elif current_item_no is not None and line and not line.startswith(('TERMS', 'DELIVERY')):
                current_desc += " " + line

        logger.debug(f"Phase 1: Found {len(items_dict)} items with descriptions")

        # FAZA 2: Parsiranje količina i cijena (strane 4-5)
        in_price_table = False
        item_counter = 1

        for line in lines:
            line = line.strip()

            # Detect price table markers
            if 'QTY' in line and 'UNIT PRICE' in line and 'TOTAL' in line:
                in_price_table = True
                continue

            # Detect price table end
            if 'SUB TOTAL' in line or 'COST AND FREIGHT' in line:
                break

            if not in_price_table or not line:
                continue

            # Try to match price line: "2.500,00 PCS 0,80 € 2.000,00 €"
            price_match = re.match(
                r'^([\d,\.]+)\s+([A-Z]{2,10})\s+([\d,\.]+)\s*€\s+([\d,\.]+)\s*€',
                line,
                re.IGNORECASE
            )

            if price_match:
                qty = _parse_number(price_match.group(1))
                unit = price_match.group(2).lower()
                price = _parse_number(price_match.group(3))
                total = _parse_number(price_match.group(4))

                # Get description from phase 1
                item_info = items_dict.get(item_counter, {'code': '', 'description': ''})
                
                # Ako nema opisa, preskoči ovu stavku (nije prava stavka)
                if not item_info.get('description'):
                    logger.debug(f"  ⚠️  Preskočena stavka {item_counter} - nema opisa")
                    item_counter += 1
                    continue
                
                # Ekstrakcija koda iz opisa ako je kod prazan
                code = item_info['code']
                description = item_info['description']
                
                if not code and description:
                    # Pokušaj ekstrahovati kod iz opisa (npr. "I-100 - K1 CHROME...")
                    code_match = re.match(r'^([A-Z0-9\-/]+)\s*[-–:]\s*(.+)$', description)
                    if code_match:
                        potential_code = code_match.group(1)
                        # Validiraj kod - mora imati barem jednu crtu i 3+ karaktera
                        if '-' in potential_code and len(potential_code) >= 5:
                            code = potential_code
                            description = code_match.group(2).strip()
                            logger.debug(f"  ✅  Ekstrahovan kod '{code}' iz opisa za stavku {item_counter}")

                # Preskoči stavke bez validnog opisa
                if not description or description.strip() == '':
                    logger.debug(f"  ⚠️  Preskočena stavka {item_counter} - nema opisa")
                    item_counter += 1
                    continue

                item = InvoiceLine(
                    line_no=item_counter,
                    product_code=code,
                    naziv_robe=description,
                    jm=unit,
                    kolicina=qty,
                    cijena_jed=price,
                    iznos=total,
                    valuta="EUR",
                    tarifni_broj="",
                    zemlja_porijekla="TR",
                    povlastica="",
                    bruto_kg=0.0,
                    neto_kg=0.0,
                )

                items.append(item)
                logger.debug(f"Matched item {item_counter}: {code} - Qty: {qty} {unit}, Price: {price}")
                item_counter += 1

    logger.info(f"Parsed {len(items)} items from IMAMOGLU PDF")
    logger.info(f"Weights: Gross {gross_kg} kg, Net {net_kg} kg")

    # ⚠️ NE raspoređuj težine automatski!
    # Težine se čuvaju u ImportResult, korisnik klikće "Izračunaj mase"

    # Pokušaj detektovati naziv exportera iz teksta
    exporter_name = _detect_exporter(full_text, fallback="IMAMOGLU")

    _imp = Party(name="IMAMOGLU D.O.O. SARAJEVO")
    _exp = Party(name=exporter_name)
    for item in items:
        item.exporter = _exp
        item.importer = _imp

    return ImportResult(
        items=items,
        bruto_kg=gross_kg,
        neto_kg=net_kg,
        invoice_name=invoice_number,
        currency="EUR",
        has_origin_statement=has_origin_statement,
        origin_statements=origin_statements,
        exporter=_exp,
        importer=_imp,
        incoterm_code=detect_incoterm(full_text),  # Rb.20 "Uslovi isporuke"
    )


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


def _parse_number(s: str) -> float:
    """Parse number from string (handles commas and dots)."""
    if not s:
        return 0.0

    # Remove spaces
    s = s.replace(' ', '')

    # Handle European format (comma as decimal, dot as thousands)
    # or US format (dot as decimal, comma as thousands)
    if ',' in s and '.' in s:
        # If comma comes after dot, it's decimal: 1.234,56 → 1234.56
        if s.rfind(',') > s.rfind('.'):
            s = s.replace('.', '').replace(',', '.')
        else:
            # If dot comes after comma, it's decimal: 1,234.56 → 1234.56
            s = s.replace(',', '')
    elif ',' in s:
        # Only comma - assume decimal: 12,34 → 12.34
        s = s.replace(',', '.')
    # else: only dots or no separators - leave as is

    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def detect_imamoglu_pdf(filepath: str) -> bool:
    """
    Detektuje da li je PDF IMAMOGLU format.

    Kriteriji:
    - Sadrži "IMAMOGLU SOGUTMA"
    - Sadrži "COMMERCIAL INVOICE"
    - Sadrži "DOLAPDERE - SISLI/ ISTANBUL"

    Args:
        filepath: Putanja do PDF fajla

    Returns:
        True ako je IMAMOGLU PDF
    """
    try:
        with pdfplumber.open(filepath) as pdf:
            if not pdf.pages:
                return False

            # Check first page
            text = pdf.pages[0].extract_text() or ""

            # Check for IMAMOGLU signature
            if "IMAMOGLU SOGUTMA" in text.upper() or "IMAMOGLU" in text:
                if "COMMERCIAL INVOICE" in text and "ISTANBUL" in text.upper():
                    return True

        return False

    except Exception as e:
        logger.warning(f"Error detecting IMAMOGLU PDF: {e}")
        return False


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
        from services.tariff.origin_statement_detector import OriginStatementDetector

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


def _detect_all_origin_statements(text: str) -> List:
    """
    Detektuj SVE izjave o preferencijalnom poreklu u tekstu.

    Args:
        text: Tekst PDF fakture

    Returns:
        Lista OriginStatementMatch objekata
    """
    try:
        from services.tariff.origin_statement_detector import OriginStatementDetector

        detector = OriginStatementDetector()
        statements = detector.detect_all_in_text(text)

        return statements

    except Exception as e:
        logger.warning(f"  ⚠️  Greška tokom detekcije izjava: {e}")
        return []


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
    test_file = "SRETO BLAGIC INV....pdf"

    logger.debug("\n" + "=" * 70)
    logger.debug("IMAMOGLU PDF PARSER - Test")
    logger.debug("=" * 70 + "\n")

    try:
        # Test detection
        is_imamoglu = detect_imamoglu_pdf(test_file)
        logger.debug(f"Detection: {is_imamoglu}")

        if is_imamoglu:
            # Test parsing
            result = parse_imamoglu_pdf(test_file)

            logger.info(f"\n✅ Parsed: {len(result.items)} items")
            logger.debug(f"Invoice: {result.invoice_name}")
            logger.debug(f"Currency: {result.currency}")
            logger.debug(f"Weights: Gross {result.bruto_kg} kg, Net {result.neto_kg} kg")

            logger.debug(f"\nPrvih 5 stavki:")
            for i, item in enumerate(result.items[:5], 1):
                logger.debug(f"\n{i}. Code: {item.product_code}")
                logger.debug(f"   Naziv: {item.naziv_robe[:60]}")
                logger.debug(f"   Qty: {item.kolicina} {item.jm}, Price: {item.cijena_jed} EUR, Amount: {item.iznos} EUR")
                logger.debug(f"   Origin: {item.zemlja_porijekla}, Tariff: {item.tarifni_broj or 'N/A'}")

    except Exception as e:
        logger.error(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
