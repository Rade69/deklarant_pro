from __future__ import annotations

import sys
import signal
import logging
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import Qt, QTimer

logger = logging.getLogger("app.run")

# Global MCP client reference — initialized once, used by all controllers
_mcp_client = None


def get_mcp_client():
    """Get the global MCP client instance (may be None if server not started)."""
    return _mcp_client


def main() -> None:
    global _mcp_client

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

    # ── MCP Server — pokreni u pozadini (ne blokira UI) ─────────────────
    _start_mcp_server(app)

    win = MainWindow()
    win.show()

    exit_code = app.exec()

    # ── Cleanup ─────────────────────────────────────────────────────────
    _stop_mcp_server()
    raise SystemExit(exit_code)


def _start_mcp_server(app: QApplication) -> None:
    """Start the MCP server as a background subprocess."""
    global _mcp_client
    try:
        from mcp_server.client import McpClientAdapter
        _mcp_client = McpClientAdapter()
        _mcp_client.server_ready.connect(
            lambda: logger.info("MCP server ready — tools: %s", _mcp_client.available_tools)
        )
        _mcp_client.server_error.connect(
            lambda msg: logger.warning("MCP server error: %s", msg)
        )
        # Start in a thread so it doesn't block the UI
        import threading
        thread = threading.Thread(
            target=_mcp_client.start,
            daemon=True,
            name="mcp-startup",
        )
        thread.start()
        logger.info("MCP server startup initiated (background)")
    except Exception as e:
        logger.warning("MCP server not available: %s", e)
        _mcp_client = None


def _stop_mcp_server() -> None:
    """Stop the MCP server on shutdown."""
    global _mcp_client
    if _mcp_client:
        _mcp_client.stop()
        _mcp_client = None
