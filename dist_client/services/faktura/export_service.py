"""
Export Service - Export u Excel i PDF
"""

from pathlib import Path
from typing import List
from core.draft import DeclarationDraft


class ExportService:
    """Export fakturnih stavki u Excel i PDF"""

    @staticmethod
    def export_to_excel(items, filepath: str) -> bool:
        """
        Export stavki u Excel fajl.

        Args:
            items: Lista InvoiceLine stavki
            filepath: Putanja do izlaznog fajla

        Returns:
            True ako je uspješno, False inače
        """
        from services.export_service import ExportService as MainExportService

        return MainExportService.export_to_excel(items, filepath)

    @staticmethod
    def export_to_pdf(draft: DeclarationDraft, filepath: str) -> bool:
        """
        Export draft-a u PDF sa grupisanjem po naimenovanjima.

        Args:
            draft: DeclarationDraft objekat
            filepath: Putanja do izlaznog fajla

        Returns:
            True ako je uspješno, False inače
        """
        from exporters.pdf_invoice_exporter import export_invoice_to_pdf

        return export_invoice_to_pdf(draft, filepath)
