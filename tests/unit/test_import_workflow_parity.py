"""
Karakterizacioni testovi — paritet ručnog i agent uvoza (Faza 1)

Ovi testovi dokumentuju TRENUTNO stanje: ručni i agent uvoz koriste različitu
završnu obradu istih rezultata parsera. Kada se implementira zajednički tok
(Faze 6-8 iz JEDINSTVENI_IMPORT_WORKFLOW_IMPLEMENTATION_PLAN.md), ovi testovi
će padati i morat će se ažurirati da dokumentuju ŽELJENO stanje (paritet).

Plan §16 Faza 1 + §17 Testna matrica.

Šta se dokumentuje:
  - ručni pojedinačni uvoz poziva: partner check, distribute weights, header, REPLACE/EXTEND
  - ručni grupni uvoz poziva: distribute weights, header
  - agent uvoz NE poziva: partner check, distribute weights, REPLACE/EXTEND
  - agent uvoz poziva: normalize tariffs, header (direktno preko fw)

NAPOMENA: testovi koriste MagicMock za self (isti obrazac kao
test_faktura_view_provjeri_nakon_uvoza.py) da izbjegnu tešku Qt/DB inicijalizaciju.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.draft.draft import DeclarationDraft, InvoiceLine
from gui.tabs.faktura_view import FakturaView
from importers.import_result import ImportResult


# ── Helperi za mock ────────────────────────────────────────────────────────


def _make_invoice_line(invoice_number="INV-001", tarifni_broj="08052190",
                       naziv_robe="Test proizvod", bruto_kg=10.0, neto_kg=9.0,
                       zemlja_porijekla="DE"):
    line = MagicMock()
    line.invoice_number = invoice_number
    line.tarifni_broj = tarifni_broj
    line.naziv_robe = naziv_robe
    line.bruto_kg = bruto_kg
    line.neto_kg = neto_kg
    line.zemlja_porijekla = zemlja_porijekla
    line.iznos = 100.0
    line.kolicina = 5
    line.jm = "kom"
    line.product_code = "TEST001"
    line.povlastica = ""
    line.eur1_number = ""
    line.tariff_similarity = 1.0
    return line


def _mock_self_for_manual_import(agent_mode=False, is_combined=False):
    """Mock self za FakturaView._on_import_finished (ručni pojedinačni)."""
    mock_self = MagicMock()
    mock_self._agent_mode = agent_mode
    mock_self.draft.invoice_lines = []
    mock_self.assembly.master_list_loaded = False
    mock_self.last_import_count = 0
    mock_self.last_invoice_name = ""
    mock_self.weight_manager.accumulated_bruto_kg = 0.0
    mock_self.weight_manager.accumulated_neto_kg = 0.0
    mock_self.on_dirty = None

    items = [_make_invoice_line()]
    mock_self._extract_import_result_data.return_value = (
        items, 10.0, 9.0, "INV-001", is_combined, "invoice",
        False, False, "IZVOZNIK", "UVOZNIK",
    )
    mock_self._get_invoice_name.return_value = "INV-001"
    mock_self._check_partner_consistency.return_value = True
    mock_self._should_show_eur1_dialog.return_value = False
    mock_self._is_same_combined_invoice.return_value = False
    mock_self._append_imported_files_message.side_effect = lambda msg, min_files=1: msg
    mock_self._auto_handle_povlastice_agent.return_value = {"pe2": 0, "eur1_pending": 0}
    return mock_self


def _mock_self_for_batch_import(agent_mode=False):
    """Mock self za FakturaView._process_batch_records (ručni grupni)."""
    mock_self = MagicMock()
    mock_self._agent_mode = agent_mode
    mock_self._batch_failed = []
    mock_self.assembly.master_list_loaded = False
    mock_self.draft.invoice_lines = []
    mock_self.draft.invoice_weights = {}
    mock_self.imported_excel_count = 0
    mock_self.imported_pdf_count = 0
    mock_self._postprocess_master_frigo_pairs_records.return_value = None
    mock_self._normalize_item_tariffs.return_value = None
    mock_self._distribute_invoice_weights.return_value = None
    mock_self._should_show_eur1_dialog.return_value = False
    mock_self._offer_split_by_country.return_value = None
    return mock_self


def _batch_records():
    return [{
        "skipped": False,
        "items": [_make_invoice_line()],
        "bruto_kg": 10.0,
        "neto_kg": 9.0,
        "invoice_name": "INV-001",
        "filepath": "INV-001.pdf",
        "parser_warnings": [],
        "_import_result": None,
    }]


# ── Trenutno stanje: ručni pojedinačni uvoz ────────────────────────────────


class TestManualSingleImportCurrentBehavior:
    """Dokumentuje šta ručni pojedinačni uvoz TRENUTNO radi."""

    def test_poziva_check_partner_consistency(self):
        """Ručni uvoz provjerava konzistentnost pošiljaoca/primaoca."""
        mock_self = _mock_self_for_manual_import()
        with patch("gui.tabs.faktura_view.QMessageBox"):
            FakturaView._on_import_finished(mock_self, [])
        mock_self._check_partner_consistency.assert_called_once()

    def test_poziva_distribute_invoice_weights(self):
        """Ručni uvoz raspoređuje ukupne težine na pojedinačne stavke."""
        mock_self = _mock_self_for_manual_import()
        with patch("gui.tabs.faktura_view.QMessageBox"):
            FakturaView._on_import_finished(mock_self, [])
        mock_self._distribute_invoice_weights.assert_called_once()

    def test_poziva_normalize_item_tariffs(self):
        """Ručni uvoz normalizuje tarifne brojeve na 8 cifara."""
        mock_self = _mock_self_for_manual_import()
        with patch("gui.tabs.faktura_view.QMessageBox"):
            FakturaView._on_import_finished(mock_self, [])
        mock_self._normalize_item_tariffs.assert_called_once()

    def test_poziva_apply_import_result_to_header(self):
        """Ručni uvoz popunjava zaglavlje iz ImportResult."""
        from importers.import_result import ImportResult
        mock_self = _mock_self_for_manual_import()
        result = ImportResult(items=[_make_invoice_line()], bruto_kg=10.0, neto_kg=9.0)
        with patch("gui.tabs.faktura_view.QMessageBox"):
            FakturaView._on_import_finished(mock_self, result)
        mock_self._apply_import_result_to_header.assert_called_once()

    def test_poziva_is_same_combined_invoice(self):
        """Ručni uvoz provjerava REPLACE/EXTEND logiku za kombinovane importe."""
        mock_self = _mock_self_for_manual_import(is_combined=True)
        with patch("gui.tabs.faktura_view.QMessageBox"):
            FakturaView._on_import_finished(mock_self, [])
        mock_self._is_same_combined_invoice.assert_called_once()

    def test_poziva_assign_invoice_name(self):
        """Ručni uvoz dodjeljuje invoice_number svakoj stavki."""
        mock_self = _mock_self_for_manual_import()
        with patch("gui.tabs.faktura_view.QMessageBox"):
            FakturaView._on_import_finished(mock_self, [])
        mock_self._assign_invoice_name.assert_called_once()

    def test_poziva_accumulate_weights(self):
        """Ručni uvoz akumulira ukupne težine."""
        mock_self = _mock_self_for_manual_import()
        with patch("gui.tabs.faktura_view.QMessageBox"):
            FakturaView._on_import_finished(mock_self, [])
        mock_self._accumulate_weights.assert_called_once()

    def test_poziva_historical_tariff_validation(self):
        """Ručni uvoz pokreće završnu historijsku tarifnu validaciju."""
        mock_self = _mock_self_for_manual_import()
        with patch("gui.tabs.faktura_view.QMessageBox"):
            FakturaView._on_import_finished(mock_self, [])
        mock_self._run_historical_tariff_validation.assert_called_once_with(auto=False)


class TestManualSingleImportUnifiedWorkflow:
    """Dokumentuje fazu 6: obični ImportResult ide kroz zajednički workflow."""

    def test_import_result_primjenjuje_plan_na_draft(self):
        mock_self = MagicMock()
        mock_self._agent_mode = False
        mock_self.draft = DeclarationDraft()
        mock_self.assembly.master_list_loaded = False
        mock_self.import_worker.filepath = "INV-006.pdf"
        mock_self.weight_manager.accumulated_bruto_kg = 0.0
        mock_self.weight_manager.accumulated_neto_kg = 0.0
        mock_self._append_imported_files_message.side_effect = lambda msg, min_files=1: msg
        mock_self.on_dirty = None

        line = InvoiceLine(
            invoice_number="INV-006",
            tarifni_broj="3824993",
            naziv_robe="Test proizvod",
            kolicina=1,
            iznos=10.0,
        )
        result = ImportResult(
            items=[line],
            bruto_kg=2.0,
            neto_kg=1.8,
            invoice_name="INV-006",
        )

        with patch("gui.tabs.faktura_view.QMessageBox"):
            FakturaView._on_import_finished(mock_self, result)

        assert len(mock_self.draft.invoice_lines) == 1
        assert mock_self.draft.invoice_lines[0].invoice_number == "INV-006"
        assert mock_self.draft.invoice_lines[0].tarifni_broj == "03824993"
        assert mock_self.draft.invoice_weights["inv-006"] == (2.0, 1.8)
        mock_self._on_import_finished_legacy.assert_not_called()
        mock_self._run_historical_tariff_validation.assert_called_once_with(auto=False)


# ── Trenutno stanje: ručni grupni uvoz ─────────────────────────────────────


class TestManualBatchImportCurrentBehavior:
    """Dokumentuje šta ručni grupni uvoz TRENUTNO radi."""

    def test_poziva_distribute_invoice_weights(self):
        """Grupni uvoz raspoređuje ukupne težine na pojedinačne stavke."""
        mock_self = _mock_self_for_batch_import()
        with patch("gui.tabs.faktura_view.QMessageBox"):
            FakturaView._process_batch_records(mock_self, _batch_records())
        mock_self._distribute_invoice_weights.assert_called_once()

    def test_poziva_normalize_item_tariffs(self):
        """Grupni uvoz normalizuje tarifne brojeve."""
        mock_self = _mock_self_for_batch_import()
        with patch("gui.tabs.faktura_view.QMessageBox"):
            FakturaView._process_batch_records(mock_self, _batch_records())
        mock_self._normalize_item_tariffs.assert_called_once()

    def test_poziva_historical_tariff_validation(self):
        """Grupni uvoz pokreće završnu historijsku validaciju."""
        mock_self = _mock_self_for_batch_import()
        with patch("gui.tabs.faktura_view.QMessageBox"):
            FakturaView._process_batch_records(mock_self, _batch_records())
        mock_self._run_historical_tariff_validation.assert_called_once_with(auto=False)


# ── Trenutno stanje: agent uvoz ────────────────────────────────────────────


def _mock_self_for_agent_import(mode="Uvezi u deklaraciju"):
    """Mock self za AgentController._on_all_completed.
    Ne koristi spec=AgentController jer se draft/faktura_tab instanciraju u __init__
    i spec ih blokira (MagicMock sa spec dozvoljava samo definisane atribute)."""
    mock_self = MagicMock()
    mock_self._current_mode = mode
    mock_self._worker = None
    mock_self.draft.invoice_lines = []
    mock_self.draft.invoice_weights = {}
    mock_self.draft.dirty = False

    # FileItem mock
    file_item = MagicMock()
    file_item.status = "Completed"
    file_item.invoice_lines = [_make_invoice_line()]
    file_item.invoice_number = "INV-001"
    file_item.filepath = "INV-001.pdf"
    file_item.file_type = "PDF"
    file_item.is_combined = False
    file_item.consumed_paths = []
    file_item.has_origin_statement = False
    file_item.is_authorized_exporter = False
    file_item.bruto_kg = 10.0
    file_item.neto_kg = 9.0
    file_item.detected_parser = "test"
    file_item.parser = "test"

    # faktura_tab.view mock
    fw = MagicMock()
    fw._normalize_item_tariffs.return_value = None
    fw._apply_import_result_to_header.return_value = None
    fw._load_data_from_draft.return_value = None
    fw._accumulate_weights.return_value = None
    fw.weight_manager.accumulated_bruto_kg = 0.0
    fw.weight_manager.accumulated_neto_kg = 0.0
    fw._offer_split_by_country.return_value = None
    mock_self.faktura_tab.view = fw

    # _dedupe_completed_import_files vraća input listu (ne MagicMock)
    mock_self._dedupe_completed_import_files.side_effect = lambda x: x
    # _normalize_finished_file_statuses ne radi ništa (status je već Completed)
    mock_self._normalize_finished_file_statuses.return_value = None

    # Chat panel mock
    chat = MagicMock()
    mock_self.view.get_chat_panel.return_value = chat
    mock_self.view.get_document_panel.return_value = MagicMock()
    mock_self.view.get_header.return_value = MagicMock()
    # view.parent() vraća None da prekine 'while parent:' petlju (inace beskonacna)
    mock_self.view.parent.return_value = None

    return mock_self, file_item, fw, chat


class TestAgentImportCurrentBehavior:
    """Dokumentuje šta agent uvoz TRENUTNO radi (i šta NE radi)."""

    def test_poziva_normalize_item_tariffs(self):
        """Agent uvoz normalizuje tarifne brojeve (ima)."""
        from gui.tabs.agent.agent_controller import AgentController
        mock_self, file_item, fw, chat = _mock_self_for_agent_import()
        with patch("gui.tabs.faktura_view.QMessageBox"), \
             patch("gui.tabs.agent.agent_controller.QApplication"), \
             patch("gui.tabs.agent.services.import_pipeline_service._origin_dialog_type",
                   return_value=None):
            AgentController._on_all_completed(mock_self, [file_item])
        fw._normalize_item_tariffs.assert_called_once()

    def test_poziva_apply_import_result_to_header(self):
        """Agent uvoz popunjava zaglavlje (ima, direktno preko fw)."""
        from gui.tabs.agent.agent_controller import AgentController
        mock_self, file_item, fw, chat = _mock_self_for_agent_import()
        with patch("gui.tabs.faktura_view.QMessageBox"), \
             patch("gui.tabs.agent.agent_controller.QApplication"), \
             patch("gui.tabs.agent.services.import_pipeline_service._origin_dialog_type",
                   return_value=None):
            AgentController._on_all_completed(mock_self, [file_item])
        fw._apply_import_result_to_header.assert_called_once()

    def test_NE_poziva_distribute_invoice_weights(self):
        """Agent uvoz NE raspoređuje težine na stavke (RAZLIKA od ručnog)."""
        from gui.tabs.agent.agent_controller import AgentController
        mock_self, file_item, fw, chat = _mock_self_for_agent_import()
        with patch("gui.tabs.faktura_view.QMessageBox"), \
             patch("gui.tabs.agent.agent_controller.QApplication"), \
             patch("gui.tabs.agent.services.import_pipeline_service._origin_dialog_type",
                   return_value=None):
            AgentController._on_all_completed(mock_self, [file_item])
        fw._distribute_invoice_weights.assert_not_called()

    def test_NE_poziva_check_partner_consistency(self):
        """Agent uvoz NE provjerava konzistentnost partnera (RAZLIKA od ručnog)."""
        from gui.tabs.agent.agent_controller import AgentController
        mock_self, file_item, fw, chat = _mock_self_for_agent_import()
        with patch("gui.tabs.faktura_view.QMessageBox"), \
             patch("gui.tabs.agent.agent_controller.QApplication"), \
             patch("gui.tabs.agent.services.import_pipeline_service._origin_dialog_type",
                   return_value=None):
            AgentController._on_all_completed(mock_self, [file_item])
        fw._check_partner_consistency.assert_not_called()

    def test_NE_poziva_is_same_combined_invoice(self):
        """Agent uvoz NE provjerava REPLACE/EXTEND logiku (RAZLIKA od ručnog)."""
        from gui.tabs.agent.agent_controller import AgentController
        mock_self, file_item, fw, chat = _mock_self_for_agent_import()
        with patch("gui.tabs.faktura_view.QMessageBox"), \
             patch("gui.tabs.agent.agent_controller.QApplication"), \
             patch("gui.tabs.agent.services.import_pipeline_service._origin_dialog_type",
                   return_value=None):
            AgentController._on_all_completed(mock_self, [file_item])
        fw._is_same_combined_invoice.assert_not_called()

    def test_NE_poziva_assign_invoice_name(self):
        """Agent uvoz NE koristi istu politiku dodjele invoice_number (RAZLIKA)."""
        from gui.tabs.agent.agent_controller import AgentController
        mock_self, file_item, fw, chat = _mock_self_for_agent_import()
        with patch("gui.tabs.faktura_view.QMessageBox"), \
             patch("gui.tabs.agent.agent_controller.QApplication"), \
             patch("gui.tabs.agent.services.import_pipeline_service._origin_dialog_type",
                   return_value=None):
            AgentController._on_all_completed(mock_self, [file_item])
        fw._assign_invoice_name.assert_not_called()

    def test_cisti_draft_po_fakturi(self):
        """Agent uvoz čisti draft za svaku fakturu (RAZLIKA — ručni ima EXTEND)."""
        from gui.tabs.agent.agent_controller import AgentController
        mock_self, file_item, fw, chat = _mock_self_for_agent_import()
        # mock invoice_lines kao pravu listu da clear() radi
        mock_self.draft.invoice_lines = MagicMock()
        mock_self.draft.invoice_lines.clear = MagicMock()
        with patch("gui.tabs.faktura_view.QMessageBox"), \
             patch("gui.tabs.agent.agent_controller.QApplication"), \
             patch("gui.tabs.agent.services.import_pipeline_service._origin_dialog_type",
                   return_value=None):
            AgentController._on_all_completed(mock_self, [file_item])
        # draft.invoice_lines.clear() se poziva prije i poslije obrade fakture
        assert mock_self.draft.invoice_lines.clear.called


# ── Željeno stanje (xfail — paritet još nije implementiran) ────────────────


class TestImportParityDesiredState:
    """
    ŽELJENO stanje: ručni i agent uvoz moraju pozivati iste metode.
    Ovi testovi su xfail dok se ne implementira zajednički tok (Faze 6-8).
    """

    @pytest.mark.xfail(reason="Paritet nije implementiran — Faza 6-8", strict=True)
    def test_agent_poziva_distribute_invoice_weights(self):
        """ŽELJENO: agent uvoz raspoređuje težine na stavke (kao ručni)."""
        from gui.tabs.agent.agent_controller import AgentController
        mock_self, file_item, fw, chat = _mock_self_for_agent_import()
        with patch("gui.tabs.faktura_view.QMessageBox"), \
             patch("gui.tabs.agent.agent_controller.QApplication"), \
             patch("gui.tabs.agent.services.import_pipeline_service._origin_dialog_type",
                   return_value=None):
            AgentController._on_all_completed(mock_self, [file_item])
        fw._distribute_invoice_weights.assert_called_once()

    @pytest.mark.xfail(reason="Paritet nije implementiran — Faza 6-8", strict=True)
    def test_agent_poziva_check_partner_consistency(self):
        """ŽELJENO: agent uvoz provjerava partnere (kao ručni)."""
        from gui.tabs.agent.agent_controller import AgentController
        mock_self, file_item, fw, chat = _mock_self_for_agent_import()
        with patch("gui.tabs.faktura_view.QMessageBox"), \
             patch("gui.tabs.agent.agent_controller.QApplication"), \
             patch("gui.tabs.agent.services.import_pipeline_service._origin_dialog_type",
                   return_value=None):
            AgentController._on_all_completed(mock_self, [file_item])
        fw._check_partner_consistency.assert_called_once()
