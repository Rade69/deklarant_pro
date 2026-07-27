"""
Testovi za services/agent/chat/tariff_history_analysis_service.py::_resolve_db_path().

Isti obrazac/regresija kao gui/tabs/sifarnici/tariff_hierarchy.py i
services/tariff/tariff_tree_service.py - frozen build fallback.
"""
import os

from services.agent.chat import tariff_history_analysis_service as svc


def test_resolve_db_path_koristi_standardnu_putanju_kad_postoji(tmp_path, monkeypatch):
    db_dir = tmp_path / "database"
    db_dir.mkdir()
    db_file = db_dir / "deklarant_sistem.db"
    db_file.write_text("")

    fake_module_file = tmp_path / "services" / "agent" / "chat" / "tariff_history_analysis_service.py"
    fake_module_file.parent.mkdir(parents=True)

    monkeypatch.setattr(svc, "__file__", str(fake_module_file))
    monkeypatch.delattr(svc.sys, "frozen", raising=False)

    result = svc._resolve_db_path()

    assert os.path.normpath(result) == os.path.normpath(str(db_file))


def test_resolve_db_path_frozen_fallback_na_exe_folder(tmp_path, monkeypatch):
    fake_module_file = tmp_path / "_internal" / "services" / "agent" / "chat" / "tariff_history_analysis_service.py"
    fake_module_file.parent.mkdir(parents=True)

    exe_dir = tmp_path / "DeklarantPro_exe_folder"
    exe_dir.mkdir()
    db_dir = exe_dir / "database"
    db_dir.mkdir()
    db_file = db_dir / "deklarant_sistem.db"
    db_file.write_text("")

    monkeypatch.setattr(svc, "__file__", str(fake_module_file))
    monkeypatch.setattr(svc.sys, "frozen", True, raising=False)
    monkeypatch.setattr(svc.sys, "executable", str(exe_dir / "DeklarantPro.exe"))

    result = svc._resolve_db_path()

    assert os.path.normpath(result) == os.path.normpath(str(db_file))
