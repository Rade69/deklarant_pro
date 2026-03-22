# importers/pdf/master_frigo_strategy.py

"""
Master Frigo PDF parsing strategija.
Specijalizovan parser za Master Frigo fakture.
"""

from typing import List, Optional, Dict
import logging

from core.draft.draft import InvoiceLine
from .base import PDFParseStrategy
from importers.import_result import ImportResult

# Import existing Master Frigo parser funkcija
from importers.master_frigo_importer import (
    parse_master_frigo_pdf,
    convert_to_invoice_lines,
    _read_mapping_xlsx,
)

logger = logging.getLogger("asycuda_pro.import.pdf.master_frigo")


class MasterFrigoStrategy(PDFParseStrategy):
    """
    Strategija za parsiranje Master Frigo PDF faktura.
    Koristi postojeći specialized parser.
    """

    def __init__(self, mapping_xlsx_path: Optional[str] = None):
        """
        Args:
            mapping_xlsx_path: Opcioni Excel fajl za mapping šifra → tarifa/porijeklo
        """
        self.mapping_xlsx_path = mapping_xlsx_path
        self.mapping: Dict[str, Dict[str, str]] = {}

        if mapping_xlsx_path:
            try:
                self.mapping = _read_mapping_xlsx(mapping_xlsx_path)
                logger.info(f"Loaded mapping from {mapping_xlsx_path}: {len(self.mapping)} codes")
            except Exception as e:
                logger.warning(f"Failed to load mapping from {mapping_xlsx_path}: {e}")

    def extract(self, filepath: str) -> ImportResult:
        """
        Ekstraktuje stavke fakture iz Master Frigo PDF-a.

        Args:
            filepath: Putanja do PDF fajla

        Returns:
            ImportResult sa stavkama i metadata (bruto/neto težina)
        """
        logger.info(f"Master Frigo parsing započet: {filepath}")

        try:
            # Parse PDF using specialized parser
            header, imported_items = parse_master_frigo_pdf(
                filepath, mapping=self.mapping
            )

            # Convert to InvoiceLine
            # Force EUR as primary currency for Master Frigo invoices
            currency = "EUR"
            invoice_lines = convert_to_invoice_lines(imported_items, currency=currency)

            # Extract weights from header
            bruto_kg = header.get("gross_kg", 0.0)
            neto_kg = header.get("net_kg", 0.0)
            invoice_name = header.get("invoice_number", "")

            logger.info(
                f"Master Frigo parsing završen: {len(invoice_lines)} stavki, "
                f"bruto={bruto_kg} kg, neto={neto_kg} kg"
            )

            # Return ImportResult with metadata
            return ImportResult(
                items=invoice_lines,
                bruto_kg=bruto_kg,
                neto_kg=neto_kg,
                invoice_name=invoice_name,
                currency=currency
            )

        except Exception as e:
            logger.error(f"Greška tokom Master Frigo parsiranja: {e}", exc_info=True)
            raise


def detect_master_frigo(text_sample: str) -> bool:
    """
    Detekcija Master Frigo formata na osnovu uzorka teksta.

    Args:
        text_sample: Uzorak teksta iz PDF-a (obično prve 2-3 stranice)

    Returns:
        True ako je detektovan Master Frigo format
    """
    text_upper = text_sample.upper()

    # Ključne riječi koje karakterišu Master Frigo fakture
    master_frigo_indicators = [
        "MASTER FRIGO",
        "VELEPRODAJA RASHLADNE OPREME",
        "MASTER-FRIGO",
    ]

    for indicator in master_frigo_indicators:
        if indicator in text_upper:
            logger.info(f"Master Frigo format detektovan: pronađen '{indicator}'")
            return True

    return False
