# importers/pdf/ocr_strategy.py

"""
OCR PDF Strategy - za skenirane PDF fakture bez tekstualnog sloja.

Workflow:
1. Konvertuje PDF u slike (pdf2image)
2. Primenjuje OCR na svakoj slici (Tesseract) sa pre-processingom (grayscale, kontrast, threshold)
3. Parsira tekst kroz 3 strategije (strukturirani → tabelarni → generički)
4. Vraća ImportResult sa stavkama, težinama i metapodacima
"""

import logging
import platform
from typing import List

from core.draft.draft import InvoiceLine
from importers.import_result import ImportResult

from .base import PDFParseStrategy

# OCR libraries (optional - graceful degradation)
try:
    from .ocr_utils import ocr_pdf_to_text
    from .ocr_invoice_parser import parse_ocr_result
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

logger = logging.getLogger("deklarant_pro.import.pdf.ocr")


class OCRPDFStrategy(PDFParseStrategy):
    """
    Strategija za parsiranje skeniranih PDF-ova pomoću OCR-a.

    Zahtijeva instaliran Tesseract OCR engine.
    Koristi ocr_invoice_parser koji probava 3 strategije: strukturirani → tabelarni → generički.
    """

    def __init__(self, dpi: int = 300, lang: str = "eng+bos+srp"):
        """
        Args:
            dpi: Rezolucija za rasterizaciju PDF-a (300 je optimalno)
            lang: Tesseract jezici (nije direktno korišten — ocr_utils koristi eng+bos)
        """
        self.dpi = dpi
        self.lang = lang
        self.ocr_available = OCR_AVAILABLE

    def extract(self, filepath: str) -> ImportResult:
        """
        Ekstraktuje stavke iz skeniranog PDF-a pomoću OCR-a.

        Args:
            filepath: Putanja do PDF fajla

        Returns:
            ImportResult sa stavkama, težinama i metapodacima
        """
        if not self.ocr_available:
            if platform.system() == "Windows":
                uputstvo = (
                    "1. Preuzmi i instaliraj Tesseract: https://github.com/UB-Mannheim/tesseract/wiki\n"
                    "2. Preuzmi i instaliraj Poppler: https://github.com/oschwartz10612/poppler-windows/releases\n"
                    "3. pip install pytesseract pdf2image"
                )
            else:
                uputstvo = (
                    "sudo apt-get install tesseract-ocr tesseract-ocr-eng tesseract-ocr-bos poppler-utils\n"
                    "pip install pytesseract pdf2image"
                )
            raise ImportError(f"OCR biblioteke nisu instalirane!\n{uputstvo}")

        logger.info(f"OCR parsing započet: {filepath} (DPI: {self.dpi})")

        try:
            pages_text = ocr_pdf_to_text(filepath, dpi=self.dpi)
            result = parse_ocr_result(pages_text, pdf_path=filepath)
            logger.info(f"OCR parsing završen: {len(result.items)} stavki")
            return result

        except Exception as e:
            logger.error(f"OCR parsing failed: {e}", exc_info=True)
            raise

