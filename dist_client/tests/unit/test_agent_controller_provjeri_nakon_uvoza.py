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
validate(auto=True), tih/log-only). Ova grana ("Uvezi u
deklaraciju" — sve OSTALE agent rute) prije fixa nije imala NIŠTA.

MainWindow.closeEvent test (test_main_window_close_event.py) je isti obrazac:
nevezana metoda se poziva direktno na MagicMock "self" da se izbjegne teška
inicijalizacija cijelog AgentController-a.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from core.draft.draft import DeclarationDraft
from gui.tabs.agent.agent_controller import AgentController


def _file_item(invoice_number: str = "1476/26") -> MagicMock:
    item = MagicMock()
    item.status = "Completed"
    line = MagicMock(naziv_robe="SUSSINA 650 tbl.", tarifni_broj="38249993")
    line.zemlja_porijekla = ""
    line.has_origin_statement = False
    line.eur1_number = ""
    item.invoice_lines = [line]
    item.is_combined = False
    item.consumed_paths = []
    item.invoice_number = invoice_number
    item.filepath = f"{invoice_number}.pdf"
    item.has_origin_statement = False
    item.is_authorized_exporter = False
    item.eur1_suggested = False
    item.bruto_kg = 0.0
    item.neto_kg = 0.0
    item.exporter = None
    item.importer = None
    item.currency = ""
    return item


def _mock_controller(current_mode: str) -> tuple[MagicMock, MagicMock]:
    ctrl = MagicMock()
    ctrl._current_mode = current_mode
    ctrl.draft = DeclarationDraft()
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
    Puna automatizacija grana NE dodaje eager interaktivni poziv
    (_run_historical_tariff_validation(auto=False)) — validacija je dio
    orkestratora ispod (tih/log-only), ne odvojen modal usred automatizovanog
    toka.
    """
    ctrl, fw = _mock_controller(current_mode="Puna automatizacija")

    with patch(
        "services.agent.workflow.declaration_workflow_service.run_declaration_workflow"
    ):
        AgentController._on_all_completed(ctrl, [_file_item()])

    fw._run_historical_tariff_validation.assert_not_called()


def test_agent_puna_automatizacija_poziva_orkestrator_do_kraja():
    """
    Popravka (2026-07-27): "Puna automatizacija" prije je pozivala
    _puna_auto_pipeline direktno i STAJALA nakon naimenovanja — zaglavlje,
    cross-tab provjera, XML readiness i izvoz su ostajali identično ručni
    kao u modu "Uvezi u deklaraciju" (korisnička primjedba: režim praktično
    beskoristan). Sad poziva run_declaration_workflow, koji iznutra ponovo
    koristi _puna_auto_pipeline za mase/tarife/validaciju/naimenovanja, a
    zatim NASTAVLJA do XML izvoza.
    """
    ctrl, fw = _mock_controller(current_mode="Puna automatizacija")
    ctrl._declaration_workflow_running = False

    # Import unutar metode je odgodjen (deferred) — patch cilja na izvorni
    # modul odakle se import radi u trenutku poziva, ne na agent_controller.
    with patch(
        "services.agent.workflow.declaration_workflow_service.run_declaration_workflow"
    ) as mock_run:
        AgentController._on_all_completed(ctrl, [_file_item()])

    mock_run.assert_called_once()
    args, kwargs = mock_run.call_args
    assert args[0] is ctrl
    assert kwargs.get("fw") is fw


def test_agent_puna_automatizacija_vraca_fokus_na_agent_tab_nakon_workflowa():
    """
    Popravka (2026-07-27, drugi krug): korisnik je uživo testirao i prijavio
    da "Puna automatizacija" i dalje izgleda identično kao prije — jer
    puna_auto_pipeline (pozvana IZNUTRA run_declaration_workflow) sama na
    svom kraju prebacuje fokus na Faktura tab
    (_otvori_faktura_tab_nakon_uvoza), a workflow zatim NASTAVLJA (zaglavlje/
    cross-tab/xml preflight/izvoz) NAKON tog prebacivanja — sve te poruke su
    ostajale nevidljive jer je korisnik gledao Faktura tab, ne Agent chat.
    Fix: nakon run_declaration_workflow, fokus se vraća na Agent tab
    (self.view.parent()) da se vidi stvaran ishod cijelog workflowa.
    """
    ctrl, fw = _mock_controller(current_mode="Puna automatizacija")
    ctrl._declaration_workflow_running = False

    class FakeMainWindow:
        pass

    main_window = FakeMainWindow()
    tabs_widget = MagicMock()
    main_window.findChildren = MagicMock(return_value=[tabs_widget])
    ctrl.view.parent.return_value = main_window

    with patch(
        "services.agent.workflow.declaration_workflow_service.run_declaration_workflow"
    ):
        AgentController._on_all_completed(ctrl, [_file_item()])

    calls = tabs_widget.setCurrentWidget.call_args_list
    assert len(calls) >= 2, "ocekivan i prebacaj na Faktura tab i povratak na Agent tab"
    assert calls[0].args[0] is ctrl.faktura_tab
    assert calls[-1].args[0] is main_window
