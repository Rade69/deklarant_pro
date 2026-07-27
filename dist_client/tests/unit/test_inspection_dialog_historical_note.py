import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from core.draft.draft import NaimenovanjeDraft
from gui.dialogs.inspection_dialog import InspectionDialog
from services.inspection_service import HistoricalDocumentHint, InspectionMatch


def _app():
    return QApplication.instance() or QApplication([])


class _StubService:
    def __init__(self, hints_by_tariff):
        self._hints_by_tariff = hints_by_tariff

    def historical_hint(self, tariff_code):
        return self._hints_by_tariff.get(tariff_code, [])


def _dialog_with_service(service) -> InspectionDialog:
    dlg = InspectionDialog.__new__(InspectionDialog)
    dlg._service = service
    return dlg


def _match(itype: str) -> InspectionMatch:
    return InspectionMatch(
        inspection_type=itype,
        tariff_code="21069098",
        condition_text=None,
        can_auto_decide=True,
        match_strength="exact",
        source_dataset="test",
    )


def test_historical_note_prikazuje_broj_pojavljivanja_za_tip_sekcije():
    _app()
    service = _StubService({
        "21069098": [
            HistoricalDocumentHint("sanitary", "Sanitarno - zdravstveno uvjerenje", 82),
            HistoricalDocumentHint("market_inspection", "Uvjerenje o kvalitetu robe", 86),
        ]
    })
    dlg = _dialog_with_service(service)
    naim = NaimenovanjeDraft(item_id="1", ordinal_no=1, tariff_code="21069098")

    lbl = dlg._build_historical_note("sanitary", [(naim, _match("sanitary"))])

    assert lbl is not None
    assert "21069098 (82x)" in lbl.text()
    assert "informativno" in lbl.text()


def test_historical_note_none_kad_nema_podatka_za_taj_tip():
    _app()
    service = _StubService({"21069098": []})
    dlg = _dialog_with_service(service)
    naim = NaimenovanjeDraft(item_id="1", ordinal_no=1, tariff_code="21069098")

    lbl = dlg._build_historical_note("veterinary", [(naim, _match("veterinary"))])

    assert lbl is None


def test_historical_note_ignorise_hint_drugog_tipa_inspekcije():
    _app()
    service = _StubService({
        "21069098": [HistoricalDocumentHint("veterinary", "Veterinarsko uvjerenje", 80)]
    })
    dlg = _dialog_with_service(service)
    naim = NaimenovanjeDraft(item_id="1", ordinal_no=1, tariff_code="21069098")

    lbl = dlg._build_historical_note("sanitary", [(naim, _match("sanitary"))])

    assert lbl is None


def test_historical_note_spaja_vise_tarifnih_brojeva_bez_duplikata():
    _app()
    service = _StubService({
        "21069098": [HistoricalDocumentHint("sanitary", "x", 82)],
        "16010099": [HistoricalDocumentHint("sanitary", "x", 62)],
    })
    dlg = _dialog_with_service(service)
    naim1 = NaimenovanjeDraft(item_id="1", ordinal_no=1, tariff_code="21069098")
    naim2 = NaimenovanjeDraft(item_id="2", ordinal_no=2, tariff_code="16010099")

    lbl = dlg._build_historical_note(
        "sanitary",
        [(naim1, _match("sanitary")), (naim2, _match("sanitary"))],
    )

    assert lbl is not None
    assert "21069098 (82x)" in lbl.text()
    assert "16010099 (62x)" in lbl.text()
