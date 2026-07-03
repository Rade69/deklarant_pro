from pathlib import Path

import pytest

from importers.smart_pdf_importer import _find_master_frigo_mapping_xlsx
from services.import_service import ImportService
from gui.tabs.agent.models.file_item import FileItem
from gui.tabs.agent.widgets.processing_worker import ProcessingWorker

_MF_FIXTURE = "najavauvoza/masterfrigo/R2600310 (20.02.2026.) (E)-MASTER FRIGO, BANJA LUKA-16.871,80 EUR.pdf"


def test_find_master_frigo_mapping_accepts_poreklu_variant(tmp_path):
    pdf = tmp_path / "R2503393.pdf"
    pdf.write_text("", encoding="utf-8")
    mapping = tmp_path / "Podela po poreklu.xlsx 18,12,2025.xlsx"
    mapping.write_text("", encoding="utf-8")

    assert Path(_find_master_frigo_mapping_xlsx(str(pdf))).name == mapping.name


@pytest.mark.skipif(
    not Path(_MF_FIXTURE).exists(),
    reason="Master Frigo fixture fakture nisu dostupne (privatni podaci van repoa)",
)
def test_master_frigo_batch_keeps_mapping_for_multiple_pdfs():
    files = [
        "najavauvoza/masterfrigo/R2600310 (20.02.2026.) (E)-MASTER FRIGO, BANJA LUKA-16.871,80 EUR.pdf",
        "najavauvoza/masterfrigo/R2600311 (20.02.2026.) (NE)-MASTER FRIGO, BANJA LUKA-3.084,00 EUR.pdf",
        "najavauvoza/masterfrigo/R2600312 (20.02.2026.) (CH)-MASTER FRIGO, BANJA LUKA-236,00 EUR.pdf",
        "najavauvoza/masterfrigo/tarife i zemlje porekla.xlsx 24,02,2026.xlsx",
    ]
    ordered = [
        item.filepath
        for item in sorted(
            (FileItem.from_filepath(path) for path in files),
            key=ProcessingWorker._pair_sort_key,
        )
    ]

    svc = ImportService()
    consumed = set()
    pdf_results = []
    for path in ordered:
        if path in consumed:
            continue
        result = svc.import_file(path)
        consumed.update(result.consumed_paths or [])
        pdf_results.append(result)

    assert len(pdf_results) == 3
    assert [len(result.items) for result in pdf_results] == [35, 16, 2]
    assert [round(sum(line.iznos or 0 for line in result.items), 2) for result in pdf_results] == [
        16871.8,
        3084.0,
        236.0,
    ]
    assert all(all(line.tarifni_broj for line in result.items) for result in pdf_results)
    assert all(all(line.zemlja_porijekla for line in result.items) for result in pdf_results)
