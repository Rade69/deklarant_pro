import sqlite3

import pytest
from PySide6.QtWidgets import QTableWidget

from gui.tabs.sifarnici.quota_panel import QuotaPanel
from gui.tabs.sifarnici import tariff_hierarchy
from gui.tabs.sifarnici_view import SifarniciView


class _ViewStub:
    def __init__(self, table):
        self.table = table


def _raise_format_error(_value):
    raise RuntimeError("test")


def test_service_table_restores_qt_state_after_format_error(qtbot):
    table = QTableWidget(0, 1)
    qtbot.addWidget(table)
    table.setSortingEnabled(True)
    view = _ViewStub(table)

    with pytest.raises(RuntimeError, match="test"):
        SifarniciView._populate_table_from_service(
            view,
            [{"value": "x"}],
            ["value"],
            format_fn=_raise_format_error,
        )

    assert table.signalsBlocked() is False
    assert table.updatesEnabled() is True
    assert table.isSortingEnabled() is True


def test_quota_table_restores_qt_state_after_format_error(qtbot, monkeypatch):
    table = QTableWidget(0, 8)
    qtbot.addWidget(table)
    panel = _ViewStub(table)
    monkeypatch.setattr(
        "gui.tabs.sifarnici.quota_panel._fmt_qty",
        _raise_format_error,
    )

    with pytest.raises(RuntimeError, match="test"):
        QuotaPanel._populate_table(
            panel,
            [{"approved_qty": 1, "used_qty": 0, "remaining_qty": 1}],
        )

    assert table.signalsBlocked() is False
    assert table.updatesEnabled() is True


def test_tariff_hierarchy_restores_qt_state_after_format_error(
    qtbot,
    monkeypatch,
    tmp_path,
):
    db_path = tmp_path / "tarifa.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE tarifa_2026 "
            "(kod TEXT, naziv TEXT, stopa_uvozna TEXT, nivo INTEGER)"
        )
        conn.execute(
            "INSERT INTO tarifa_2026 VALUES (?, ?, ?, ?)",
            ("0101", "Opis", "5", 4),
        )
    monkeypatch.setattr(tariff_hierarchy, "_DB_PATH", db_path)
    table = QTableWidget(0, 2)
    qtbot.addWidget(table)

    with pytest.raises(RuntimeError, match="test"):
        tariff_hierarchy.populate_tariff_hierarchy(
            table,
            "0101",
            clean_opis_fn=_raise_format_error,
        )

    assert table.signalsBlocked() is False
    assert table.updatesEnabled() is True

