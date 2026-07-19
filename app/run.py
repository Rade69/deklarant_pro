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

    # ── Product similarity memory — osvježi u pozadini ako je zastario ──
    _start_product_similarity_sync()

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


_PRODUCT_SIMILARITY_STALE_DAYS = 7


def _start_product_similarity_sync() -> None:
    """
    Pokreni sync + embedding catalogs.product_similarity_memory u pozadinskom
    daemon thread-u, ali samo ako je zadnje ažuriranje starije od
    _PRODUCT_SIMILARITY_STALE_DAYS. Ranije se ovo pokretalo isključivo ručno
    (scripts/sync_product_similarity_memory.py + embed_product_similarity_memory.py)
    pa je zaostajalo mjesecima — vidi agent_reports/2026-07-19_*.
    """
    try:
        import threading
        thread = threading.Thread(
            target=_run_product_similarity_sync_if_stale,
            daemon=True,
            name="product-similarity-sync",
        )
        thread.start()
        logger.info("Product similarity sync provjera pokrenuta (pozadina)")
    except Exception as e:
        logger.warning("Product similarity sync se ne može pokrenuti: %s", e)


def _run_product_similarity_sync_if_stale() -> None:
    try:
        from datetime import datetime, timedelta

        from database.db import get_db_connection
        from services.agent.learning.product_similarity_memory_service import (
            sync_product_similarity_memory,
        )

        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT MAX(updated_at) AS last_updated FROM catalogs.product_similarity_memory"
                )
                row = cursor.fetchone()
                last_updated = row["last_updated"] if row else None

        if last_updated is not None and datetime.now() - last_updated < timedelta(
            days=_PRODUCT_SIMILARITY_STALE_DAYS
        ):
            logger.info(
                "Product similarity memory je ažurna (zadnje ažuriranje %s) — preskačem sync",
                last_updated,
            )
            return

        logger.info("Product similarity memory zastarjela/prazna — pokrećem sync...")
        sync_result = sync_product_similarity_memory()
        if sync_result.error:
            logger.warning("Product similarity sync greška: %s", sync_result.error)
            return

        try:
            from services.agent.learning.product_similarity_embedding_service import (
                ProductSimilarityEmbeddingService,
            )
            embed_result = ProductSimilarityEmbeddingService().embed_pending(batch_size=200)
            if embed_result.error:
                logger.warning("Product similarity embedding greška: %s", embed_result.error)
                return
            logger.info(
                "Product similarity memory ažurirana: synced=%s, embedded=%s",
                sync_result.synced, embed_result.embedded,
            )
        except ImportError:
            logger.info(
                "sentence-transformers nije instaliran (extra 'embeddings') — "
                "sync=%s završen, embedding preskočen", sync_result.synced,
            )
    except Exception as e:
        logger.warning("Product similarity sync nije uspio: %s", e)


def _stop_mcp_server() -> None:
    """Stop the MCP server on shutdown."""
    global _mcp_client
    if _mcp_client:
        _mcp_client.stop()
        _mcp_client = None
