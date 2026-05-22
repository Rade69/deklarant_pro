import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QComboBox

from core.draft.draft import InvoiceLine
from gui.dialogs.eur1_quick_dialog import Eur1QuickDialog
from gui.tabs.faktura_view import FakturaView
from importers.vendors.pip_food.pip_food_parser import parse_pip_food_pdf


PIP92_PATH = Path(__file__).resolve().parents[2] / "najavauvoza" / "PIP92.pdf"


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


@pytest.mark.skipif(not PIP92_PATH.exists(), reason="PIP92.pdf nije dostupan u lokalnom workspace-u")
def test_eur1_dialog_groups_real_pip92_invoices(monkeypatch):
    _app()
    monkeypatch.setattr(Eur1QuickDialog, "_create_country_combo", _fake_country_combo)
    monkeypatch.setattr(Eur1QuickDialog, "_get_country_name", lambda _self, key: key.split(" - ")[-1])

    result = parse_pip_food_pdf(str(PIP92_PATH))
    dialog = Eur1QuickDialog(result.items)

    assert {
        key: len(data["items"])
        for key, data in dialog.country_inputs.items()
    } == {
        "IF0520/26-01 - RS": 10,
        "IF0520/26-02 - RS": 14,
        "IF0520/26-03 - RS": 1,
    }


def test_assign_invoice_name_preserves_parser_invoice_numbers():
    lines = [
        InvoiceLine(invoice_number="IF0520/26-01", zemlja_porijekla="RS"),
        InvoiceLine(invoice_number="", zemlja_porijekla="RS"),
    ]

    FakturaView._assign_invoice_name(None, lines, "IF0520/26-02")

    assert lines[0].invoice_number == "IF0520/26-01"
    assert lines[1].invoice_number == "IF0520/26-02"
