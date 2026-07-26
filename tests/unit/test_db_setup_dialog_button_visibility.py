"""
Test za DbSetupDialog dugmad — vidljivost boja (2026-07-26).

Korisnička primjedba (uz screenshot): "Testiraj konekciju" je bio bez
lokalnog stylesheet-a, pa se u praksi renderovao sa bijelim slovima na
svijetloj pozadini (nevidljivo) u ovom modalnom dijalogu — dok je "Snimi i
nastavi" (već je imalo lokalni stylesheet) bilo ispravno vidljivo. Fix:
oba dugmeta sad dijele isti eksplicitan stylesheet, umjesto oslanjanja na
globalni app QSS koji se u ovom kontekstu nije ispravno primjenjivao.

Test provjerava samo da oba dugmeta imaju POSTAVLJEN i MEĐUSOBNO IDENTIČAN
stylesheet — regresiona zaštita da se "Testiraj konekciju" opet ne ostavi
bez lokalnog stila.
"""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from gui.dialogs.db_setup_dialog import DbSetupDialog


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    if QApplication.instance() is None:
        QApplication([])


def test_test_i_save_dugme_imaju_eksplicitan_i_identican_stylesheet():
    dialog = DbSetupDialog()
    try:
        test_style = dialog._btn_test.styleSheet()
        save_style = dialog._btn_save.styleSheet()

        assert test_style, "Testiraj konekciju mora imati eksplicitan stylesheet"
        assert save_style, "Snimi i nastavi mora imati eksplicitan stylesheet"
        assert test_style == save_style, "Oba dugmeta moraju dijeliti isti stil radi konzistentnosti"
        assert "color: white" in test_style
        assert "background: #2980b9" in test_style
    finally:
        dialog.deleteLater()
