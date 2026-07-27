"""
Testovi za gui/tabs/sifarnici/tariff_hierarchy.py::_resolve_db_path().

Regresija: u PyInstaller frozen buildu __file__ pokazuje unutar _internal/
bundle-a, dok stvarna (read-write) deklarant_sistem.db živi pored .exe-a.
Bez frozen-svjesnog fallback-a, sqlite3.connect() tiho pravi novu praznu
bazu na pogrešnoj putanji -> "no such table: tarifa_2026" na upitu.
"""
import os

from gui.tabs.sifarnici import tariff_hierarchy


def test_resolve_db_path_koristi_standardnu_putanju_kad_postoji(tmp_path, monkeypatch):
    db_dir = tmp_path / "database"
    db_dir.mkdir()
    db_file = db_dir / "deklarant_sistem.db"
    db_file.write_text("")

    fake_module_file = tmp_path / "gui" / "tabs" / "sifarnici" / "tariff_hierarchy.py"
    fake_module_file.parent.mkdir(parents=True)

    monkeypatch.setattr(tariff_hierarchy, "__file__", str(fake_module_file))
    monkeypatch.delattr(tariff_hierarchy.sys, "frozen", raising=False)

    result = tariff_hierarchy._resolve_db_path()

    assert os.path.normpath(result) == os.path.normpath(str(db_file))


def test_resolve_db_path_frozen_fallback_na_exe_folder(tmp_path, monkeypatch):
    # Standardna (dev) putanja NE postoji - simulira frozen build gdje
    # __file__ pokazuje unutar _internal/ bundle-a bez database/ foldera.
    fake_module_file = tmp_path / "_internal" / "gui" / "tabs" / "sifarnici" / "tariff_hierarchy.py"
    fake_module_file.parent.mkdir(parents=True)

    exe_dir = tmp_path / "DeklarantPro_exe_folder"
    exe_dir.mkdir()
    db_dir = exe_dir / "database"
    db_dir.mkdir()
    db_file = db_dir / "deklarant_sistem.db"
    db_file.write_text("")

    monkeypatch.setattr(tariff_hierarchy, "__file__", str(fake_module_file))
    monkeypatch.setattr(tariff_hierarchy.sys, "frozen", True, raising=False)
    monkeypatch.setattr(tariff_hierarchy.sys, "executable", str(exe_dir / "DeklarantPro.exe"))

    result = tariff_hierarchy._resolve_db_path()

    assert os.path.normpath(result) == os.path.normpath(str(db_file))


def test_resolve_db_path_vraca_prvi_kandidat_kad_nista_ne_postoji(tmp_path, monkeypatch):
    fake_module_file = tmp_path / "nowhere" / "tariff_hierarchy.py"
    fake_module_file.parent.mkdir(parents=True)

    monkeypatch.chdir(tmp_path)  # CWD-relativni kandidat takodje ne smije postojati
    monkeypatch.setattr(tariff_hierarchy, "__file__", str(fake_module_file))
    monkeypatch.delattr(tariff_hierarchy.sys, "frozen", raising=False)

    result = tariff_hierarchy._resolve_db_path()

    expected_first_candidate = os.path.normpath(
        os.path.join(os.path.dirname(str(fake_module_file)), "..", "..", "..", "database", "deklarant_sistem.db")
    )
    assert os.path.normpath(result) == expected_first_candidate
