"""
Test za AgentController._on_all_completed — istorijska tarifna provjera
ODMAH nakon agent uvoza (2026-07-22).

Korisnička primjedba: agent uvoz (rutu "Uvezi u deklaraciju") NIJE pokretao
automatsku provjeru čak ni nakon što je FakturaView._on_import_finished/
_process_batch_records ispravljen da je uvijek zove — jer agent uvoz ide
kroz POTPUNO ODVOJEN kod-put (AgentController._on_all_completed), koji
popunjava draft/tabelu direktno (fw._load_data_from_draft()), bez ikad
prolaska kroz _on_import_finished/_process_batch_records (Qt signal
handleri vezani za obični GUI ImportWorker, ne agent processing_worker).

"Puna automatizacija" grana već ima svoj poziv (_puna_auto_pipeline ->
_on_validate_all(auto=True), tih/log-only). Ova grana ("Uvezi u
deklaraciju" — sve OSTALE agent rute) prije fixa nije imala NIŠTA.

MainWindow.closeEvent test (test_main_window_close_event.py) je isti obrazac:
nevezana metoda se poziva direktno na MagicMock "self" da se izbjegne teška
inicijalizacija cijelog AgentController-a.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from gui.tabs.agent.agent_controller import AgentController


def _file_item(invoice_number: str = "1476/26") -> MagicMock:
    item = MagicMock()
    item.status = "Completed"
    item.invoice_lines = [MagicMock(naziv_robe="SUSSINA 650 tbl.", tarifni_broj="38249993")]
    item.is_combined = False
    item.consumed_paths = []
    item.invoice_number = invoice_number
    item.filepath = f"{invoice_number}.pdf"
    item.has_origin_statement = False
    item.is_authorized_exporter = False
    item.bruto_kg = 0.0
    item.neto_kg = 0.0
    return item


def _mock_controller(current_mode: str) -> tuple[MagicMock, MagicMock]:
    ctrl = MagicMock()
    ctrl._current_mode = current_mode
    ctrl.draft.invoice_lines = []
    ctrl.draft.invoice_weights = {}
    ctrl._dedupe_completed_import_files.side_effect = lambda completed: completed
    ctrl._proactive_analysis.return_value = "test analiza"
    ctrl.view.parent.return_value = None

    fw = MagicMock()
    ctrl.faktura_tab.view = fw
    return ctrl, fw


def test_agent_uvezi_u_deklaraciju_pokrece_provjeru_nakon_uvoza():
    ctrl, fw = _mock_controller(current_mode="Uvezi u deklaraciju")

    AgentController._on_all_completed(ctrl, [_file_item()])

    fw._run_historical_tariff_validation.assert_called_once_with(auto=False)


def test_agent_puna_automatizacija_ne_duplira_eager_poziv():
    """
    Puna automatizacija grana ima SVOJ poziv preko _puna_auto_pipeline
    (koji kasnije zove _on_validate_all(auto=True), tih/log-only) — eager
    interaktivni poziv (auto=False) se NE dodaje u ovu granu da ne prikaže
    modal usred inače potpuno automatizovanog toka.
    """
    ctrl, fw = _mock_controller(current_mode="Puna automatizacija")

    AgentController._on_all_completed(ctrl, [_file_item()])

    fw._run_historical_tariff_validation.assert_not_called()
    ctrl._puna_auto_pipeline.assert_called_once()
