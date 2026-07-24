import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication, QPushButton

from gui.main_window import MainWindow


def test_exit_button_keeps_vertical_margin_from_tab_bar():
    app = QApplication.instance() or QApplication([])
    button = QPushButton()

    class TabBar:
        @staticmethod
        def geometry():
            return QRect(0, 0, 600, 40)

    class Tabs:
        @staticmethod
        def tabBar():
            return TabBar()

    window = type(
        "Window",
        (),
        {"btn_exit_app": button, "tabs_widget": Tabs()},
    )()

    MainWindow._position_exit_button(window)

    assert button.height() == 32
    assert button.y() == 4
    assert button.geometry().bottom() <= 35
    assert button.x() == 611
    app.processEvents()
