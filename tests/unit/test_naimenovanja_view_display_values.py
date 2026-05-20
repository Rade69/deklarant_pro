from types import SimpleNamespace

from core.draft.draft import NaimenovanjeDraft
from gui.tabs.naimenovanja_view import NaimenovanjaView


def test_rub46_display_uses_imported_statistical_value_before_recalculation():
    view = NaimenovanjaView.__new__(NaimenovanjaView)
    item = NaimenovanjeDraft(
        item_id="1",
        ordinal_no=1,
        item_value=125.90,
        statistical_value=246.24,
    )

    assert view._get_item_field_value(item, "statistical_value") == 246.24


def test_rub46_display_recalculates_when_statistical_value_missing():
    view = NaimenovanjaView.__new__(NaimenovanjaView)
    item = NaimenovanjeDraft(
        item_id="1",
        ordinal_no=1,
        item_value=100,
        statistical_value=0,
    )
    view.draft = SimpleNamespace(items=[item], kurs=2, trosak_1=10)

    assert view._get_item_field_value(item, "statistical_value") == "210.00"
