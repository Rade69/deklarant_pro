#!/usr/bin/env python3
"""
Testovi: PDF parser pipeline bez Java/tabula zavisnosti.

Potvrđuje da:
1. Nema importa tabula-py u projektnom kodu
2. pdfplumber je dostupan i funkcionalan
3. Svi parseri rade bez Java runtime-a
4. Smart PDF pipeline radi sa stvarnim fakturama
"""

import sys
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# ============================================================
# 1. PROVERA — NEMA TABULA IMPORT U KODU
# ============================================================

def test_no_tabula_import_in_code():
    """Nijedan .py fajl u projektu ne sme da uvozi tabula."""
    offenders = []
    for py_file in project_root.rglob("*.py"):
        parts = py_file.parts
        if any(skip in parts for skip in (".venv", "venv", "__pycache__", "backup", "tests")):
            continue
        try:
            content = py_file.read_text()
            if "import tabula" in content or "from tabula" in content:
                offenders.append(str(py_file.relative_to(project_root)))
        except Exception:
            pass
    assert len(offenders) == 0, f"Pronađen tabula import u: {offenders}"


def test_tabula_not_in_smart_pdf():
    """smart_pdf_importer ne sme da uvozi tabula-py."""
    f = project_root / "importers" / "smart_pdf_importer.py"
    content = f.read_text()
    assert "import tabula" not in content, "smart_pdf_importer uvozi tabula!"
    assert "from tabula" not in content, "smart_pdf_importer uvozi tabula!"


# ============================================================
# 2. PROVERA — PDFPLUMBER DOSTUPAN
# ============================================================

def test_pdfplumber_importable():
    """pdfplumber mora biti dostupan."""
    import pdfplumber
    assert pdfplumber is not None


def test_pdfplumber_can_open_pdf():
    """pdfplumber može da otvori i pročita PDF sa tekstom."""
    pdf_path = project_root / "najavauvoza" / "LOREN" / "fwrauni" / "107VP-2026 BLAGIC.pdf"
    if not pdf_path.exists():
        pytest.skip(f"Test PDF ne postoji: {pdf_path}")
    import pdfplumber
    with pdfplumber.open(str(pdf_path)) as pdf:
        assert len(pdf.pages) > 0
        full_text = ""
        for page in pdf.pages[:3]:
            t = page.extract_text() or ""
            full_text += t
        assert len(full_text) > 10, f"Tekst prekratak: {len(full_text)} znakova"


# ============================================================
# 3. SVI PARSERI SE MOGU IMPORTOVATI BEZ JAVA
# ============================================================

PARSER_MODULES = [
    "importers.smart_pdf_importer",
    "importers.generic_pdf_importer",
    "importers.excel_importer",
    "importers.xml_importer",
    "importers.faktura_xml_parser",
    "importers.invoice_improved_parser",
    "importers.blagic_loren_pdf_parser",
    "importers.blagic_attos_importer",
    "importers.imamoglu_pdf_parser",
    "importers.imamoglu_excel_importer",
    "importers.sumaprom_pdf_parser",
    "importers.sumaprom_excel_parser",
    "importers.packing_list_parser",
    "importers.proton_system_importer",
    "importers.strategies.pdf_strategy",
    "importers.strategies.excel_strategy",
    "importers.strategies.xml_strategy",
    "importers.pdf.ocr_utils",
]


@pytest.mark.parametrize("module_name", PARSER_MODULES)
def test_parser_module_importable(module_name):
    """Svaki parser modul se može importovati bez Java greške."""
    __import__(module_name)


# ============================================================
# 4. STRATEGY REGISTRY — RADI BEZ JAVA
# ============================================================

def test_strategy_registry_no_java():
    """StrategyRegistry se kreira i radi bez Java."""
    from importers.strategy_registry import get_registry, reset_registry
    reset_registry()
    registry = get_registry()
    strategies = registry.list_strategies()
    assert len(strategies) == 3, f"Očekujem 3 strategije, dobijeno {len(strategies)}"
    assert "PDF Import" in strategies
    assert "Excel Import" in strategies
    assert "XML Import" in strategies


def test_pdf_strategy_accepts_pdf():
    """PDF strategija prihvata .pdf fajlove."""
    from importers.strategies.pdf_strategy import PDFImportStrategy
    s = PDFImportStrategy()
    assert s.can_handle(Path("test.pdf"))
    assert not s.can_handle(Path("test.xlsx"))
    assert s.strategy_name == "PDF Import"
    assert s.priority == 10


# ============================================================
# 5. SMART PDF PIPELINE SA STVARNIM FAKTURAMA
# ============================================================

REAL_PDF_TESTS = [
    # (label, putanja, min_stavki, ocekivani_format)
    ("Medicopharm", "najavauvoza/Medicopharm.pdf", 0, None),  # PDF sa slikama
    ("Blagić Attos 720", "najavauvoza/blagic-attos/Faktura 720 - Blagić.pdf", 1, "blagic_attos"),
    ("Blagić Loren 107", "najavauvoza/LOREN/fwrauni/107VP-2026 BLAGIC.pdf", 1, "blagic_loren"),
    ("Šumaprom", "najavauvoza/suma/DOC041122-04112022130817.pdf", 0, None),  # Skenirani PDF — zahteva OCR
    ("Master Frigo R2503393", "najavauvoza/R2503393 (16.12.2025.) (E)-MASTER FRIGO, BANJA LUKA  (AVANSNO)-23.503,15 EUR.pdf", 1, "master_frigo"),
    ("Invoice Improved (Blagić 113)", "najavauvoza/LOREN/fwrauni/113VP-2026 BLAGIC.pdf", 1, None),
    ("Blagić 111", "najavauvoza/LOREN/fwrauni/111VP-2026 BLAGIC.pdf", 1, None),
]


@pytest.mark.parametrize("label,rel_path,min_stavki,expected_format", REAL_PDF_TESTS)
def test_smart_pdf_parses_real_invoice(label, rel_path, min_stavki, expected_format):
    """Smart PDF parser parsira stvarnu fakturu bez Java."""
    from importers.smart_pdf_importer import parse_smart_pdf, _detect_pdf_format

    full_path = project_root / rel_path
    if not full_path.exists():
        pytest.skip(f"Fajl ne postoji: {full_path}")

    # Provera detekcije formata
    detected = _detect_pdf_format(str(full_path))
    assert detected is not None
    assert detected != ""
    if expected_format:
        assert detected == expected_format, \
            f"Očekivan format '{expected_format}', detektovan '{detected}'"

    # Parsiranje
    result = parse_smart_pdf(str(full_path))
    assert result is not None, f"parse_smart_pdf vratio None za {label}"
    assert hasattr(result, 'items'), f"Rezultat nema 'items' za {label}"
    assert len(result.items) >= min_stavki, \
        f"{label}: očekivano ≥{min_stavki} stavki, dobijeno {len(result.items)}"
    assert result.currency in ("EUR", "BAM", ""), \
        f"{label}: neočekivana valuta '{result.currency}'"


# ============================================================
# 6. GENERIC PDF FALLBACK
# ============================================================

def test_generic_pdf_no_java():
    """Generic PDF parser ne zahteva Java."""
    from importers.generic_pdf_importer import parse_generic_pdf

    pdf_path = project_root / "najavauvoza" / "Medicopharm.pdf"
    if not pdf_path.exists():
        pytest.skip("Test PDF ne postoji")

    result = parse_generic_pdf(str(pdf_path))
    assert result is not None
    assert hasattr(result, 'items')


# ============================================================
# 7. OCR FALLBACK — PROVERA DOSTUPNOSTI
# ============================================================

def test_ocr_module_importable():
    """OCR modul se može importovati bez Java."""
    from importers.pdf import ocr_utils
    from importers.pdf import ocr_invoice_parser
    assert ocr_utils is not None
    assert ocr_invoice_parser is not None


def test_scanned_pdf_detection():
    """Detekcija skeniranog PDF-a radi bez Java."""
    from importers.pdf.ocr_utils import is_scanned_pdf

    pdf_path = project_root / "najavauvoza" / "Medicopharm.pdf"
    if not pdf_path.exists():
        pytest.skip("Test PDF ne postoji")

    result = is_scanned_pdf(str(pdf_path))
    assert isinstance(result, bool)


# ============================================================
# 8. OCR PIPELINE — PYTESSERACT TEST (opciono)
# ============================================================

def test_pytesseract_import_or_skip():
    """pytesseract se može importovati ili se test preskače."""
    try:
        import pytesseract
        assert pytesseract is not None
    except ImportError:
        pytest.skip("pytesseract nije instaliran — OCR testovi preskočeni")


def test_ocr_pdf_to_text():
    """OCR konverzija PDF-a u tekst (ako je pytesseract dostupan)."""
    pytesseract = pytest.importorskip("pytesseract")
    pdf2image = pytest.importorskip("pdf2image")

    from importers.pdf.ocr_utils import ocr_pdf_to_text

    pdf_path = project_root / "najavauvoza" / "Medicopharm.pdf"
    if not pdf_path.exists():
        pytest.skip("Test PDF ne postoji")

    pages_text = ocr_pdf_to_text(str(pdf_path), dpi=150)
    assert isinstance(pages_text, list)
    assert len(pages_text) > 0
    # Bar jedna strana ima neki tekst
    total_text = "".join(pages_text)
    assert len(total_text) > 0, "OCR nije izvukao nikakav tekst"


def test_ocr_parse_result():
    """OCR rezultat se parsira u ImportResult (ako je pytesseract dostupan)."""
    pytesseract = pytest.importorskip("pytesseract")
    pdf2image = pytest.importorskip("pdf2image")

    from importers.pdf.ocr_utils import ocr_pdf_to_text
    from importers.pdf.ocr_invoice_parser import parse_ocr_result

    pdf_path = project_root / "najavauvoza" / "Medicopharm.pdf"
    if not pdf_path.exists():
        pytest.skip("Test PDF ne postoji")

    pages_text = ocr_pdf_to_text(str(pdf_path), dpi=150)
    result = parse_ocr_result(pages_text, pdf_path=str(pdf_path))
    assert result is not None
    assert hasattr(result, 'items')


def test_ocr_fallback_in_smart_pipeline():
    """Smart PDF pipeline koristi OCR fallback za skenirane PDF-ove."""
    pytesseract = pytest.importorskip("pytesseract")
    pdf2image = pytest.importorskip("pdf2image")

    from importers.smart_pdf_importer import parse_smart_pdf

    pdf_path = project_root / "najavauvoza" / "Medicopharm.pdf"
    if not pdf_path.exists():
        pytest.skip("Test PDF ne postoji")

    result = parse_smart_pdf(str(pdf_path))
    assert result is not None
    assert hasattr(result, 'items')
    # OCR bi trebalo da nađe bar 1 stavku u Medicopharm PDF-u
    assert len(result.items) >= 1, \
        f"OCR fallback nije pronašao stavke u Medicopharm.pdf ({len(result.items)} stavki)"


def test_startup_ocr_check():
    """run._check_ocr_availability() se izvršava bez exception-a."""
    from run import _check_ocr_availability
    _check_ocr_availability()  # Ne sme da baci exception
