from datetime import datetime
from unittest.mock import MagicMock

from gui.tabs.agent.models.file_item import FileItem
from gui.tabs.agent.agent_controller import (
    AgentController,
    _agent_invoice_sort_key,
    _agent_invoice_token,
)
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


def test_pair_sort_key_orders_invoice_numbers_naturally():
    f100 = _mk("/tmp/100VP-2026 BLAGIC.pdf")
    f99 = _mk("/tmp/99VP-2026 BLAGIC.pdf")
    ordered = sorted([f100, f99], key=ProcessingWorker._pair_sort_key)
    assert ordered[0].filepath.endswith("99VP-2026 BLAGIC.pdf")
    assert ordered[1].filepath.endswith("100VP-2026 BLAGIC.pdf")


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


def test_mapping_detection_accepts_kg_fashion_manifest_names():
    assert ProcessingWorker._is_mapping_xlsx("/tmp/15467- PTP 11.05.2026..xls")
    assert ProcessingWorker._is_mapping_xlsx("/tmp/transport PTP manifest.xlsx")


def test_agent_invoice_token_ignores_blagic_suffix():
    assert _agent_invoice_token("268VP-2026 SRETO BLAGIC") == _agent_invoice_token("268VP-2026")


def test_agent_controller_orders_completed_files_by_invoice_number():
    f268 = _mk("/tmp/268VP-2026 SRETO BLAGIC.pdf")
    f262 = _mk("/tmp/262VP-2026 SRETO BLAGIC.pdf")
    f268.invoice_number = "268VP-2026"
    f262.invoice_number = "262VP-2026"
    ordered = sorted([f268, f262], key=_agent_invoice_sort_key)
    assert [f.invoice_number for f in ordered] == ["262VP-2026", "268VP-2026"]


def test_agent_controller_dedupe_skips_excel_pair_when_combined_pdf_exists():
    controller = AgentController.__new__(AgentController)
    table = MagicMock()
    doc = MagicMock()
    doc.file_table = table
    view = MagicMock()
    view.get_document_panel.return_value = doc
    controller.view = view

    excel = _mk("/tmp/268VP-2026 SRETO BLAGIC.xlsx")
    excel.status = "Completed"
    excel.invoice_number = "268VP-2026 SRETO BLAGIC"
    excel.invoice_lines = [object()]

    pdf = _mk("/tmp/268VP-2026 SRETO BLAGIC.pdf")
    pdf.status = "Completed"
    pdf.invoice_number = "268VP-2026"
    pdf.invoice_lines = [object()]
    pdf.is_combined = True
    pdf.consumed_paths = [excel.filepath]

    result = controller._dedupe_completed_import_files([excel, pdf])

    assert result == [pdf]
    assert excel.status == "Skipped"
    assert excel.invoice_lines == []


def test_agent_controller_dedupe_honors_consumed_path_without_combined_flag():
    controller = AgentController.__new__(AgentController)
    table = MagicMock()
    doc = MagicMock()
    doc.file_table = table
    view = MagicMock()
    view.get_document_panel.return_value = doc
    controller.view = view

    packing = _mk("/tmp/Pak lista 2419 - Blagic.pdf")
    packing.status = "Completed"
    packing.invoice_lines = [object()]

    invoice = _mk("/tmp/Faktura 2419 - Blagic.pdf")
    invoice.status = "Completed"
    invoice.invoice_lines = [object()]
    invoice.consumed_paths = [packing.filepath]

    result = controller._dedupe_completed_import_files([packing, invoice])

    assert result == [invoice]
    assert packing.status == "Skipped"
    assert packing.invoice_lines == []
