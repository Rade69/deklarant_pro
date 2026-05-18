from services.import_service import get_import_service
from importers.blagic_loren_importer import parse_blagic_loren_excel


EXCEL_46 = "najavauvoza/loren-fakture/46VP-2026 BLAGIC.xlsx"
PDF_46 = "najavauvoza/loren-fakture/46VP-2026 BLAGIC.pdf"


def test_blagic_loren_excel_does_not_consume_matching_pdf():
    result = parse_blagic_loren_excel(EXCEL_46)

    assert result.consumed_paths == []
    assert sum(line.iznos or 0 for line in result.items) == 0


def test_blagic_loren_import_service_combines_pdf_after_excel():
    svc = get_import_service()
    svc.clear_memory()

    excel_result = svc.import_file(EXCEL_46)
    pdf_result = svc.import_file(PDF_46)

    assert excel_result.consumed_paths == []
    assert pdf_result.is_combined is True
    assert pdf_result.consumed_paths == [EXCEL_46]
    assert len(pdf_result.items) == 31
    assert round(sum(line.iznos or 0 for line in pdf_result.items), 2) == 3853.57
