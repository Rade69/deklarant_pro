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

from core.draft.draft import DeclarationDraft, InvoiceLine, Party
from gui.tabs.faktura_view import FakturaView
from importers.import_result import ImportResult


# ── Helperi za mock ────────────────────────────────────────────────────────


def _make_invoice_line(invoice_number="INV-001", tarifni_broj="08052190",
                       naziv_robe="Test proizvod", bruto_kg=10.0, neto_kg=9.0,
                       zemlja_porijekla="DE"):
    return InvoiceLine(
        invoice_number=invoice_number,
        tarifni_broj=tarifni_broj,
        naziv_robe=naziv_robe,
        bruto_kg=bruto_kg,
        neto_kg=neto_kg,
        zemlja_porijekla=zemlja_porijekla,
        iznos=100.0,
        kolicina=5,
        jm="kom",
        product_code="TEST001",
        povlastica="",
        eur1_number="",
        tariff_similarity=1.0,
    )


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
    mock_self.draft = DeclarationDraft()
    mock_self.imported_excel_count = 0
    mock_self.imported_pdf_count = 0
    mock_self._postprocess_master_frigo_pairs_records.return_value = None
    mock_self._normalize_item_tariffs.return_value = None
    mock_self._distribute_invoice_weights.return_value = None
    mock_self._should_show_eur1_dialog.return_value = False
    mock_self._offer_split_by_country.return_value = None
    mock_self.on_dirty = None
    return mock_self


def _batch_records():
    result = ImportResult(
        items=[_make_invoice_line(tarifni_broj="3824993", bruto_kg=0.0, neto_kg=0.0, zemlja_porijekla="")],
        bruto_kg=10.0,
        neto_kg=9.0,
        invoice_name="INV-001",
    )
    return [{
        "skipped": False,
        "items": result.items,
        "bruto_kg": 10.0,
        "neto_kg": 9.0,
        "invoice_name": "INV-001",
        "filepath": "INV-001.pdf",
        "parser_warnings": [],
        "_import_result": result,
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
        mock_self._finish_import_legacy_path.assert_not_called()
        mock_self._run_historical_tariff_validation.assert_called_once_with(auto=False)


# ── Trenutno stanje: ručni grupni uvoz ─────────────────────────────────────


class TestManualBatchImportCurrentBehavior:
    """Dokumentuje ručni grupni uvoz nakon povezivanja na zajednički workflow."""

    def test_rasporedjuje_tezine_kroz_zajednicku_primjenu(self):
        """Grupni uvoz raspoređuje ukupne težine na pojedinačne stavke."""
        mock_self = _mock_self_for_batch_import()
        with patch("gui.tabs.faktura_view.QMessageBox"):
            FakturaView._process_batch_records(mock_self, _batch_records())
        assert mock_self.draft.invoice_lines[0].bruto_kg == pytest.approx(10.0)
        assert mock_self.draft.invoice_lines[0].neto_kg == pytest.approx(9.0)

    def test_normalizuje_tarife_kroz_zajednicki_plan(self):
        """Grupni uvoz normalizuje tarifne brojeve."""
        mock_self = _mock_self_for_batch_import()
        with patch("gui.tabs.faktura_view.QMessageBox"):
            FakturaView._process_batch_records(mock_self, _batch_records())
        assert mock_self.draft.invoice_lines[0].tarifni_broj == "03824993"

    def test_poziva_historical_tariff_validation(self):
        """Grupni uvoz pokreće završnu historijsku validaciju."""
        mock_self = _mock_self_for_batch_import()
        with patch("gui.tabs.faktura_view.QMessageBox"):
            FakturaView._process_batch_records(mock_self, _batch_records())
        mock_self._run_historical_tariff_validation.assert_called_once_with(auto=False)

    def test_partner_konflikt_ide_kroz_zajednicku_potvrdu(self):
        mock_self = _mock_self_for_batch_import()
        mock_self.draft.izvoznik_naziv = "POSTOJECI IZVOZNIK"
        records = _batch_records()
        records[0]["_import_result"].exporter = Party(name="NOVI IZVOZNIK")

        with patch("gui.tabs.faktura_view.QMessageBox"):
            FakturaView._process_batch_records(mock_self, records)

        mock_self._confirm_import_partner_conflicts.assert_called_once()

    def test_isti_broj_fakture_radi_replace_umjesto_duplikata(self):
        mock_self = _mock_self_for_batch_import()
        mock_self.draft.invoice_lines.append(
            _make_invoice_line(invoice_number="INV-001", naziv_robe="Stara stavka")
        )
        mock_self.draft.invoice_weights["inv-001"] = (1.0, 1.0)
        records = _batch_records()
        records[0]["items"][0].naziv_robe = "Nova stavka"

        with patch("gui.tabs.faktura_view.QMessageBox"):
            FakturaView._process_batch_records(mock_self, records)

        assert len(mock_self.draft.invoice_lines) == 1
        assert mock_self.draft.invoice_lines[0].naziv_robe == "Nova stavka"

    def test_master_list_rezim_ostaje_na_legacy_batch_toku(self):
        mock_self = _mock_self_for_batch_import()
        mock_self.assembly.master_list_loaded = True

        with patch("gui.tabs.faktura_view.QMessageBox"):
            FakturaView._process_batch_records(mock_self, _batch_records())

        mock_self._normalize_item_tariffs.assert_called_once()
        mock_self._distribute_invoice_weights.assert_called_once()


# ── Trenutno stanje: agent uvoz ────────────────────────────────────────────


def _mock_self_for_agent_import(mode="Uvezi u deklaraciju"):
    """Mock self za AgentController._on_all_completed.
    Ne koristi spec=AgentController jer se draft/faktura_tab instanciraju u __init__
    i spec ih blokira (MagicMock sa spec dozvoljava samo definisane atribute)."""
    mock_self = MagicMock()
    mock_self._current_mode = mode
    mock_self._worker = None
    mock_self.draft = DeclarationDraft()

    # FileItem mock
    file_item = MagicMock()
    file_item.status = "Completed"
    file_item.invoice_lines = [_make_invoice_line()]
    file_item.invoice_lines[0].zemlja_porijekla = ""
    file_item.invoice_lines[0].has_origin_statement = False
    file_item.invoice_lines[0].eur1_number = ""
    file_item.invoice_number = "INV-001"
    file_item.filepath = "INV-001.pdf"
    file_item.file_type = "PDF"
    file_item.is_combined = False
    file_item.consumed_paths = []
    file_item.has_origin_statement = False
    file_item.is_authorized_exporter = False
    file_item.eur1_suggested = False
    file_item.bruto_kg = 10.0
    file_item.neto_kg = 9.0
    file_item.detected_parser = "test"
    file_item.parser = "test"
    file_item.exporter = None
    file_item.importer = None
    file_item.currency = ""

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
    """Dokumentuje Agent uvoz nakon povezivanja na zajednički import workflow."""

    def test_normalizuje_tarife_kroz_zajednicki_plan(self):
        """Agent uvoz normalizuje tarifne brojeve kroz prepare_import."""
        from gui.tabs.agent.agent_controller import AgentController
        mock_self, file_item, fw, chat = _mock_self_for_agent_import()
        file_item.invoice_lines[0].tarifni_broj = "3824993"
        with patch("gui.tabs.faktura_view.QMessageBox"), \
             patch("gui.tabs.agent.agent_controller.QApplication"), \
             patch("gui.tabs.agent.services.import_pipeline_service._origin_dialog_type",
                   return_value=None):
            AgentController._on_all_completed(mock_self, [file_item])
        assert mock_self.draft.invoice_lines[0].tarifni_broj == "03824993"

    def test_popunjava_zaglavlje_kroz_zajednicku_primjenu(self):
        """Agent uvoz popunjava header kroz apply_import_plan."""
        from gui.tabs.agent.agent_controller import AgentController
        mock_self, file_item, fw, chat = _mock_self_for_agent_import()
        file_item.exporter = Party(
            name="IZVOZNIK DOO",
            address="Adresa izvoznika",
            city="Sofia",
            country="BG",
        )
        file_item.importer = Party(
            name="UVOZNIK DOO",
            address="Adresa primaoca",
            city="Banja Luka",
            country="BA",
            vat_or_id="4000000000000",
        )
        with patch("gui.tabs.faktura_view.QMessageBox"), \
             patch("gui.tabs.agent.agent_controller.QApplication"), \
             patch("gui.tabs.agent.services.import_pipeline_service._origin_dialog_type",
                   return_value=None):
            AgentController._on_all_completed(mock_self, [file_item])
        assert mock_self.draft.izvoznik_naziv == "IZVOZNIK DOO"
        assert mock_self.draft.izvoznik_grad == "Sofia"
        assert mock_self.draft.primalac_naziv == "UVOZNIK DOO"
        assert mock_self.draft.primalac_id == "4000000000000"

    def test_rasporedjuje_tezine_kroz_zajednicku_primjenu(self):
        """Agent uvoz raspoređuje bruto/neto mase kroz MassCalculator."""
        from gui.tabs.agent.agent_controller import AgentController
        mock_self, file_item, fw, chat = _mock_self_for_agent_import()
        file_item.invoice_lines[0].bruto_kg = 0.0
        file_item.invoice_lines[0].neto_kg = 0.0
        with patch("gui.tabs.faktura_view.QMessageBox"), \
             patch("gui.tabs.agent.agent_controller.QApplication"), \
             patch("gui.tabs.agent.services.import_pipeline_service._origin_dialog_type",
                   return_value=None):
            AgentController._on_all_completed(mock_self, [file_item])
        assert mock_self.draft.invoice_lines[0].bruto_kg == pytest.approx(10.0)
        assert mock_self.draft.invoice_lines[0].neto_kg == pytest.approx(9.0)

    def test_partner_konflikt_ide_kroz_zajednicku_potvrdu(self):
        """Agent uvoz više ne preskače provjeru partnera."""
        from gui.tabs.agent.agent_controller import AgentController
        mock_self, file_item, fw, chat = _mock_self_for_agent_import()
        mock_self.draft.izvoznik_naziv = "POSTOJECI IZVOZNIK"
        file_item.exporter = Party(name="NOVI IZVOZNIK")
        with patch("gui.tabs.faktura_view.QMessageBox"), \
             patch("gui.tabs.agent.agent_controller.QApplication"), \
             patch("gui.tabs.faktura_view.FakturaView._confirm_import_partner_conflicts",
                   return_value=True) as confirm_partner, \
             patch("gui.tabs.agent.services.import_pipeline_service._origin_dialog_type",
                   return_value=None):
            AgentController._on_all_completed(mock_self, [file_item])
        confirm_partner.assert_called_once()

    def test_isti_broj_fakture_radi_replace_umjesto_duplikata(self):
        """Agent uvoz koristi istu REPLACE logiku za postojeću fakturu."""
        from gui.tabs.agent.agent_controller import AgentController
        mock_self, file_item, fw, chat = _mock_self_for_agent_import()
        mock_self.draft.invoice_lines.append(
            _make_invoice_line(invoice_number="INV-001", naziv_robe="Stara stavka")
        )
        mock_self.draft.invoice_weights["inv-001"] = (1.0, 1.0)
        file_item.invoice_lines[0].naziv_robe = "Nova stavka"
        with patch("gui.tabs.faktura_view.QMessageBox"), \
             patch("gui.tabs.agent.agent_controller.QApplication"), \
             patch("gui.tabs.agent.services.import_pipeline_service._origin_dialog_type",
                   return_value=None):
            AgentController._on_all_completed(mock_self, [file_item])
        assert len(mock_self.draft.invoice_lines) == 1
        assert mock_self.draft.invoice_lines[0].naziv_robe == "Nova stavka"

    def test_dodjeljuje_invoice_number_kad_stavka_nema_broj(self):
        """Agent uvoz koristi zajedničku politiku dodjele broja fakture."""
        from gui.tabs.agent.agent_controller import AgentController
        mock_self, file_item, fw, chat = _mock_self_for_agent_import()
        file_item.invoice_lines[0].invoice_number = ""
        with patch("gui.tabs.faktura_view.QMessageBox"), \
             patch("gui.tabs.agent.agent_controller.QApplication"), \
             patch("gui.tabs.agent.services.import_pipeline_service._origin_dialog_type",
                   return_value=None):
            AgentController._on_all_completed(mock_self, [file_item])
        assert mock_self.draft.invoice_lines[0].invoice_number == "INV-001"

    def test_ne_cisti_draft_po_fakturi_nego_primjenjuje_plan(self):
        """Agent uvoz više ne radi per-file clear, nego ADD/REPLACE kroz plan."""
        from gui.tabs.agent.agent_controller import AgentController
        mock_self, file_item, fw, chat = _mock_self_for_agent_import()
        file_item_2 = MagicMock()
        file_item_2.status = "Completed"
        file_item_2.invoice_lines = [
            _make_invoice_line(invoice_number="INV-002", naziv_robe="Druga faktura")
        ]
        file_item_2.invoice_lines[0].zemlja_porijekla = ""
        file_item_2.invoice_number = "INV-002"
        file_item_2.filepath = "INV-002.pdf"
        file_item_2.file_type = "PDF"
        file_item_2.is_combined = False
        file_item_2.consumed_paths = []
        file_item_2.has_origin_statement = False
        file_item_2.is_authorized_exporter = False
        file_item_2.eur1_suggested = False
        file_item_2.bruto_kg = 2.0
        file_item_2.neto_kg = 1.0
        file_item_2.detected_parser = "test"
        file_item_2.parser = "test"
        file_item_2.exporter = None
        file_item_2.importer = None
        file_item_2.currency = ""
        with patch("gui.tabs.faktura_view.QMessageBox"), \
             patch("gui.tabs.agent.agent_controller.QApplication"), \
             patch("gui.tabs.agent.services.import_pipeline_service._origin_dialog_type",
                   return_value=None):
            AgentController._on_all_completed(mock_self, [file_item, file_item_2])
        assert [line.invoice_number for line in mock_self.draft.invoice_lines] == [
            "INV-001",
            "INV-002",
        ]
