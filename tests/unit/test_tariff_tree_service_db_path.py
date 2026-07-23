"""
Testovi za services/tariff/tariff_tree_service.py::_resolve_db_path().

Regresija: originalna putanja je imala pogresan broj '..' (jedan umjesto
dva) - resila se u services/database/ koji ne postoji, umjesto u
database/ na korijenu projekta. Pogresno cak i u dev modu, ne samo u
frozen buildu.
"""
import os

from services.tariff import tariff_tree_service


def test_resolve_db_path_koristi_ispravnu_putanju_kad_postoji(tmp_path, monkeypatch):
    db_dir = tmp_path / "database"
    db_dir.mkdir()
    db_file = db_dir / "deklarant_sistem.db"
    db_file.write_text("")

    fake_module_file = tmp_path / "services" / "tariff" / "tariff_tree_service.py"
    fake_module_file.parent.mkdir(parents=True)

    monkeypatch.setattr(tariff_tree_service, "__file__", str(fake_module_file))
    monkeypatch.delattr(tariff_tree_service.sys, "frozen", raising=False)

    result = tariff_tree_service._resolve_db_path()

    assert os.path.normpath(result) == os.path.normpath(str(db_file))


def test_resolve_db_path_frozen_fallback_na_exe_folder(tmp_path, monkeypatch):
    fake_module_file = tmp_path / "_internal" / "services" / "tariff" / "tariff_tree_service.py"
    fake_module_file.parent.mkdir(parents=True)

    exe_dir = tmp_path / "DeklarantPro_exe_folder"
    exe_dir.mkdir()
    db_dir = exe_dir / "database"
    db_dir.mkdir()
    db_file = db_dir / "deklarant_sistem.db"
    db_file.write_text("")

    monkeypatch.setattr(tariff_tree_service, "__file__", str(fake_module_file))
    monkeypatch.setattr(tariff_tree_service.sys, "frozen", True, raising=False)
    monkeypatch.setattr(tariff_tree_service.sys, "executable", str(exe_dir / "DeklarantPro.exe"))

    result = tariff_tree_service._resolve_db_path()

    assert os.path.normpath(result) == os.path.normpath(str(db_file))


def test_resolve_db_path_dva_nivoa_gore_ne_jedan(tmp_path, monkeypatch):
    """Regresija: prvobitni kod je imao samo jedan '..' (services/database/
    umjesto database/) - ovaj test bi pao na staroj implementaciji jer bi
    prvi kandidat bio 'services/database/deklarant_sistem.db'."""
    fake_module_file = tmp_path / "services" / "tariff" / "tariff_tree_service.py"
    fake_module_file.parent.mkdir(parents=True)

    monkeypatch.setattr(tariff_tree_service, "__file__", str(fake_module_file))
    monkeypatch.delattr(tariff_tree_service.sys, "frozen", raising=False)

    result = tariff_tree_service._resolve_db_path()

    assert "services" + os.sep + "database" not in os.path.normpath(result)
