# importers/sumaprom_excel_parser.py

"""
SUMAPROM Excel Importer
Specijalizovan parser za SUMAPROM fakture (Bijeljina).

Format:
- Header podaci rasuti po celijama (kupac, broj fakture, datum)
- Stavke od reda 18 (0-indexed) sa kolonama:
  - Pos. R.br. | Item Code | Description | U.M. | Quantity | Unit Price | Total Amount | Country of origin
- Footer: Ukupan iznos, bruto tezina, broj paketa
- EKSPORTATOR: Podaci o izvozniku u headeru fakture
- IMPORTER: Podaci o uvozniku (nasa firma)
"""

import os
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

import xlrd
import openpyxl

from core.draft.draft import InvoiceLine, Party
from importers.import_result import ImportResult
from utils.country_normalizer import normalize_country_name

logger = logging.getLogger("deklarant_pro.import.sumaprom")


class _SheetAdapter:
    """Minimal sheet adapter with xlrd-like interface."""

    def __init__(self, rows: List[List[Any]]) -> None:
        self._rows = rows
        self.nrows = len(rows)
        self.ncols = max((len(row) for row in rows), default=0)

    def cell_value(self, row_idx: int, col_idx: int) -> Any:
        if row_idx < 0 or row_idx >= self.nrows:
            return ""
        row = self._rows[row_idx]
        if col_idx < 0 or col_idx >= len(row):
            return ""
        value = row[col_idx]
        return "" if value is None else value


def _load_sheet(filepath: str) -> _SheetAdapter:
    """Load first sheet from .xls/.xlsx and return unified adapter."""
    ext = Path(filepath).suffix.lower()
    if ext == ".xlsx":
        wb = openpyxl.load_workbook(filepath, data_only=True, read_only=True)
        try:
            ws = wb.worksheets[0]
            rows = [list(row) for row in ws.iter_rows(values_only=True)]
        finally:
            wb.close()
        return _SheetAdapter(rows)

    wb = xlrd.open_workbook(filepath)
    sheet = wb.sheet_by_index(0)
    rows: List[List[Any]] = []
    for row_idx in range(sheet.nrows):
        rows.append([sheet.cell_value(row_idx, col_idx) for col_idx in range(sheet.ncols)])
    return _SheetAdapter(rows)


def detect_sumaprom_excel(filepath: str) -> bool:
    """
    Detekcija SUMAPROM formata.

    Kriteriji:
    - Extension .xls ili .xlsx
    - Sheet sadrzi "SUMAPROM" u headeru
    - Ima header kolone: "Pos.", "Item Code", "Description", "U.M.", "Quantity", "Unit Price", "Total Amount", "Country of origin"

    Args:
        filepath: Putanja do Excel fajla

    Returns:
        True ako je SUMAPROM format
    """
    try:
        # Check extension
        if not filepath.lower().endswith(('.xls', '.xlsx')):
            return False

        sheet = _load_sheet(filepath)

        # Search for SUMAPROM in first 20 rows
        found_sumaprom = False
        header_row_idx = -1

        for row_idx in range(min(20, sheet.nrows)):
            row_text = ""
            for col_idx in range(sheet.ncols):
                cell_value = sheet.cell_value(row_idx, col_idx)
                if cell_value:
                    row_text += str(cell_value).upper() + " "

            # Check for SUMAPROM
            if "SUMAPROM" in row_text or "ŠUMAPROM" in row_text:
                found_sumaprom = True

            # Check for header row (Pos. R.br. | Item Code | Description)
            if "POS." in row_text and "ITEM CODE" in row_text and "DESCRIPTION" in row_text:
                header_row_idx = row_idx
                break

        if found_sumaprom and header_row_idx >= 0:
            logger.info(f"SUMAPROM format detektovan: header na redu {header_row_idx}")
            return True

        return False

    except Exception as e:
        logger.warning(f"Greska tokom detekcije SUMAPROM formata: {e}")
        return False


def parse_sumaprom_excel(filepath: str) -> ImportResult:
    """
    Parse SUMAPROM Excel fakture.

    Args:
        filepath: Putanja do Excel fajla

    Returns:
        ImportResult sa stavkama i metapodacima

    Raises:
        ValueError: Ako format nije validan
    """
    logger.info(f"SUMAPROM parsing zapocet: {filepath}")

    try:
        sheet = _load_sheet(filepath)

        # STEP 1: Extract header information
        header_info = _extract_header_info(sheet)
        logger.info(f"Header info: {header_info}")

        # STEP 2: Find header row and parse items
        items, total_amount = _parse_items(sheet)

        # ENHANCED: Kreiraj Party objekte i postavi na stavke
        exporter = Party(
            name=header_info.get('exporter_name', ''),
            address=header_info.get('exporter_address', ''),
            city=header_info.get('exporter_city', ''),
            country=header_info.get('exporter_country', ''),
            vat_or_id=header_info.get('exporter_vat', ''),
        )
        importer = Party(
            name=header_info.get('importer_name', ''),
            address=header_info.get('importer_address', ''),
            city=header_info.get('importer_city', ''),
            country=header_info.get('importer_country', ''),
            vat_or_id=header_info.get('importer_vat', ''),
        )
        
        # Log extracted parties
        if exporter.name:
            logger.info(f"Exporter: {exporter.name}")
        if importer.name:
            logger.info(f"Importer: {importer.name}")
        
        # Postavi exporter/importer na svaku stavku
        for item in items:
            item.exporter = exporter
            item.importer = importer

        logger.info(
            f"SUMAPROM parsing zavrsen: {len(items)} stavki, "
            f"ukupno={total_amount} EUR"
        )

        # STEP 3: Extract invoice name
        # Prioritet: header_info['invoice_number'] > filename
        invoice_name = header_info.get('invoice_number', '') or Path(filepath).stem

        # ENHANCED: Return ImportResult sa exporter/importer
        return ImportResult(
            items=items,
            bruto_kg=header_info.get('bruto_kg', 0.0),
            neto_kg=header_info.get('neto_kg', 0.0),
            invoice_name=invoice_name,
            currency="EUR",
            exporter=exporter if exporter.name else None,
            importer=importer if importer.name else None,
        )

    except Exception as e:
        logger.error(f"Greska tokom SUMAPROM parsiranja: {e}", exc_info=True)
        raise ValueError(f"Nije moguce parsirati SUMAPROM Excel: {e}") from e


def _extract_header_info(sheet: _SheetAdapter) -> Dict[str, Any]:
    """
    Extract header information from sheet.

    Header podaci su rasuti po celijama:
    - EKSPORTATOR: SUMAPROM (prvih 18 redova)
    - Broj fakture: 059/2022
    - Datum: 04.11.2022.
    - Bruto tezina: 266,00 KG (u footeru)
    - Broj paketa: 15

    Returns:
        Dict sa extracted podacima ukljucujuci exporter i importer
    """
    header_info = {
        'buyer': '',
        'invoice_number': '',
        'invoice_date': '',
        'bruto_kg': 0.0,
        'neto_kg': 0.0,
        'num_packages': 0,
        'total_amount': 0.0,
        # ENHANCED: Exporter/Importer podaci
        'exporter_name': '',
        'exporter_address': '',
        'exporter_city': '',
        'exporter_country': '',
        'exporter_vat': '',
        'importer_name': '',
        'importer_address': '',
        'importer_city': '',
        'importer_country': '',
        'importer_vat': '',
    }

    # Collect all text from first 25 rows for analysis
    all_rows_text = []
    for row_idx in range(min(25, sheet.nrows)):
        row_cells = []
        for col_idx in range(sheet.ncols):
            cell_value = sheet.cell_value(row_idx, col_idx)
            if cell_value:
                row_cells.append((col_idx, str(cell_value).strip()))
        all_rows_text.append(row_cells)

    # Search through first 20 rows for basic info
    for row_idx in range(min(20, sheet.nrows)):
        for col_idx in range(sheet.ncols):
            cell_value = str(sheet.cell_value(row_idx, col_idx)).strip()

            # Look for invoice number pattern: "Invoice No." or "FAKTURA BR."
            if "INVOICE NO." in cell_value.upper() or "FAKTURA BR." in cell_value.upper():
                # Sakupljaj sledece kolone dok ne naidjes na ne-broj
                parts = []
                for next_col in range(col_idx + 1, min(col_idx + 5, sheet.ncols)):
                    next_val = sheet.cell_value(row_idx, next_col)
                    if next_val:
                        parts.append(str(next_val).strip())
                full = ''.join(parts)
                # Izvuci broj oblika 059/2022
                match = re.search(r'(\d+\s*/\s*\d+)', full)
                if match:
                    header_info['invoice_number'] = match.group(1).replace(' ', '')
                else:
                    # Fallback: samo prvi broj
                    match = re.search(r'(\d+)[^\d]*$', full)
                    if match:
                        header_info['invoice_number'] = match.group(1)

            # Look for date pattern (dd.mm.yyyy)
            date_match = re.search(r'(\d{1,2}\.\d{1,2}\.\d{4})', cell_value)
            if date_match and not header_info['invoice_date']:
                header_info['invoice_date'] = date_match.group(1)

    # EKSPORTATOR (strani prodavac/dobavljac) — trazimo po labelama SELLER/EKSPORTATOR
    # Napomena: SUMAPROM je KUPAC (consignee/uvoznik), NE eksportator!
    seller_keywords = ['SELLER', 'EKSPORTATOR', 'EXPORTER', 'PRODAVAC', 'SUPPLIER', 'DOBAVLJAC', 'FROM:']
    for row_idx in range(min(20, sheet.nrows)):
        for col_idx, cell_str in all_rows_text[row_idx]:
            if any(kw in cell_str.upper() for kw in seller_keywords):
                # Sljedeci red ili sljedeca kolona sadrzi ime prodavca
                if row_idx + 1 < sheet.nrows:
                    for check_col in range(sheet.ncols):
                        seller_cell = sheet.cell_value(row_idx + 1, check_col)
                        if seller_cell:
                            seller_str = str(seller_cell).strip()
                            if any(kw in seller_str.upper() for kw in seller_keywords):
                                continue
                            if len(seller_str) > 3 and 'SUMAPROM' not in seller_str.upper():
                                header_info['exporter_name'] = seller_str
                                break
                if header_info['exporter_name']:
                    break
        if header_info['exporter_name']:
            break

    # ENHANCED: Extract IMPORTER (buyer - nasa firma / consignee)
    # Look for buyer info - usually contains "BUYER", "KUPAC", or company name
    for row_idx in range(min(25, sheet.nrows)):
        for col_idx in range(sheet.ncols):
            cell_value = sheet.cell_value(row_idx, col_idx)
            if cell_value:
                cell_str = str(cell_value).upper()
                
                # Look for buyer header
                if any(kw in cell_str for kw in ['BUYER', 'KUPAC', 'IMPORTER', 'UVOZNIK', 'CONSIGNEE']):
                    # Usually next row has the buyer info
                    if row_idx + 1 < sheet.nrows:
                        for check_col in range(sheet.ncols):
                            buyer_cell = sheet.cell_value(row_idx + 1, check_col)
                            if buyer_cell:
                                buyer_str = str(buyer_cell).strip()
                                # Skip header keywords
                                if any(kw in buyer_str.upper() for kw in ['BUYER', 'KUPAC', 'CONSIGNEE']):
                                    continue
                                # Look for company name
                                if buyer_str and len(buyer_str) > 5:
                                    if any(ind in buyer_str.upper() for ind in ['D.O.O', 'LTD', 'INC', 'GMBH', 'DOO']):
                                        header_info['importer_name'] = buyer_str
                                        # Try to get address from next columns
                                        if check_col + 1 < sheet.ncols:
                                            addr = sheet.cell_value(row_idx + 1, check_col + 1)
                                            if addr:
                                                header_info['importer_address'] = str(addr).strip()
                                        # Try to get city from next row
                                        if row_idx + 2 < sheet.nrows:
                                            city = sheet.cell_value(row_idx + 2, check_col)
                                            if city:
                                                header_info['importer_city'] = str(city).strip()
                                        break
                        if header_info['importer_name']:
                            break
                break

    # Search entire sheet for gross weight
    for row_idx in range(sheet.nrows):
        for col_idx in range(sheet.ncols):
            cell_value = sheet.cell_value(row_idx, col_idx)
            if cell_value:
                cell_str = str(cell_value)
                
                # Look for gross weight: "Gross weight" or "BRUTO TEZINA"
                if "GROSS WEIGHT" in cell_str.upper() or "BRUTO" in cell_str.upper() and "TEŽINA" in cell_str.upper():
                    weight_match = re.search(r'([\d,\.]+)\s*KG', cell_str, re.IGNORECASE)
                    if weight_match:
                        weight_str = weight_match.group(1).replace(',', '.')
                        header_info['bruto_kg'] = float(weight_str)
                        break
                # Look for net weight: "Net weight" or "NETO TEŽINA"
                if "NET WEIGHT" in cell_str.upper() or "NETO" in cell_str.upper() and "TEŽINA" in cell_str.upper():
                    weight_match = re.search(r'([\d,\.]+)\s*KG', cell_str, re.IGNORECASE)
                    if weight_match:
                        weight_str = weight_match.group(1).replace(',', '.')
                        header_info['neto_kg'] = float(weight_str)
                        break

    # Search for number of packages: "BROJ KOLETA" or "Box No."
    for row_idx in range(sheet.nrows):
        for col_idx in range(sheet.ncols):
            cell_value = sheet.cell_value(row_idx, col_idx)
            if cell_value:
                cell_str = str(cell_value)
                
                if "BROJ KOLETA" in cell_str.upper() or "BOX NO." in cell_str.upper():
                    # Next cell should contain the number
                    if col_idx + 1 < sheet.ncols:
                        pkg_str = str(sheet.cell_value(row_idx, col_idx + 1)).strip()
                        pkg_match = re.search(r'(\d+)', pkg_str)
                        if pkg_match:
                            header_info['num_packages'] = int(pkg_match.group(1))
                            break

    # Search for total amount in footer (last rows)
    for row_idx in range(sheet.nrows - 1, max(0, sheet.nrows - 11), -1):
        for col_idx in range(sheet.ncols):
            cell_value = sheet.cell_value(row_idx, col_idx)
            if cell_value:
                cell_str = str(cell_value).upper()
                # Look for "TOTAL INVOICE AMOUNT" or "UKUPNO ZA UPLATU"
                if "TOTAL INVOICE AMOUNT" in cell_str or "UKUPNO ZA UPLATU" in cell_str:
                    # Find the amount in the same row or next row
                    for check_col in range(sheet.ncols):
                        check_value = sheet.cell_value(row_idx, check_col)
                        if check_value:
                            amount_str = str(check_value).replace(',', '.').replace(' ', '')
                            amount_match = re.search(r'([\d.]+)', amount_str)
                            if amount_match and float(amount_match.group(1)) > 0:
                                header_info['total_amount'] = float(amount_match.group(1))
                                break
                    if header_info['total_amount'] > 0:
                        break

    return header_info


def _parse_items(sheet: _SheetAdapter) -> Tuple[List[InvoiceLine], float]:
    """
    Parse items from sheet.

    Header row sadrzi: Pos. R.br. | Item Code | Description | U.M. | Quantity | Unit Price | Total Amount | Country of origin

    Args:
        sheet: Excel worksheet

    Returns:
        Tuple of (items, total_amount)
    """
    items = []
    total_amount = 0.0

    # STEP 1: Find header row
    header_row_idx = -1
    header_map = {}

    for row_idx in range(min(30, sheet.nrows)):
        row_text = ""
        for col_idx in range(sheet.ncols):
            cell_value = sheet.cell_value(row_idx, col_idx)
            if cell_value:
                row_text += str(cell_value).upper() + " | "

        # Check for header pattern
        if "POS." in row_text and "ITEM CODE" in row_text and "DESCRIPTION" in row_text:
            header_row_idx = row_idx
            # Parse header to map columns
            header_map = _parse_header_row(sheet, row_idx)
            logger.debug(f"Header row found at {row_idx}, map: {header_map}")
            break

    if header_row_idx < 0:
        raise ValueError("Header row not found! Expected columns: Pos., Item Code, Description, U.M., Quantity, Unit Price, Total Amount, Country of origin")

    # STEP 2: Parse items starting from next row
    row_idx = header_row_idx + 1

    while row_idx < sheet.nrows:
        # Check if this is a total/summary row
        is_total_row = False
        for col_idx in range(sheet.ncols):
            cell_value = sheet.cell_value(row_idx, col_idx)
            if cell_value:
                cell_str = str(cell_value).upper()
                if "TOTAL" in cell_str or "SUM(" in cell_str or "UKUPNO" in cell_str:
                    is_total_row = True
                    break

        if is_total_row:
            logger.debug(f"Total row found at {row_idx}, stopping item parsing")
            break

        # Parse item
        try:
            item = _parse_item_row(sheet, row_idx, header_map)
            if item:
                items.append(item)
        except Exception as e:
            logger.warning(f"Preskakanje reda {row_idx}: {e}")

        row_idx += 1

    # Calculate total from items if not found in header
    if items:
        total_amount = sum(item.iznos for item in items)

    return items, total_amount


def _parse_header_row(sheet: _SheetAdapter, row_idx: int) -> Dict[str, int]:
    """
    Parse header row and map columns.

    Expected columns:
    - Pos. R.br. (line number)
    - Item Code (product code)
    - Description (item name)
    - U.M. (unit of measure)
    - Quantity
    - Unit Price
    - Total Amount
    - Country of origin

    Returns:
        Dict mapping standard names to column indices
    """
    header_map = {}

    for col_idx in range(sheet.ncols):
        cell_value = sheet.cell_value(row_idx, col_idx)
        if not cell_value:
            continue

        header_value = str(cell_value).strip().lower()

        # Map columns - check for keywords in header text
        if "pos." in header_value or "r.br." in header_value or "r br" in header_value:
            header_map["line_no"] = col_idx
        elif "item code" in header_value or "sifra" in header_value:
            header_map["product_code"] = col_idx
        elif "description" in header_value or "opis" in header_value or "naziv" in header_value:
            header_map["naziv_robe"] = col_idx
        elif "u.m." in header_value or "jm" in header_value:
            header_map["jm"] = col_idx
        elif "quantity" in header_value or "kolicina" in header_value:
            header_map["kolicina"] = col_idx
        elif "unit price" in header_value or "cena" in header_value or "cijena" in header_value:
            header_map["cijena_jed"] = col_idx
        elif "total amount" in header_value or "iznos" in header_value or "ukupno" in header_value:
            header_map["iznos"] = col_idx
        elif "country" in header_value or "origin" in header_value or "poreklo" in header_value or "porijeklo" in header_value:
            header_map["zemlja_porijekla"] = col_idx

    # Validate required columns
    required = ["naziv_robe", "kolicina", "iznos"]
    missing = [col for col in required if col not in header_map]

    if missing:
        raise ValueError(f"Nedostaju obavezne kolone u header-u: {missing}")

    return header_map


def _parse_item_row(
    sheet: _SheetAdapter,
    row_idx: int,
    header_map: Dict[str, int]
) -> Optional[InvoiceLine]:
    """
    Parse one item row.

    Args:
        sheet: Excel worksheet
        row_idx: Row index
        header_map: Column mapping

    Returns:
        InvoiceLine or None if row should be skipped
    """
    # Helper to get cell value
    def get_value(field_name: str) -> str:
        col_idx = header_map.get(field_name)
        if col_idx is not None and col_idx < sheet.ncols:
            value = sheet.cell_value(row_idx, col_idx)
            return str(value).strip() if value else ""
        return ""

    # Helper to get float value
    def get_float(field_name: str) -> float:
        value_str = get_value(field_name)
        if not value_str:
            return 0.0

        # Clean non-numeric characters and convert European format
        cleaned = re.sub(r'[^\d\.,\-]', '', value_str)
        cleaned = cleaned.replace(',', '.')

        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return 0.0

    # Extract fields
    line_no_str = get_value("line_no")
    # Use line_no from cell if available, otherwise calculate from row index
    if line_no_str:
        # Handle both string and numeric values
        try:
            # float() handles both "1.0" string and 1.0 float -> 1
            line_no = int(float(line_no_str))
        except (ValueError, TypeError):
            # Fallback if conversion fails
            line_no = row_idx - header_map.get("line_no", 19) + 1
    else:
        # Fallback: calculate from row index (header is at header_map["line_no"])
        line_no = row_idx - header_map.get("line_no", 19) + 1

    product_code = get_value("product_code")
    naziv_robe = get_value("naziv_robe")
    jm = get_value("jm")
    kolicina = get_float("kolicina")
    cijena_jed = get_float("cijena_jed")
    iznos = get_float("iznos")
    zemlja_porijekla_raw = get_value("zemlja_porijekla")
    tarifni_broj = ""  # SUMAPROM Excel nema tarifni broj

    # Skip empty rows
    if not naziv_robe or len(naziv_robe) < 2:
        return None

    # Skip non-product rows (headers, footers, comments)
    skip_keywords = [
        'TOTAL', 'SUBTOTAL', 'NETO', 'BRUTO', 'UKUPNO', 'ZBIR',
        'KOMENTAR', 'NAPOMENA', 'PRICE TERM', 'DELIVERY', 'BANK',
        'ISSUED BY', 'UNDER', 'VAT', 'PDV', 'OSLOBOĐENO'
    ]
    if any(kw in naziv_robe.upper() for kw in skip_keywords):
        return None

    # Normalize country name to ISO code
    # First extract just the ISO code if format is "XX / COUNTRY NAME"
    zemlja_iso = ""
    if zemlja_porijekla_raw:
        # Try to extract ISO code from format like "DE / NEMACKA" or "SER / SRBIJA"
        iso_match = re.match(r'^([A-Z]{2,3})\s*/', zemlja_porijekla_raw)
        if iso_match:
            zemlja_iso = iso_match.group(1)
            # Normalize common codes to 2-letter ISO
            if zemlja_iso == "SER":
                zemlja_iso = "RS"
            elif zemlja_iso == "SLO":
                zemlja_iso = "SI"
            elif zemlja_iso == "SK":
                zemlja_iso = "SK"
            elif zemlja_iso == "DE":
                zemlja_iso = "DE"
            elif zemlja_iso == "IT":
                zemlja_iso = "IT"
            elif zemlja_iso == "CN":
                zemlja_iso = "CN"
            elif zemlja_iso == "TW":
                zemlja_iso = "TW"
            elif zemlja_iso == "IN":
                zemlja_iso = "IN"
            elif zemlja_iso == "BR" or zemlja_iso == "BRA":
                zemlja_iso = "BR"  # Brazil -> BR
            elif zemlja_iso == "IE":
                zemlja_iso = "IE"
            elif zemlja_iso == "IR":
                # Šumaprom koristi "IR" za Irsku (IRSKA), a ne za Iran
                full_name = zemlja_porijekla_raw.upper()
                if "IRSKA" in full_name or "IRELAND" in full_name:
                    zemlja_iso = "IE"
                # else ostaje "IR" (Iran)
        else:
            # Fallback to normalizer
            zemlja_iso = normalize_country_name(zemlja_porijekla_raw)

    # Create InvoiceLine
    item = InvoiceLine(
        line_no=line_no,
        naziv_robe=naziv_robe,
        product_code=product_code,
        tarifni_broj=tarifni_broj,
        zemlja_porijekla=zemlja_iso,
        kolicina=kolicina,
        cijena_jed=cijena_jed,
        iznos=iznos,
        valuta="EUR",
        bruto_kg=0.0,  # Težine nisu po stavkama u Excelu
        neto_kg=0.0,
        jm=jm if jm else "kom",
        povlastica=""  # Nije dostupno u Excelu
    )

    return item


# ============================================================
# USAGE EXAMPLE
# ============================================================

if __name__ == "__main__":
    import sys
    from pathlib import Path

    # Test with sample file
    test_file = "/home/radovan/Desktop/deklarant_pro/najavauvoza/suma/"

    if os.path.exists(test_file):
        files = [f for f in os.listdir(test_file) if f.endswith(('.xls', '.xlsx'))]
        if files:
            test_file = os.path.join(test_file, files[0])
            logger.info(f"Test fajl: {test_file}")
            
            # Test detection
            is_sumaprom = detect_sumaprom_excel(test_file)
            logger.debug(f"Detection result: {is_sumaprom}")

            if is_sumaprom:
                # Test parsing
                result = parse_sumaprom_excel(test_file)
                logger.debug(f"Parsed: {len(result.items)} items")
                logger.debug(f"Invoice: {result.invoice_name}")
                logger.debug(f"Total amount: {sum(item.iznos for item in result.items):.2f} EUR")
                logger.debug(f"Gross weight: {result.bruto_kg} kg")
                
                # ENHANCED: Log exporter/importer
                if result.exporter:
                    logger.debug(f"Exporter: {result.exporter.name}")
                if result.importer:
                    logger.debug(f"Importer: {result.importer.name}")

                logger.debug(f"Prvih 5 stavki:")
                for i, item in enumerate(result.items[:5], 1):
                    logger.debug(f"{i}. Code: {item.product_code}")
                    logger.debug(f"   Naziv: {item.naziv_robe[:60]}")
                    logger.debug(f"   Qty: {item.kolicina} {item.jm}, Amount: {item.iznos} EUR")
                    logger.debug(f"   Country: {item.zemlja_porijekla}")
    else:
        logger.debug(f"Test folder not found: {test_file}")

