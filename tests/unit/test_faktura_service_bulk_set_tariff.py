"""
Karakterizacioni test za FakturaService.bulk_set_tariff() — Faza 7b
(2026-08-02), izdvojeno iz FakturaView._on_bulk_change_tariff (mutation
loop razdvojen od Qt redraw-a/DB korekcije).
"""
from core.draft import InvoiceLine
from services.faktura.faktura_service import FakturaService


def _line(tarifni_broj: str) -> InvoiceLine:
    return InvoiceLine(line_no=1, naziv_robe="Test", tarifni_broj=tarifni_broj, kolicina=1.0, jm="kom")


def test_postavlja_tarifu_na_sve_izabrane_redove():
    lines = [_line("11111111"), _line("22222222"), _line("33333333")]
    FakturaService.bulk_set_tariff(lines, [0, 1, 2], "99999999")
    assert [l.tarifni_broj for l in lines] == ["99999999"] * 3


def test_ne_dira_neizabrane_redove():
    lines = [_line("11111111"), _line("22222222")]
    FakturaService.bulk_set_tariff(lines, [0], "99999999")
    assert lines[0].tarifni_broj == "99999999"
    assert lines[1].tarifni_broj == "22222222"


def test_vraca_samo_redove_gdje_se_vrijednost_promijenila():
    lines = [_line("11111111"), _line("99999999"), _line("33333333")]
    changed = FakturaService.bulk_set_tariff(lines, [0, 1, 2], "99999999")
    assert changed == [(0, "11111111"), (2, "33333333")]


def test_prazna_stara_tarifa_racuna_se_kao_promjena():
    lines = [_line("")]
    changed = FakturaService.bulk_set_tariff(lines, [0], "99999999")
    assert changed == [(0, "")]


def test_van_opsega_indeks_se_preskace():
    lines = [_line("11111111")]
    changed = FakturaService.bulk_set_tariff(lines, [0, 5], "99999999")
    assert lines[0].tarifni_broj == "99999999"
    assert changed == [(0, "11111111")]


def test_ne_normalizuje_tarifu_isto_ponasanje_kao_prije():
    """View NE poziva normalize_tariff_number ovdje (za razliku od
    FakturaController.bulk_change_tariff, koji je odvojen tok u
    faktura_tab.py) - ekstrakcija ne smije promijeniti ovo ponasanje."""
    lines = [_line("11111111")]
    FakturaService.bulk_set_tariff(lines, [0], "0805.21.90")
    assert lines[0].tarifni_broj == "0805.21.90"
