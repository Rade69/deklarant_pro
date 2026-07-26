"""
Testovi za HistoricalValidationWorker i njegovu integraciju sa FakturaView
(Codex analiza faktura taba, nalaz 2b — istorijska validacija tarifa je
blokirala UI thread poslije svakog importa preko DB upita po stavci; sad se
radi u pozadinskom QThread-u, vidi docs/CONTEXT.md §59).
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication

from services.historical_validation_worker import HistoricalValidationWorker
from services.agent.validation.historical_tariff_search_service import (
    HistoricalTariffSearchService,
    TariffHistoryMatch,
)
from gui.tabs.faktura_view import FakturaView
from gui.main_window import MainWindow


def _match(line_index=0, tarifni_broj_historijski="12345678"):
    return TariffHistoryMatch(
        line_index=line_index,
        naziv_robe_original="ROBA",
        naziv_robe_historijski="ROBA",
        tarifni_broj_historijski=tarifni_broj_historijski,
        tarifni_broj_trenutni="",
        supplier_match=True,
        usage_count=3,
        source="test.xml",
        confidence=0.9,
    )


def _app():
    return QApplication.instance() or QApplication([])


def test_worker_emits_finished_validation_with_matches(qtbot):
    _app()
    matches = [_match()]
    with patch.object(HistoricalTariffSearchService, "validate_lines", return_value=matches):
        worker = HistoricalValidationWorker([], izvoznik_naziv="X", uvoznik_naziv="Y")
        with qtbot.waitSignal(worker.finished_validation, timeout=3000) as blocker:
            worker.start()
        assert blocker.args[0] == matches
        assert blocker.args[1] == []
        assert blocker.args[2] == []
    worker.wait(1000)


def test_worker_emits_error_occurred_on_exception(qtbot):
    _app()
    with patch.object(
        HistoricalTariffSearchService, "validate_lines", side_effect=RuntimeError("DB down")
    ):
        worker = HistoricalValidationWorker([])
        with qtbot.waitSignal(worker.error_occurred, timeout=3000) as blocker:
            worker.start()
        assert "DB down" in blocker.args[0]
    worker.wait(1000)


def test_worker_emits_error_when_last_db_error_set_even_with_empty_matches(qtbot):
    """
    validate_lines() vraca [] BEZ izuzetka (DB greska po liniji se hvata
    unutar servisa) - worker mora provjeriti last_db_error i emitovati
    error_occurred umjesto finished_validation, inace izgleda kao
    "provjereno, nema prijedloga" (2026-07-26, SUSSINA slucaj).
    """
    _app()

    def _fake_validate_lines(self, *args, **kwargs):
        self.last_db_error = "connection to server failed: timeout expired"
        return []

    with patch.object(HistoricalTariffSearchService, "validate_lines", _fake_validate_lines):
        worker = HistoricalValidationWorker([])
        with qtbot.waitSignal(worker.error_occurred, timeout=3000) as blocker:
            worker.start()
        assert "nedostupna" in blocker.args[0] or "timeout" in blocker.args[0]
    worker.wait(1000)


def test_worker_cancel_before_start_skips_validate_lines(qtbot):
    _app()
    with patch.object(HistoricalTariffSearchService, "validate_lines") as mock_validate:
        worker = HistoricalValidationWorker([])
        worker.cancel()
        worker.start()
        worker.wait(2000)
        mock_validate.assert_not_called()


def _fake_faktura_self(token: int, generation: int):
    fake = type("FakeFakturaSelf", (), {})()
    fake._historical_validation_token = token
    fake._validation_generation = generation
    fake.draft = MagicMock()
    fake.draft.invoice_lines = []
    fake.table = MagicMock()
    fake._set_table_item = MagicMock()
    fake._validate_and_color_row = MagicMock()
    fake._update_status_bar = MagicMock()
    fake._notify_auto_applied_tariffs = MagicMock()
    fake._notify_auto_rejected_tariffs = MagicMock()
    fake.window = MagicMock(return_value=None)
    return fake


def test_on_historical_validation_finished_discards_stale_token():
    """Rezultat kasnijeg 'Provjeri' klika ne smije primijeniti stariji worker."""
    fake_self = _fake_faktura_self(token=5, generation=1)
    with patch("PySide6.QtWidgets.QMessageBox.information") as mock_info:
        FakturaView._on_historical_validation_finished(
            fake_self,
            matches=[_match()],
            auto_applied=[(0, "12345678")],
            auto_rejected=[],
            row_indexes=None,
            auto=False,
            modal=False,
            token=4,  # stariji poziv — trenutni token je 5
            generation=1,
        )
    fake_self.table.blockSignals.assert_not_called()
    fake_self._notify_auto_applied_tariffs.assert_not_called()
    mock_info.assert_not_called()


def test_on_historical_validation_finished_discards_stale_generation():
    """Rezultat se odbacuje ako je draft promijenjen (reload) dok je worker radio."""
    fake_self = _fake_faktura_self(token=1, generation=3)
    with patch("PySide6.QtWidgets.QMessageBox.information") as mock_info:
        FakturaView._on_historical_validation_finished(
            fake_self,
            matches=[_match()],
            auto_applied=[(0, "12345678")],
            auto_rejected=[],
            row_indexes=None,
            auto=False,
            modal=False,
            token=1,
            generation=2,  # stara generacija — draft je otad reloadovan
        )
    fake_self.table.blockSignals.assert_not_called()
    fake_self._notify_auto_applied_tariffs.assert_not_called()
    mock_info.assert_not_called()


def test_on_historical_validation_error_prikazuje_dijalog_kad_nije_auto():
    fake_self = type("FakeFakturaSelf", (), {})()
    with patch("gui.tabs.faktura_view.QMessageBox") as mock_msgbox:
        FakturaView._on_historical_validation_error(fake_self, "Baza nedostupna", auto=False)
    mock_msgbox.warning.assert_called_once()


def test_on_historical_validation_error_tih_kad_je_auto():
    fake_self = type("FakeFakturaSelf", (), {})()
    with patch("gui.tabs.faktura_view.QMessageBox") as mock_msgbox:
        FakturaView._on_historical_validation_error(fake_self, "Baza nedostupna", auto=True)
    mock_msgbox.warning.assert_not_called()


def test_shutdown_agent_workers_stops_both_agent_and_faktura_worker():
    """MainWindow._shutdown_agent_workers mora ugasiti i Agent i Faktura worker (nalaz 6b)."""
    agent_worker = MagicMock()
    agent_worker.isRunning.return_value = True
    agent_worker.wait.return_value = True

    faktura_worker = MagicMock()
    faktura_worker.isRunning.return_value = True
    faktura_worker.wait.return_value = True

    fake_window = type("FakeWindow", (), {})()
    fake_window.agent_tab = type("AgentTab", (), {})()
    fake_window.agent_tab.controller = type("Controller", (), {"_worker": agent_worker})()
    fake_window.faktura_tab = type("FakturaTab", (), {})()
    fake_window.faktura_tab.view = type(
        "View", (), {"historical_validation_worker": faktura_worker}
    )()

    MainWindow._shutdown_agent_workers(fake_window)

    agent_worker.cancel.assert_called_once()
    agent_worker.quit.assert_called_once()
    faktura_worker.cancel.assert_called_once()
    faktura_worker.quit.assert_called_once()
