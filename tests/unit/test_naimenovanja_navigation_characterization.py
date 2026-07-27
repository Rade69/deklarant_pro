"""
Karakterizacioni testovi: navigacija i multidraft.

Faza 0 prema Codex planu §8.
"""
from __future__ import annotations

import pytest

from core.draft.draft import DeclarationDraft, NaimenovanjeDraft
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
