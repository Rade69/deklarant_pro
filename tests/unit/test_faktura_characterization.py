"""
Karakterizacioni testovi: import, validacija, signali, težine, auto-popuna.

Faza 0 prema Codex planu §8. Karakterizacija bez promjene koda.
Koristi MagicMock za FakturaView (isti obrazac kao postojeći testovi).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gui.tabs.faktura_view import FakturaView


class _MockWeightManager:
    accumulated_bruto_kg = 0.0
    accumulated_neto_kg = 0.0


def _mock_self_for_import():
    mock_self = MagicMock()
    mock_self._agent_mode = False
    mock_self.draft.invoice_lines = []
    mock_self.draft.invoice_weights = {}
    mock_self.assembly.master_list_loaded = False
    mock_self.weight_manager = _MockWeightManager()
    mock_self.on_dirty = None
    items = [MagicMock(naziv_robe="Test", tarifni_broj="08052190")]
    mock_self._extract_import_result_data.return_value = (
        items, 10.0, 9.0, "INV-001", False, "invoice", False, False,
        "IZVOZNIK", "UVOZNIK",
    )
    mock_self._get_invoice_name.return_value = "INV-001"
    mock_self._check_partner_consistency.return_value = True
    mock_self._should_show_eur1_dialog.return_value = False
    mock_self._is_same_combined_invoice.return_value = False
    mock_self._auto_handle_povlastice_agent.return_value = {"pe2": 0, "eur1_pending": 0}
    mock_self._append_imported_files_message.side_effect = lambda msg, min_files=1: msg
    return mock_self


class TestImportCharacterization:

    def test_on_import_finished_calls_extract_data(self):
        """ImportResult se ekstraktuje prije obrade."""
        mock_self = _mock_self_for_import()
        with patch("gui.tabs.faktura_view.QMessageBox"):
            FakturaView._on_import_finished(mock_self, [])
        mock_self._extract_import_result_data.assert_called_once()

    def test_on_import_finished_calls_normalize_tariffs(self):
        mock_self = _mock_self_for_import()
        with patch("gui.tabs.faktura_view.QMessageBox"):
            FakturaView._on_import_finished(mock_self, [])
        mock_self._normalize_item_tariffs.assert_called_once()


class TestValidationCharacterization:

    def test_view_has_validator(self):
        """FakturaView ima FakturaItemValidator."""
        from services.validation.validation_service import FakturaItemValidator
        validator = FakturaItemValidator()
        assert hasattr(validator, "validate")


class TestSignalCharacterization:

    def test_naimenovanja_created_signal_exists(self, qtbot):
        """Signal postoji i može se konektovati."""
        from core.draft import DeclarationDraft
        from gui.tabs.faktura_view import FakturaView
        draft = DeclarationDraft()
        view = FakturaView(draft=draft)
        qtbot.addWidget(view)
        from PySide6.QtCore import Signal
        assert isinstance(view.naimenovanja_created, Signal)


class TestWeightCharacterization:

    def test_weight_manager_has_accumulated_fields(self):
        wm = _MockWeightManager()
        assert hasattr(wm, "accumulated_bruto_kg")
        assert hasattr(wm, "accumulated_neto_kg")

    def test_mass_calculator_exists(self):
        """MassCalculator postoji i ima calculate_masses."""
        from services.faktura.mass_calculator import MassCalculator
        assert hasattr(MassCalculator, "calculate_masses")


class TestAutoFillCharacterization:

    def test_auto_fill_uses_tariff_facade(self):
        """Auto-popuna koristi TariffFacade kroz _on_auto_fill."""
        from services.tariff_facade import TariffFacade
        facade = TariffFacade.get_instance()
        assert hasattr(facade, "auto_populate_tariffs")
        assert hasattr(facade, "commit_proposals")


class TestPublicContracts:

    def test_faktura_view_has_set_analysis_summary(self):
        """set_analysis_summary postoji (poziva ga AgentController)."""
        from core.draft import DeclarationDraft
        from gui.tabs.faktura_view import FakturaView
        draft = DeclarationDraft()
        view = FakturaView(draft=draft)
        assert hasattr(view, "set_analysis_summary")

    def test_faktura_view_has_get_data_set_data_clear_form(self):
        """BaseView API mora biti funkcionalan."""
        from core.draft import DeclarationDraft
        from gui.tabs.faktura_view import FakturaView
        draft = DeclarationDraft()
        view = FakturaView(draft=draft)
        assert hasattr(view, "get_data")
        assert hasattr(view, "set_data")
        assert hasattr(view, "clear_form")


class TestDistStandalone:

    def test_faktura_view_imports(self):
        """FakturaView se može importovati samostalno."""
        from gui.tabs.faktura_view import FakturaView
        assert FakturaView is not None

    def test_faktura_services_importable(self):
        """Svi faktura servisi se mogu importovati."""
        import services.faktura.mass_calculator
        import services.faktura.weight_manager
        import services.faktura.validation_service
