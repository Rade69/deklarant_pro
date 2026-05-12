from pathlib import Path

from importers.smart_pdf_importer import _find_master_frigo_mapping_xlsx


def test_find_master_frigo_mapping_accepts_poreklu_variant(tmp_path):
    pdf = tmp_path / "R2503393.pdf"
    pdf.write_text("", encoding="utf-8")
    mapping = tmp_path / "Podela po poreklu.xlsx 18,12,2025.xlsx"
    mapping.write_text("", encoding="utf-8")

    assert Path(_find_master_frigo_mapping_xlsx(str(pdf))).name == mapping.name
