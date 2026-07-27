from pathlib import Path

from services.agent import llm_audit_log
from services import tariff_doc_history_service


def test_llm_audit_uses_database_beside_frozen_executable(monkeypatch, tmp_path):
    executable = tmp_path / "DeklarantPro.exe"
    monkeypatch.setattr(llm_audit_log.sys, "frozen", True, raising=False)
    monkeypatch.setattr(llm_audit_log.sys, "executable", str(executable))

    assert llm_audit_log._resolve_sqlite_path() == (
        tmp_path / "database" / "llm_audit.db"
    )


def test_tariff_history_uses_database_beside_frozen_executable(
    monkeypatch,
    tmp_path,
):
    executable = tmp_path / "DeklarantPro.exe"
    monkeypatch.setattr(
        tariff_doc_history_service.sys,
        "frozen",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        tariff_doc_history_service.sys,
        "executable",
        str(executable),
    )

    assert Path(tariff_doc_history_service._resolve_db_path()) == (
        tmp_path / "database" / "deklarant_sistem.db"
    )

