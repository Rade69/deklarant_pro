#!/usr/bin/env python3
"""
ASYCUDA Pro - Application Launcher
Jednostavno pokretanje aplikacije
"""

import sys
import os

# Dodaj venv site-packages u sys.path ako venv nije aktiviran
_script_dir = os.path.dirname(os.path.abspath(__file__))
if not os.environ.get("VIRTUAL_ENV"):
    import glob as _glob
    _patterns = os.path.join(_script_dir, "venv", "lib", "python*", "site-packages")
    for _sp in _glob.glob(_patterns):
        if _sp not in sys.path:
            sys.path.insert(0, _sp)
import logging
import warnings

# Suppress RuntimeWarnings about signal disconnections
warnings.filterwarnings('ignore', category=RuntimeWarning, message='Failed to disconnect')

# Redirect stderr and stdout to suppress verbose startup messages
# (QtAwesome load messages, etc.)
class StderrSuppressor:
    """Suppress stderr messages during startup"""
    def write(self, text):
        pass  # Ignore all stderr output
    def flush(self):
        pass

# Save original stderr for later restoration
_original_stderr = sys.stderr

# Suppress stderr during imports (QtAwesome, etc.)
sys.stderr = StderrSuppressor()
sys.stdout = StderrSuppressor()

# Add parent directory to path so asycuda_pro.* imports work
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from gui.main_window import MainWindow


def main():
    """Pokreni ASYCUDA Pro aplikaciju"""

    # Restore stderr/stdout so errors and warnings can be seen
    sys.stderr = _original_stderr
    sys.stdout = _original_stderr

    # Configure logging - WARNING level hides verbose INFO messages
    # force=True resetuje postojeće log konfiguracije
    logging.basicConfig(
        level=logging.WARNING,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S',
        force=True
    )

    # Kreiraj Qt aplikaciju
    app = QApplication(sys.argv)
    app.setApplicationName("ASYCUDA Pro")
    app.setOrganizationName("Carina")

    # Kreiraj i prikaži glavni prozor
    window = MainWindow()
    window.show()

    # Pokreni event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
