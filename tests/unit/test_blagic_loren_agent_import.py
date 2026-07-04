from pathlib import Path

import pytest

from importers.vendors.blagic.blagic_combined_importer import (
    combine_blagic_excel_and_pdf,
    import_blagic_combined,
)
from importers.vendors.blagic.blagic_loren_pdf_parser import parse_blagic_loren_pdf
from services.import_service import ImportService, get_import_service
from importers.blagic_loren_importer import parse_blagic_loren_excel


EXCEL_46 = "najavauvoza/loren-fakture/46VP-2026 BLAGIC.xlsx"
PDF_46 = "najavauvoza/loren-fakture/46VP-2026 BLAGIC.pdf"
EXCEL_267 = "najavauvoza/LOREN/fwrauniipakingliste/267VP-2026 SRETO BLAGIC.xlsx"
EXCEL_268 = "najavauvoza/LOREN/fwrauniipakingliste/268VP-2026 SRETO BLAGIC.xlsx"
PDF_268 = "najavauvoza/LOREN/fwrauniipakingliste/268VP-2026 SRETO BLAGIC.pdf"

# Ovi testovi zavise od stvarnih Blagić faktura koje su privatni podaci van repoa.
# Kad fixture fajlovi nisu prisutni (druga mašina, CI), preskoči umjesto pada.
pytestmark = pytest.mark.skipif(
    not Path(EXCEL_46).exists(),
    reason="Blagić fixture fakture nisu dostupne (privatni podaci van repoa)",
)


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
    assert [Path(p) for p in pdf_result.consumed_paths] == [Path(EXCEL_46)]
    assert pdf_result.invoice_name == "46VP-2026"
    assert len(pdf_result.items) == 31
    assert round(sum(line.iznos or 0 for line in pdf_result.items), 2) == 3853.57


def test_blagic_loren_excel_infers_origin_when_header_is_wrong():
    result = parse_blagic_loren_excel(EXCEL_267, _skip_pdf_lookup=True)

    assert len(result.items) == 22
    assert {line.zemlja_porijekla for line in result.items} == {"CN"}


def test_blagic_loren_combined_uses_pdf_total_weights():
    _items, stats = combine_blagic_excel_and_pdf(EXCEL_268, PDF_268)

    assert stats["bruto_kg"] == 542.51
    assert stats["neto_kg"] == 527.0
    assert round(sum(item.bruto_kg for item in _items), 2) == 565.58


def test_blagic_loren_per_item_neto_distributed_from_pdf():
    """Neto po stavci mora biti < bruto (raspodijeljen iz PDF ukupnog neto)."""
    _items, stats = combine_blagic_excel_and_pdf(EXCEL_268, PDF_268)

    assert stats["neto_kg"] < stats["bruto_kg"], "Ukupni neto mora biti manji od bruta"
    assert all(item.neto_kg < item.bruto_kg for item in _items if item.bruto_kg > 0), (
        "Svaka stavka mora imati neto < bruto"
    )
    assert round(sum(item.neto_kg for item in _items), 2) == stats["neto_kg"], (
        "Suma neto stavki mora biti jednaka PDF ukupnom netu"
    )


def test_blagic_loren_pdf_invoice_name_comes_from_pdf_text():
    result = parse_blagic_loren_pdf(PDF_268)

    assert result.invoice_name == "268VP-2026"


def test_blagic_loren_combined_invoice_name_comes_from_pdf_text():
    result = import_blagic_combined(EXCEL_268, PDF_268)

    assert result.invoice_name == "268VP-2026"


def test_worker_private_instance_combines_all_three_pairs():
    """
    Simulira worker redoslijed: xlsx→pdf za svaki par, privatna instanca.
    Race condition sa singleton-om bi spriječio kombinovanje za 2.+ par.
    """
    svc = ImportService()  # privatna instanca kao u ProcessingWorker

    pairs = [
        ("najavauvoza/loren-fakture/702VP-2025 BLAGIC.xlsx",
         "najavauvoza/loren-fakture/702VP-2025 BLAGIC.pdf"),
        ("najavauvoza/loren-fakture/703VP-2025 BLAGIC.xlsx",
         "najavauvoza/loren-fakture/703VP-2025 BLAGIC.pdf"),
        ("najavauvoza/loren-fakture/704VP-2025 BLAGIC.xlsx",
         "najavauvoza/loren-fakture/704VP-2025 BLAGIC.pdf"),
    ]

    combined_results = []
    for excel, pdf in pairs:
        svc.import_file(excel)
        result = svc.import_file(pdf)
        combined_results.append(result)

    assert all(r.is_combined for r in combined_results), (
        "Svi parovi moraju biti kombinovani — ako ne, race condition je prisutan"
    )
    assert [len(r.items) for r in combined_results] == [29, 23, 23]
