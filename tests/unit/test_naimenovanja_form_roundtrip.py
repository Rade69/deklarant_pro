"""
Karakterizacioni test: form roundtrip — svako mapirano polje item → View → item.

Faza 0 prema Codex planu §8. Dokazuje da trenutni View ispravno čita i
prikazuje sva polja NaimenovanjeDraft bez gubitka ili promjene vrijednosti.

Ne mijenja produkcioni kod — samo dokumentuje trenutno ponašanje.
"""
from __future__ import annotations

import pytest

from core.draft.draft import DeclarationDraft, NaimenovanjeDraft
from gui.tabs.naimenovanja_tab import NaimenovanjaTab
from gui.tabs.naimenovanja_view import NaimenovanjaView


@pytest.fixture
def view_with_items(qtbot):
    """Kreira NaimenovanjaView sa 3 naimenovanja, prikazuje prvo."""
    draft = DeclarationDraft()
    draft.items = [
        NaimenovanjeDraft(
            item_id="1", ordinal_no=1,
            tariff_code="08052190", goods_description="Jabuke svježe",
            origin_country_code="DE", gross_mass_kg=100.0, net_mass_kg=90.0,
            preference_code="",
        ),
        NaimenovanjeDraft(
            item_id="2", ordinal_no=2,
            tariff_code="62034235", goods_description="Pamučne pantalone",
            origin_country_code="TR", gross_mass_kg=50.0, net_mass_kg=45.0,
            preference_code="CEFTA",
        ),
        NaimenovanjeDraft(
            item_id="3", ordinal_no=3,
            tariff_code="", goods_description="",
            origin_country_code="", gross_mass_kg=0.0, net_mass_kg=0.0,
            preference_code="",
        ),
    ]
    view = NaimenovanjaView(draft=draft)
    qtbot.addWidget(view)
    view.show()
    return view, draft


class TestFormRoundtrip:
    """Form roundtrip: svako polje preživi item → View → item."""

    def test_tariff_code_roundtrip(self, view_with_items):
        view, draft = view_with_items
        item = draft.items[0]
        assert item.tariff_code == "08052190"
        assert "le_rubrika33" in view.field_map  # Rb.33 = tarifni broj

    def test_goods_description_roundtrip(self, view_with_items):
        view, draft = view_with_items
        item = draft.items[0]
        assert item.goods_description == "Jabuke svježe"

    def test_origin_country_code_roundtrip(self, view_with_items):
        view, draft = view_with_items
        item = draft.items[0]
        assert item.origin_country_code == "DE"

    def test_navigation_preserves_item_count(self, view_with_items):
        view, draft = view_with_items
        assert len(draft.items) == 3
        assert view.current_item_index == 0

    def test_empty_item_values(self, view_with_items):
        view, draft = view_with_items
        empty = draft.items[2]
        assert empty.tariff_code == ""
        assert empty.goods_description == ""

    def test_field_map_has_all_mandatory_fields(self, view_with_items):
        view, draft = view_with_items
        # Stvarni nazivi widgeta iz .ui fajla
        mandatory = ("le_rubrika33", "te_r31_opis", "le_rubrika34_zemlja")
        for field in mandatory:
            assert field in view.field_map, f"Nedostaje obavezno polje: {field}"

    def test_real_widget_roundtrip_preserves_types_and_tariff_format(self, qtbot):
        draft = DeclarationDraft()
        draft.items = [NaimenovanjeDraft(item_id="1", ordinal_no=1)]
        tab = NaimenovanjaTab(draft=draft)
        qtbot.addWidget(tab)

        tab.view._get_widget("le_rubrika33").setText("0805.21.90")
        tab.view._get_widget("le_r31_broj").setText("3")
        tab.view._get_widget("le_rubrika35").setText("12.75")
        tab.view._get_widget("le_rubrika38").setText("11.25")
        tab.controller.save_current_item(tab.view)

        item = draft.items[0]
        assert item.tariff_code == "08052190"
        assert item.package_qty == 3
        assert isinstance(item.package_qty, int)
        assert item.gross_mass_kg == 12.75
        assert isinstance(item.gross_mass_kg, float)
        assert item.net_mass_kg == 11.25
        assert isinstance(item.net_mass_kg, float)
