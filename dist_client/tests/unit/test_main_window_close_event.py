"""
Testovi za MainWindow.closeEvent - zatvaranje preko OS X dugmeta/Alt+F4
mora poštovati istu "Agent još radi" potvrdu kao custom "Izlaz" dugme.

MainWindow se ne instancira u punom obliku (teška inicijalizacija — tabovi,
DB konekcije) — poziva se nevezana metoda direktno na MagicMock "self",
standardan pristup za testiranje pojedinačne metode teške Qt klase.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from gui.main_window import MainWindow


def _mock_self(confirm_result: bool) -> MagicMock:
    mock_self = MagicMock()
    mock_self._confirm_safe_to_exit.return_value = confirm_result
    mock_self.windowHandle.return_value = None
    mock_self._active_screen = None
    return mock_self


def test_close_event_ignorise_zatvaranje_dok_agent_radi():
    """
    Regresioni test za fix: closeEvent (OS X dugme/Alt+F4) ranije NIJE
    provjeravao _confirm_safe_to_exit() - samo custom "Izlaz" dugme jeste.
    """
    mock_self = _mock_self(confirm_result=False)
    event = MagicMock()

    MainWindow.closeEvent(mock_self, event)

    event.ignore.assert_called_once()
    mock_self._save_window_state.assert_not_called()
