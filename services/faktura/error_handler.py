"""
Error Handler - Centralizovano rukovanje greškama
"""

from typing import Optional
from PySide6.QtWidgets import QMessageBox


class ErrorHandler:
    """Centralizovano rukovanje greškama"""

    def __init__(self, parent):
        self.parent = parent

    def handle_error(self, error: Exception, context: str = "") -> None:
        """
        Uniformno rukovanje greškama.

        Args:
            error: Izuzetak koji se desio
            context: Kontekst u kojem se greška desila (npr. "Import", "Validacija")
        """
        from PySide6.QtWidgets import QMessageBox
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"[{context}] Greška: {error}")

        # Očisti UI stanje
        if hasattr(self.parent, "_set_buttons_enabled"):
            self.parent._set_buttons_enabled(True)
        if hasattr(self.parent, "progress_bar") and self.parent.progress_bar:
            self.parent.progress_bar.setVisible(False)
            self.parent.progress_bar.setValue(0)

        # Prikaži poruku
        QMessageBox.critical(
            self.parent,
            "Greška",
            f"{context}\n\n{str(error)}",
        )

    def handle_validation_error(self, error: Exception) -> None:
        """Rukuje greškama u validaciji"""
        self.handle_error(error, "Validacija")

    def handle_import_error(self, error: Exception) -> None:
        """Rukuje greškama u importu"""
        self.handle_error(error, "Import")

    def handle_export_error(self, error: Exception) -> None:
        """Rukuje greškama u exportu"""
        self.handle_error(error, "Export")

    def handle_auto_fill_error(self, error: Exception) -> None:
        """Rukuje greškama u auto-popunjavanju"""
        self.handle_error(error, "Auto-popunjavanje")
