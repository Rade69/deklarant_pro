from __future__ import annotations

import sys
import signal
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import Qt, QTimer


def main() -> None:
    # Import ovde da izbegnemo kružne importe na startu
    from gui.main_window import MainWindow

    app = QApplication(sys.argv)

    # Omogući Ctrl+C da zaustavi aplikaciju
    # Qt blokira Python signal handling, pa moramo periodično
    # dozvoliti Pythonu da procesuje signale
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # Timer koji periodično aktivira Python interpreter
    # da može da procesuje signale (Ctrl+C)
    timer = QTimer()
    timer.timeout.connect(lambda: None)  # Prazna funkcija, samo da probudi interpreter
    timer.start(500)  # Svakih 500ms

    # ASYCUDA World svetla tema - forsiramo svetle boje
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(240, 240, 240))
    palette.setColor(QPalette.WindowText, QColor(0, 0, 0))
    palette.setColor(QPalette.Base, QColor(255, 255, 255))
    palette.setColor(QPalette.AlternateBase, QColor(245, 245, 245))
    palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 220))
    palette.setColor(QPalette.ToolTipText, QColor(0, 0, 0))
    palette.setColor(QPalette.Text, QColor(0, 0, 0))
    palette.setColor(QPalette.Button, QColor(240, 240, 240))
    palette.setColor(QPalette.ButtonText, QColor(0, 0, 0))
    palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
    palette.setColor(QPalette.Link, QColor(0, 0, 255))
    palette.setColor(QPalette.Highlight, QColor(0, 120, 215))
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))

    app.setPalette(palette)
    app.setStyle("Fusion")

    # Provjeri konekciju na bazu — prikaži setup dialog ako treba
    from gui.dialogs.db_setup_dialog import check_and_setup_db
    if not check_and_setup_db(app):
        raise SystemExit(0)

    win = MainWindow()
    win.show()
    raise SystemExit(app.exec())
