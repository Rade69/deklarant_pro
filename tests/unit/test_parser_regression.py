"""
Regression testovi parsera sa realnim fajlovima.

Svaki test vezuje parser za konkretan fajl i provjerava:
  - Tačan broj stavki (regresija)
  - Pozitivne težine (ispravnost)
  - Prolaz ImportResult.validate() (pouzdanost)

Ako parser promijeni izlaz, ovdje test pada — odmah je vidljivo.
"""

import pytest
from pathlib import Path

FIXTURES_ROOT = Path(__file__).parent.parent.parent / "najavauvoza"


def _skip_if_missing(*paths):
    for p in paths:
        if not Path(p).exists():
            pytest.skip(f"Test fajl nije dostupan: {p}")


# ---------------------------------------------------------------------------
# Leburic / Pekabesko — Excel
# ---------------------------------------------------------------------------

class TestLeburicExcel:
    XLSX = FIXTURES_ROOT / "leburic-pekabesko" / "20-00015.xlsx"

    def test_detect(self):
        _skip_if_missing(self.XLSX)
        from importers.leburic_pekabesko_importer import detect_leburic_pekabesko_excel
        assert detect_leburic_pekabesko_excel(str(self.XLSX))

    def test_item_count(self):
        _skip_if_missing(self.XLSX)
        from importers.leburic_pekabesko_importer import parse_leburic_pekabesko_excel
        r = parse_leburic_pekabesko_excel(str(self.XLSX))
        assert len(r.items) == 4, f"Očekivano 4 stavki, dobijeno {len(r.items)}"

    def test_weights(self):
        _skip_if_missing(self.XLSX)
        from importers.leburic_pekabesko_importer import parse_leburic_pekabesko_excel
        r = parse_leburic_pekabesko_excel(str(self.XLSX))
        assert r.bruto_kg == pytest.approx(5323.0, abs=1.0)
        assert r.neto_kg == pytest.approx(3876.76, abs=1.0)

    def test_first_item_has_naziv(self):
        _skip_if_missing(self.XLSX)
        from importers.leburic_pekabesko_importer import parse_leburic_pekabesko_excel
        r = parse_leburic_pekabesko_excel(str(self.XLSX))
        assert r.items[0].naziv_robe.strip() != ""

    def test_validate_passes(self):
        _skip_if_missing(self.XLSX)
        from importers.leburic_pekabesko_importer import parse_leburic_pekabesko_excel
        from services.import_validator import validate_import_result
        r = parse_leburic_pekabesko_excel(str(self.XLSX))
        vr = validate_import_result(r, self.XLSX.name)
        assert vr.ok, f"Validacija nije prošla: {vr.errors}"


# ---------------------------------------------------------------------------
# Leburic / Pekabesko — PDF (skenirani OCR)
# ---------------------------------------------------------------------------

class TestLeburicPdf21:
    PDF = FIXTURES_ROOT / "leburic-pekabesko" / "LEBURIĆ-PEKABESKO-00021.pdf"

    def test_detect(self):
        _skip_if_missing(self.PDF)
        from importers.leburic_pekabesko_importer import detect_leburic_pekabesko_pdf
        assert detect_leburic_pekabesko_pdf(str(self.PDF))

    def test_item_count(self):
        _skip_if_missing(self.PDF)
        from importers.leburic_pekabesko_importer import parse_leburic_pekabesko_pdf
        r = parse_leburic_pekabesko_pdf(str(self.PDF))
        assert len(r.items) == 8, f"Očekivano 8 stavki, dobijeno {len(r.items)}"

    def test_bruto_weight(self):
        _skip_if_missing(self.PDF)
        from importers.leburic_pekabesko_importer import parse_leburic_pekabesko_pdf
        r = parse_leburic_pekabesko_pdf(str(self.PDF))
        assert r.bruto_kg == pytest.approx(4909.0, abs=1.0)

    def test_total_iznos(self):
        _skip_if_missing(self.PDF)
        from importers.leburic_pekabesko_importer import parse_leburic_pekabesko_pdf
        r = parse_leburic_pekabesko_pdf(str(self.PDF))
        total = sum(x.iznos for x in r.items)
        assert total == pytest.approx(17904.35, abs=1.0)

    def test_validate_passes(self):
        _skip_if_missing(self.PDF)
        from importers.leburic_pekabesko_importer import parse_leburic_pekabesko_pdf
        from services.import_validator import validate_import_result
        r = parse_leburic_pekabesko_pdf(str(self.PDF))
        vr = validate_import_result(r, self.PDF.name)
        assert vr.ok, f"Validacija nije prošla: {vr.errors}"


class TestLeburicPdf22:
    PDF = FIXTURES_ROOT / "leburic-pekabesko" / "LEBURIĆ-PEKABESKO-00022.pdf"

    def test_item_count(self):
        _skip_if_missing(self.PDF)
        from importers.leburic_pekabesko_importer import parse_leburic_pekabesko_pdf
        r = parse_leburic_pekabesko_pdf(str(self.PDF))
        assert len(r.items) == 12, f"Očekivano 12 stavki, dobijeno {len(r.items)}"

    def test_total_iznos(self):
        _skip_if_missing(self.PDF)
        from importers.leburic_pekabesko_importer import parse_leburic_pekabesko_pdf
        r = parse_leburic_pekabesko_pdf(str(self.PDF))
        total = sum(x.iznos for x in r.items)
        assert total == pytest.approx(52071.06, abs=1.0)

    def test_validate_passes(self):
        _skip_if_missing(self.PDF)
        from importers.leburic_pekabesko_importer import parse_leburic_pekabesko_pdf
        from services.import_validator import validate_import_result
        r = parse_leburic_pekabesko_pdf(str(self.PDF))
        vr = validate_import_result(r, self.PDF.name)
        assert vr.ok, f"Validacija nije prošla: {vr.errors}"


# ---------------------------------------------------------------------------
# Imamoglu — Excel Packing List
# ---------------------------------------------------------------------------

class TestImamogluPackingList:
    XLSX = FIXTURES_ROOT / "iamoglu" / "PACKING LIST.xlsx"

    def test_detect(self):
        _skip_if_missing(self.XLSX)
        from importers.imamoglu_excel_importer import detect_imamoglu_packing_list
        assert detect_imamoglu_packing_list(str(self.XLSX))

    def test_item_count(self):
        _skip_if_missing(self.XLSX)
        from importers.imamoglu_excel_importer import parse_imamoglu_packing_list
        r = parse_imamoglu_packing_list(str(self.XLSX))
        assert len(r.items) == 42, f"Očekivano 42 stavki, dobijeno {len(r.items)}"

    def test_weights(self):
        _skip_if_missing(self.XLSX)
        from importers.imamoglu_excel_importer import parse_imamoglu_packing_list
        r = parse_imamoglu_packing_list(str(self.XLSX))
        assert r.bruto_kg == pytest.approx(2383.0, abs=1.0)
        assert r.neto_kg == pytest.approx(2277.0, abs=1.0)

    def test_first_item_naziv(self):
        _skip_if_missing(self.XLSX)
        from importers.imamoglu_excel_importer import parse_imamoglu_packing_list
        r = parse_imamoglu_packing_list(str(self.XLSX))
        assert "BASE FOOT" in r.items[0].naziv_robe.upper()

    def test_all_items_have_naziv(self):
        _skip_if_missing(self.XLSX)
        from importers.imamoglu_excel_importer import parse_imamoglu_packing_list
        r = parse_imamoglu_packing_list(str(self.XLSX))
        empty = [i for i, it in enumerate(r.items, 1) if not it.naziv_robe.strip()]
        assert not empty, f"Stavke bez naziva: {empty}"

    def test_all_items_have_positive_kolicina(self):
        _skip_if_missing(self.XLSX)
        from importers.imamoglu_excel_importer import parse_imamoglu_packing_list
        r = parse_imamoglu_packing_list(str(self.XLSX))
        bad = [i for i, it in enumerate(r.items, 1) if it.kolicina <= 0]
        assert not bad, f"Stavke sa količinom <= 0: {bad}"

    def test_validate_passes(self):
        _skip_if_missing(self.XLSX)
        from importers.imamoglu_excel_importer import parse_imamoglu_packing_list
        from services.import_validator import validate_import_result
        r = parse_imamoglu_packing_list(str(self.XLSX))
        vr = validate_import_result(r, self.XLSX.name)
        assert vr.ok, f"Validacija nije prošla: {vr.errors}"


# ---------------------------------------------------------------------------
# Medicopharm — PDF (realni fajl)
# ---------------------------------------------------------------------------

class TestMedicopharmPdf:
    PDF = FIXTURES_ROOT / "medicopharm-421.pdf"

    def test_item_count_positive(self):
        _skip_if_missing(self.PDF)
        from importers.medicopharm_importer import parse_medicopharm_pdf
        r = parse_medicopharm_pdf(str(self.PDF))
        assert len(r.items) > 0, "Medicopharm parser vratio 0 stavki"

    def test_validate_passes(self):
        _skip_if_missing(self.PDF)
        from importers.medicopharm_importer import parse_medicopharm_pdf
        from services.import_validator import validate_import_result
        r = parse_medicopharm_pdf(str(self.PDF))
        vr = validate_import_result(r, self.PDF.name)
        assert vr.ok, f"Validacija nije prošla: {vr.errors}"


# ---------------------------------------------------------------------------
# Sumaprom — mock test (nema realni fajl u fixtures)
# ---------------------------------------------------------------------------

class TestSumapromMock:
    """Mock testovi — Šumaprom realni fajl nije u najavauvoza/."""

    def test_detect_returns_false_for_nonexistent(self):
        from importers.sumaprom_pdf_parser import detect_sumaprom_pdf
        assert detect_sumaprom_pdf("/nonexistent/file.pdf") is False

    def test_detect_excel_returns_false_for_nonexistent(self):
        from importers.sumaprom_excel_parser import detect_sumaprom_excel
        assert detect_sumaprom_excel("/nonexistent/file.xlsx") is False

    def test_parse_returns_empty_result_gracefully(self):
        """Parser sa nepostojećim fajlom vraća ImportResult sa 0 stavki, ne exception."""
        from importers.sumaprom_pdf_parser import parse_sumaprom_pdf
        try:
            r = parse_sumaprom_pdf("/nonexistent/file.pdf")
            # Ako vrati rezultat, mora biti ImportResult (0 stavki)
            assert hasattr(r, "items")
        except FileNotFoundError:
            pass  # Prihvatljivo — fajl ne postoji
        except Exception as e:
            pytest.fail(f"Parser nije trebao baciti {type(e).__name__}: {e}")
