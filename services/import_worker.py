# services/import_worker.py

"""
ASYCUDA Pro - Import Worker (Threading)
Non-blocking import sa progress reporting za PySide6 Qt aplikaciju
"""

from PySide6.QtCore import QThread, Signal
from typing import List, Union
import logging

from core.draft.draft import InvoiceLine
from importers import ImportResult
from services.import_service import get_import_service

logger = logging.getLogger("asycuda_pro.import.worker")


class ImportWorker(QThread):
    """
    Background thread za import.

    Omogućava non-blocking import sa progress reporting u Qt aplikaciji.

    Signals:
        progress(int): Progress percentage (0-100)
        finished(object): Import completed successfully - ImportResult ili List[InvoiceLine]
        error(str): Import failed sa error porukom
    """

    # Qt Signals
    progress = Signal(int)
    finished = Signal(object)  # Changed to object to support both ImportResult and List[InvoiceLine]
    error = Signal(str)

    def __init__(self, filepath: str, parent=None):
        """
        Initialize import worker.

        Args:
            filepath: Path to file to import
            parent: Optional parent QObject
        """
        super().__init__(parent)
        self.filepath = filepath
        self.logger = logger

    def run(self):
        """
        Run import in background thread.

        This method is called when QThread.start() is invoked.
        """

        try:
            self.logger.info(f"Import worker started for: {self.filepath}")

            # Get import service i import with progress callback
            # VAŽNO: koristiti singleton get_import_service() da se sačuva memorija
            # između importa (za auto-kombinovanje parova Excel+PDF)
            from services.import_service import get_import_service
            service = get_import_service()
            result = service.import_file(
                self.filepath,
                progress_callback=self.progress.emit
            )

            # Log based on result type
            if isinstance(result, ImportResult):
                self.logger.info(
                    f"Import completed: {len(result.items)} items, "
                    f"bruto: {result.bruto_kg} kg, neto: {result.neto_kg} kg"
                )
            else:
                self.logger.info(f"Import completed: {len(result)} items")

            # Emit success (result can be ImportResult or List[InvoiceLine])
            self.finished.emit(result)

        except Exception as e:
            self.logger.error(f"Import worker failed: {e}", exc_info=True)

            # Emit error
            error_message = str(e)
            self.error.emit(error_message)


# ============================================================
# USAGE EXAMPLE (za Qt GUI aplikaciju)
# ============================================================

if __name__ == "__main__":
    """
    NOTE: Ovaj primjer ne može se pokrenuti direktno jer zahtijeva Qt aplikaciju.

    Primjer korištenja u GUI kodu:

    from services.import_worker import ImportWorker

    class FakturaTab(QWidget):

        def on_import_button_clicked(self):
            filepath = self.get_selected_file()

            # Create worker
            self.worker = ImportWorker(filepath)

            # Connect signals
            self.worker.progress.connect(self.update_progress_bar)
            self.worker.finished.connect(self.on_import_finished)
            self.worker.error.connect(self.on_import_error)

            # Start import (non-blocking)
            self.worker.start()

        def update_progress_bar(self, percentage: int):
            self.progress_bar.setValue(percentage)

        def on_import_finished(self, items: List[InvoiceLine]):
            # Load items into table
            self.load_items_to_table(items)
            QMessageBox.information(
                self,
                "Import uspješan",
                f"Uvezeno {len(items)} stavki."
            )

        def on_import_error(self, error_message: str):
            QMessageBox.critical(
                self,
                "Greška pri import-u",
                error_message
            )
    """

    logger.debug("ImportWorker - Qt Threading wrapper za import")
    logger.debug()
    logger.debug("Ne može se pokrenuti direktno - zahtijeva Qt aplikaciju.")
    logger.debug("Vidi example usage u kodu iznad.")
