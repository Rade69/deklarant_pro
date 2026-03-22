# importers/pdf/ocr_utils.py

"""
OCR utility funkcije za PDF import.

- detekcija da li je PDF skeniran (nema tekstualnog sloja)
- OCR ekstrakcija pomoću Tesseract-a
"""

from typing import List
import PyPDF2
import pytesseract
from pdf2image import convert_from_path


def is_scanned_pdf(filepath: str, min_text_len: int = 50) -> bool:
    """
    Provjerava da li PDF ima tekstualni sloj ili je skeniran.

    Args:
        filepath: putanja do PDF-a
        min_text_len: minimalna dužina teksta da se smatra validnim

    Returns:
        True ako je skeniran PDF (potreban OCR)
    """

    try:
        with open(filepath, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text = page.extract_text()
                if text and len(text.strip()) >= min_text_len:
                    return False
        return True
    except Exception:
        # Ako PyPDF2 ne može čitati – tretiraj kao skeniran
        return True


def ocr_pdf_to_text(filepath: str, dpi: int = 300) -> List[str]:
    """
    Radi OCR nad svim stranicama PDF-a.

    Args:
        filepath: PDF fajl
        dpi: rezolucija za rasterizaciju (300 je sweet spot)

    Returns:
        Lista stringova (jedan string po stranici)
    """

    images = convert_from_path(filepath, dpi=dpi)
    pages_text: List[str] = []

    for image in images:
        text = pytesseract.image_to_string(image, lang="eng+deu+bos+srp")
        pages_text.append(text)

    return pages_text
