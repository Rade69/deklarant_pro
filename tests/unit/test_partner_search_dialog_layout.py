from PySide6.QtWidgets import QApplication, QHeaderView

from gui.widgets import db_widgets


def _app():
    return QApplication.instance() or QApplication([])


def test_consignee_dialog_prioritizes_company_details(monkeypatch):
    _app()
    monkeypatch.setattr(db_widgets.db, "search_uvoznike", lambda *_args, **_kwargs: [])

    dialog = db_widgets.PartnerSearchDialog(partner_type="consignee")
    header = dialog.table.horizontalHeader()

    assert dialog.windowTitle() == "Pretraga uvoznika"
    assert dialog.minimumWidth() >= 900
    assert header.sectionResizeMode(0) == QHeaderView.ResizeToContents
    assert header.sectionResizeMode(1) == QHeaderView.Stretch
    assert header.sectionResizeMode(2) == QHeaderView.Stretch


def test_exporter_dialog_shows_full_values_in_tooltips(monkeypatch):
    _app()
    company = {
        "jib": "",
        "naziv": "Veoma dugačak puni naziv izvoznika koji mora biti dostupan",
        "adresa": "Industrijska zona 123, poslovna zgrada B",
        "grad": "Istanbul",
        "postanski_broj": "34000",
        "drzava": "TR",
    }
    monkeypatch.setattr(db_widgets.db, "search_izvoznike", lambda *_args, **_kwargs: [company])

    dialog = db_widgets.PartnerSearchDialog(partner_type="exporter")

    assert dialog.windowTitle() == "Pretraga izvoznika"
    assert dialog.table.isColumnHidden(0)
    assert dialog.table.item(0, 1).toolTip() == company["naziv"]
    assert dialog.table.item(0, 2).toolTip() == company["adresa"]
