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
_log_dir = os.path.join(os.path.expanduser("~"), ".deklarant_pro", "logs")
_log_file = os.path.join(_log_dir, "deklarant_pro.log")

import logging
import warnings

warnings.filterwarnings('ignore', category=RuntimeWarning, message='Failed to disconnect')

logging.getLogger("deklarant_pro.resize_debug").setLevel(logging.DEBUG)
_handlers = [logging.StreamHandler(sys.stderr)]
try:
    os.makedirs(_log_dir, exist_ok=True)
    _handlers.append(logging.FileHandler(_log_file, encoding="utf-8"))
except OSError:
    pass

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=_handlers
)

try:
    from PySide6.QtWidgets import QApplication, QMessageBox
    from gui.main_window import MainWindow
    from gui.utils.safe_message_box import SafeMessageBox as QMessageBox
except Exception as _import_err:
    # Upiši grešku u log fajl pa prikaži korisniku
    with open(_log_file, "a", encoding="utf-8") as _f:
        import traceback
        _f.write(f"\n=== IMPORT GREŠKA ===\n{traceback.format_exc()}\n")
    raise


def _check_ocr_availability():
    """Proveri da li je OCR (pytesseract) dostupan. Samo log upozorenje."""
    try:
        import pytesseract

        # Učitaj ocr_utils PRIJE provjere — on pri importu auto-detektuje
        # Tesseract na uobičajenim Windows lokacijama (npr. "C:\Program Files\
        # Tesseract-OCR\tesseract.exe") i postavlja pytesseract.tesseract_cmd.
        # Bez ovoga, get_tesseract_version() oslanja se samo na PATH i javlja
        # lažno upozorenje iako je Tesseract instaliran (samo nije u PATH-u).
        try:
            from importers.pdf import ocr_utils  # noqa: F401
        except ImportError:
            pass

        pytesseract.get_tesseract_version()
        logging.getLogger("deklarant_pro").info("✅ OCR (Tesseract) dostupan")
    except ImportError:
        logging.getLogger("deklarant_pro").warning(
            "⚠️ OCR nije dostupan — pytesseract nije instaliran. "
            "Skenirani PDF-ovi neće biti parsirani. "
            "Instaliraj sa: uv sync --extra ocr"
        )
    except Exception as e:
        logging.getLogger("deklarant_pro").warning(
            f"⚠️ OCR nije dostupan — Tesseract greška: {e}"
        )


def _check_autosave_on_startup(parent=None):
    """Ponudi oporavak autosave-a pri startu. Ne blokira aplikaciju ako nema."""
    try:
        from services.draft_autosave_service import has_autosave, autosave_timestamp, load_autosave, clear_autosave
        if not has_autosave():
            return
        ts = autosave_timestamp()
        ts_str = ts.strftime("%d.%m.%Y. %H:%M") if ts else "nepoznato vrijeme"
        reply = QMessageBox.question(
            parent,
            "Nesačuvan rad",
            f"Pronađen je nesačuvan rad iz {ts_str}.\n\n"
            "Da li želite da učitate automatski sačuvanu deklaraciju?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply == QMessageBox.Yes:
            draft = load_autosave()
            if draft is not None:
                # Zamijeni trenutni draft u MainWindow
                from copy import deepcopy
                from dataclasses import fields
                if parent and hasattr(parent, 'draft'):
                    callbacks = list(getattr(parent.draft, "_data_change_callbacks", []) or [])
                    for field_info in fields(type(parent.draft)):
                        if field_info.name == "_data_change_callbacks":
                            continue
                        setattr(parent.draft, field_info.name, deepcopy(getattr(draft, field_info.name)))
                    parent.draft._data_change_callbacks = callbacks
                    parent.draft.dirty = False
                    parent._reload_all_tabs_from_draft()
                    parent._on_dirty()
                    logging.getLogger("deklarant_pro").info("📂 Autosave oporavljen na startu")
        else:
            clear_autosave()
    except Exception as e:
        logging.getLogger("deklarant_pro").warning(f"⚠️ Autosave recovery nije uspio: {e}")


def _check_license_on_startup(parent=None):
    """Proveri licencu pri startu. Ne blokira aplikaciju ako nije validna."""
    try:
        from core.licensing.license_paths import get_license_path
        from core.licensing.license_validator import validate_license_file
        from core.licensing.license_models import LicenseStatus

        result = validate_license_file(get_license_path())

        if result.is_valid:
            if result.status == LicenseStatus.EXPIRED_GRACE:
                QMessageBox.warning(
                    parent, "Licenca ističe", result.message
                )
            return

        QMessageBox.critical(
            parent, "Licenca nije validna",
            f"{result.message}\n\n"
            "Otvorite Admin Panel → Licenca da uvezete novu licencu."
        )
    except Exception as e:
        logging.getLogger("deklarant_pro").warning(
            f"Licenca provera nije uspela: {e}"
        )


def main():
    import time
    _t0 = time.perf_counter()
    mcp_started = False

    if os.name == 'nt':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Carina.DeklarantPro.1")
        # Fusion stil — identičan izgled na Windows i Linux
        os.environ.setdefault("QT_STYLE_OVERRIDE", "Fusion")

    app = QApplication(sys.argv)
    app.setApplicationName("Deklarant Pro")
    app.setDesktopFileName("deklarant-pro")
    app.setOrganizationName("Carina")

    if os.name == 'nt':
        app.setStyle("Fusion")

    # Globalna paleta: selekcija teksta čitljiva na svim widgetima
    # (QPalette Highlight/HighlightedText važi i za widgete sa inline setStyleSheet())
    from PySide6.QtGui import QPalette, QColor, QFont, QIcon
    _font_size = 9 if os.name == 'nt' else 13
    app.setFont(QFont("Segoe UI", _font_size))
    icon_path = os.path.join(_script_dir, "assets", "icons", "deklarant_icon_256.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    palette = app.palette()
    palette.setColor(QPalette.Highlight, QColor("#DBEAFE"))          # Svijetlo plava pozadina
    palette.setColor(QPalette.HighlightedText, QColor("#1E3A8A"))    # Tamno plavi tekst
    # Inactive selection (kad prozor nema fokus) — isti stil
    palette.setColor(QPalette.Inactive, QPalette.Highlight, QColor("#DBEAFE"))
    palette.setColor(QPalette.Inactive, QPalette.HighlightedText, QColor("#1E3A8A"))
    app.setPalette(palette)

    # OCR provera — opciona zavisnost, samo upozorenje ako nedostaje
    _check_ocr_availability()

    try:
        try:
            from app.run import _start_mcp_server
            _start_mcp_server(app)
            mcp_started = True
        except Exception as e:
            logging.getLogger("deklarant_pro").warning(
                f"MCP server nije pokrenut: {e}"
            )

        window = MainWindow()
        window.show()
        _startup_ms = (time.perf_counter() - _t0) * 1000
        logging.getLogger("deklarant_pro").warning(f"⏱️ Startup: {_startup_ms:.0f}ms")

        # Autosave recovery — ponudi oporavak ako postoji nesačuvan rad
        _check_autosave_on_startup(window)

        # Licenca provera — ne blokira aplikaciju, samo upozorenje
        _check_license_on_startup(window)
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

    try:
        exit_code = app.exec()
    finally:
        if mcp_started:
            try:
                from app.run import _stop_mcp_server
                _stop_mcp_server()
            except Exception as e:
                logging.getLogger("deklarant_pro").warning(
                    f"MCP server cleanup nije uspio: {e}"
                )
        try:
            from database.db import close_all_connections
            close_all_connections()
        except Exception as e:
            logging.getLogger("deklarant_pro").warning(
                f"DB pool cleanup nije uspio: {e}"
            )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()


