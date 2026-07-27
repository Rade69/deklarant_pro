# tests/unit/test_faktura_view_tariff_description_db_path.py

"""
Regresija (2026-07-25, otkrio Pi agent): FakturaView._get_tariff_description()
je racunao putanju do deklarant_sistem.db preko __file__-relativne putanje
bez sys.frozen svijesti (isti obrazac kao §44/45) - u frozen .exe buildu bi
tiho vracao prazan opis. Sad delegira na TariffService.load_hierarchical_label
(vec frozen-svjestan preko tarifa_service._resolve_db_path, uz cache za N+1 —
commit 703a68e).

NAPOMENA: self mora podržavati postavljanje atributa (cache polje
_tariff_desc_service) — bare object() to ne dozvoljava, koristi se lagani
stub sa __dict__.
"""
from gui.tabs.faktura_view import FakturaView


class _FakeSelf:
    """Minimalni stub koji podržava cache atribut kao stvaran FakturaView (QWidget)."""


def test_get_tariff_description_vraca_stvaran_opis():
    opis = FakturaView._get_tariff_description(_FakeSelf(), "33049900")
    assert opis
    assert opis != "33049900"  # ne smije se vratiti sam kod (znak greske)


def test_get_tariff_description_koristi_tariff_service():
    import inspect
    src = inspect.getsource(FakturaView._get_tariff_description)
    assert "TariffService" in src
    assert "load_hierarchical_label" in src
    assert "sys.frozen" not in src  # logika je delegirana, ne duplirana ovdje


def test_get_tariff_description_prazan_kod_vraca_prazno():
    assert FakturaView._get_tariff_description(_FakeSelf(), "") == ""


def test_get_tariff_description_ne_digit_vraca_prazno():
    assert FakturaView._get_tariff_description(_FakeSelf(), "abc") == ""
