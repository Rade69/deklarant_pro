from pathlib import Path

import pytest

from importers.smart_pdf_importer import parse_smart_pdf
from importers.vendors.medicopharm.medicopharm_importer import _try_parse_item_line


PDF_PATH = Path(__file__).resolve().parents[2] / "najavauvoza" / "BIH 893.pdf"


def test_country_suffix_odvojen_razmakom_ne_ide_u_naziv():
    """Regresija (2026-07-25, faktura 1476/26 Rb.93): zemljin razdvojni sufiks
    ("0000") ponekad nije slijepljen uz tarifu ("330499000080") nego odvojen
    razmakom ("33051000 0000") — taj cisto brojcani token ne smije zavrsiti
    kao prefiks naziva robe."""
    line = "93 1633 33051000 0000 NP SAMPON ENERGETSKI 75ML KOM 10.00 1.822 18.22 0.00 0.00 18.22"
    parsed = _try_parse_item_line(line)
    assert parsed is not None
    assert parsed["tariff"] == "33051000"
    assert parsed["name"] == "NP SAMPON ENERGETSKI 75ML"


def test_normalan_red_bez_razdvojenog_sufiksa_nepromijenjen():
    """Kontrolni slucaj: red bez razdvojenog sufiksa i dalje radi ispravno."""
    line = "1 11878 38249993 SUSSINA 650 tbl. KOM 400.00 1.020 407.86 0.00 0.00 407.86"
    parsed = _try_parse_item_line(line)
    assert parsed is not None
    assert parsed["tariff"] == "38249993"
    assert parsed["name"] == "SUSSINA 650 tbl."


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
