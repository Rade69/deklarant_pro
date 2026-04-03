# importers/pdf/importer.py

"""
PDF Importer – centralna ulazna tačka za uvoz PDF faktura.

Automatski bira strategiju:
- MasterFrigoStrategy → za Master Frigo fakture
- BlagicStrategy      → za Blagić/Loren fakture
- GenericPDFStrategy  → za bilo koju fakturu (pametna automatska detekcija)
- OCRPDFStrategy      → za skenirane PDF-ove
"""

import os
import logging
import PyPDF2
import pdfplumber
from typing import List, Optional, Union

from core.draft.draft import InvoiceLine
from services.error_handler import error_handler
from importers.import_result import ImportResult

# Tabula strategy (optional - requires tabula-py)
try:
    from .tabula_strategy import TabulaPDFStrategy  # type: ignore[import-not-found]
    TABULA_STRATEGY_AVAILABLE = True
except ImportError:
    TABULA_STRATEGY_AVAILABLE = False
    TabulaPDFStrategy = None

from .generic_strategy import GenericPDFStrategy
from .master_frigo_strategy import MasterFrigoStrategy, detect_master_frigo
from .blagic_strategy import BlagicStrategy, detect_blagic

# OCR strategy (optional - requires tesseract)
try:
    from .ocr_strategy import OCRPDFStrategy
    OCR_STRATEGY_AVAILABLE = True
except ImportError:
    OCR_STRATEGY_AVAILABLE = False
    OCRPDFStrategy = None

# Optional OCR support (requires pytesseract)
try:
    from .ocr_utils import is_scanned_pdf
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    def is_scanned_pdf(filepath: str) -> bool:
        """Fallback: assume not scanned if OCR not available"""
        return False

logger = logging.getLogger("asycuda_pro.import.pdf")


class PDFImporter:
    """
    Orkestrator za PDF import.
    Automatski detektuje format i bira odgovarajuću strategiju.
    """

    def __init__(
        self,
        mapping_xlsx_path: Optional[str] = None,
        packing_xlsx_path: Optional[str] = None,
    ):
        """
        Args:
            mapping_xlsx_path: Excel mapping za Master Frigo (opciono)
            packing_xlsx_path: Excel packing lista za Blagić (opciono)
        """
        # Tabula strategy (opciono - samo ako je tabula-py instaliran)
        if TABULA_STRATEGY_AVAILABLE:
            try:
                self.tabula_strategy = TabulaPDFStrategy()  # type: ignore[misc]
                logger.debug("✅ Tabula strategija dostupna")
            except Exception as e:
                logger.debug(f"Tabula strategija nije mogla biti inicijalizovana: {e}")
                self.tabula_strategy = None
        else:
            self.tabula_strategy = None
            logger.debug("Tabula biblioteka nije instalirana (tabula-py)")

        self.generic_strategy = GenericPDFStrategy()  # Novi univerzalni parser (glavni fallback)
        self.master_frigo_strategy = MasterFrigoStrategy(mapping_xlsx_path)
        self.blagic_strategy = BlagicStrategy(packing_xlsx_path)

        # OCR strategy (samo ako su i klasa i biblioteke dostupne)
        self.ocr_strategy: Optional[object] = None
        if OCR_STRATEGY_AVAILABLE and OCR_AVAILABLE:
            try:
                self.ocr_strategy = OCRPDFStrategy(dpi=300, lang="eng+bos+srp")  # type: ignore[misc]
                logger.info("✅ OCR strategija dostupna (Tesseract instaliran)")
            except Exception as e:
                logger.debug(f"OCR strategija nije mogla biti inicijalizovana: {e}")
                self.ocr_strategy = None
            if not OCR_AVAILABLE:
                logger.debug("OCR biblioteke nisu instalirane (pytesseract, pdf2image)")
            else:
                logger.debug("OCR strategija nije dostupna")

    def import_pdf(
        self, filepath: str, progress_callback=None
    ) -> Union[ImportResult, List[InvoiceLine]]:
        """
        Uvezi PDF fakturu i vrati InvoiceLine stavke.

        Args:
            filepath: Putanja do PDF fajla
            progress_callback: Opcioni callback za praćenje napretka

        Returns:
            ImportResult sa metadata (ako strategy podržava) ili Lista InvoiceLine objekata
        """

        logger.info(f"Počinjem PDF import: {filepath}")

        try:
            self._validate_file(filepath)

            # AUTO-DETEKCIJA FORMATA
            pdf_format = self._detect_format(filepath)
            logger.info(f"Detektovan format: {pdf_format}")

            # Odabir strategije
            if pdf_format == "master_frigo":
                strategy = self.master_frigo_strategy
            elif pdf_format == "blagic_attos":
                # Blagic-Attos format - use specialized parser directly (not a strategy)
                from importers.blagic_attos_importer import parse_blagic_attos_with_auto_combine

                if progress_callback:
                    progress_callback(50)

                result = parse_blagic_attos_with_auto_combine(filepath)

                if progress_callback:
                    progress_callback(100)

                # Handle ImportResult
                if isinstance(result, ImportResult):
                    items = result.items
                    logger.info(
                        f"PDF import završen. Stavki: {len(items)}, "
                        f"bruto: {result.bruto_kg} kg, neto: {result.neto_kg} kg"
                    )
                else:
                    items = result
                    logger.info(f"PDF import završen. Stavki: {len(items)}")

                if not items:
                    logger.warning("PDF import završen, ali nema parsiranih stavki")

                return result

            elif pdf_format == "blagic":
                strategy = self.blagic_strategy
            elif pdf_format == "scanned":
                if self.ocr_strategy:
                    logger.info("✅ Detektovan skenirani PDF - koristim OCR strategiju")
                    strategy = self.ocr_strategy
                else:
                    logger.warning(
                        "⚠️ Detektovan skenirani PDF, ali OCR nije instaliran!\n"
                        "   Instaliraj: pip install pytesseract pdf2image\n"
                        "   + sudo apt-get install tesseract-ocr tesseract-ocr-eng tesseract-ocr-bos"
                    )
                    logger.info("Pokušavam sa Generic strategijom kao fallback...")
                    strategy = self.generic_strategy
            else:  # generic
                logger.info("🤖 Koristim Generic PDF Strategy - automatska detekcija")
                strategy = self.generic_strategy

            # Extract items
            if progress_callback:
                progress_callback(50)  # 50%

            result = strategy.extract(filepath)

            if progress_callback:
                progress_callback(100)  # 100%

            # Handle both ImportResult and List[InvoiceLine] for backward compatibility
            if isinstance(result, ImportResult):
                items = result.items
                logger.info(
                    f"PDF import završen. Stavki: {len(items)}, "
                    f"bruto: {result.bruto_kg} kg, neto: {result.neto_kg} kg"
                )
            else:
                items = result
                logger.info(f"PDF import završen. Stavki: {len(items)}")

            # FALLBACK: Ako specijalizovani parser vrati 0 stavki, pokušaj sa Generic strategijom
            if not items and strategy != self.generic_strategy:
                logger.warning("⚠️  Specijalizovani parser nije pronašao stavke")
                logger.info("🔄 Pokušavam sa Generic PDF Strategy kao fallback...")

                try:
                    if progress_callback:
                        progress_callback(50)

                    result = self.generic_strategy.extract(filepath)

                    if progress_callback:
                        progress_callback(100)

                    # Handle result
                    if isinstance(result, ImportResult):
                        items = result.items
                        logger.info(
                            f"✅ Generic parser našao {len(items)} stavki! "
                            f"(bruto: {result.bruto_kg} kg, neto: {result.neto_kg} kg)"
                        )
                    else:
                        items = result
                        logger.info(f"✅ Generic parser našao {len(items)} stavki!")

                except Exception as e:
                    logger.error(f"Generic fallback parser takođe nije uspio: {e}")

            # FALLBACK: Ako generic parser vrati 0 stavki, pokušaj OCR (ako je skenirani PDF)
            if not items and self.ocr_strategy and OCR_AVAILABLE:
                logger.info("🔍 Nema stavki — provjeravam da li je PDF skeniran...")
                try:
                    if is_scanned_pdf(filepath):
                        logger.info("📷 PDF je skeniran — pokušavam OCR...")
                        if progress_callback:
                            progress_callback(50)
                        result = self.ocr_strategy.extract(filepath)
                        if progress_callback:
                            progress_callback(100)
                        if isinstance(result, ImportResult):
                            items = result.items
                            logger.info(f"✅ OCR fallback: {len(items)} stavki")
                        else:
                            items = result
                except Exception as e_ocr:
                    logger.warning(f"OCR fallback nije uspio: {e_ocr}")

            if not items:
                logger.warning("PDF import završen, ali nema parsiranih stavki")

            return result

        except Exception as e:
            logger.error("Greška tokom PDF importa", exc_info=True)

            error_response = error_handler.handle_import_error(
                e,
                context={
                    "filename": filepath,
                    "file_type": "PDF",
                },
            )

            raise ImportError(error_response.message) from e

    def _detect_format(self, filepath: str) -> str:
        """
        Detektuje format PDF-a (Master Frigo, Blagić Attos, Blagić Loren, generic, ili scanned).

        Returns:
            "master_frigo", "blagic_attos", "blagic", "scanned", ili "generic"
        """
        try:
            # Check for specialized formats first
            # Blagic-Attos detection (file-level check)
            from importers.blagic_attos_importer import detect_blagic_attos_pdf

            if detect_blagic_attos_pdf(filepath):
                return "blagic_attos"

            # Ekstraktuj tekst iz prvih 2-3 stranica
            with pdfplumber.open(filepath) as pdf:
                text = ""
                for page in pdf.pages[:3]:
                    page_text = page.extract_text() or ""
                    text += page_text[:2000]  # Ograniči na 2000 karaktera po stranici

                # Master Frigo detection
                if detect_master_frigo(text):
                    return "master_frigo"

                # Blagic-Loren detection (existing)
                if detect_blagic(text):
                    return "blagic"

                # Check if scanned
                if is_scanned_pdf(filepath):
                    return "scanned"

                # Default to generic
                return "generic"

        except Exception as e:
            logger.warning(f"Greška tokom detekcije formata: {e}")
            return "generic"

    @staticmethod
    def _validate_file(filepath: str):
        """
        Osnovna validacija PDF fajla.
        """

        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Fajl ne postoji: {filepath}")

        if not filepath.lower().endswith(".pdf"):
            raise ValueError("Dokument nije PDF")

        if not os.access(filepath, os.R_OK):
            raise PermissionError("PDF fajl nije čitljiv")

        # Provjera validnosti PDF-a
        try:
            with open(filepath, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                if len(reader.pages) == 0:
                    raise ValueError("PDF nema nijednu stranicu")
        except Exception as e:
            raise ValueError(f"Nevažeći PDF dokument: {e}")
