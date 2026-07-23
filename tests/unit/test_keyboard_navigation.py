import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLineEdit, QMainWindow, QTabWidget

from gui.main_window import MainWindow
from gui.tabs.faktura_view import FakturaView
from gui.tabs.zaglavlje_view import ZaglavljeView


def _app():
    return QApplication.instance() or QApplication([])


def test_main_tabs_have_direct_shortcuts_and_tooltips():
    _app()
    window = QMainWindow()
    window.tabs_widget = QTabWidget(window)
    for label in (
        "Faktura", "Naimenovanja", "Zaglavlje",
        "Šifrarnici", "Admin", "Agent",
    ):
        window.tabs_widget.addTab(QLineEdit(), label)

    MainWindow._setup_keyboard_shortcuts(window)

    assert len(window._main_tab_shortcuts) == 6
    assert window._main_tab_shortcuts[2].key().toString() == "Ctrl+3"
    assert "Ctrl+6" in window.tabs_widget.tabToolTip(5)
    window._main_tab_shortcuts[4].activated.emit()
    assert window.tabs_widget.currentIndex() == 4


def test_faktura_keyboard_row_navigation_is_bounded():
    class Table:
        def __init__(self):
            self.current = -1
            self.selected = []

        def rowCount(self):
            return 3

        def currentRow(self):
            return self.current

        def selectRow(self, row):
            self.current = row
            self.selected.append(row)

        def item(self, row, column):
            return None

    view = type("View", (), {"table": Table()})()

    FakturaView._navigate_invoice_row(view, 1)
    FakturaView._navigate_invoice_row(view, 1)
    FakturaView._navigate_invoice_row(view, 5)

    assert view.table.selected == [0, 1, 2]


def test_zaglavlje_tab_order_follows_field_registry():
    _app()
    container = QMainWindow()
    first = QLineEdit(container)
    second = QLineEdit(container)
    third = QLineEdit(container)
    view = type(
        "View",
        (),
        {
            "field_widgets": {
                "first": first,
                "second": second,
                "duplicate": second,
                "third": third,
            },
            "table": None,
        },
    )()

    ZaglavljeView._setup_tab_order(view)

    assert first.nextInFocusChain() is second
    assert second.nextInFocusChain() is third
