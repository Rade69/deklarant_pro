# importers/blagic_loren_importer.py

"""
Blagić Loren Excel Importer
Specijalizovan parser za Blagić fakture od Loren dobavljača (Beograd).

Format:
- 9 kolona: RB, Kod, Artikal, JM, Količina, Težina po komadu kg, Težina ukupno kg, Tarifni broj, Poreklo
- Header u redu 1
- Stavke od reda 2
- Suma težine na kraju sa formulom =SUM(G2:Gn)
- Broj koleta u posljednjoj liniji
"""

import os
import logging
import re
from typing import List, Optional, Tuple, Dict
from pathlib import Path

import openpyxl
from openpyxl.worksheet.worksheet import Worksheet

from core.draft.draft import InvoiceLine, Party
from importers.import_result import ImportResult
from utils.country_normalizer import normalize_country_name

logger = logging.getLogger("asycuda_pro.import.blagic_loren")


def detect_blagic_loren_excel(filepath: str) -> bool:
    """
    Detekcija Blagic-Loren formata.

    Kriteriji:
    - Extension .xlsx
    - Ima header: "RB", "Kod", "Artikal", "JM", "Kolicina", "Težina po komadu kg", "Težina ukupno kg", "Tarifni broj", "Poreklo"
    - Sheet ime sadrži "VP-2025" ili "BLAGIC"

    Args:
        filepath: Putanja do Excel fajla

    Returns:
        True ako je Blagic-Loren format
    """
    try:
        # Check extension
        if not filepath.lower().endswith('.xlsx'):
            return False

        # Open workbook
        wb = openpyxl.load_workbook(filepath, data_only=True, read_only=True)

        # Check sheet names
        for sheet in wb.worksheets:
            sheet_name_upper = sheet.title.upper()

            # Check if sheet name contains indicators
            if "VP-2025" in sheet_name_upper or "BLAGIC" in sheet_name_upper:
                # Check header row (row 1)
                header_values = []
                for cell in sheet[1]:
                    if cell.value:
                        header_values.append(str(cell.value).strip())

                # Expected columns (case-insensitive partial match)
                expected = ["RB", "Kod", "Artikal", "JM", "Kolicina", "Težina", "Tarifni", "Poreklo"]

                # Check if header contains most of the expected columns
                matches = 0
                for exp in expected:
                    if any(exp.lower() in h.lower() for h in header_values):
                        matches += 1

                if matches >= 6:  # At least 6 out of 8 expected columns
                    wb.close()
                    logger.info(f"Blagic-Loren format detektovan: sheet '{sheet.title}'")
                    return True

        wb.close()
        return False

    except Exception as e:
        logger.warning(f"Greška tokom detekcije Blagic-Loren formata: {e}")
        return False


def _find_and_extract_weights_from_pdf(excel_path: str) -> tuple[float, float]:
    """
    Pronađi matching PDF fajl i izvuci ukupne težine.

    Args:
        excel_path: Putanja do Excel fajla

    Returns:
        (bruto_kg, neto_kg) tuple, ili (0.0, 0.0) ako PDF nije pronađen
    """
    import pdfplumber
    import re

    # Try to find matching PDF (same name, different extension)
    pdf_path = Path(excel_path).with_suffix('.pdf')

    if not pdf_path.exists():
        logger.debug(f"Matching PDF not found: {pdf_path}")
        return (0.0, 0.0)

    logger.info(f"Found matching PDF: {pdf_path}")

    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Extract text from all pages
            full_text = ""
            for page in pdf.pages:
                full_text += page.extract_text() or ""

            # Search for weight information
            # Format: "Gross weight: 394,15 kg" and "Net weight: 383,00 kg"
            bruto_kg = 0.0
            neto_kg = 0.0

            # Try to find Gross weight
            gross_match = re.search(r'Gross\s+weight:\s*([\d,\.]+)\s*kg', full_text, re.IGNORECASE)
            if gross_match:
                weight_str = gross_match.group(1).replace(',', '.')
                bruto_kg = float(weight_str)
                logger.info(f"Extracted Gross weight: {bruto_kg} kg")

            # Try to find Net weight
            net_match = re.search(r'Net\s+weight:\s*([\d,\.]+)\s*kg', full_text, re.IGNORECASE)
            if net_match:
                weight_str = net_match.group(1).replace(',', '.')
                neto_kg = float(weight_str)
                logger.info(f"Extracted Net weight: {neto_kg} kg")

            # Validation: neto should not be greater than bruto
            if neto_kg > 0 and bruto_kg > 0 and neto_kg > bruto_kg:
                logger.warning(f"⚠️ VALIDACIJA: Neto ({neto_kg} kg) > Bruto ({bruto_kg} kg)! Provjerite PDF.")

            return (bruto_kg, neto_kg)

    except Exception as e:
        logger.error(f"Error extracting weights from PDF: {e}")
        return (0.0, 0.0)


def parse_blagic_loren_excel(filepath: str) -> ImportResult:
    """
    Parse Blagic-Loren Excel fakture.
    Auto-kombinuje sa matching PDF-om za ukupne težine (bruto i neto).

    Args:
        filepath: Putanja do Excel fajla

    Returns:
        ImportResult sa stavkama i ukupnom težinom

    Raises:
        ValueError: Ako format nije validan
    """
    logger.info(f"Blagic-Loren parsing započet: {filepath}")

    try:
        # Open workbook
        wb = openpyxl.load_workbook(filepath, data_only=True)

        try:
            # Select first sheet (usually the only one)
            sheet = wb.worksheets[0]
            sheet_name = sheet.title

            logger.info(f"Parsing sheet: {sheet_name}")

            # Parse header (row 1)
            header_map = _parse_header(sheet)
            logger.info(f"Column mapping: {header_map}")

            # Parse items (from row 2 until sum row)
            items, total_weight_kg, num_packages = _parse_items(sheet, header_map)

            logger.info(
                f"Blagic-Loren parsing završen: {len(items)} stavki, "
                f"ukupna težina={total_weight_kg} kg, koleta={num_packages}"
            )
        finally:
            # Ensure workbook is always closed
            wb.close()

        # Extract invoice name from FILENAME (ne sheet name) da bi se matchovao sa PDF-om
        # Sheet name može imati dodatne prefixe (npr. "24407VP-2026") koji se ne poklapaju sa file name-om
        invoice_name = Path(filepath).stem
        logger.debug(f"Invoice name: '{invoice_name}' (iz file name-a, ne sheet-a: '{sheet_name}')")

        # Try to find and extract weights from matching PDF
        bruto_kg, neto_kg = _find_and_extract_weights_from_pdf(filepath)

        # If PDF not found or weights not extracted, use calculated neto from Excel
        if neto_kg == 0.0:
            neto_kg = total_weight_kg
            logger.info(f"Using calculated neto from Excel: {neto_kg} kg")

        # Return ImportResult with weights from PDF (if available)
        _exp = Party(name="LOREN")
        _imp = Party(name="BLAGIĆ D.O.O.")  # domaća BiH firma
        for item in items:
            item.exporter = _exp
            item.importer = _imp

        return ImportResult(
            items=items,
            bruto_kg=bruto_kg,
            neto_kg=neto_kg,
            invoice_name=invoice_name,
            currency="EUR",
            import_type="loren_excel",
            exporter=_exp,
            importer=_imp,
        )

    except Exception as e:
        logger.error(f"Greška tokom Blagic-Loren parsiranja: {e}", exc_info=True)
        raise ValueError(f"Nije moguće parsirati Blagic-Loren Excel: {e}") from e


def _parse_header(sheet: Worksheet) -> Dict[str, int]:
    """
    Parse header row and map columns.

    Expected columns:
    - RB (kolona A, index 0)
    - Kod (kolona B, index 1)
    - Artikal (kolona C, index 2)
    - JM (kolona D, index 3)
    - Kolicina (kolona E, index 4)
    - Težina po komadu kg (kolona F, index 5)
    - Težina ukupno kg (kolona G, index 6)
    - Tarifni broj (kolona H, index 7)
    - Poreklo (kolona I, index 8)

    Returns:
        Dict mapping standard names to column indices
    """
    header_row = list(sheet[1])

    column_map = {}

    for idx, cell in enumerate(header_row):
        if not cell.value:
            continue

        header_value = str(cell.value).strip().lower()

        # Map columns
        if "rb" in header_value:
            column_map["rb"] = idx
        elif "kod" in header_value or "šifra" in header_value:
            column_map["kod"] = idx
        elif "artikal" in header_value or "naziv" in header_value:
            column_map["artikal"] = idx
        elif "jm" in header_value or "jedinica" in header_value:
            column_map["jm"] = idx
        elif "kolicina" in header_value or "količina" in header_value:
            column_map["kolicina"] = idx
        elif "težina po komadu" in header_value or "tezina po komadu" in header_value:
            column_map["tezina_po_komadu"] = idx
        elif "težina ukupno" in header_value or "tezina ukupno" in header_value:
            column_map["tezina_ukupno"] = idx
        elif "tarifni" in header_value:
            column_map["tarifni_broj"] = idx
        elif "poreklo" in header_value or "porijeklo" in header_value:
            column_map["poreklo"] = idx

    # Validate required columns
    required = ["artikal", "kolicina", "tezina_ukupno"]
    missing = [col for col in required if col not in column_map]

    if missing:
        raise ValueError(f"Nedostaju obavezne kolone u header-u: {missing}")

    return column_map


def _parse_items(
    sheet: Worksheet,
    header_map: Dict[str, int]
) -> Tuple[List[InvoiceLine], float, int]:
    """
    Parse items from sheet.

    Args:
        sheet: Excel worksheet
        header_map: Column mapping

    Returns:
        Tuple of (items, total_weight_kg, num_packages)
    """
    items = []
    total_weight_kg = 0.0
    num_packages = 0

    # Start from row 2 (after header)
    row_idx = 2
    max_row = sheet.max_row

    while row_idx <= max_row:
        row = list(sheet[row_idx])

        # Check if this is a sum row (formula in tezina_ukupno column)
        tezina_col_idx = header_map.get("tezina_ukupno", 6)
        if tezina_col_idx < len(row):
            cell = row[tezina_col_idx]

            # Check if cell has formula (SUM)
            if hasattr(cell, 'value') and cell.value is not None:
                cell_value_str = str(cell.value).upper()

                # If this row contains SUM formula or is empty in artikal column, it's the end
                artikal_col_idx = header_map.get("artikal", 2)
                artikal_value = row[artikal_col_idx].value if artikal_col_idx < len(row) else None

                # Check for sum row
                if "SUM(" in cell_value_str or artikal_value is None or str(artikal_value).strip() == "":
                    # This is the sum row - extract total weight
                    if isinstance(cell.value, (int, float)):
                        total_weight_kg = float(cell.value)

                    # Look for number of packages in the next row
                    if row_idx + 1 <= max_row:
                        next_row = list(sheet[row_idx + 1])
                        artikal_next = next_row[artikal_col_idx].value if artikal_col_idx < len(next_row) else None

                        if artikal_next:
                            # Try to extract number from text like "26 KOLETA"
                            match = re.search(r'(\d+)\s*(KOLET|PRIPOJENA)', str(artikal_next).upper())
                            if match:
                                num_packages = int(match.group(1))

                    break

        # Parse item
        try:
            item = _parse_item_row(row, header_map, row_idx)
            if item:
                items.append(item)
        except Exception as e:
            logger.warning(f"Preskakanje reda {row_idx}: {e}")

        row_idx += 1

    return items, total_weight_kg, num_packages


def _parse_item_row(
    row: List,
    header_map: Dict[str, int],
    row_number: int
) -> Optional[InvoiceLine]:
    """
    Parse one item row.

    Args:
        row: Excel row cells
        header_map: Column mapping
        row_number: Row number (for line_no)

    Returns:
        InvoiceLine or None if row should be skipped
    """
    # Helper to get cell value
    def get_value(field_name: str) -> str:
        col_idx = header_map.get(field_name)
        if col_idx is not None and col_idx < len(row):
            value = row[col_idx].value
            return str(value).strip() if value else ""
        return ""

    # Helper to get float value
    def get_float(field_name: str) -> float:
        value_str = get_value(field_name)
        if not value_str:
            return 0.0

        # Clean non-numeric characters
        cleaned = re.sub(r'[^\d\.,\-]', '', value_str)
        cleaned = cleaned.replace(',', '.')

        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return 0.0

    # Extract fields
    rb = get_value("rb")
    kod = get_value("kod")
    artikal = get_value("artikal")
    jm = get_value("jm")
    kolicina = get_float("kolicina")
    tezina_po_komadu = get_float("tezina_po_komadu")
    tezina_ukupno = get_float("tezina_ukupno")
    tarifni_broj = get_value("tarifni_broj")
    poreklo = get_value("poreklo")

    # Skip empty rows
    if not artikal or len(artikal) < 2:
        return None

    # Normalize country name to ISO code
    zemlja_porijekla = normalize_country_name(poreklo) if poreklo else ""

    # Normalize tarifni_broj: if more than 10 digits, take first 10
    if tarifni_broj and len(tarifni_broj) > 10:
        tarifni_broj = tarifni_broj[:10]

    # Create InvoiceLine
    # Note: Blagic-Loren Excel doesn't have prices, only weights
    # Prices would need to come from PDF if needed
    item = InvoiceLine(
        line_no=row_number - 1,  # Adjust for 0-based indexing
        naziv_robe=artikal,
        product_code=kod,  # IMPORTANT: Populate product code from "Kod" column for matching
        tarifni_broj=tarifni_broj,
        zemlja_porijekla=zemlja_porijekla,
        kolicina=kolicina,
        cijena_jed=0.0,  # Not available in Excel
        iznos=0.0,  # Not available in Excel
        valuta="EUR",
        bruto_kg=tezina_ukupno,  # VAŽNO: "Težina ukupno" u Excel-u je BRUTO težina!
        neto_kg=tezina_po_komadu * kolicina if tezina_po_komadu > 0 else 0.0,
        jm=jm if jm else "kom",
        povlastica=""  # Not available in Blagic-Loren Excel
    )

    return item


# ============================================================
# USAGE EXAMPLE
# ============================================================

if __name__ == "__main__":
    # Test with sample file
    test_file = "/home/radovan/Desktop/PythonProjects/asycuda_pro/najavauvoza/blagic-loren/702VP-2025 BLAGIC.xlsx"

    if os.path.exists(test_file):
        # Test detection
        is_loren = detect_blagic_loren_excel(test_file)
        logger.debug(f"Detection result: {is_loren}")

        if is_loren:
            # Test parsing
            result = parse_blagic_loren_excel(test_file)
            logger.debug(f"\nParsed: {len(result.items)} items")
            logger.debug(f"Total weight: {result.neto_kg} kg")
            logger.debug(f"Invoice name: {result.invoice_name}")
            logger.debug(f"\nFirst 3 items:")
            for item in result.items[:3]:
                logger.debug(f"  - {item.naziv_robe[:50]}")
                logger.debug(f"    Tariff: {item.tarifni_broj}, Country: {item.zemlja_porijekla}, Qty: {item.kolicina}, Weight: {item.neto_kg} kg")
    else:
        logger.debug(f"Test file not found: {test_file}")
