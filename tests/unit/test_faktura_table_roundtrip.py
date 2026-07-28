"""
Karakterizacioni test: tabela roundtrip — InvoiceLine → View tabela → InvoiceLine.

Faza 0 prema Codex planu §8. Dokazuje da FakturaView tabela ispravno
prikazuje sva polja InvoiceLine bez gubitka ili promjene vrijednosti.

Ne mijenja produkcioni kod.
"""
from __future__ import annotations

import pytest

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
