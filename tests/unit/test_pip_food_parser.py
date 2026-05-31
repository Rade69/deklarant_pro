from collections import Counter
from pathlib import Path

import pytest

from importers.smart_pdf_importer import _detect_pdf_format, parse_smart_pdf
from importers.vendors.pip_food.pip_food_parser import parse_pip_food_pdf


PDF_PATH = Path(__file__).resolve().parents[2] / "najavauvoza" / "PIP92.pdf"


@pytest.mark.skipif(not PDF_PATH.exists(), reason="PIP92.pdf nije dostupan u lokalnom workspace-u")
def test_pip92_real_pdf_parses_all_invoices_items_weights_and_origin():
    result = parse_pip_food_pdf(str(PDF_PATH))

    assert result.import_type == "pip_food_pdf"
    assert result.invoice_name == "IF0520/26-02"
    assert len(result.items) == 25
    assert result.bruto_kg == 8956.0
    assert result.neto_kg == 8880.0
    assert result.has_origin_statement is False

    invoice_counts = Counter(item.invoice_number for item in result.items)
    assert invoice_counts == {
        "IF0520/26-02": 14,
        "IF0520/26-01": 10,
        "IF0520/26-03": 1,
    }

    assert round(sum(item.iznos or 0 for item in result.items), 2) == 32876.50
    assert round(sum(item.bruto_kg or 0 for item in result.items), 2) == 8956.00
    assert round(sum(item.neto_kg or 0 for item in result.items), 2) == 8880.00
    assert {item.zemlja_porijekla for item in result.items} == {"RS"}

    first = result.items[0]
    assert first.invoice_number == "IF0520/26-02"
    assert first.line_no == 1
    assert first.naziv_robe == "FROSTY GOLD 10/1"
    assert first.tarifni_broj == "2106909890"
    assert first.kolicina == 600.0
    assert first.jm == "KG"
    assert first.cijena_jed == 3.25
    assert first.iznos == 1950.0

    yeast = result.items[-1]
    assert yeast.invoice_number == "IF0520/26-03"
    assert yeast.naziv_robe == "SVEŽI PEKARSKI KVASAC"
    assert yeast.tarifni_broj == ""
    assert yeast.kolicina == 2800.0
    assert yeast.iznos == 1932.0


@pytest.mark.skipif(not PDF_PATH.exists(), reason="PIP92.pdf nije dostupan u lokalnom workspace-u")
def test_pip92_real_pdf_is_routed_by_smart_pdf_importer():
    assert _detect_pdf_format(str(PDF_PATH)) == "pip_food"

    result = parse_smart_pdf(str(PDF_PATH))

    assert result.import_type == "pip_food_pdf"
    assert len(result.items) == 25
