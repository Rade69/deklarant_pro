from pathlib import Path

import pytest

from importers.smart_pdf_importer import parse_smart_pdf


PDF_PATH = Path(__file__).resolve().parents[2] / "najavauvoza" / "BIH 893.pdf"


@pytest.mark.skipif(not PDF_PATH.exists(), reason="BIH 893.pdf nije dostupan u lokalnom workspace-u")
def test_medicopharm_bih_893_summary_weights_and_origin_mapping():
    result = parse_smart_pdf(str(PDF_PATH))
    items = {item.line_no: item for item in result.items}

    assert len(result.items) == 61
    assert result.invoice_name == "893/26"
    assert result.bruto_kg == pytest.approx(170.0)
    assert result.neto_kg == pytest.approx(154.91)
    assert sum(item.neto_kg for item in result.items) == pytest.approx(154.91)

    assert all(item.zemlja_porijekla for item in result.items)
    assert items[39].zemlja_porijekla == "FR"
    assert items[39].neto_kg == pytest.approx(0.312128, abs=0.000001)
    assert items[59].zemlja_porijekla == "RS"
    assert items[59].neto_kg == pytest.approx(1.0)
    assert items[59].has_origin_statement is True

    assert items[25].has_origin_statement is False
    assert items[33].has_origin_statement is False
    assert items[61].naziv_robe == "CICASTIM GEL15 ML. (5+1)PROMO"
