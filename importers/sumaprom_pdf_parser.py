# importers/sumaprom_pdf_parser.py

"""
ŠUMAPROM PDF Parser
Parser za ŠUMAPROM PDF fakture (skenirane ili tekstualne).

Format:
- Header: ŠUMAPROM COMMERCE, D.O.O., broj fakture, datum
- Stavke: tabela sa kolonama (R.br., Šifra, Opis, JM, Količina, Cena, Iznos, Zemlja)
- Footer: Ukupan iznos, bruto težina, broj paketa

Podržava:
- Tekstualne PDF-ove (pdfplumber)
- Skenirane PDF-ove (OCR sa Tesseract)
"""

import logging
import re
from typing import List, Dict, Any, Optional
from pathlib import Path

import pdfplumber

from core.draft.draft import InvoiceLine
from importers.import_result import ImportResult
from utils.country_normalizer import normalize_country_name

logger = logging.getLogger("asycuda_pro.import.sumaprom_pdf")


def detect_sumaprom_pdf(filepath: str) -> bool:
    """
    Detektuje da li je PDF ŠUMAPROM format.

    Kriteriji:
    - Sadrži "ŠUMAPROM" ili "SUMAPROM"
    - Sadrži "FAKTURA" ili "INVOICE"
    - Radi i za skenirane PDF-ove (koristi OCR ako treba)

    Args:
        filepath: Putanja do PDF fajla

    Returns:
        True ako je ŠUMAPROM PDF
    """
    try:
        # STEP 1: Try text extraction first (fast)
        with pdfplumber.open(filepath) as pdf:
            if not pdf.pages:
                return False

            text = ""
            for page in pdf.pages[:2]:
                page_text = page.extract_text() or ""
                text += page_text

            text_upper = text.upper()

            # Check for ŠUMAPROM signature
            has_sumaprom = "ŠUMAPROM" in text or "SUMAPROM" in text_upper
            
            # Check for invoice format
            has_invoice = "FAKTURA" in text_upper or "INVOICE" in text_upper

            if has_sumaprom and has_invoice:
                logger.debug(f"✅ ŠUMAPROM PDF detected (text): {filepath}")
                return True

        # STEP 2: If no text, try OCR (for scanned PDFs)
        if len(text.strip()) < 50:
            logger.debug(f"  ℹ️  No text found - trying OCR for: {filepath}")
            try:
                from importers.pdf.ocr_utils import ocr_pdf_to_text
                
                pages_text = ocr_pdf_to_text(filepath, dpi=300)
                ocr_text = "\n".join(pages_text[:2])  # First 2 pages
                ocr_text_upper = ocr_text.upper()
                
                has_sumaprom_ocr = "SUMAPROM" in ocr_text_upper or "ŠUMAPROM" in ocr_text
                has_invoice_ocr = "FAKTURA" in ocr_text_upper or "INVOICE" in ocr_text_upper
                
                if has_sumaprom_ocr and has_invoice_ocr:
                    logger.debug(f"✅ ŠUMAPROM PDF detected (OCR): {filepath}")
                    return True
                    
            except ImportError:
                logger.debug("  ℹ️  OCR not available for detection")
            except Exception as e:
                logger.debug(f"  ℹ️  OCR detection failed: {e}")

        return False

    except Exception as e:
        logger.warning(f"Error detecting ŠUMAPROM PDF: {e}")
        return False


def parse_sumaprom_pdf(pdf_path: str) -> ImportResult:
    """
    Parse ŠUMAPROM PDF fakturu.

    Napomena: Za ŠUMAPROM fakture, PDF se koristi SAMO za:
    - Ekstrakciju header informacija (broj fakture, težine, datumi)
    - Stavke se uzimaju iz Excela (kombinovanjem)

    Workflow:
    1. Pokušaj tekstualno parsiranje (pdfplumber)
    2. Ako nema teksta → koristi OCR
    3. Ekstrahuj SAMO header (težine, broj fakture)
    4. Vrati ImportResult (prazan items ili samo header)

    Args:
        pdf_path: Putanja do PDF fajla

    Returns:
        ImportResult sa header informacijama (items su prazni ako je skenirani PDF)
    """
    logger.info(f"ŠUMAPROM PDF parsing started: {pdf_path}")
    logger.info(f"  Napomena: PDF se koristi za ekstrakciju težina, stavke iz Excela")

    try:
        # STEP 1: Try text extraction
        with pdfplumber.open(pdf_path) as pdf:
            full_text = ""
            
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                full_text += page_text

            # Check if we got meaningful text
            if len(full_text.strip()) > 100:
                logger.info(f"  ✅ Textual PDF detected: {len(full_text)} chars")
                return _parse_textual_pdf(pdf_path, full_text, [])
            else:
                logger.info(f"  ℹ️  Skenirani PDF ({len(full_text.strip())} chars) - prelazim na OCR")
                return _parse_ocr_pdf(pdf_path)

    except Exception as e:
        logger.error(f"PDF parsing failed: {e}", exc_info=True)
        # Return empty result instead of raising
        return ImportResult(items=[], bruto_kg=0.0, neto_kg=0.0, invoice_name=Path(pdf_path).stem, currency="EUR")


def _parse_textual_pdf(
    pdf_path: str,
    full_text: str,
    tables: List
) -> ImportResult:
    """
    Parse textual ŠUMAPROM PDF.

    Args:
        pdf_path: Putanja do PDF
        full_text: Extracted text
        tables: Extracted tables

    Returns:
        ImportResult sa stavkama
    """
    logger.info(f"  Parsing textual PDF...")

    items: List[InvoiceLine] = []
    header_info: Dict[str, Any] = {}

    # STEP 1: Extract header info from text
    header_info = _extract_header_from_text(full_text)

    # STEP 2: Parse tables
    if tables:
        items = _parse_tables(tables)

    # STEP 3: If no items from tables, try text parsing
    if not items:
        items = _parse_items_from_text(full_text)

    # STEP 4: Calculate totals
    total_amount = sum(item.iznos for item in items) if items else 0.0

    logger.info(f"  Parsed {len(items)} items, total={total_amount:.2f} EUR")

    return ImportResult(
        items=items,
        bruto_kg=header_info.get('bruto_kg', 0.0),
        neto_kg=header_info.get('neto_kg', 0.0),
        invoice_name=header_info.get('invoice_name', Path(pdf_path).stem),
        currency="EUR",
    )


def _parse_ocr_pdf(pdf_path: str) -> ImportResult:
    """
    Parse skenirani ŠUMAPROM PDF koristeći OCR.

    Napomena: Za skenirane PDF-ove, ekstrahujemo SAMO header informacije:
    - Bruto težina
    - Neto težina
    - Broj fakture
    - Datum
    
    Stavke se uzimaju iz Excela prilikom kombinovanja.

    Args:
        pdf_path: Putanja do PDF fajla

    Returns:
        ImportResult sa header informacijama (items prazni)
    """
    logger.info(f"  Starting OCR for header extraction...")

    try:
        # Import OCR utilities
        from importers.pdf.ocr_utils import ocr_pdf_to_text
        
        # STEP 1: OCR ekstrakcija
        logger.info(f"  Converting PDF to images and running OCR...")
        pages_text = ocr_pdf_to_text(pdf_path, dpi=300)
        full_ocr_text = "\n".join(pages_text)
        
        logger.info(f"  ✅ OCR completed: {len(pages_text)} pages, {len(full_ocr_text)} chars")
        
        # STEP 2: Extract ONLY header info (weights, invoice number)
        header_info = _extract_header_from_text(full_ocr_text)
        
        logger.info(f"  Extracted header: bruto={header_info.get('bruto_kg', 0.0)} kg, neto={header_info.get('neto_kg', 0.0)} kg")
        
        # Return ImportResult with header info but NO items
        # Items will come from Excel when combined
        return ImportResult(
            items=[],  # Prazno - stavke dolaze iz Excela
            bruto_kg=header_info.get('bruto_kg', 0.0),
            neto_kg=header_info.get('neto_kg', 0.0),
            invoice_name=header_info.get('invoice_name', Path(pdf_path).stem),
            currency="EUR",
        )

    except ImportError as e:
        logger.warning(f"⚠️  OCR biblioteke nisu instalirane: {e}")
        logger.warning("   Instaliraj: pip install pytesseract pdf2image")
        logger.warning("   Tesseract: sudo apt-get install tesseract-ocr tesseract-ocr-bos tesseract-ocr-srp poppler-utils")
        return ImportResult(items=[], bruto_kg=0.0, neto_kg=0.0, invoice_name=Path(pdf_path).stem, currency="EUR")

    except Exception as e:
        logger.error(f"OCR parsing failed: {e}", exc_info=True)
        return ImportResult(items=[], bruto_kg=0.0, neto_kg=0.0, invoice_name=Path(pdf_path).stem, currency="EUR")


def _extract_header_from_text(text: str) -> Dict[str, Any]:
    """
    Extract header information from PDF text.

    Args:
        text: PDF text

    Returns:
        Dict sa: invoice_number, invoice_date, bruto_kg, neto_kg, num_packages
    """
    header_info = {
        'invoice_number': '',
        'invoice_date': '',
        'bruto_kg': 0.0,
        'neto_kg': 0.0,
        'num_packages': 0,
        'invoice_name': '',
    }

    # Invoice number: "059/2022" or "Broj: 059/2022" or "FAKTURA BR. 059/ 2022"
    invoice_match = re.search(r'(?:Invoice|FAKTURA|Broj)[:\s]*(\d+\s*/\s*\d+)', text, re.IGNORECASE)
    if invoice_match:
        invoice_num = invoice_match.group(1).replace(' ', '')
        header_info['invoice_number'] = invoice_num
        header_info['invoice_name'] = invoice_num

    # Date: "04.11.2022." or "04.11.2022"
    date_match = re.search(r'(\d{1,2}\.\d{1,2}\.\d{4})', text)
    if date_match:
        header_info['invoice_date'] = date_match.group(1)

    # Gross weight: "266,00 KG" or "266.00 kg" or "Gross weight: 266,00"
    # Try multiple patterns
    gross_patterns = [
        r'(?:Gross|BRUTO|Bruto|GROSS)[:\s]*([\d,\.]+)\s*KG',
        r'([\d,\.]+)\s*KG',
        r'BRUTO\s*[:=]?\s*([\d,\.]+)',
    ]
    
    for pattern in gross_patterns:
        gross_match = re.search(pattern, text, re.IGNORECASE)
        if gross_match:
            weight_str = gross_match.group(1).replace(',', '.')
            try:
                header_info['bruto_kg'] = float(weight_str)
                break
            except ValueError:
                pass

    # Net weight: "Neto" or "Net"
    net_patterns = [
        r'(?:Neto|Net)[:\s]*([\d,\.]+)\s*KG',
        r'NETO\s*[:=]?\s*([\d,\.]+)',
    ]
    
    for pattern in net_patterns:
        net_match = re.search(pattern, text, re.IGNORECASE)
        if net_match:
            weight_str = net_match.group(1).replace(',', '.')
            try:
                header_info['neto_kg'] = float(weight_str)
                break
            except ValueError:
                pass

    # Number of packages: "15 KOLETA" or "Box No.: 15"
    pkg_match = re.search(r'(\d+)\s*(?:KOLETA|Box|Pak)', text, re.IGNORECASE)
    if pkg_match:
        header_info['num_packages'] = int(pkg_match.group(1))

    return header_info


def _parse_tables(tables: List) -> List[InvoiceLine]:
    """
    Parse items from extracted tables.

    Args:
        tables: List of tables from pdfplumber

    Returns:
        List of InvoiceLine
    """
    items = []

    for table in tables:
        if not table or len(table) < 2:
            continue

        # Try to find header row
        header_idx = _find_table_header(table)
        if header_idx < 0:
            continue

        # Parse data rows
        for row_idx in range(header_idx + 1, len(table)):
            row = table[row_idx]
            if not row or len(row) < 5:
                continue

            # Skip total/summary rows
            row_text = ' '.join(str(cell) for cell in row if cell)
            if 'TOTAL' in row_text.upper() or 'UKUPNO' in row_text.upper():
                break

            item = _parse_table_row(row, row_idx - header_idx)
            if item:
                items.append(item)

    return items


def _find_table_header(table: List) -> int:
    """
    Find header row in table.

    Args:
        table: Table rows

    Returns:
        Index of header row, or -1 if not found
    """
    for idx, row in enumerate(table):
        if not row:
            continue

        row_text = ' '.join(str(cell) for cell in row if cell).upper()

        # Look for header keywords
        if any(kw in row_text for kw in ['POS.', 'R.BR.', 'DESCRIPTION', 'ITEM', 'CODE', 'KOLIČINA']):
            return idx

    return -1


def _parse_table_row(row: List, line_no: int) -> Optional[InvoiceLine]:
    """
    Parse one table row into InvoiceLine.

    Expected columns (flexible):
    - R.br. | Šifra | Opis | JM | Količina | Cena | Iznos | Zemlja

    Args:
        row: Table row cells
        line_no: Line number

    Returns:
        InvoiceLine or None
    """
    # Clean row values
    clean_row = [str(cell).strip() if cell else '' for cell in row]

    # Try to extract fields (flexible column positions)
    naziv_robe = ''
    product_code = ''
    kolicina = 0.0
    cijena_jed = 0.0
    iznos = 0.0
    zemlja_porijekla = ''
    jm = 'kom'

    # Look for numeric patterns
    numbers = []
    for cell in clean_row:
        num_match = re.search(r'([\d,\.]+)', cell)
        if num_match:
            try:
                num = float(num_match.group(1).replace(',', '.'))
                numbers.append(num)
            except ValueError:
                pass

    # Heuristic: find quantity, price, amount from numbers
    if len(numbers) >= 3:
        # Usually: quantity, price, amount
        kolicina = numbers[-3] if len(numbers) >= 3 else 0.0
        cijena_jed = numbers[-2] if len(numbers) >= 2 else 0.0
        iznos = numbers[-1]

    # Find description (longest text cell)
    text_cells = [cell for cell in clean_row if cell and not re.match(r'^[\d,\.]+$', cell)]
    if text_cells:
        naziv_robe = max(text_cells, key=len)

    # Find product code (short alphanumeric)
    for cell in clean_row:
        if re.match(r'^[A-Z0-9\-]{3,15}$', cell, re.IGNORECASE):
            product_code = cell
            break

    # Find country
    for cell in clean_row:
        cell_upper = cell.upper()
        if any(country in cell_upper for country in ['DE ', 'RS ', 'IT ', 'CN ', 'SI ', 'SK ', 'BR ', 'TW ', 'IN ']):
            zemlja_porijekla = cell
            break

    # Skip if no description
    if not naziv_robe or len(naziv_robe) < 3:
        return None

    # Normalize country
    zemlja_iso = ''
    if zemlja_porijekla:
        iso_match = re.match(r'^([A-Z]{2,3})\s*/', zemlja_porijekla)
        if iso_match:
            zemlja_iso = iso_match.group(1)
            if zemlja_iso == "SER":
                zemlja_iso = "RS"
            elif zemlja_iso == "SLO":
                zemlja_iso = "SI"
        else:
            zemlja_iso = normalize_country_name(zemlja_porijekla)

    return InvoiceLine(
        line_no=line_no,
        naziv_robe=naziv_robe,
        product_code=product_code,
        tarifni_broj='',
        zemlja_porijekla=zemlja_iso,
        kolicina=kolicina,
        cijena_jed=cijena_jed,
        iznos=iznos,
        valuta="EUR",
        bruto_kg=0.0,
        neto_kg=0.0,
        jm=jm,
    )


def _parse_ocr_tables(pdf_path: str, pages_text: List[str]) -> List[InvoiceLine]:
    """
    Advanced parsing for OCR text - try to find table patterns.

    Args:
        pdf_path: Putanja do PDF
        pages_text: List of OCR text per page

    Returns:
        List of InvoiceLine
    """
    logger.info(f"  Advanced OCR table parsing...")
    
    # Try to parse using line-by-line pattern matching
    items = []
    
    for page_idx, page_text in enumerate(pages_text):
        lines = page_text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or len(line) < 20:
                continue
            
            # Try to match item pattern
            # Pattern: Number Code Description Qty Price Amount Country
            match = re.search(
                r'(\d+)\s+'  # R.br.
                r'([A-Z0-9\-]+)\s+'  # Code
                r'(.+?)\s+'  # Description (greedy)
                r'(\d+[,\.\d]*)\s+'  # Qty
                r'([\d,\.]+)\s+'  # Price
                r'([\d,\.]+)\s*'  # Amount
                r'([A-Z]{2,3}/[A-Z\s]+)?',  # Country (optional)
                line
            )
            
            if match:
                try:
                    line_no = int(match.group(1))
                    product_code = match.group(2).strip()
                    naziv_robe = match.group(3).strip()
                    kolicina = float(match.group(4).replace(',', '.'))
                    cijena_jed = float(match.group(5).replace(',', '.'))
                    iznos = float(match.group(6).replace(',', '.'))
                    country_raw = match.group(7).strip() if match.group(7) else ''
                    
                    # Normalize country
                    zemlja_iso = ''
                    if country_raw:
                        iso_match = re.match(r'^([A-Z]{2,3})/', country_raw)
                        if iso_match:
                            zemlja_iso = iso_match.group(1)
                            # Normalize to 2-letter ISO codes
                            if zemlja_iso == "SER":
                                zemlja_iso = "RS"
                            elif zemlja_iso == "SLO":
                                zemlja_iso = "SI"
                            elif zemlja_iso == "BRA":
                                zemlja_iso = "BR"  # Brazil → BR
                        else:
                            zemlja_iso = normalize_country_name(country_raw)
                    
                    items.append(InvoiceLine(
                        line_no=line_no,
                        naziv_robe=naziv_robe,
                        product_code=product_code,
                        tarifni_broj='',
                        zemlja_porijekla=zemlja_iso,
                        kolicina=kolicina,
                        cijena_jed=cijena_jed,
                        iznos=iznos,
                        valuta="EUR",
                        bruto_kg=0.0,
                        neto_kg=0.0,
                        jm="kom",
                    ))
                except (ValueError, IndexError) as e:
                    logger.debug(f"Failed to parse line: {e}")
                    continue
    
    logger.info(f"  Advanced parsing found {len(items)} items")
    return items


def _parse_items_from_text(text: str) -> List[InvoiceLine]:
    """
    Parse items directly from text (fallback if tables fail).

    Args:
        text: PDF text

    Returns:
        List of InvoiceLine
    """
    items = []

    # Pattern for item rows
    # Example: "1 001-401 STARTNO UŽE 4,0mmX50M Nr/kom 5 8,8 44 DE/NEMAČKA"
    item_pattern = re.compile(
        r'^(\d+)\s+'  # R.br.
        r'([A-Z0-9\-]+)\s+'  # Šifra
        r'(.+?)\s+'  # Opis
        r'(\d+[,\.\d]*)\s+'  # Količina
        r'([\d,\.]+)\s+'  # Cena
        r'([\d,\.]+)\s+'  # Iznos
        r'([A-Z]{2,3}/[A-Z\s]+)?',  # Zemlja (optional)
        re.MULTILINE
    )

    for match in item_pattern.finditer(text):
        try:
            line_no = int(match.group(1))
            product_code = match.group(2).strip()
            naziv_robe = match.group(3).strip()
            kolicina = float(match.group(4).replace(',', '.'))
            cijena_jed = float(match.group(5).replace(',', '.'))
            iznos = float(match.group(6).replace(',', '.'))
            zemlja_raw = match.group(7).strip() if match.group(7) else ''

            # Normalize country
            zemlja_iso = ''
            if zemlja_raw:
                iso_match = re.match(r'^([A-Z]{2,3})/', zemlja_raw)
                if iso_match:
                    zemlja_iso = iso_match.group(1)
                    if zemlja_iso == "SER":
                        zemlja_iso = "RS"
                    elif zemlja_iso == "SLO":
                        zemlja_iso = "SI"
                else:
                    zemlja_iso = normalize_country_name(zemlja_raw)

            items.append(InvoiceLine(
                line_no=line_no,
                naziv_robe=naziv_robe,
                product_code=product_code,
                tarifni_broj='',
                zemlja_porijekla=zemlja_iso,
                kolicina=kolicina,
                cijena_jed=cijena_jed,
                iznos=iznos,
                valuta="EUR",
                bruto_kg=0.0,
                neto_kg=0.0,
                jm="kom",
            ))
        except (ValueError, IndexError) as e:
            logger.debug(f"Failed to parse item: {e}")
            continue

    return items


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        test_file = sys.argv[1]
        logger.info(f"Testing ŠUMAPROM PDF parser with: {test_file}")

        # Test detection
        is_sumaprom = detect_sumaprom_pdf(test_file)
        logger.info(f"Detection: {is_sumaprom}")

        if is_sumaprom:
            # Test parsing
            result = parse_sumaprom_pdf(test_file)
            logger.info(f"\n✅ Parsed: {len(result.items)} items")
            logger.info(f"Invoice: {result.invoice_name}")
            logger.info(f"Total: {sum(item.iznos for item in result.items):.2f} EUR")
            logger.info(f"Bruto: {result.bruto_kg} kg")
            logger.info(f"Neto: {result.neto_kg} kg")

            logger.info(f"\nFirst 3 items:")
            for i, item in enumerate(result.items[:3], 1):
                logger.info(f"  {i}. {item.product_code} - {item.naziv_robe[:50]}")
                logger.info(f"     Qty: {item.kolicina}, Price: {item.cijena_jed}, Amount: {item.iznos}")
                logger.info(f"     Country: {item.zemlja_porijekla}")
    else:
        logger.info("Usage: python sumaprom_pdf_parser.py <pdf_file>")
