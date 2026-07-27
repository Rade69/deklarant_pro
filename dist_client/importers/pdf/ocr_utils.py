# importers/pdf/ocr_utils.py

"""
OCR utility funkcije za PDF import.

- detekcija da li je PDF skeniran (nema tekstualnog sloja)
- pre-processing slike za bolji OCR kvalitet
- OCR ekstrakcija pomoću Tesseract-a
"""

import logging
import os
import platform
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("deklarant_pro.import.ocr")

# Session-level OCR cache: (filepath, mtime, dpi) → List[str]
_ocr_cache: Dict[Tuple[str, float, int], List[str]] = {}

# Poppler path za pdf2image (None = tražiti u PATH-u)
_poppler_path: Optional[str] = None


def _find_tesseract() -> Optional[str]:
    """Vraća putanju do Tesseract exe-a, ili None ako nije pronađen."""
    if platform.system() != "Windows":
        return None  # Na Linux/Mac tesseract je u PATH-u

    candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        Path.home() / "AppData" / "Local" / "Tesseract-OCR" / "tesseract.exe",
        r"C:\tools\tesseract\tesseract.exe",  # chocolatey
    ]
    for path in candidates:
        if Path(path).exists():
            return str(path)
    return None


def _find_poppler() -> Optional[str]:
    """Vraća putanju do Poppler bin/ foldera na Windowsu, ili None."""
    if platform.system() != "Windows":
        return None  # Na Linux/Mac poppler je u PATH-u

    candidates = [
        r"C:\Program Files\poppler\bin",
        r"C:\poppler\bin",
        r"C:\tools\poppler\bin",  # chocolatey
        r"C:\ProgramData\chocolatey\bin",
    ]
    for path in candidates:
        if Path(path).exists() and any(
            Path(path, exe).exists() for exe in ["pdftoppm.exe", "pdfinfo.exe"]
        ):
            return path
    return None


def _setup_ocr_engines() -> None:
    """Konfigurira Tesseract i Poppler putanje jednom pri prvom pozivu."""
    global _poppler_path

    # Tesseract
    try:
        import pytesseract
        tess_path = _find_tesseract()
        if tess_path:
            pytesseract.pytesseract.tesseract_cmd = tess_path
            logger.debug(f"Tesseract path: {tess_path}")
    except ImportError:
        pass

    # Poppler
    poppler = _find_poppler()
    if poppler:
        _poppler_path = poppler
        logger.debug(f"Poppler path: {poppler}")


_setup_ocr_engines()


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

    images = convert_from_path(filepath, dpi=dpi, poppler_path=_poppler_path)
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

    images = convert_from_path(filepath, dpi=dpi, poppler_path=_poppler_path)
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


def _remove_table_lines(img):
    """
    Uklanja horizontalne i vertikalne linije tabele iz slike koristeći OpenCV morfološke operacije.
    Vraća PIL Image pogodnu za OCR.
    Fallback: vraća originalnu grayscale sliku ako OpenCV nije dostupan.
    """
    try:
        import cv2
        import numpy as np

        gray = img.convert("L")
        arr = np.array(gray)

        thresh = cv2.threshold(arr, 150, 255, cv2.THRESH_BINARY_INV)[1]
        h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (80, 1))
        h_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, h_kernel, iterations=2)
        v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 80))
        v_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, v_kernel, iterations=2)
        lines_mask = cv2.add(h_lines, v_lines)
        cleaned = cv2.subtract(thresh, lines_mask)
        result = cv2.bitwise_not(cleaned)

        from PIL import Image as PILImage
        return PILImage.fromarray(result)

    except ImportError:
        logger.debug("opencv nije dostupan — koristi se standardni preprocessing")
        return _preprocess_image(img)


def ocr_pdf_to_text_no_lines(filepath: str, dpi: int = 300) -> List[str]:
    """
    OCR sa uklanjanjem linija tabele (za fakture sa tabličnim formatom).
    Koristi OpenCV morfološke operacije za brisanje linija prije OCR-a.
    Rezultat se kešira u memoriji po (filepath, mtime, dpi) — isti fajl
    se ne OCR-uje više puta u jednoj sesiji.
    """
    # Cache lookup
    try:
        mtime = os.path.getmtime(filepath)
    except OSError:
        mtime = 0.0
    cache_key = (os.path.abspath(filepath), mtime, dpi)
    if cache_key in _ocr_cache:
        logger.debug(f"⚡ OCR cache hit: {os.path.basename(filepath)}")
        return _ocr_cache[cache_key]

    import pytesseract
    from pdf2image import convert_from_path

    logger.info(f"🔍 OCR (no-lines): {filepath} @ {dpi} DPI")
    images = convert_from_path(filepath, dpi=dpi, poppler_path=_poppler_path)
    pages_text: List[str] = []
    tess_config = "--psm 6 --oem 3"

    for page_num, img in enumerate(images, 1):
        processed = _remove_table_lines(img)
        try:
            text = pytesseract.image_to_string(processed, lang="eng+bos", config=tess_config)
        except pytesseract.TesseractError:
            text = pytesseract.image_to_string(processed, lang="eng", config=tess_config)
        pages_text.append(text)
        logger.debug(f"  Stranica {page_num}: {len(text)} karaktera")

    logger.info(f"✅ OCR (no-lines) završen: {len(pages_text)} stranica")
    _ocr_cache[cache_key] = pages_text
    return pages_text

