#!/usr/bin/env python3
"""
Deklarant Pro - Application Launcher
"""

import sys
import os

# Projektni root = direktorij gdje se nalazi ovaj fajl
_script_dir = os.path.dirname(os.path.abspath(__file__))

# KRITIČNO: osiguraj da je projektni root u sys.path
# (desktop ikonica nema CWD = project root, za razliku od terminala)
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

# Greške pri pokretanju pisati u log fajl (vidljivo i bez terminala)
_log_file = os.path.join(_script_dir, "asycuda_launch.log")

import logging
import warnings

warnings.filterwarnings('ignore', category=RuntimeWarning, message='Failed to disconnect')

logging.getLogger("deklarant_pro.resize_debug").setLevel(logging.DEBUG)
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler(_log_file, encoding="utf-8"),
    ]
)

try:
    from PySide6.QtWidgets import QApplication, QMessageBox
    from gui.main_window import MainWindow
except Exception as _import_err:
    # Upiši grešku u log fajl pa prikaži korisniku
    with open(_log_file, "a", encoding="utf-8") as _f:
        import traceback
        _f.write(f"\n=== IMPORT GREŠKA ===\n{traceback.format_exc()}\n")
    raise


def main():
    import time
    _t0 = time.perf_counter()

    app = QApplication(sys.argv)
    app.setApplicationName("Deklarant Pro")
    app.setOrganizationName("Carina")

    # Globalna paleta: selekcija teksta čitljiva na svim widgetima
    # (QPalette Highlight/HighlightedText važi i za widgete sa inline setStyleSheet())
    from PySide6.QtGui import QPalette, QColor
    palette = app.palette()
    palette.setColor(QPalette.Highlight, QColor("#DBEAFE"))          # Svijetlo plava pozadina
    palette.setColor(QPalette.HighlightedText, QColor("#1E3A8A"))    # Tamno plavi tekst
    # Inactive selection (kad prozor nema fokus) — isti stil
    palette.setColor(QPalette.Inactive, QPalette.Highlight, QColor("#DBEAFE"))
    palette.setColor(QPalette.Inactive, QPalette.HighlightedText, QColor("#1E3A8A"))
    app.setPalette(palette)

    try:
        window = MainWindow()
        window.show()
        _startup_ms = (time.perf_counter() - _t0) * 1000
        logging.getLogger("deklarant_pro").warning(f"⏱️ Startup: {_startup_ms:.0f}ms")
    except Exception as e:
        import traceback
        msg = QMessageBox()
        msg.setWindowTitle("Deklarant Pro — Greška pri pokretanju")
        msg.setText(str(e))
        msg.setDetailedText(traceback.format_exc())
        msg.setIcon(QMessageBox.Critical)
        msg.exec()
        with open(_log_file, "a", encoding="utf-8") as f:
            f.write(f"\n=== RUNTIME GREŠKA ===\n{traceback.format_exc()}\n")
        sys.exit(1)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
