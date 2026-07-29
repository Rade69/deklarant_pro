from __future__ import annotations

from core.draft.draft import InvoiceLine
from services.faktura.validation_service import ValidationService


def test_missing_tariff_is_cell_override_not_whole_row():
    style = ValidationService().validate_and_get_style(
        InvoiceLine(naziv_robe="Test", tarifni_broj="", zemlja_porijekla="CN")
    )

    assert style.row_color == "#ffffff"
    assert style.row_tooltip == ""
    assert style.cell_overrides[4] == (
        "#F9E4E3",
        "❌ Greška: Nedostaje tarifni broj",
    )


def test_missing_country_is_cell_override_not_whole_row():
    style = ValidationService().validate_and_get_style(
        InvoiceLine(naziv_robe="Test", tarifni_broj="39269097", zemlja_porijekla="")
    )

    assert style.row_color == "#ffffff"
    assert style.row_tooltip == ""
    assert style.cell_overrides[9] == (
        "#F9E4E3",
        "❌ Greška: Nedostaje zemlja porijekla",
    )


def test_unmatched_marks_tariff_and_country_cells_blue():
    style = ValidationService().validate_and_get_style(
        InvoiceLine(naziv_robe="Test", tarifni_broj="", zemlja_porijekla="")
    )

    assert style.row_color == "#ffffff"
    assert style.cell_overrides[4] == ("#E6F0F8", "❌ Nedostaje tarifni broj")
    assert style.cell_overrides[9] == ("#E6F0F8", "❌ Nedostaje zemlja porijekla")


def test_fuzzy_tariff_marks_only_tariff_cell():
    style = ValidationService().validate_and_get_style(
        InvoiceLine(
            naziv_robe="Test",
            tarifni_broj="39269097",
            zemlja_porijekla="CN",
            tariff_similarity=0.85,
        )
    )

    assert style.row_color == "#ffffff"
    assert style.cell_overrides[4][0] == "#FFF4D6"
    assert "Pouzdanje: 85%" in style.cell_overrides[4][1]


def test_valid_line_uses_current_green_palette():
    style = ValidationService().validate_and_get_style(
        InvoiceLine(
            naziv_robe="Test",
            tarifni_broj="39269097",
            zemlja_porijekla="CN",
            iznos=10.0,
            kolicina=1,
        )
    )

    assert style.row_color == "#EAF4EE"
    assert style.row_tooltip == "✅ Validna stavka"
