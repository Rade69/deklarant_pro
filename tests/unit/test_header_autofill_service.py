"""
Testovi za header_autofill_service — auto-popuna Izvoznik/Primalac/Deklarant
iz istorijskog XML-a (isti mehanizam kao dugme "Uvezi XML").
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from core.draft.draft import DeclarationDraft
from services.agent.workflow import header_autofill_service as svc


def _draft(izvoznik: str = "MEDICO PHARM SERVIS") -> DeclarationDraft:
    d = DeclarationDraft()
    d.izvoznik_naziv = izvoznik
    return d


def _chat():
    chat = MagicMock()
    chat.add_activity = MagicMock()
    return chat


class TestBezIzvoznika:

    def test_bez_izvoznika_ne_radi_nista(self):
        ctrl = MagicMock()
        ctrl.draft = DeclarationDraft()
        assert svc.auto_fill_header_from_history(ctrl, _chat()) is False


class TestNemaPogotka:

    def test_find_xml_for_pair_vraca_none(self, monkeypatch):
        monkeypatch.setattr(
            "services.agent.learning.exporter_xml_indexer.find_xml_for_pair",
            lambda *a, **kw: None,
        )
        ctrl = MagicMock()
        ctrl.draft = _draft()
        assert svc.auto_fill_header_from_history(ctrl, _chat()) is False

    def test_find_xml_for_pair_baca_izuzetak(self, monkeypatch):
        def _boom(*a, **kw):
            raise RuntimeError("baza nedostupna")

        monkeypatch.setattr(
            "services.agent.learning.exporter_xml_indexer.find_xml_for_pair", _boom
        )
        ctrl = MagicMock()
        ctrl.draft = _draft()
        assert svc.auto_fill_header_from_history(ctrl, _chat()) is False


class TestPopunjavanje:

    def _patch_pogodak(self, monkeypatch, header_data):
        monkeypatch.setattr(
            "services.agent.learning.exporter_xml_indexer.find_xml_for_pair",
            lambda *a, **kw: {
                "xml_filepath": "C:/fake/prethodna.xml",
                "exporter_original": "MEDICO PHARM SERVIS",
            },
        )
        fake_service = MagicMock()
        fake_service.load_from_xml.return_value = header_data
        monkeypatch.setattr(
            "services.zaglavlje_service.ZaglavljeService", lambda: fake_service
        )

    def test_popuni_samo_prazna_polja(self, monkeypatch):
        self._patch_pogodak(monkeypatch, {
            "izvoznik_adresa": "Ul. Neka 1",
            "primalac_naziv": "MOJA FIRMA DOO",
            "primalac_id": "1234567",
            "deklarant_naziv": "MOJA FIRMA DOO",
        })
        ctrl = MagicMock(spec=["draft", "zaglavlje_tab"])
        ctrl.draft = _draft()
        ctrl.draft.primalac_naziv = "VEC UNESENO"  # ne smije biti prepisano
        ctrl.zaglavlje_tab = None

        chat = _chat()
        result = svc.auto_fill_header_from_history(ctrl, chat)

        assert result is True
        assert ctrl.draft.izvoznik_adresa == "Ul. Neka 1"
        assert ctrl.draft.primalac_naziv == "VEC UNESENO"  # nepromijenjeno
        assert ctrl.draft.primalac_id == "1234567"
        assert ctrl.draft.deklarant_naziv == "MOJA FIRMA DOO"
        chat.add_activity.assert_called_once()

    def test_nista_novo_za_popuniti_vraca_false(self, monkeypatch):
        self._patch_pogodak(monkeypatch, {"izvoznik_naziv": "NEKO DRUGI"})
        ctrl = MagicMock(spec=["draft", "zaglavlje_tab"])
        ctrl.draft = _draft()  # izvoznik_naziv vec popunjen
        ctrl.zaglavlje_tab = None

        chat = _chat()
        assert svc.auto_fill_header_from_history(ctrl, chat) is False
        chat.add_activity.assert_not_called()

    def test_osvjezava_otvoren_zaglavlje_tab(self, monkeypatch):
        self._patch_pogodak(monkeypatch, {"primalac_naziv": "MOJA FIRMA DOO"})
        ctrl = MagicMock(spec=["draft", "zaglavlje_tab"])
        ctrl.draft = _draft()
        ctrl.zaglavlje_tab = MagicMock()

        assert svc.auto_fill_header_from_history(ctrl, _chat()) is True
        ctrl.zaglavlje_tab.load_from_draft.assert_called_once_with(ctrl.draft)
