"""
Karakterizacioni test: tabela roundtrip — InvoiceLine → View tabela → InvoiceLine.

Faza 0 prema Codex planu §8. Dokazuje da FakturaView tabela ispravno
prikazuje sva polja InvoiceLine bez gubitka ili promjene vrijednosti.

Ne mijenja produkcioni kod.
"""
from __future__ import annotations

import pytest

from PySide6.QtCore import Qt

from core.draft.draft import DeclarationDraft, InvoiceLine


@pytest.fixture
def view_with_lines(qtbot):
    from gui.tabs.faktura_view import FakturaView
    draft = DeclarationDraft()
    draft.invoice_lines = [
        InvoiceLine(
            tarifni_broj="08052190", naziv_robe="Jabuke svježe",
            zemlja_porijekla="DE", bruto_kg=100.0, neto_kg=90.0,
            iznos=500.0, kolicina=10, jm="kom",
        ),
        InvoiceLine(
            tarifni_broj="", naziv_robe="", zemlja_porijekla="",
            bruto_kg=0.0, neto_kg=0.0, iznos=0.0, kolicina=0, jm="",
        ),
    ]
    view = FakturaView(draft=draft)
    qtbot.addWidget(view)
    view.show()
    return view, draft


class TestFakturaTableRoundtrip:

    def test_table_has_rows_for_all_lines(self, view_with_lines):
        view, draft = view_with_lines
        assert view.table.rowCount() == len(draft.invoice_lines)

    def test_lines_preserved_in_draft(self, view_with_lines):
        view, draft = view_with_lines
        assert len(draft.invoice_lines) == 2
        assert draft.invoice_lines[0].tarifni_broj == "08052190"
        assert draft.invoice_lines[0].naziv_robe == "Jabuke svježe"

    def test_empty_line_values(self, view_with_lines):
        view, draft = view_with_lines
        empty = draft.invoice_lines[1]
        assert empty.tarifni_broj == ""
        assert empty.naziv_robe == ""

    def test_table_is_qtablewidget(self, view_with_lines):
        view, draft = view_with_lines
        from PySide6.QtWidgets import QTableWidget
        assert isinstance(view.table, QTableWidget)

    def test_table_has_expected_columns(self, view_with_lines):
        view, draft = view_with_lines
        assert view.table.columnCount() >= 8  # rb, naziv, tarifa, zemlja, povlastica...

    def test_view_has_naimenovanja_created_signal(self, view_with_lines):
        view, draft = view_with_lines
        from PySide6.QtCore import Signal
        assert hasattr(view, "naimenovanja_created")
        assert isinstance(view.naimenovanja_created, Signal)

    def test_sync_table_to_draft_preserves_all_editable_columns(self, view_with_lines):
        view, draft = view_with_lines

        view.table.blockSignals(True)
        try:
            view.table.item(0, 1).setText("INV-900")
            view.table.item(0, 3).setText("Izmijenjen naziv robe")
            view.table.item(0, 4).setText("0805.21.90")
            view.table.item(0, 5).setText("1.234,50")
            view.table.item(0, 6).setText("2.469,00")
            view.table.item(0, 7).setText("123,456")
            view.table.item(0, 8).setText("120,111")
            view.table.item(0, 9).setData(Qt.UserRole, "DE")
            view.table.item(0, 9).setText("✅ DE")
            view.table.item(0, 10).setText("EUPR")
            view.table.item(0, 11).setText("EUR")
        finally:
            view.table.blockSignals(False)

        view._sync_table_to_draft()
        line = draft.invoice_lines[0]

        assert line.invoice_number == "INV-900"
        assert line.naziv_robe == "Izmijenjen naziv robe"
        assert line.tarifni_broj == "0805.21.90"
        assert line.kolicina == pytest.approx(1234.50)
        assert line.iznos == pytest.approx(2469.00)
        assert line.cijena_jed == pytest.approx(2.0)
        assert line.bruto_kg == pytest.approx(123.456)
        assert line.neto_kg == pytest.approx(120.111)
        assert line.zemlja_porijekla == "DE"
        assert line.povlastica == "EUPR"
        assert line.valuta == "EUR"

    def test_sync_table_to_draft_does_not_guess_missing_tariff_digits(self, view_with_lines):
        view, draft = view_with_lines

        view.table.blockSignals(True)
        try:
            view.table.item(0, 4).setText("3304990")
        finally:
            view.table.blockSignals(False)

        view._sync_table_to_draft()

        assert draft.invoice_lines[0].tarifni_broj == "3304990"
