import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLineEdit, QMainWindow, QPushButton,
    QTabWidget, QVBoxLayout, QWidget,
)

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
    window._focus_active_toolbar = lambda: None

    MainWindow._setup_keyboard_shortcuts(window)

    assert len(window._main_tab_shortcuts) == 6
    assert window._main_tab_shortcuts[2].key().toString() == "Ctrl+3"
    assert "Ctrl+6" in window.tabs_widget.tabToolTip(5)
    window._main_tab_shortcuts[4].activated.emit()
    assert window.tabs_widget.currentIndex() == 4


def test_f6_enters_toolbar_and_keyboard_moves_focus():
    app = _app()
    window = QMainWindow()
    window._active_toolbar_buttons = MainWindow._active_toolbar_buttons.__get__(window)
    window._focus_active_toolbar = MainWindow._focus_active_toolbar.__get__(window)
    window.tabs_widget = QTabWidget(window)
    page = QWidget()
    page_layout = QVBoxLayout(page)
    field = QLineEdit(page)
    toolbar = QWidget(page)
    toolbar.setObjectName("toolbar")
    toolbar_layout = QHBoxLayout(toolbar)
    first = QPushButton("Prvo", toolbar)
    second = QPushButton("Drugo", toolbar)
    toolbar_layout.addWidget(first)
    toolbar_layout.addWidget(second)
    page_layout.addWidget(toolbar)
    page_layout.addWidget(field)
    window.tabs_widget.addTab(page, "Test")
    window.setCentralWidget(window.tabs_widget)
    window.show()
    app.processEvents()

    MainWindow._setup_keyboard_shortcuts(window)
    field.setFocus()
    window._toolbar_shortcut.activated.emit()
    assert app.focusWidget() is first

    right = QKeyEvent(QEvent.KeyPress, Qt.Key_Right, Qt.NoModifier)
    assert MainWindow.eventFilter(window, first, right)
    assert app.focusWidget() is second

    escape = QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)
    assert MainWindow.eventFilter(window, second, escape)
    assert app.focusWidget() is field


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
