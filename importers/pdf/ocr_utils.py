# importers/pdf/ocr_utils.py

"""
OCR utility funkcije za PDF import.

- detekcija da li je PDF skeniran (nema tekstualnog sloja)
- pre-processing slike za bolji OCR kvalitet
- OCR ekstrakcija pomoću Tesseract-a
"""

import logging
from typing import List

logger = logging.getLogger("asycuda_pro.import.ocr")


def is_scanned_pdf(filepath: str, min_text_len: int = 80) -> bool:
    """
    Provjerava da li PDF ima tekstualni sloj ili je skeniran.
    Koristi pdfplumber (tačniji od PyPDF2 za ekstrakciju teksta).

    Returns:
        True ako je skeniran PDF (potreban OCR)
    """
    try:
        import pdfplumber
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages[:3]:
                text = page.extract_text() or ""
                if len(text.strip()) >= min_text_len:
                    return False
        return True
    except Exception:
        return True


def _preprocess_image(img):
    """
    Pre-processing slike za bolji OCR kvalitet.

    Koraci:
    1. Grayscale — uklanja boju koja zbunjuje OCR
    2. Kontrast — pojačava razliku tekst/pozadina
    3. Oštrina — pojašnjava ivice slova
    4. Binary threshold — čisti pozadinu (bijelo/crno)
    """
    from PIL import ImageEnhance

    img = img.convert("L")                              # grayscale
    img = ImageEnhance.Contrast(img).enhance(2.0)      # pojačaj kontrast
    img = ImageEnhance.Sharpness(img).enhance(2.5)     # pojačaj oštrinu
    img = img.point(lambda x: 255 if x > 145 else 0, "1")  # binary threshold
    return img


def ocr_pdf_to_words(filepath: str, dpi: int = 300) -> List[List[dict]]:
    """
    OCR sa word-level koordinatama (kao pdfplumber.extract_words()).
    Svaka stranica je lista {text, x0, top, x1, bottom}.
    Rijeci sa confidence < 30 se filtriraju (OCR šum).
    """
    import pytesseract
    from pytesseract import Output
    from pdf2image import convert_from_path

    logger.info(f"🔍 OCR (word-level): {filepath} @ {dpi} DPI")

    images = convert_from_path(filepath, dpi=dpi)
    all_pages: List[List[dict]] = []

    tess_config = "--psm 6 --oem 3"

    for page_num, img in enumerate(images, 1):
        processed = _preprocess_image(img)
        try:
            data = pytesseract.image_to_data(
                processed, lang="eng+bos", config=tess_config, output_type=Output.DICT
            )
        except pytesseract.TesseractError:
            data = pytesseract.image_to_data(
                processed, lang="eng", config=tess_config, output_type=Output.DICT
            )

        words = []
        for i in range(len(data["text"])):
            text = (data["text"][i] or "").strip()
            conf = int(data["conf"][i])
            if text and conf >= 30:
                words.append({
                    "text": text,
                    "x0": data["left"][i],
                    "top": data["top"][i],
                    "x1": data["left"][i] + data["width"][i],
                    "bottom": data["top"][i] + data["height"][i],
                })

        all_pages.append(words)
        logger.debug(f"  Stranica {page_num}: {len(words)} rijeci")

    logger.info(f"✅ OCR word-level završen: {len(all_pages)} stranica")
    return all_pages


def ocr_pdf_to_text(filepath: str, dpi: int = 300) -> List[str]:
    """
    Radi OCR nad svim stranicama PDF-a sa pre-processingom.

    Args:
        filepath: PDF fajl
        dpi: rezolucija za rasterizaciju (300 daje dobar balans brzina/kvalitet)

    Returns:
        Lista stringova (jedan string po stranici)
    """
    import pytesseract
    from pdf2image import convert_from_path

    logger.info(f"🔍 OCR: {filepath} @ {dpi} DPI")

    images = convert_from_path(filepath, dpi=dpi)
    pages_text: List[str] = []

    # Tesseract konfiguracija: psm 6 = uniforman blok teksta (idealno za fakture)
    tess_config = "--psm 6 --oem 3"

    for page_num, img in enumerate(images, 1):
        processed = _preprocess_image(img)

        # Pokušaj sa eng+bos; ako bos nije dostupan, fallback na eng
        try:
            text = pytesseract.image_to_string(processed, lang="eng+bos", config=tess_config)
        except pytesseract.TesseractError:
            text = pytesseract.image_to_string(processed, lang="eng", config=tess_config)

        pages_text.append(text)
        logger.debug(f"  Stranica {page_num}: {len(text)} karaktera")

    logger.info(f"✅ OCR završen: {len(pages_text)} stranica, ukupno {sum(len(t) for t in pages_text)} karaktera")
    return pages_text
