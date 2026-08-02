"""
Karakterizacioni test za FakturaService.apply_cell_edit() — Faza 7b
(2026-08-02, project_rooms/2026-08-01_faktura-3layer-refaktor-fazni-plan.md),
izdvojeno iz FakturaView._on_item_changed (mapiranje kolona->polje,
parsiranje brojeva, ciscenje ikonica-prefiksa iz zemlje porijekla).
"""
from core.draft import InvoiceLine
from services.faktura.faktura_service import FakturaService

_ICONS = ["✅", "📋", "⚠️", "🚨"]


def _line() -> InvoiceLine:
    return InvoiceLine(line_no=1, naziv_robe="Test", tarifni_broj="", kolicina=0.0, jm="kom")


def test_kolona_1_faktura_broj():
    item = _line()
    field = FakturaService.apply_cell_edit(item, 1, "INV-001", _ICONS)
    assert item.invoice_number == "INV-001"
    assert field == "invoice_number"


def test_kolona_3_naziv_robe():
    item = _line()
    FakturaService.apply_cell_edit(item, 3, "Grejac spirala", _ICONS)
    assert item.naziv_robe == "Grejac spirala"


def test_kolona_4_tarifni_broj():
    item = _line()
    field = FakturaService.apply_cell_edit(item, 4, "85168020", _ICONS)
    assert item.tarifni_broj == "85168020"
    assert field == "tarifni_broj"


def test_kolona_5_kolicina_parsira_broj():
    item = _line()
    FakturaService.apply_cell_edit(item, 5, "1.234,56", _ICONS)
    assert item.kolicina == 1234.56


def test_kolona_5_prazna_vrijednost_daje_nulu():
    item = _line()
    FakturaService.apply_cell_edit(item, 5, "", _ICONS)
    assert item.kolicina == 0.0


def test_kolona_6_iznos_ne_dira_cijenu_jed():
    item = _line()
    item.cijena_jed = 10.0
    FakturaService.apply_cell_edit(item, 6, "100,00", _ICONS)
    assert item.iznos == 100.0
    assert item.cijena_jed == 10.0


def test_kolona_7_bruto_kg():
    item = _line()
    FakturaService.apply_cell_edit(item, 7, "12,5", _ICONS)
    assert item.bruto_kg == 12.5


def test_kolona_8_neto_kg():
    item = _line()
    FakturaService.apply_cell_edit(item, 8, "10,25", _ICONS)
    assert item.neto_kg == 10.25


def test_kolona_9_zemlja_ciste_vrijednost_ostaje_ista():
    item = _line()
    field = FakturaService.apply_cell_edit(item, 9, "IT", _ICONS)
    assert item.zemlja_porijekla == "IT"
    assert field == "zemlja_porijekla"


def test_kolona_9_zemlja_uklanja_ikonicu_prefiks():
    item = _line()
    FakturaService.apply_cell_edit(item, 9, "✅ IT", _ICONS)
    assert item.zemlja_porijekla == "IT"


def test_kolona_9_zemlja_uklanja_samo_prvu_poklapajucu_ikonicu():
    item = _line()
    FakturaService.apply_cell_edit(item, 9, "⚠️ DE", _ICONS)
    assert item.zemlja_porijekla == "DE"


def test_kolona_10_povlastica():
    item = _line()
    field = FakturaService.apply_cell_edit(item, 10, "DA", _ICONS)
    assert item.povlastica == "DA"
    assert field == "povlastica"


def test_kolona_11_valuta():
    item = _line()
    FakturaService.apply_cell_edit(item, 11, "EUR", _ICONS)
    assert item.valuta == "EUR"


def test_nepoznata_kolona_ne_mijenja_nista_i_vraca_none():
    item = _line()
    field = FakturaService.apply_cell_edit(item, 99, "x", _ICONS)
    assert field is None
