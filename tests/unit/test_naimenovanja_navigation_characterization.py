"""
Karakterizacioni testovi: navigacija i multidraft.

Faza 0 prema Codex planu §8.
"""
from __future__ import annotations

import pytest

from core.draft.draft import DeclarationDraft, NaimenovanjeDraft
from gui.tabs.naimenovanja_tab import NaimenovanjaTab
from gui.tabs.naimenovanja_view import NaimenovanjaView


@pytest.fixture
def view_with_items(qtbot):
    draft = DeclarationDraft()
    draft.items = [
        NaimenovanjeDraft(item_id=str(i), ordinal_no=i,
                          tariff_code=f"0805219{i}", goods_description=f"Item {i}",
                          origin_country_code="DE", gross_mass_kg=10.0, net_mass_kg=9.0)
        for i in range(1, 4)
    ]
    view = NaimenovanjaView(draft=draft)
    qtbot.addWidget(view)
    view.show()
    return view, draft


class TestNavigationCharacterization:

    def test_initial_item_is_first(self, view_with_items):
        view, draft = view_with_items
        assert view.current_item_index == 0

    def test_total_item_count(self, view_with_items):
        view, draft = view_with_items
        assert len(draft.items) == 3

    def test_items_have_unique_ids(self, view_with_items):
        view, draft = view_with_items
        ids = [item.item_id for item in draft.items]
        assert len(ids) == len(set(ids))

    def test_items_have_sequential_ordinals(self, view_with_items):
        view, draft = view_with_items
        for i, item in enumerate(draft.items, 1):
            assert item.ordinal_no == i


class TestMultidraft:

    def test_draft_is_not_shared_view_attribute(self, view_with_items):
        """View.draft je referenca na DeclarationDraft — isto za sada."""
        view, draft = view_with_items
        assert view.draft is draft

    def test_draft_items_accessible(self, view_with_items):
        view, draft = view_with_items
        assert view.draft.items == draft.items

    def test_new_draft_has_different_items(self, qtbot):
        """Kad se promijeni draft, items se mijenjaju."""
        draft1 = DeclarationDraft()
        draft1.items = [NaimenovanjeDraft(item_id="1", ordinal_no=1,
                          tariff_code="11111111", goods_description="Stari")]
        draft2 = DeclarationDraft()
        draft2.items = [NaimenovanjeDraft(item_id="2", ordinal_no=1,
                          tariff_code="22222222", goods_description="Novi")]

        view = NaimenovanjaView(draft=draft1)
        qtbot.addWidget(view)
        view.show()
        assert view.draft.items[0].tariff_code == "11111111"

        view.draft = draft2
        assert view.draft.items[0].tariff_code == "22222222"

    def test_save_after_draft_switch_never_mutates_old_draft(self, qtbot):
        draft1 = DeclarationDraft()
        draft1.items = [
            NaimenovanjeDraft(
                item_id="1", ordinal_no=1, tariff_code="11111111"
            )
        ]
        draft2 = DeclarationDraft()
        draft2.items = [
            NaimenovanjeDraft(
                item_id="2", ordinal_no=1, tariff_code="22222222"
            )
        ]
        tab = NaimenovanjaTab(draft=draft1)
        qtbot.addWidget(tab)
        tab.view.draft = draft2
        tab.view.reload_data()
        tab.view._get_widget("le_rubrika33").setText("33333333")

        tab.controller.save_current_item(tab.view)

        assert draft1.items[0].tariff_code == "11111111"
        assert draft2.items[0].tariff_code == "33333333"


class TestControllerNavigation:

    def test_navigation_saves_current_item_before_switch(self, qtbot):
        draft = DeclarationDraft()
        draft.items = [
            NaimenovanjeDraft(item_id="1", ordinal_no=1, tariff_code="11111111"),
            NaimenovanjeDraft(item_id="2", ordinal_no=2, tariff_code="22222222"),
        ]
        tab = NaimenovanjaTab(draft=draft)
        qtbot.addWidget(tab)
        tab.view._get_widget("le_rubrika33").setText("33333333")

        tab.controller.navigate_to(tab.view, 1)

        assert draft.items[0].tariff_code == "33333333"
        assert tab.view.current_item_index == 1

    def test_delete_middle_item_does_not_overwrite_next_item(self, qtbot):
        draft = DeclarationDraft()
        draft.items = [
            NaimenovanjeDraft(item_id="1", ordinal_no=1, tariff_code="11111111"),
            NaimenovanjeDraft(item_id="2", ordinal_no=2, tariff_code="22222222"),
            NaimenovanjeDraft(item_id="3", ordinal_no=3, tariff_code="33333333"),
        ]
        tab = NaimenovanjaTab(draft=draft)
        qtbot.addWidget(tab)
        tab.view.current_item_index = 1
        tab.view.render_current_item()
        tab.view._get_widget("le_rubrika33").setText("99999999")

        tab.controller.delete_item(tab.view, 1)

        assert [item.tariff_code for item in draft.items] == [
            "11111111",
            "33333333",
        ]
        assert [item.ordinal_no for item in draft.items] == [1, 2]
