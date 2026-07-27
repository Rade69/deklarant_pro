"""
Test za DatabasePanel._on_settings (2026-07-26).

Korisnička primjedba: Admin panel ima dugme "Testiraj konekciju" ali nema
način da se host/port/baza/korisnik/lozinka promijene iz aplikacije — jedini
put je ručno uređivanje .env fajla. Gotov DbSetupDialog (host/port/test/
snimi u .env) je postojao, ali nigdje nije bio pozvan.

Isti obrazac kao test_faktura_view_auto_applied_notice.py: nevezana metoda
se poziva direktno na MagicMock "self" da se izbjegne teška inicijalizacija
cijelog DatabasePanel-a (Qt widgeti, QThread-ovi).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QDialog

from gui.tabs.admin.panels.database_panel import DatabasePanel


def test_on_settings_reload_i_test_konekcije_nakon_potvrde():
    mock_self = MagicMock()
    mock_dialog = MagicMock()
    mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
    mock_settings = MagicMock(host="192.168.0.25", port=5432, database="deklarant_pro")

    with patch(
        "gui.dialogs.db_setup_dialog.DbSetupDialog", return_value=mock_dialog
    ) as MockDialog, patch(
        "gui.dialogs.db_setup_dialog._reload_settings"
    ) as mock_reload, patch(
        "config.settings.get_db_settings", return_value=mock_settings
    ):
        DatabasePanel._on_settings(mock_self)

    MockDialog.assert_called_once_with(parent=mock_self)
    mock_dialog.exec.assert_called_once()
    mock_reload.assert_called_once()
    mock_self.lbl_server.setText.assert_called_once_with("192.168.0.25:5432/deklarant_pro")
    mock_self._on_test_conn.assert_called_once()


def test_on_settings_ne_radi_nista_pri_otkazivanju():
    mock_self = MagicMock()
    mock_dialog = MagicMock()
    mock_dialog.exec.return_value = QDialog.DialogCode.Rejected

    with patch(
        "gui.dialogs.db_setup_dialog.DbSetupDialog", return_value=mock_dialog
    ), patch(
        "gui.dialogs.db_setup_dialog._reload_settings"
    ) as mock_reload:
        DatabasePanel._on_settings(mock_self)

    mock_reload.assert_not_called()
    mock_self.lbl_server.setText.assert_not_called()
    mock_self._on_test_conn.assert_not_called()
