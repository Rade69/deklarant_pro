"""
Import Service - Upravljanje importom fajlova
"""

from pathlib import Path
from typing import List, Tuple, Optional
from services.import_worker import ImportWorker
from importers.import_result import ImportResult


class ImportService:
    """Kompletna logika za import PDF/Excel/XML fajlova"""

    def __init__(self, tab):
        """Inicijalizacija sa referencom na tab"""
        self.tab = tab
        self.import_service = None

    def import_pdf(self, filepath: str) -> Optional[ImportResult]:
        """Import PDF fajla"""
        return self._import_file(filepath, "pdf")

    def import_excel(self, filepath: str) -> Optional[ImportResult]:
        """Import Excel fajla"""
        return self._import_file(filepath, "excel")

    def import_xml(self, filepath: str):  # type: ignore[return]
        """Import ASYCUDA XML fajla"""
        from importers.xml_importer import XMLImporter

        importer = XMLImporter()
        result = importer.import_file(Path(filepath))
        return result

    def _import_file(self, filepath: str, file_type: str) -> Optional[ImportResult]:
        """Import jednog fajla koristeći ImportWorker"""
        worker = ImportWorker(filepath)
        result = worker.run()  # Synchronous run
        return result

    def import_multiple_files(self, filepaths: List[str]) -> dict:
        """
        Import više fajlova odjednom.

        Args:
            filepaths: Lista putanja do fajlova

        Returns:
            Dict sa rezultatima:
            {
                "items": List[InvoiceLine],
                "total_bruto_kg": float,
                "total_neto_kg": float,
                "successful": int,
                "failed": int
            }
        """
        from services.import_service import ImportService as MainImportService

        # Kreiraj instancu glavne import service
        import_service = MainImportService()

        # Agregatori za rezultate
        all_items = []
        total_bruto_kg = 0.0
        total_neto_kg = 0.0
        successful_imports = 0
        failed_imports = 0

        for filepath in filepaths:
            try:
                result = import_service.import_file(filepath)

                if isinstance(result, ImportResult):
                    all_items.extend(result.items)
                    total_bruto_kg += result.bruto_kg or 0.0
                    total_neto_kg += result.neto_kg or 0.0
                    successful_imports += 1
                else:
                    failed_imports += 1
            except Exception as e:
                failed_imports += 1

        return {
            "items": all_items,
            "total_bruto_kg": total_bruto_kg,
            "total_neto_kg": total_neto_kg,
            "successful": successful_imports,
            "failed": failed_imports,
        }

    def extract_import_result_data(
        self, result
    ) -> Tuple[List, float, float, str, bool, str]:
        """
        Ekstraktuje stavke i metadata iz ImportResult-a.

        Args:
            result: ImportResult ili List[InvoiceLine]

        Returns:
            Tuple: (items, bruto_kg, neto_kg, invoice_name, is_combined, import_type)
        """
        if isinstance(result, ImportResult):
            items = result.items
            bruto_kg = result.bruto_kg or 0.0
            neto_kg = result.neto_kg or 0.0
            invoice_name = result.invoice_name or ""
            is_combined = result.is_combined or False
            import_type = result.import_type or "unknown"
        else:
            items = result if isinstance(result, list) else []
            bruto_kg = 0.0
            neto_kg = 0.0
            invoice_name = ""
            is_combined = False
            import_type = "unknown"

        return items, bruto_kg, neto_kg, invoice_name, is_combined, import_type

    def get_invoice_name(self, invoice_name_from_result: str) -> str:
        """Dobij naziv fakture iz rezultata ili filepath-a"""
        if invoice_name_from_result:
            return invoice_name_from_result

        if hasattr(self.tab, "import_worker") and self.tab.import_worker:
            filepath = getattr(self.tab.import_worker, "filepath", "")
            if filepath:
                return Path(filepath).name

        return "Unknown"

    def track_file_type(self, filepath: str) -> None:
        """Broji Excel vs PDF importovane fajlove"""
        ext = Path(filepath).suffix.lower()

        if ext == ".xlsx" or ext == ".xls":
            self.tab.imported_excel_count += 1
        elif ext == ".pdf":
            self.tab.imported_pdf_count += 1
