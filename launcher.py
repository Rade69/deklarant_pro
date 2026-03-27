#!/usr/bin/env python3
import sys, os

LOG = "/tmp/asycuda_debug.log"

def log(msg):
    with open(LOG, "a") as f:
        f.write(msg + "\n")

log("=== launcher.py startuje ===")
log(f"DISPLAY={os.environ.get('DISPLAY')}")
log(f"WAYLAND={os.environ.get('WAYLAND_DISPLAY')}")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from PySide6.QtWidgets import QApplication
    log("PySide6 OK")
except Exception as e:
    log(f"PySide6 GRESKA: {e}")
    sys.exit(1)

try:
    from gui.main_window import MainWindow
    log("MainWindow importovan")
except Exception as e:
    log(f"MainWindow GRESKA: {e}")
    sys.exit(1)

try:
    app = QApplication(sys.argv)
    log("QApplication kreiran")
    window = MainWindow()
    log("MainWindow kreiran")
    window.show()
    log("show() pozvan")
    code = app.exec()
    log(f"app.exec() završen sa kodom {code}")
    sys.exit(code)
except Exception as e:
    log(f"GRESKA u pokretanju: {e}")
    import traceback
    log(traceback.format_exc())
    sys.exit(1)
