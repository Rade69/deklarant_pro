# importers/pdf/blagic_strategy.py

"""
Blagić/Loren PDF parsing strategija.
Specijalizovan parser za Blagić/Loren fakture.
"""

from typing import List, Optional, Dict
import logging
from pathlib import Path

from core.draft.draft import InvoiceLine
from .base import PDFParseStrategy

# Import existing Blagić parser funkcija
from importers.blagic_importer import (
    parse_blagic_invoice_pdf,
    parse_blagic_packing_xlsx,
    merge_invoice_with_packing,
    convert_to_invoice_lines,
)

logger = logging.getLogger("asycuda_pro.import.pdf.blagic")


class BlagicStrategy(PDFParseStrategy):
    """
    Strategija za parsiranje Blagić/Loren PDF faktura.
    Koristi postojeći specialized parser.

    Može raditi sa samo PDF-om ili sa PDF + Excel packing listom.
    """

    def __init__(self, packing_xlsx_path: Optional[str] = None):
        """
        Args:
            packing_xlsx_path: Opcioni Excel fajl sa packing listom
        """
        self.packing_xlsx_path = packing_xlsx_path
        self.packing: Dict[str, Dict] = {}

        if packing_xlsx_path:
            try:
                self.packing = parse_blagic_packing_xlsx(packing_xlsx_path)
                logger.info(
                    f"Loaded packing list from {packing_xlsx_path}: {len(self.packing)} items"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to load packing list from {packing_xlsx_path}: {e}"
                )

    def extract(self, filepath: str) -> List[InvoiceLine]:
        """
        Ekstraktuje stavke fakture iz Blagić PDF-a.

        Args:
            filepath: Putanja do PDF fajla

        Returns:
            Lista InvoiceLine objekata
        """
        logger.info(f"Blagić parsing započet: {filepath}")

        try:
            # Parse PDF
            header, invoice_items = parse_blagic_invoice_pdf(filepath)

            # Merge with packing list if available
            if self.packing:
                merged = merge_invoice_with_packing(invoice_items, self.packing)
            else:
                logger.info("Packing list not provided, using PDF data only")
                merged = invoice_items

            # Convert to InvoiceLine
            currency = header.get("currency", "EUR")
            invoice_lines = convert_to_invoice_lines(merged, currency=currency)

            logger.info(f"Blagić parsing završen: {len(invoice_lines)} stavki")

            # Check for missing tariffs
            missing_tariffs = [
                it.code
                for it in merged
                if not it.tariff
            ]
            if missing_tariffs:
                logger.warning(
                    f"Missing tariff codes for: {', '.join(missing_tariffs)}"
                )

            return invoice_lines

        except Exception as e:
            logger.error(f"Greška tokom Blagić parsiranja: {e}", exc_info=True)
            raise


def detect_blagic(text_sample: str) -> bool:
    """
    Detekcija Blagić/Loren formata na osnovu uzorka teksta.

    Args:
        text_sample: Uzorak teksta iz PDF-a (obično prve 2-3 stranice)

    Returns:
        True ako je detektovan Blagić format
    """
    text_upper = text_sample.upper()

    # Ključne riječi koje karakterišu Blagić/Loren fakture
    blagic_indicators = [
        "BLAGIC",
        "BLAGIĆ",
        "LOREN",
        "LOREN D.O.O",
    ]

    for indicator in blagic_indicators:
        if indicator in text_upper:
            logger.info(f"Blagić format detektovan: pronađen '{indicator}'")
            return True

    return False
