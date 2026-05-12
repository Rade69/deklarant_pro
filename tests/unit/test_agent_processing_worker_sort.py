from datetime import datetime

from gui.tabs.agent.models.file_item import FileItem
from gui.tabs.agent.widgets.processing_worker import ProcessingWorker


def _mk(filepath: str) -> FileItem:
    ext = filepath.lower().split(".")[-1] if "." in filepath else ""
    if ext == "pdf":
        file_type = "PDF"
    elif ext in ("xlsx", "xls", "xlsm"):
        file_type = "Excel"
    elif ext == "xml":
        file_type = "XML"
    else:
        file_type = "Unknown"
    return FileItem(
        filepath=filepath,
        filename=filepath.split("/")[-1],
        file_type=file_type,
        size_bytes=0,
        parser="Auto-detect",
        status="Uploaded",
        confidence=0.0,
        added_at=datetime.now(),
    )


def test_normalized_invoice_token_ignores_packing_keywords():
    t1 = ProcessingWorker._normalized_invoice_token("/tmp/FAI-7-0-26.xlsx")
    t2 = ProcessingWorker._normalized_invoice_token("/tmp/FAI-7-0-26 PACKING LIST.pdf")
    assert t1 == t2


def test_pair_sort_key_orders_excel_before_pdf_for_same_invoice():
    excel = _mk("/tmp/702VP-2025.xlsx")
    pdf = _mk("/tmp/702VP-2025.pdf")
    ordered = sorted([pdf, excel], key=ProcessingWorker._pair_sort_key)
    assert ordered[0].filepath.endswith(".xlsx")
    assert ordered[1].filepath.endswith(".pdf")


def test_pair_sort_key_puts_mapping_excel_after_pdf():
    pdf = _mk("/tmp/MF-2026-001.pdf")
    mapping = _mk("/tmp/tarife_i_zemlje_porekla.xlsx")
    ordered = sorted([mapping, pdf], key=ProcessingWorker._pair_sort_key)
    assert ordered[-1].filepath.endswith("tarife_i_zemlje_porekla.xlsx")


def test_pair_sort_key_puts_mapping_excel_after_unrelated_non_mapping_files():
    mapping = _mk("/tmp/Podela po poreklu.xlsx")
    excel = _mk("/tmp/702VP-2025.xlsx")
    ordered = sorted([mapping, excel], key=ProcessingWorker._pair_sort_key)
    assert ordered[-1].filepath.endswith("Podela po poreklu.xlsx")


def test_mapping_detection_accepts_poreklu_variant():
    assert ProcessingWorker._is_mapping_xlsx("/tmp/Podela po poreklu.xlsx 18,12,2025.xlsx")
