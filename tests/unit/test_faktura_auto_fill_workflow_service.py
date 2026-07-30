from unittest.mock import MagicMock

from core.draft import InvoiceLine
from services.faktura.auto_fill_workflow_service import AutoFillWorkflowService
from services.faktura.models import AutoFillWorkflowRequest
from services.tariff.tariff_mapping_service import MappingResult, TariffProposal


def _line(line_no=1, tarifni_broj="", product_code="P1", naziv_robe="Roba"):
    return InvoiceLine(
        line_no=line_no,
        product_code=product_code,
        naziv_robe=naziv_robe,
        tarifni_broj=tarifni_broj,
    )


def test_prepare_preview_koristi_dry_run_i_threshold_092():
    facade = MagicMock()
    facade.auto_populate_tariffs.return_value = MappingResult(
        total_items=1,
        matched_items=1,
        unmatched_items=0,
        proposals=[MagicMock()],
    )
    service = AutoFillWorkflowService(facade=facade)
    line = _line()

    result = service.prepare_preview(
        AutoFillWorkflowRequest(target_lines=[line], supplier_name="SUP")
    )

    assert result.proposals
    facade.auto_populate_tariffs.assert_called_once_with(
        [line],
        min_similarity=0.92,
        overwrite_existing=False,
        supplier="SUP",
        dry_run=True,
    )


def test_commit_preview_upisuje_tacno_potvrdjene_prijedloge_bez_recalculation():
    facade = MagicMock()
    proposal = TariffProposal(
        line_no=1,
        naziv_ili_kod="P1",
        tarifni_broj="84818099",
        precision_1="",
        source="baza_znanja",
        confidence=0.98,
        line_index=0,
    )
    facade.commit_proposals.return_value = MappingResult(
        total_items=1,
        matched_items=1,
        unmatched_items=0,
        proposals=[],
    )
    service = AutoFillWorkflowService(facade=facade)
    line = _line()

    result = service.run(
        AutoFillWorkflowRequest(
            target_lines=[line],
            supplier_name="SUP",
            confirmed_proposals=[proposal],
            basic_filled_count=0,
        )
    )

    assert result.mapping_result.matched_items == 1
    facade.commit_proposals.assert_called_once_with([line], [proposal])
    facade.auto_populate_tariffs.assert_not_called()


def test_auto_mode_koristi_auto_populate_i_ne_prepisuje_postojece():
    facade = MagicMock()
    facade.auto_populate_tariffs.return_value = MappingResult(
        total_items=1,
        matched_items=0,
        unmatched_items=1,
    )
    service = AutoFillWorkflowService(facade=facade)
    line = _line()

    service.run(
        AutoFillWorkflowRequest(target_lines=[line], supplier_name="SUP", auto=True)
    )

    facade.auto_populate_tariffs.assert_called_once_with(
        [line],
        min_similarity=0.92,
        overwrite_existing=False,
        supplier="SUP",
    )


def test_skipped_details_razlikuje_stavke_sa_postojecom_tarifom():
    service = AutoFillWorkflowService()
    line = _line(line_no=7, tarifni_broj="85011000", product_code="MOTOR")

    assert service.skipped_details_for([line]) == [(7, "MOTOR", "85011000")]
