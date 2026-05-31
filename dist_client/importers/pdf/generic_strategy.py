"""
Generic PDF Strategy - Pametna automatska detekcija bilo koje fakture

Koristi pdfplumber za automatsku detekciju tabela i heuristike za identifikaciju kolona.
Ovo je univerzalni fallback parser koji može raditi sa bilo kojom fakturom.
"""

import logging
from typing import List, Union

from core.draft.draft import InvoiceLine
from importers.import_result import ImportResult
from importers.generic_pdf_importer import parse_generic_pdf

from .base import PDFParseStrategy

logger = logging.getLogger("deklarant_pro.import.pdf.generic")


class GenericPDFStrategy(PDFParseStrategy):
    """
    Univerzalna PDF parsing strategija.

    Automatski detektuje:
    - Tabele u PDF-u (pdfplumber automatic table extraction)
    - Kolone (code, naziv, količina, cijena, iznos...)
    - Metadata (broj fakture, bruto/neto težina)

    Radi sa bilo kojom fakturom koja ima tabelarnu strukturu.
    """

    def extract(self, filepath: str) -> Union[List[InvoiceLine], ImportResult]:
        """
        Ekstraktuje stavke iz bilo koje PDF fakture automatski.

        Args:
            filepath: Putanja do PDF fajla

        Returns:
            ImportResult sa parsiranim stavkama i metadata
        """
        logger.info(f"🤖 Koristim Generic PDF Strategy za: {filepath}")

        try:
            result = parse_generic_pdf(filepath)

            if not result.items:
                logger.warning("⚠️  Generic parser nije pronašao stavke u PDF-u")
            else:
                logger.info(f"✅ Generic parser izvukao {len(result.items)} stavki")
                logger.info(f"   Bruto: {result.bruto_kg} kg, Neto: {result.neto_kg} kg")

            return result

        except Exception as e:
            logger.error(f"❌ Generic parser failed: {e}", exc_info=True)
            # Return empty result instead of crashing
            return ImportResult(
                items=[],
                bruto_kg=0.0,
                neto_kg=0.0,
                invoice_name="",
                currency="EUR"
            )
