# importers/pdf/ocr_strategy.py

"""
OCR PDF Strategy - za skenirane PDF fakture bez tekstualnog sloja.

Workflow:
1. Konvertuje PDF u slike (pdf2image)
2. Primenjuje OCR na svakoj slici (Tesseract)
3. Kombinuje tekst sa svih stranica
4. Parsira tekst kao da je ekstraktorvao iz običnog PDF-a
5. Koristi tabula-style parsing sa regex pattern matching
"""

import logging
import re
from typing import List, Dict, Any

from core.draft.draft import InvoiceLine
# from config.settings import settings  # uklonjeno - settings objekat ne postoji
from utils.country_normalizer import normalize_country_name

from .base import PDFParseStrategy
from .utils import normalize_number

# OCR libraries (optional - graceful degradation)
try:
    from .ocr_utils import ocr_pdf_to_text
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

logger = logging.getLogger("asycuda_pro.import.pdf.ocr")


class OCRPDFStrategy(PDFParseStrategy):
    """
    Strategija za parsiranje skeniranih PDF-ova pomoću OCR-a.

    Zahtijeva instaliran Tesseract OCR engine.
    """

    # Regex patterns za pronalaženje podataka u OCR tekstu
    PATTERNS = {
        # Tarifni broj (8-10 cifara)
        'tarifni_broj': re.compile(r'\b(\d{8,10})\b'),

        # Količina (broj sa decimalama + jedinica)
        'kolicina': re.compile(r'(\d+[.,]\d+|\d+)\s*(kom|kg|l|m|kom\.)', re.IGNORECASE),

        # Cijena (broj sa decimalama + valuta)
        'cijena': re.compile(r'(\d+[.,]\d+|\d+)\s*(EUR|USD|BAM|RSD)', re.IGNORECASE),

        # Iznos/Total
        'iznos': re.compile(r'(?:ukupno|total|iznos)[:=\s]+(\d+[.,]\d+|\d+)', re.IGNORECASE),

        # Bruto/Neto težina
        'bruto': re.compile(r'(?:bruto|gross)[:=\s]+(\d+[.,]\d+|\d+)\s*kg', re.IGNORECASE),
        'neto': re.compile(r'(?:neto|net)[:=\s]+(\d+[.,]\d+|\d+)\s*kg', re.IGNORECASE),

        # Zemlja porijekla
        'zemlja': re.compile(r'(?:origin|porijeklo|zemlja)[:=\s]+([A-Z]{2,})', re.IGNORECASE),
    }

    def __init__(self, dpi: int = 300, lang: str = "eng+bos+srp"):
        """
        Args:
            dpi: Rezolucija za rasterizaciju PDF-a (300 je optimalno)
            lang: Tesseract jezici (format: "eng+bos+srp")
        """
        # Ne bacaj grešku u __init__ - dopusti da se klasa kreira
        # Greška će biti bacena samo ako se extract() pozove bez instaliranih biblioteka
        self.dpi = dpi
        self.lang = lang
        self.ocr_available = OCR_AVAILABLE

    def extract(self, filepath: str) -> List[InvoiceLine]:
        """
        Ekstraktuje stavke iz skeniranog PDF-a pomoću OCR-a.

        Args:
            filepath: Putanja do PDF fajla

        Returns:
            Lista InvoiceLine objekata
        """
        # Provjeri da li su OCR biblioteke dostupne
        if not self.ocr_available:
            raise ImportError(
                "OCR biblioteke nisu instalirane! Instaliraj: "
                "pip install pytesseract pdf2image poppler-utils"
            )

        logger.info(f"OCR parsing započet: {filepath} (DPI: {self.dpi}, Lang: {self.lang})")

        try:
            # STEP 1: OCR ekstrakcija teksta
            pages_text = ocr_pdf_to_text(filepath, dpi=self.dpi)
            logger.info(f"OCR završen: {len(pages_text)} stranica")

            # STEP 2: Kombinuj tekst sa svih stranica
            full_text = "\n\n=== NOVA STRANICA ===\n\n".join(pages_text)

            # STEP 3: Parse tekst
            items = self._parse_ocr_text(full_text)

            logger.info(f"OCR parsing završen: {len(items)} stavki")
            return items

        except Exception as e:
            logger.error(f"OCR parsing failed: {e}", exc_info=True)
            raise

    def _parse_ocr_text(self, text: str) -> List[InvoiceLine]:
        """
        Parsira OCR tekst u InvoiceLine objekte.

        OCR tekst je često "prljav" (greške prepoznavanja), pa koristimo:
        1. Pattern matching sa regex
        2. Heuristike za grupiranje podataka u stavke
        3. Fuzzy matching za nazivé proizvoda
        """
        items: List[InvoiceLine] = []

        # Split u linije
        lines = text.split('\n')

        # Prolazi kroz linije i traži pattern-e za stavke
        current_item = None
        current_item_data = {}

        for line in lines:
            line = line.strip()

            if not line or len(line) < 3:
                continue

            # Detektuj novi item (linija sa tarifnim brojem je obično početak)
            tariff_match = self.PATTERNS['tarifni_broj'].search(line)
            if tariff_match:
                # Sačuvaj prethodni item ako postoji
                if current_item_data:
                    item = self._create_item_from_data(current_item_data, len(items) + 1)
                    if item:
                        items.append(item)

                # Započni novi item
                current_item_data = {
                    'naziv_robe': '',
                    'tarifni_broj': tariff_match.group(1),
                    'raw_lines': [line]
                }
            elif current_item_data:
                # Dodaj liniju postojećem itemu
                current_item_data['raw_lines'].append(line)

                # Ekstraktuj podatke iz linije
                self._extract_data_from_line(line, current_item_data)

        # Dodaj poslednji item
        if current_item_data:
            item = self._create_item_from_data(current_item_data, len(items) + 1)
            if item:
                items.append(item)

        # Ako nema stavki iz pattern matching-a, pokušaj sa line-by-line heuristics
        if not items:
            logger.warning("Pattern matching nije pronašao stavke - pokušavam heuristički pristup")
            items = self._parse_with_heuristics(text)

        return items

    def _extract_data_from_line(self, line: str, item_data: Dict[str, Any]):
        """Ekstraktuje podatke iz jedne linije i dodaje ih u item_data."""

        # Količina
        qty_match = self.PATTERNS['kolicina'].search(line)
        if qty_match and 'kolicina' not in item_data:
            item_data['kolicina'] = normalize_number(qty_match.group(1))
            item_data['jm'] = qty_match.group(2)

        # Cijena
        price_match = self.PATTERNS['cijena'].search(line)
        if price_match and 'cijena_jed' not in item_data:
            item_data['cijena_jed'] = normalize_number(price_match.group(1))
            item_data['valuta'] = price_match.group(2).upper()

        # Iznos
        amount_match = self.PATTERNS['iznos'].search(line)
        if amount_match and 'iznos' not in item_data:
            item_data['iznos'] = normalize_number(amount_match.group(1))

        # Težine
        bruto_match = self.PATTERNS['bruto'].search(line)
        if bruto_match and 'bruto_kg' not in item_data:
            item_data['bruto_kg'] = normalize_number(bruto_match.group(1))

        neto_match = self.PATTERNS['neto'].search(line)
        if neto_match and 'neto_kg' not in item_data:
            item_data['neto_kg'] = normalize_number(neto_match.group(1))

        # Zemlja porijekla
        country_match = self.PATTERNS['zemlja'].search(line)
        if country_match and 'zemlja_porijekla' not in item_data:
            item_data['zemlja_porijekla'] = country_match.group(1)

        # Naziv robe (sve što nije pattern je vjerovatno dio naziva)
        if not any(pattern.search(line) for pattern in self.PATTERNS.values()):
            if item_data['naziv_robe']:
                item_data['naziv_robe'] += ' ' + line
            else:
                item_data['naziv_robe'] = line

    def _create_item_from_data(self, data: Dict[str, Any], line_no: int) -> InvoiceLine | None:
        """Kreira InvoiceLine iz parsiranih podataka."""

        # Cleanup naziv robe (OCR često dodaje suvišne spaces)
        naziv = re.sub(r'\s+', ' ', data.get('naziv_robe', '')).strip()

        if not naziv or len(naziv) < 2:
            return None

        # Normalizuj zemlju porijekla
        zemlja = data.get('zemlja_porijekla', '')
        zemlja_normalized = normalize_country_name(zemlja) if zemlja else ''

        # Kalkuliraj iznos ako nedostaje
        kolicina = data.get('kolicina', 0.0)
        cijena = data.get('cijena_jed', 0.0)
        iznos = data.get('iznos', 0.0)

        if iznos == 0.0 and kolicina > 0 and cijena > 0:
            iznos = kolicina * cijena

        return InvoiceLine(
            line_no=line_no,
            naziv_robe=naziv,
            tarifni_broj=data.get('tarifni_broj', ''),
            zemlja_porijekla=zemlja_normalized,
            kolicina=kolicina,
            cijena_jed=cijena,
            iznos=iznos,
            valuta=data.get('valuta', "EUR"),
            bruto_kg=data.get('bruto_kg', 0.0),
            neto_kg=data.get('neto_kg', 0.0),
            jm=data.get('jm', 'kom'),
        )

    def _parse_with_heuristics(self, text: str) -> List[InvoiceLine]:
        """
        Fallback parsing sa heuristikama kada pattern matching ne uspe.
        Jednostavniji pristup: svaka linija sa brojem može biti stavka.
        """
        items = []
        lines = text.split('\n')

        for idx, line in enumerate(lines):
            line = line.strip()

            # Skip prazne i kratke linije
            if not line or len(line) < 10:
                continue

            # Traži linije sa brojevima (količina, cijena)
            if re.search(r'\d+[.,]\d+', line):
                # Jednostavan item sa ograničenim podacima
                item = InvoiceLine(
                    line_no=len(items) + 1,
                    naziv_robe=line[:100],  # Prvih 100 karaktera kao naziv
                    tarifni_broj='',
                    zemlja_porijekla='',
                    kolicina=0.0,
                    cijena_jed=0.0,
                    iznos=0.0,
                    valuta="EUR",
                )
                items.append(item)

        logger.info(f"Heuristički parsing pronašao {len(items)} stavki")
        return items


# ============================================================
# TEST / USAGE EXAMPLE
# ============================================================

if __name__ == "__main__":
    import sys

    if not OCR_AVAILABLE:
        logger.error("❌ OCR biblioteke nisu instalirane!")
        logger.debug("\nInstaliraj:")
        logger.debug("  pip install pytesseract pdf2image")
        logger.debug("  sudo apt-get install tesseract-ocr tesseract-ocr-eng tesseract-ocr-bos")
        sys.exit(1)

    # Test OCR strategy
    strategy = OCRPDFStrategy(dpi=300)

    test_file = "tests/data/scanned_invoice.pdf"

    try:
        items = strategy.extract(test_file)

        logger.info(f"\n✅ OCR parsing uspješan: {len(items)} stavki\n")

        for item in items[:5]:
            logger.debug(f"  {item.line_no}. {item.naziv_robe}")
            logger.debug(f"     Tarifni: {item.tarifni_broj}, Količina: {item.kolicina}")
            logger.debug()

    except FileNotFoundError:
        logger.debug(f"Test fajl nije pronađen: {test_file}")
    except Exception as e:
        logger.error(f"❌ Greška: {e}")
