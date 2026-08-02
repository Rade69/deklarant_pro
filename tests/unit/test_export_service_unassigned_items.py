"""
Karakterizacioni test za ExportService.find_unassigned_items() —
Faza 7a (2026-08-02, project_rooms/2026-08-01_faktura-3layer-refaktor-
fazni-plan.md), izdvojeno iz FakturaView._on_export_excel.
"""
from core.draft import InvoiceLine
from services.export_service import ExportService


def _line(ordinal: int) -> InvoiceLine:
    return InvoiceLine(
        line_no=1, naziv_robe="Test", tarifni_broj="84186900",
        zemlja_porijekla="IT", kolicina=1.0, jm="kom",
        assigned_naimenovanje_ordinal=ordinal,
    )


def test_sve_stavke_dodijeljene_vraca_praznu_listu():
    items = [_line(1), _line(2), _line(3)]
    assert ExportService.find_unassigned_items(items) == []


def test_nedodijeljene_stavke_vraceno_ordinal_nula():
    unassigned = _line(0)
    items = [_line(1), unassigned, _line(2)]
    result = ExportService.find_unassigned_items(items)
    assert result == [unassigned]


def test_negativan_ordinal_takodje_nedodijeljen():
    unassigned = _line(-1)
    result = ExportService.find_unassigned_items([unassigned])
    assert result == [unassigned]


def test_prazna_lista_vraca_praznu_listu():
    assert ExportService.find_unassigned_items([]) == []
