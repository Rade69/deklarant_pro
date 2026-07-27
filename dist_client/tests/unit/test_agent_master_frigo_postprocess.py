from datetime import datetime

from gui.tabs.agent.models.file_item import FileItem
from gui.tabs.agent.widgets.processing_worker import ProcessingWorker


class _Line:
    def __init__(self, product_code="", naziv_robe="", kolicina=0.0, cijena_jed=0.0, iznos=0.0):
        self.product_code = product_code
        self.naziv_robe = naziv_robe
        self.kolicina = kolicina
        self.cijena_jed = cijena_jed
        self.iznos = iznos


def _mk(filepath: str, file_type: str, status="Completed", parser="", lines=None) -> FileItem:
    return FileItem(
        filepath=filepath,
        filename=filepath.split("/")[-1],
        file_type=file_type,
        size_bytes=0,
        parser="Auto-detect",
        status=status,
        confidence=1.0,
        added_at=datetime.now(),
        invoice_lines=lines or [],
        detected_parser=parser,
    )


def test_apply_excel_financials_by_product_code():
    pdf_lines = [_Line(product_code="A-100", naziv_robe="Roba A", kolicina=2, cijena_jed=0, iznos=0)]
    excel_lines = [_Line(product_code="A100", naziv_robe="Roba A", kolicina=2, cijena_jed=10, iznos=20)]

    updated = ProcessingWorker._apply_excel_financials(pdf_lines, excel_lines)

    assert updated == 1
    assert pdf_lines[0].cijena_jed == 10
    assert pdf_lines[0].iznos == 20


def test_postprocess_master_frigo_pairs_marks_excel_skipped_and_combined():
    pdf = _mk(
        "/tmp/MF-2026-001.pdf",
        "PDF",
        parser="master_frigo",
        lines=[_Line(product_code="K-1", naziv_robe="Kompresor", kolicina=1, cijena_jed=0, iznos=0)],
    )
    excel = _mk(
        "/tmp/MF-2026-001.xlsx",
        "Excel",
        lines=[_Line(product_code="K1", naziv_robe="Kompresor", kolicina=1, cijena_jed=150, iznos=150)],
    )
    worker = ProcessingWorker(files=[])

    worker._postprocess_master_frigo_pairs([pdf, excel])

    assert pdf.is_combined is True
    assert pdf.invoice_lines[0].iznos == 150
    assert excel.status == "Skipped"
    assert excel.invoice_lines == []
