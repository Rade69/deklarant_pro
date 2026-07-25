# tests/unit/test_faktura_view_tariff_description_db_path.py

"""
Regresija (2026-07-25, otkrio Pi agent): FakturaView._get_tariff_description()
je racunao putanju do deklarant_sistem.db preko __file__-relativne putanje
bez sys.frozen svijesti (isti obrazac kao §44/45) - u frozen .exe buildu bi
tiho vracao prazan opis. Sad koristi vec popravljen, frozen-svjestan
_DB_PATH iz gui.tabs.sifarnici.tariff_hierarchy.
"""
from gui.tabs.faktura_view import FakturaView


def test_get_tariff_description_vraca_stvaran_opis():
    opis = FakturaView._get_tariff_description(object(), "33049900")
    assert opis
    assert opis != "33049900"  # ne smije se vratiti sam kod (znak greske)


def test_get_tariff_description_koristi_frozen_svjestan_db_path():
    from gui.tabs.sifarnici.tariff_hierarchy import _DB_PATH
    import inspect
    src = inspect.getsource(FakturaView._get_tariff_description)
    assert "tariff_hierarchy" in src
    assert "sys.frozen" not in src  # logika je delegirana, ne duplirana ovdje


def test_get_tariff_description_prazan_kod_vraca_prazno():
    assert FakturaView._get_tariff_description(object(), "") == ""


def test_get_tariff_description_ne_digit_vraca_prazno():
    assert FakturaView._get_tariff_description(object(), "abc") == ""
