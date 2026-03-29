"""
ProcessingWorker - background thread za procesiranje fajlova.

Koristi import_service (isti kao ručni uvoz kroz Faktura Tab):
- import_service SAM detektuje parove (Excel + PDF)
- import_service SAM kombinuje podatke
- import_service SAM popunjava težine, zemlje, izjave o porijeklu
"""
from PySide6.QtCore import QThread, Signal
from pathlib import Path
from gui.tabs.agent.models.file_item import FileItem


class ProcessingWorker(QThread):
    """Background thread koji parsira fajlove koristeći import_service."""

    progress = Signal(str)             # poruka za activity log
    file_started = Signal(str)         # filepath - počelo procesiranje fajla
    file_completed = Signal(object)    # FileItem - fajl završen
    all_completed = Signal(list)       # List[FileItem] - sve završeno
    error_occurred = Signal(str, str)  # filepath, error_message

    def __init__(self, files: list, parent=None):
        super().__init__(parent)
        self.files = files  # List[FileItem]
        self._cancelled = False

    def cancel(self):
        """Otkaži procesiranje."""
        self._cancelled = True

    def run(self):
        """
        Glavni thread loop - koristi import_service (ISTI KAO RUČNI UVOZ!).
        
        import_service SAM:
        - Detektuje format (Blagić/Master Frigo/ŠUMAPROM/etc.)
        - Detektuje parove (Excel+PDF sa istim brojem fakture)
        - Kombinuje podatke (poziva combine_blagic_excel_and_pdf())
        - Popunjava težine, zemlje, izjave o porijeklu
        """
        import time
        total_start = time.time()
        
        from services.import_service import get_import_service
        from importers.import_result import ImportResult

        # ⭐ KLJUČNO: Koristi singleton import_service (isti kao Faktura Tab!)
        svc = get_import_service()
        svc.clear_memory()  # Resetuj memoriju za detekciju parova

        # ⭐ Sortiraj: grupiraj po imenu fajla, unutar grupe Excel PRVI pa PDF
        # KLJUČNO za višestruke parove: 46VP Excel, 46VP PDF, 47VP Excel, 47VP PDF...
        # Stari sort (svi Exceli pa svi PDF-ovi) kvari import_service memoriju!
        sorted_files = sorted(
            self.files,
            key=lambda f: (
                Path(f.filepath).stem,                                          # Grupiraj po imenu
                0 if f.filepath.lower().endswith(('.xlsx', '.xls')) else 1      # Excel prije PDF
            )
        )

        self.progress.emit(f"📊 Ukupno fajlova: {len(sorted_files)}")
        self.progress.emit(f"🔍 import_service: {svc}")
        self.progress.emit(f"📋 Redoslijed: {[f.filename for f in sorted_files]}")

        # ⭐ Uvozi redom - import_service SAM radi sve!
        for file_item in sorted_files:
            if self._cancelled:
                break

            file_start = time.time()
            self.file_started.emit(file_item.filepath)
            self.progress.emit(f"\n📄 Parsing: {file_item.filename}")
            self.progress.emit(f"   📍 Tip: {file_item.file_type}")
            
            try:
                # ⭐ KORISTI IMPORT_SERVICE (ISTI KAO RUČNI UVOZ!)
                self.progress.emit(f"   🔄 import_service.import_file()...")
                result = svc.import_file(str(file_item.filepath))
                
                if isinstance(result, ImportResult):
                    invoice_lines = result.items
                    
                    # ⭐ Sačuvaj SVE podatke iz ImportResult
                    file_item.bruto_kg = result.bruto_kg
                    file_item.neto_kg = result.neto_kg
                    file_item.has_origin_statement = result.has_origin_statement
                    file_item.origin_statements = result.origin_statements
                    file_item.is_combined = result.is_combined  # ⭐ KLJUČNO za duplikat detekciju
                    file_item.invoice_lines = invoice_lines
                    file_item.status = 'Completed'
                    file_item.detected_parser = getattr(result, '_detected_format', 'auto') or 'auto'
                    file_item.confidence = 1.0 if invoice_lines else 0.4

                    # ⭐ KLJUČNO: Da li je kombinovano?
                    if result.is_combined:
                        self.progress.emit(f"   ✅ KOMBINOVANO (Excel+PDF): {len(invoice_lines)} stavki")
                        self.progress.emit(f"   ⚖️ Bruto: {result.bruto_kg:.2f}kg, Neto: {result.neto_kg:.2f}kg")
                        if result.has_origin_statement:
                            self.progress.emit(f"   🌍 IZJAVA O PORIJEKLU: DA ({len(result.origin_statements or [])} izjava)")
                        else:
                            self.progress.emit(f"   🌍 IZJAVA O PORIJEKLU: NE")
                    else:
                        self.progress.emit(f"   📄 Single import: {len(invoice_lines)} stavki")
                        self.progress.emit(f"   ⚖️ Bruto: {result.bruto_kg:.2f}kg, Neto: {result.neto_kg:.2f}kg")
                    # Prikaži warnings (npr. neto nije pronađen)
                    for w in getattr(result, 'warnings', []):
                        self.progress.emit(f"   {w}")
                elif isinstance(result, list):
                    # Fallback na listu
                    invoice_lines = result
                    file_item.invoice_lines = invoice_lines
                    file_item.status = 'Completed'
                    file_item.detected_parser = 'auto'
                    file_item.confidence = 1.0 if invoice_lines else 0.4
                    self.progress.emit(f"   ✅ List: {len(invoice_lines)} stavki")
                else:
                    file_item.status = 'Error'
                    file_item.error_message = "Nema rezultata"
                    self.progress.emit(f"   ❌ Nema rezultata")
                
                file_elapsed = time.time() - file_start
                self.progress.emit(f"   ⏱️ Vrijeme: {file_elapsed:.1f}s")
                self.file_completed.emit(file_item)
                
            except Exception as e:
                import traceback
                file_item.status = 'Error'
                file_item.error_message = str(e)
                self.error_occurred.emit(file_item.filepath, str(e))
                self.progress.emit(f"   ❌ Greška: {e}")
                self.progress.emit(f"   📋 Stack: {traceback.format_exc()}")
                self.file_completed.emit(file_item)

        # Ukupno vrijeme
        total_elapsed = time.time() - total_start
        self.progress.emit(f"\n{'='*60}")
        self.progress.emit(f"⏱️ UKUPNO: {total_elapsed:.1f}s")
        self.progress.emit(f"📊 Prosjek: {total_elapsed/len(self.files):.1f}s po fajlu")
        self.progress.emit(f"{'='*60}\n")

        self.all_completed.emit(self.files)

    def _parse_xml(self, file_item: FileItem, filepath: Path) -> list:
        """Parsira XML fajl."""
        try:
            from importers.xml_importer import XMLImporter
            importer = XMLImporter()
            result = importer.import_file(filepath)
            file_item.detected_parser = 'XML'
            return result.get('items', [])
        except ImportError:
            # Fallback na import_service
            from services.import_service import get_import_service
            svc = get_import_service()
            result = svc.import_file(str(filepath))
            from importers.import_result import ImportResult
            if isinstance(result, ImportResult):
                return result.items
            elif isinstance(result, list):
                return result
            return []
