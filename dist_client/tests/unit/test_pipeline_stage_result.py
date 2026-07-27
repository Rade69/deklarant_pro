"""Testovi za gui/tabs/agent/services/pipeline_stage_result.py (Faza C)."""
from __future__ import annotations

from gui.tabs.agent.services.pipeline_stage_result import (
    PipelineStageResult, PipelineStageStatus, overall_outcome,
)


def _r(status: PipelineStageStatus) -> PipelineStageResult:
    return PipelineStageResult(stage="test", status=status)


def test_sve_success_daje_completed():
    assert overall_outcome([_r(PipelineStageStatus.SUCCESS), _r(PipelineStageStatus.SUCCESS)]) == "COMPLETED"


def test_jedan_warning_daje_partial():
    assert overall_outcome([_r(PipelineStageStatus.SUCCESS), _r(PipelineStageStatus.WARNING)]) == "PARTIAL"


def test_jedan_failed_daje_failed_bez_obzira_na_ostale():
    assert overall_outcome([
        _r(PipelineStageStatus.SUCCESS),
        _r(PipelineStageStatus.WARNING),
        _r(PipelineStageStatus.FAILED),
    ]) == "FAILED"


def test_cancelled_ima_prioritet_nad_svim_ostalim():
    assert overall_outcome([
        _r(PipelineStageStatus.SUCCESS),
        _r(PipelineStageStatus.CANCELLED),
        _r(PipelineStageStatus.FAILED),
    ]) == "CANCELLED"


def test_prazna_lista_ne_tvrdi_uspjeh():
    assert overall_outcome([]) == "FAILED"


def test_can_continue_default_true():
    r = PipelineStageResult(stage="x", status=PipelineStageStatus.SUCCESS)
    assert r.can_continue is True


def test_stats_default_prazan_dict():
    r = PipelineStageResult(stage="x", status=PipelineStageStatus.SUCCESS)
    assert r.stats == {}
