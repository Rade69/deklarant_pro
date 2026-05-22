import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QComboBox

from core.draft.draft import InvoiceLine
from gui.dialogs.eur1_quick_dialog import Eur1QuickDialog


def _app():
    return QApplication.instance() or QApplication([])


def _fake_country_combo(_self, current_country: str):
    combo = QComboBox()
    combo.addItem(current_country, current_country)
    return combo


def test_eur1_dialog_groups_by_invoice_and_country(monkeypatch):
    _app()
    monkeypatch.setattr(Eur1QuickDialog, "_create_country_combo", _fake_country_combo)
    monkeypatch.setattr(Eur1QuickDialog, "_get_country_name", lambda _self, key: key.split(" - ")[-1])

    lines = [
        InvoiceLine(invoice_number="IF0520/26-01", zemlja_porijekla="RS", naziv_robe="A"),
        InvoiceLine(invoice_number="IF0520/26-01", zemlja_porijekla="IT", naziv_robe="B"),
        InvoiceLine(invoice_number="IF0520/26-02", zemlja_porijekla="RS", naziv_robe="C"),
    ]

    dialog = Eur1QuickDialog(lines)

    assert sorted(dialog.country_inputs) == [
        "IF0520/26-01 - IT",
        "IF0520/26-01 - RS",
        "IF0520/26-02 - RS",
    ]


def test_eur1_dialog_applies_only_selected_invoice_country_group(monkeypatch):
    _app()
    monkeypatch.setattr(Eur1QuickDialog, "_create_country_combo", _fake_country_combo)
    monkeypatch.setattr(Eur1QuickDialog, "_get_country_name", lambda _self, key: key.split(" - ")[-1])
    monkeypatch.setattr(Eur1QuickDialog, "_suggest_preference", lambda _self, country: "CEFTAR" if country == "RS" else "")

    selected = InvoiceLine(invoice_number="IF0520/26-01", zemlja_porijekla="RS", naziv_robe="A")
    not_selected_same_country = InvoiceLine(invoice_number="IF0520/26-02", zemlja_porijekla="RS", naziv_robe="B")
    not_selected_other_country = InvoiceLine(invoice_number="IF0520/26-01", zemlja_porijekla="IT", naziv_robe="C")
    lines = [selected, not_selected_same_country, not_selected_other_country]

    dialog = Eur1QuickDialog(lines)
    group = dialog.country_inputs["IF0520/26-01 - RS"]
    group["checkbox"].setChecked(True)
    group["eur1_number"].setText("EUR1-123")

    eur1_data = dialog.get_data()
    updated = Eur1QuickDialog.apply_eur1_data(lines, eur1_data)

    assert updated == 1
    assert selected.eur1_number == "EUR1-123"
    assert selected.povlastica == "CEFTAR"
    assert not_selected_same_country.eur1_number == ""
    assert not_selected_same_country.povlastica == ""
    assert not_selected_other_country.eur1_number == ""
    assert not_selected_other_country.povlastica == ""
