# services/import_worker.py

"""
Deklarant Pro - Import Worker (Threading)
Non-blocking import sa progress reporting za PySide6 Qt aplikaciju
"""

from PySide6.QtCore import QThread, Signal
import os
from typing import List, Union
import logging

from core.draft.draft import InvoiceLine
from importers import ImportResult
from services.import_service import get_import_service

logger = logging.getLogger("deklarant_pro.import.worker")


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


class ManualBatchImportWorker(QThread):
    """
    Background thread za ručni grupni uvoz (Faktura tab).

    Parsira sve fajlove u pozadini — GUI thread ostaje responsivan.
    NE prikazuje dijaloge (EUR1/PE2) — to radi main thread u _on_batch_done.

    Signals:
        progress(int, str): (file_index, filename) — ažurira progress dialog
        all_done(list):     lista record dict-ova za post-processing na main threadu
        parse_error(str, str): (filepath, poruka) — non-fatal, dodaje se u failed listu
    """

    progress    = Signal(int, str)
    all_done    = Signal(list)
    parse_error = Signal(str, str)

    def __init__(self, sorted_filepaths: list, parent=None):
        super().__init__(parent)
        self.sorted_filepaths = sorted_filepaths
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        from pathlib import Path
        from services.import_service import ImportService
        from importers.import_result import ImportResult

        # Privatna instanca — ne singleton (race condition sa main threadom)
        svc = ImportService()

        def canonical_path(value) -> str:
            return os.path.normcase(str(Path(value).resolve()))

        consumed_paths: set[str] = set()
        records: list = []

        for i, filepath in enumerate(self.sorted_filepaths):
            if self._cancelled:
                break

            if canonical_path(filepath) in consumed_paths:
                self.progress.emit(i + 1, Path(filepath).name)
                continue

            self.progress.emit(i, Path(filepath).name)
            try:
                result = svc.import_file(filepath)
            except Exception as exc:
                self.parse_error.emit(filepath, str(exc))
                continue

            is_import_result = isinstance(result, ImportResult)
            items      = result.items if is_import_result else list(result)
            bruto_kg   = (result.bruto_kg or 0.0) if is_import_result else 0.0
            neto_kg    = (result.neto_kg  or 0.0) if is_import_result else 0.0
            inv_name   = (result.invoice_name or "") if is_import_result else ""
            is_auth    = getattr(result, "is_authorized_exporter", False)
            has_origin = getattr(result, "has_origin_statement", False)
            warnings   = list(result.warnings) if is_import_result else []

            if inv_name:
                for item in items:
                    if not item.invoice_number:
                        item.invoice_number = inv_name

            consumed_from = (
                list(getattr(result, "consumed_paths", []) or [])
                if is_import_result else []
            )
            for cp in consumed_from:
                canonical_cp = canonical_path(cp)
                consumed_paths.add(canonical_cp)
                for rec in records:
                    if canonical_path(rec["filepath"]) == canonical_cp:
                        rec["skipped"] = True
                        rec["items"] = []

            records.append({
                "filepath":    filepath,
                "items":       items,
                "bruto_kg":    bruto_kg,
                "neto_kg":     neto_kg,
                "invoice_name": inv_name or Path(filepath).stem,
                "is_authorized_exporter": is_auth,
                "has_origin_statement":   has_origin,
                "parser_warnings":        warnings,
                "skipped": False,
            })

        self.all_done.emit(records)


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
