"""
Testovi za _puna_auto_pipeline (Faza C — pouzdan status pune automatizacije).

Vidi: docs/agent/AGENT_MODE_IMPROVEMENT_IMPLEMENTATION_PLAN.md §7
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from gui.tabs.agent.services.import_pipeline_service import _puna_auto_pipeline
from gui.tabs.agent.services import import_pipeline_service as ips


def _line(tarifni_broj="12345678", bruto_kg=0, neto_kg=0):
    # bruto_kg/neto_kg=0 podrazumijevano (ne None/MagicMock auto-attribut,
    # koji bi bio uvijek truthy i lažno "preskočio" fazu mase — vidi
    # TestPreskociMaseAkoVecPopunjene ispod) — odražava svježe uvezenu
    # stavku bez izračunate mase.
    return MagicMock(tarifni_broj=tarifni_broj, bruto_kg=bruto_kg, neto_kg=neto_kg)


@pytest.fixture
def mock_ctrl():
    ctrl = MagicMock()
    ctrl.draft.invoice_lines = [_line(), _line()]
    ctrl.draft.items = []
    return ctrl


@pytest.fixture
def mock_fw():
    fw = MagicMock()
    fw.calculate_masses.return_value = True
    fw._on_calculate_masses.return_value = True
    fw.auto_fill.return_value = MagicMock(matched_items=1)
    fw._on_auto_fill.return_value = MagicMock(matched_items=1)
    fw.validate.return_value = (True, 0, 0)
    fw._on_validate_all.return_value = (True, 0, 0)
    fw.create_naimenovanja.return_value = True
    fw._on_create_naimenovanja.return_value = True
    return fw


@pytest.fixture
def mock_chat():
    return MagicMock()


def _agent_messages(chat) -> list[str]:
    return [call.args[0] for call in chat.add_agent_message.call_args_list]


@pytest.fixture(autouse=True)
def _confirm_declarant(monkeypatch):
    """Default: deklarant potvrđuje korak 4 (Yes). Testovi mogu override-ovati."""
    monkeypatch.setattr(ips.QMessageBox, "question", lambda *a, **kw: ips.QMessageBox.Yes)


@pytest.fixture(autouse=True)
def completion_sound(monkeypatch):
    sound = MagicMock()
    monkeypatch.setattr(
        "services.process_completion_sound.play_process_completion_sound",
        sound,
    )
    return sound


class TestCekanjeNaIstorijskuValidaciju:
    """
    Popravka (2026-07-27): _on_validate_all(auto=True) iznutra pokreće
    HistoricalValidationWorker kao fire-and-forget QThread i vraća se ODMAH
    — bez čekanja, "Puna automatizacija" je nastavljala na EUR.1/PE potvrdu
    i kreiranje naimenovanja dok je taj worker još radio (korisnička
    primjedba: "Nije završen proces u tabu faktura").
    """

    def test_ceka_pravi_qthread_da_zavrsi(self, qtbot):
        """isRunning() na MagicMock-u je uvijek truthy (lažan pozitivan async
        gap) — _wait_for_historical_validation mora raditi sa STVARNIM
        QThread-om, ne samo formalno "pozvati isRunning()"."""
        import time
        from PySide6.QtCore import QThread

        class _SlowWorker(QThread):
            def run(self):
                time.sleep(0.3)

        fw = MagicMock()
        worker = _SlowWorker()
        fw.historical_validation_worker = worker
        worker.start()
        assert worker.isRunning()

        waited = ips._wait_for_historical_validation(fw, timeout_ms=5000)

        assert waited is True
        assert not worker.isRunning()

    def test_ne_ceka_kad_nema_workera(self):
        fw = MagicMock()
        fw.historical_validation_worker = None
        assert ips._wait_for_historical_validation(fw) is False

    def test_ne_ceka_na_magicmock_worker(self):
        """MagicMock() nije QThread instanca — mora se preskočiti bez čekanja
        (regresija bi ovdje visila do timeout-a u svakom testu ove svite)."""
        fw = MagicMock()
        assert ips._wait_for_historical_validation(fw, timeout_ms=100) is False


class TestUspjesanTok:
    def test_sve_faze_uspjesne_daje_zavrsnu_poruku(
        self, mock_ctrl, mock_fw, mock_chat, completion_sound
    ):
        mock_ctrl.draft.items = [MagicMock()]

        _puna_auto_pipeline(mock_ctrl, mock_fw, mock_chat, [])

        messages = _agent_messages(mock_chat)
        assert any("Puna automatizacija završena!" in m for m in messages)
        assert not any("zaustavljena" in m or "djelimično" in m for m in messages)
        mock_fw.calculate_masses.assert_called_once_with(auto=True)
        mock_fw._on_calculate_masses.assert_not_called()
        mock_fw.validate.assert_called_once_with(auto=True)
        mock_fw._on_validate_all.assert_not_called()
        mock_fw.create_naimenovanja.assert_called_once_with(auto=True)
        mock_fw._on_create_naimenovanja.assert_not_called()
        completion_sound.assert_called_once_with("success")

    def test_preskace_auto_popuni_kad_sve_stavke_imaju_tarifu(self, mock_ctrl, mock_fw, mock_chat):
        _puna_auto_pipeline(mock_ctrl, mock_fw, mock_chat, [])
        mock_fw.auto_fill.assert_not_called()


class TestJavniApiIFallback:
    def test_javni_api_pokriva_sve_agent_faze_prije_private_fallbacka(
        self, mock_ctrl, mock_fw, mock_chat
    ):
        line = _line(tarifni_broj="", bruto_kg=0, neto_kg=0)
        mock_ctrl.draft.invoice_lines = [line]
        mock_ctrl.draft.items = [MagicMock()]

        def _auto_fill(auto=False):
            line.tarifni_broj = "12345678"
            return MagicMock(matched_items=1)

        mock_fw.auto_fill.side_effect = _auto_fill

        _puna_auto_pipeline(mock_ctrl, mock_fw, mock_chat, [])

        mock_fw.calculate_masses.assert_called_once_with(auto=True)
        mock_fw.auto_fill.assert_called_once_with(auto=True)
        mock_fw.validate.assert_called_once_with(auto=True)
        mock_fw.create_naimenovanja.assert_called_once_with(auto=True)
        mock_fw._on_calculate_masses.assert_not_called()
        mock_fw._on_auto_fill.assert_not_called()
        mock_fw._on_validate_all.assert_not_called()
        mock_fw._on_create_naimenovanja.assert_not_called()

    def test_bez_javnog_api_zaustavlja_bez_private_fallbacka(
        self, mock_ctrl, mock_chat, completion_sound
    ):
        line = _line(tarifni_broj="", bruto_kg=0, neto_kg=0)
        mock_ctrl.draft.invoice_lines = [line]
        mock_ctrl.draft.items = [MagicMock()]

        class LegacyFakturaView:
            def __init__(self):
                self._on_calculate_masses = MagicMock(return_value=True)
                self._on_auto_fill = MagicMock(side_effect=self._auto_fill)
                self._on_validate_all = MagicMock(return_value=(True, 0, 0))
                self._on_create_naimenovanja = MagicMock(return_value=True)

            def _auto_fill(self, auto=False):
                line.tarifni_broj = "12345678"
                return MagicMock(matched_items=1)

        fw = LegacyFakturaView()

        _puna_auto_pipeline(mock_ctrl, fw, mock_chat, [])

        fw._on_calculate_masses.assert_not_called()
        fw._on_auto_fill.assert_not_called()
        fw._on_validate_all.assert_not_called()
        fw._on_create_naimenovanja.assert_not_called()
        messages = _agent_messages(mock_chat)
        assert any("zaustavljena" in m and "mase" in m for m in messages)
        completion_sound.assert_called_once_with("error")


class TestPreskociMaseAkoVecPopunjene:
    """
    Popravka (2026-07-28): _on_calculate_masses(auto=True) vraća False i
    kad NEMA šta da se preračuna (sve stavke već imaju obje težine —
    faktura_view.py:5180 "updated_count == 0"), ne samo pri stvarnom padu.
    _puna_auto_pipeline je taj benigni "nema šta da se radi" ishod tretirala
    kao fatalan pad i lažno zaustavljala cijelu automatizaciju — korisnička
    primjedba: mase su ispravno prikazane u tabeli (npr. parser koji
    ekstraktuje bruto/neto direktno po stavci), a pipeline ipak javlja
    "Izračun masa nije uspio".
    """

    def test_ne_poziva_calculate_masses_kad_sve_stavke_vec_imaju_masu(
        self, mock_ctrl, mock_fw, mock_chat,
    ):
        mock_ctrl.draft.invoice_lines = [
            _line(bruto_kg=5.58, neto_kg=5.13),
            _line(bruto_kg=1.90, neto_kg=1.75),
        ]
        mock_ctrl.draft.items = [MagicMock()]

        _puna_auto_pipeline(mock_ctrl, mock_fw, mock_chat, [])

        mock_fw.calculate_masses.assert_not_called()
        messages = _agent_messages(mock_chat)
        assert not any("zaustavljena" in m for m in messages)

    def test_poziva_calculate_masses_kad_bar_jedna_stavka_nema_masu(
        self, mock_ctrl, mock_fw, mock_chat,
    ):
        mock_ctrl.draft.invoice_lines = [
            _line(bruto_kg=5.58, neto_kg=5.13),
            _line(bruto_kg=0, neto_kg=0),
        ]
        mock_ctrl.draft.items = [MagicMock()]

        _puna_auto_pipeline(mock_ctrl, mock_fw, mock_chat, [])

        mock_fw.calculate_masses.assert_called_once_with(auto=True)
        mock_fw._on_calculate_masses.assert_not_called()


class TestKritickeFazePadaju:
    """Kriticna greska (mase / validacija-fail / naimenovanja) mora zaustaviti
    pipeline PRIJE sljedece faze — ne smije se nastaviti sa "except -> warn -> nastavi"."""

    def test_pad_izracuna_masa_zaustavlja_sve_naredne_faze(
        self, mock_ctrl, mock_fw, mock_chat, completion_sound
    ):
        mock_fw.calculate_masses.return_value = False

        _puna_auto_pipeline(mock_ctrl, mock_fw, mock_chat, [])

        mock_fw.auto_fill.assert_not_called()
        mock_fw.validate.assert_not_called()
        mock_fw.create_naimenovanja.assert_not_called()
        messages = _agent_messages(mock_chat)
        assert any("zaustavljena" in m and "mase" in m for m in messages)
        assert not any("završena!" in m for m in messages)
        completion_sound.assert_called_once_with("error")

    def test_izuzetak_u_izracunu_masa_ne_probija_pipeline(self, mock_ctrl, mock_fw, mock_chat):
        """Ako View metoda baci izuzetak (a ne samo vrati False), pipeline i
        dalje mora ispravno zaustaviti — ne propagirati izuzetak dalje."""
        mock_fw.calculate_masses.side_effect = RuntimeError("neočekivano")

        _puna_auto_pipeline(mock_ctrl, mock_fw, mock_chat, [])  # ne smije baciti

        mock_fw.create_naimenovanja.assert_not_called()

    def test_validacija_sa_kritickim_greskama_zaustavlja_prije_naimenovanja(
        self, mock_ctrl, mock_fw, mock_chat
    ):
        mock_fw.validate.return_value = (True, 3, 1)  # 3 kritične greške

        _puna_auto_pipeline(mock_ctrl, mock_fw, mock_chat, [])

        mock_fw.create_naimenovanja.assert_not_called()
        messages = _agent_messages(mock_chat)
        assert any("zaustavljena" in m and "validacija" in m for m in messages)

    def test_validacija_koja_ne_moze_biti_izvrsena_zaustavlja(self, mock_ctrl, mock_fw, mock_chat):
        mock_fw.validate.return_value = (False, -1, -1)

        _puna_auto_pipeline(mock_ctrl, mock_fw, mock_chat, [])

        mock_fw.create_naimenovanja.assert_not_called()

    def test_pad_kreiranja_naimenovanja_ne_prijavljuje_lazan_uspjeh(self, mock_ctrl, mock_fw, mock_chat):
        mock_fw.create_naimenovanja.return_value = False

        _puna_auto_pipeline(mock_ctrl, mock_fw, mock_chat, [])

        messages = _agent_messages(mock_chat)
        assert any("zaustavljena" in m and "naimenovanja" in m for m in messages)
        assert not any("završena!" in m for m in messages)


class TestDeklarantskaPotvrda:
    def test_odbijena_potvrda_ne_kreira_naimenovanja_i_ne_javlja_zavrseno(
        self, mock_ctrl, mock_fw, mock_chat, monkeypatch, completion_sound
    ):
        monkeypatch.setattr(ips.QMessageBox, "question", lambda *a, **kw: ips.QMessageBox.No)

        _puna_auto_pipeline(mock_ctrl, mock_fw, mock_chat, [])

        mock_fw.create_naimenovanja.assert_not_called()
        messages = _agent_messages(mock_chat)
        assert any("pauzirana" in m for m in messages)
        assert not any("završena!" in m or "zaustavljena" in m for m in messages)
        completion_sound.assert_not_called()


class TestParcijalniRezultat:
    def test_nerijesene_tarife_daju_djelimican_zavrsetak_ali_nastavlja(
        self, mock_ctrl, mock_fw, mock_chat
    ):
        mock_ctrl.draft.invoice_lines = [_line(tarifni_broj=""), _line(tarifni_broj="12345678")]
        mock_fw.auto_fill.return_value = MagicMock(matched_items=0)  # ništa novo popunjeno

        _puna_auto_pipeline(mock_ctrl, mock_fw, mock_chat, [])

        messages = _agent_messages(mock_chat)
        assert any("djelimično" in m for m in messages)
        assert not any("završena!" in m for m in messages)
        # PARTIAL i dalje nastavlja do kraja — naimenovanja se kreiraju
        mock_fw.auto_fill.assert_called_once_with(auto=True)
        mock_fw._on_auto_fill.assert_not_called()
        mock_fw.create_naimenovanja.assert_called_once_with(auto=True)
        mock_fw._on_create_naimenovanja.assert_not_called()

    def test_validacija_sa_samo_upozorenjima_nastavlja_i_daje_partial(
        self, mock_ctrl, mock_fw, mock_chat, completion_sound
    ):
        mock_fw.validate.return_value = (True, 0, 2)  # 0 grešaka, 2 upozorenja

        _puna_auto_pipeline(mock_ctrl, mock_fw, mock_chat, [])

        mock_fw.create_naimenovanja.assert_called_once_with(auto=True)
        mock_fw._on_create_naimenovanja.assert_not_called()
        messages = _agent_messages(mock_chat)
        assert any("djelimično" in m for m in messages)
        completion_sound.assert_called_once_with("warning")
