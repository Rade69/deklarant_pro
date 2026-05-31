# importers/excel_importer.py

"""
Deklarant Pro - Excel Importer
Parsira .xlsx i .xls fakture koristeći openpyxl
"""

import os
import logging
from typing import List, Optional, Callable, Dict, Any, Union
from dataclasses import dataclass
import re

# Excel libraries
import openpyxl
from openpyxl.utils import get_column_letter

# Project imports
from core.draft.draft import InvoiceLine
from importers.import_result import ImportResult
from services.error_handler import error_handler
# from config.settings import settings  # uklonjeno - settings objekat ne postoji
from utils.country_normalizer import normalize_country_name

logger = logging.getLogger("deklarant_pro.import.excel")


@dataclass
class ExcelImportConfig:
    """Configuration za Excel import"""

    sheet_name: Optional[str] = None    # None = auto-detect
    header_row: int = 0                 # Header u redu 0
    start_row: int = 1                  # Data počinje od reda 1
    end_row: Optional[int] = None       # None = do kraja

    # Auto-detection
    auto_detect_header: bool = True     # Auto-find header row
    min_data_rows: int = 1              # Minimum redova da se smatra validnim


class ExcelImporter:
    """
    Excel Importer sa openpyxl.

    Workflow:
    1. Open workbook
    2. Select sheet (auto-detect ili specified)
    3. Find header row (auto ili specified)
    4. Parse rows → InvoiceLine
    5. Return normalized items
    """

    # Column mappings (isti kao PDF)
    COLUMN_MAP = {
        "naziv_robe": [
            "naziv", "naziv robe", "opis", "description",
            "item", "artikal", "roba", "proizvod"
        ],
        "tarifni_broj": [
            "tarifni broj", "tarifni", "tariff", "hs code",
            "tarifa", "cn", "cn code", "commodity code"
        ],
        "kolicina": [
            "količina", "kolicina", "qty", "quantity", "kol", "kol.", "kom"
        ],
        "cijena_jed": [
            "cijena", "price", "cijena jed", "unit price", "cij", "cjena"
        ],
        "iznos": [
            "iznos", "amount", "ukupno", "total", "vrijednost", "value"
        ],
        "bruto_kg": [
            "bruto", "brutto", "gross", "bruto masa", "bruto kg", "gross weight"
        ],
        "neto_kg": [
            "neto", "net", "net weight", "neto masa", "neto kg"
        ],
        "zemlja_porijekla": [
            "zemlja", "country", "origin", "porijeklo", "country of origin"
        ],
        "valuta": [
            "valuta", "currency", "curr", "val"
        ],
    }

    def __init__(self, config: Optional[ExcelImportConfig] = None):
        self.config = config or ExcelImportConfig()
        self.logger = logger

    def import_excel(
        self,
        filepath: str,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> Union[ImportResult, List[InvoiceLine]]:
        """
        Import Excel fakture.

        Args:
            filepath: Path to Excel file (.xlsx ili .xls)
            progress_callback: Optional progress callback

        Returns:
            ImportResult (for specialized formats) or List[InvoiceLine] (for generic)

        Raises:
            ImportError: Ako import fail-uje
        """

        self.logger.info(f"Excel import started: {filepath}")

        try:
            # ================================================
            # STEP 0: AUTO-DETECT SPECIALIZED FORMATS
            # ================================================

            # Try IMAMOGLU Packing List format (.xlsx)
            from importers.imamoglu_excel_importer import (
                detect_imamoglu_packing_list, parse_imamoglu_packing_list,
                detect_imamoglu_mal_tanimlari, parse_imamoglu_mal_tanimlari
            )

            if detect_imamoglu_packing_list(filepath):
                self.logger.info("Detected IMAMOGLU Packing List format")
                if progress_callback:
                    progress_callback(50)
                result = parse_imamoglu_packing_list(filepath)
                if progress_callback:
                    progress_callback(100)
                return result

            if detect_imamoglu_mal_tanimlari(filepath):
                self.logger.info("Detected IMAMOGLU Mal Tanımları format")
                if progress_callback:
                    progress_callback(50)
                result = parse_imamoglu_mal_tanimlari(filepath)
                if progress_callback:
                    progress_callback(100)
                return result

            # Try Blagic-Loren format detection
            from importers.blagic_loren_importer import detect_blagic_loren_excel, parse_blagic_loren_excel

            if detect_blagic_loren_excel(filepath):
                self.logger.info("Detected Blagic-Loren format - using specialized parser")
                if progress_callback:
                    progress_callback(50)

                result = parse_blagic_loren_excel(filepath)

                if progress_callback:
                    progress_callback(100)

                return result

            # Try Leburic/Pekabesko format detection
            from importers.leburic_pekabesko_importer import (
                detect_leburic_pekabesko_excel, parse_leburic_pekabesko_excel
            )

            if detect_leburic_pekabesko_excel(filepath):
                self.logger.info("Detected Leburic/Pekabesko format - using specialized parser")
                if progress_callback:
                    progress_callback(50)
                result = parse_leburic_pekabesko_excel(filepath)
                if progress_callback:
                    progress_callback(100)
                return result

            # Try ŠUMAPROM format detection
            from importers.sumaprom_excel_parser import detect_sumaprom_excel, parse_sumaprom_excel

            if detect_sumaprom_excel(filepath):
                self.logger.info("Detected ŠUMAPROM format - using specialized parser")
                if progress_callback:
                    progress_callback(50)

                result = parse_sumaprom_excel(filepath)

                if progress_callback:
                    progress_callback(100)

                return result

            # ================================================
            # STEP 1: VALIDATE FILE (Generic format)
            # ================================================

            self._validate_file(filepath)

            if progress_callback:
                progress_callback(10)

            # ================================================
            # STEP 2: OPEN WORKBOOK
            # ================================================

            self.logger.info("Opening workbook...")
            
            # Use xlrd for .xls files, openpyxl for .xlsx
            ext = os.path.splitext(filepath)[1].lower()
            if ext == '.xls':
                import xlrd
                wb = xlrd.open_workbook(filepath)
                self.logger.debug("Opened .xls file with xlrd")
            else:
                wb = openpyxl.load_workbook(filepath, data_only=True)
                self.logger.debug(f"Opened .xlsx file with openpyxl")

            try:
                if progress_callback:
                    progress_callback(20)

                # ================================================
                # STEP 3: SELECT SHEET
                # ================================================

                sheet = self._select_sheet(wb)
                self.logger.info(f"Using sheet: {sheet.title}")

                if progress_callback:
                    progress_callback(30)

                # ================================================
                # STEP 4: FIND HEADER ROW
                # ================================================

                header_row = self._find_header_row(sheet)
                self.logger.info(f"Header row: {header_row}")

                if progress_callback:
                    progress_callback(40)

                # ================================================
                # STEP 5: PARSE ROWS
                # ================================================

                items = self._parse_sheet(sheet, header_row, progress_callback)

                self.logger.info(f"Parsed {len(items)} items")
            finally:
                # Ensure workbook is always closed (only for openpyxl)
                if ext == '.xlsx':
                    wb.close()

            if progress_callback:
                progress_callback(100)

            return items

        except Exception as e:
            self.logger.error(f"Excel import failed: {e}", exc_info=True)

            error_response = error_handler.handle_import_error(
                e,
                context={
                    "filename": filepath,
                    "file_type": "Excel"
                }
            )

            raise ImportError(error_response.message) from e

    def _validate_file(self, filepath: str):
        """Validate Excel file"""

        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Fajl nije pronađen: {filepath}")

        ext = os.path.splitext(filepath)[1].lower()
        if ext not in ['.xlsx', '.xls']:
            raise ValueError(f"Fajl nije Excel: {filepath}")

        if not os.access(filepath, os.R_OK):
            raise PermissionError(f"Ne mogu čitati fajl: {filepath}")

    def _select_sheet(self, wb):
        """
        Select worksheet to import.

        Logic:
        - If config.sheet_name specified → use that
        - Else → use first sheet with data
        """

        if self.config.sheet_name:
            if self.config.sheet_name in wb.sheetnames:
                return wb[self.config.sheet_name]
            else:
                raise ValueError(
                    f"Sheet '{self.config.sheet_name}' not found. "
                    f"Available: {wb.sheetnames}"
                )

        # Auto-select first non-empty sheet
        for sheet in wb.worksheets:
            if sheet.max_row > 1:  # Has at least 2 rows
                return sheet

        # Fallback to first sheet
        return wb.worksheets[0]

    def _find_header_row(self, sheet) -> int:
        """
        Find header row (sa column names).

        Logic:
        - If auto_detect_header:
            - Search first 5 rows
            - Row with most "known column names" = header
        - Else:
            - Use config.header_row
        """

        if not self.config.auto_detect_header:
            return self.config.header_row

        # Search first 5 rows
        max_matches = 0
        best_row = 0

        for row_idx in range(min(5, sheet.max_row)):
            row_values = [
                str(cell.value).lower().strip()
                for cell in sheet[row_idx + 1]
                if cell.value
            ]

            # Count how many match known columns
            matches = 0
            for cell_value in row_values:
                for possible_names in self.COLUMN_MAP.values():
                    if any(name in cell_value for name in possible_names):
                        matches += 1
                        break

            if matches > max_matches:
                max_matches = matches
                best_row = row_idx

        return best_row

    def _parse_sheet(
        self,
        sheet,
        header_row: int,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> List[InvoiceLine]:
        """Parse sheet rows → InvoiceLines"""

        items = []

        # Get header columns
        header_cells = list(sheet[header_row + 1])
        column_map = self._identify_columns(header_cells)

        self.logger.info(f"Column mapping: {column_map}")

        # Parse data rows
        start_row = header_row + 2  # After header
        end_row = sheet.max_row + 1

        total_rows = end_row - start_row

        for row_idx in range(start_row, end_row):
            row = list(sheet[row_idx])

            try:
                item = self._parse_row(row, column_map, row_idx)
                if item:
                    items.append(item)

            except Exception as e:
                self.logger.warning(f"Preskakanje reda {row_idx}: {e}")
                continue

            # Progress
            if progress_callback and total_rows > 0:
                progress = 40 + int((row_idx - start_row + 1) / total_rows * 50)
                progress_callback(progress)

        return items

    def _identify_columns(self, header_cells) -> Dict[str, int]:
        """
        Identify columns.

        Returns:
            Dict[standard_name, column_index]
        """

        column_map = {}

        for col_idx, cell in enumerate(header_cells):
            cell_value = str(cell.value).lower().strip() if cell.value else ""

            if not cell_value:
                continue

            # Match against known columns
            for standard_name, possible_names in self.COLUMN_MAP.items():
                for possible in possible_names:
                    if possible in cell_value:
                        column_map[standard_name] = col_idx
                        break

        return column_map

    def _parse_row(
        self,
        row,
        column_map: Dict[str, int],
        row_index: int
    ) -> Optional[InvoiceLine]:
        """Parse jedan red → InvoiceLine"""

        # Helper - get value by standard name
        def get_value(field_name: str) -> str:
            col_idx = column_map.get(field_name)
            if col_idx is not None and col_idx < len(row):
                cell = row[col_idx]
                value = cell.value
                return str(value).strip() if value else ""
            return ""

        # Helper - parse float
        def get_float(field_name: str) -> float:
            value_str = get_value(field_name)
            if not value_str:
                return 0.0

            # Clean non-numeric
            cleaned = re.sub(r'[^\d\.,\-]', '', value_str)
            cleaned = cleaned.replace(',', '.')

            try:
                return float(cleaned)
            except (ValueError, TypeError):
                return 0.0

        # Extract fields
        naziv = get_value("naziv_robe")
        tarifni = get_value("tarifni_broj")
        kolicina = get_float("kolicina")
        cijena = get_float("cijena_jed")
        iznos = get_float("iznos")
        bruto = get_float("bruto_kg")
        neto = get_float("neto_kg")
        zemlja = get_value("zemlja_porijekla")
        valuta = get_value("valuta") or "EUR"

        # Skip empty rows
        if not naziv or len(naziv) < 2:
            return None

        # Create InvoiceLine
        item = InvoiceLine(
            line_no=row_index,
            naziv_robe=naziv,
            tarifni_broj=tarifni,
            zemlja_porijekla=normalize_country_name(zemlja),  # Normalize to ISO code
            kolicina=kolicina,
            cijena_jed=cijena,
            iznos=iznos if iznos > 0 else (cijena * kolicina),
            valuta=valuta,
            bruto_kg=bruto,
            neto_kg=neto,
        )

        return item


# ============================================================
# USAGE EXAMPLE
# ============================================================

if __name__ == "__main__":
    importer = ExcelImporter()

    def progress_callback(percentage: int):
        logger.debug(f"Progress: {percentage}%")

    try:
        items = importer.import_excel(
            "tests/data/faktura_test.xlsx",
            progress_callback=progress_callback
        )

        logger.debug(f"\nImported {len(items)} items:")
        for item in items[:5]:
            logger.debug(f"  {item.naziv_robe} - {item.tarifni_broj}")

    except Exception as e:
        logger.debug(f"Import failed: {e}")
