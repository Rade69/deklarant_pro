# gui/tabs/faktura_controller.py

"""
Faktura Controller - Orchestration Layer

Koordinacija između View i Service layer-a.
NEMA direktne UI manipulacije ili business logike.

Odgovornosti:
- Event handling (button clicks, signals)
- Orchestration (View ↔ Service communication)
- Error handling i poruke korisniku
- Progress tracking
"""

from typing import Optional, List, Dict, Any
from gui.tabs.faktura_view import FakturaView
from services.faktura_service import FakturaService
from core.draft.draft import DeclarationDraft


class FakturaController:
    """
    Controller layer za Faktura tab - orchestration!
    
    Odgovornosti:
    - Povezivanje View signala sa handler-ima
    - Orchestration load/save operacija
    - Error handling
    - User feedback
    
    NEMA:
    - Direktne UI manipulacije (to radi View)
    - Business logike (to radi Service)
    """
    
    def __init__(self, view: FakturaView, service: FakturaService):
        """
        Inicijalizacija Controller-a.
        
        Args:
            view: FakturaView instanca
            service: FakturaService instanca
        """
        self.view = view
        self.service = service
        self.draft: Optional[DeclarationDraft] = None
        
        # Connect signals
        self._connect_signals()
    
    def _connect_signals(self):
        """Povezivanje View signala sa handler metodama."""
        # Import signals
        self.view.import_requested.connect(self._on_import_requested)
        self.view.load_master_requested.connect(self._on_load_master_requested)

        # Export signals
        self.view.export_requested.connect(self._on_export_requested)

        # Edit signals
        self.view.add_item_requested.connect(self._on_add_item)
        self.view.delete_item_requested.connect(self._on_delete_item)
        self.view.clear_all_requested.connect(self._on_clear_all)

        # Smart features
        self.view.validate_requested.connect(self._on_validate)
        self.view.calc_masses_requested.connect(self._on_calc_masses)
        self.view.auto_fill_requested.connect(self._on_auto_fill)
        self.view.load_mappings_requested.connect(self._on_load_mappings)

        # Naimenovanja
        self.view.create_naimenovanja_requested.connect(self._on_create_naimenovanja)

        # Data changes
        self.view.data_changed.connect(self._on_data_changed)
    
    # ============================================================
    # PUBLIC METHODS
    # ============================================================
    
    def load_data(self, draft: DeclarationDraft):
        """
        Orchestrate učitavanje podataka iz Draft-a.
        
        1. Pozovi Service da konvertuje Draft → data dict
        2. Pozovi View da prikaže podatke
        3. Handle errors
        """
        try:
            self.draft = draft
            data = self.service.load_from_draft(draft)
            self.view.set_data(data)
            self.handle_success(f"Učitano {len(data['items'])} stavki")
        except Exception as e:
            self.handle_error(e, "load_data")
    
    def save_data(self) -> Optional[DeclarationDraft]:
        """
        Orchestrate čuvanje podataka u Draft.
        
        1. Pozovi View da prikupi podatke
        2. Pozovi Service da validira
        3. Pozovi Service da konvertuje View data → Draft
        4. Return Draft
        5. Handle errors
        """
        try:
            # Get data from View
            data = self.view.get_data()
            
            # Validate
            errors = self._validate_data(data)
            if errors:
                self._show_validation_errors(errors)
                return None
            
            # Save to Draft
            if self.draft:
                self.draft = self.service.save_to_draft(self.draft, data)
                self.handle_success(f"Sačuvano {len(self.draft.items)} stavki")
                return self.draft
            
            return None
            
        except Exception as e:
            self.handle_error(e, "save_data")
            return None
    
    def handle_error(self, error: Exception, context: str):
        """
        Centralizovano error handling.
        
        Args:
            error: Exception koji se desio
            context: Kontekst gdje se error desio
        """
        msg = f"Greška ({context}): {str(error)}"
        self.view.show_error(msg)
    
    def handle_success(self, msg: str):
        """
        Centralizovano success handling.
        
        Args:
            msg: Success poruka
        """
        self.view.show_success(msg)
    
    # ============================================================
    # EVENT HANDLERS
    # ============================================================
    
    def _on_import_requested(self, file_format: str):
        """
        Handler za import request.

        Args:
            file_format: 'pdf', 'excel', ili 'xml'
        """
        from PySide6.QtWidgets import QFileDialog

        filters = {
            'pdf': "PDF Files (*.pdf)",
            'excel': "Excel Files (*.xlsx *.xls)",
            'xml': "XML Files (*.xml)",
        }

        filepath, _ = QFileDialog.getOpenFileName(
            self.view,
            f"Import {file_format.upper()}",
            "",
            filters.get(file_format, "All Files (*)")
        )

        if filepath:
            try:
                # TODO: Implement actual import via ImportWorker
                self.view.show_warning(f"Import {file_format.upper()} iz: {filepath}\n(Ova funkcionalnost će biti implementirana)")
            except Exception as e:
                self.handle_error(e, f"import_{file_format}")

    def _on_load_master_requested(self):
        """Handler za load master list request."""
        from PySide6.QtWidgets import QFileDialog
        
        filepath, _ = QFileDialog.getOpenFileName(
            self.view,
            "Učitaj glavnu listu",
            "",
            "Excel Files (*.xlsx *.xls)"
        )
        
        if filepath:
            try:
                self.view.show_success(f"Učitavanje master liste iz: {filepath}\n(Ova funkcionalnost će biti implementirana)")
            except Exception as e:
                self.handle_error(e, "load_master")
    
    def _on_export_requested(self, format: str):
        """
        Handler za export request.
        
        Args:
            format: 'pdf' ili 'excel'
        """
        from PySide6.QtWidgets import QFileDialog
        
        if format == 'excel':
            filepath, _ = QFileDialog.getSaveFileName(
                self.view,
                "Export to Excel",
                "",
                "Excel Files (*.xlsx)"
            )
        else:
            filepath, _ = QFileDialog.getSaveFileName(
                self.view,
                "Export to PDF",
                "",
                "PDF Files (*.pdf)"
            )
        
        if filepath:
            try:
                # TODO: Implement actual export
                self.view.show_warning(f"Export {format.upper()} u: {filepath}\n(Ova funkcionalnost će biti implementirana)")
            except Exception as e:
                self.handle_error(e, f"export_{format}")
    
    def _on_add_item(self):
        """Handler za dodavanje stavke."""
        # TODO: Open dialog to add item
        self.view.show_warning("Dodavanje stavke (biće implementirano)")
    
    def _on_delete_item(self):
        """Handler za brisanje stavke."""
        if not self.view.table:
            return
        
        selected_rows = self.view.table.selectedItems()
        if not selected_rows:
            self.view.show_warning("Odaberite stavku za brisanje")
            return
        
        # Get row from first selected item
        row = selected_rows[0].row()
        self.view.table.removeRow(row)
        self.view.data_changed.emit()
    
    def _on_clear_all(self):
        """Handler za čišćenje svih stavki."""
        from PySide6.QtWidgets import QMessageBox
        
        reply = QMessageBox.question(
            self.view,
            "Očisti sve",
            "Da li ste sigurni da želite obrisati sve stavke?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.view.clear_form()
            self.view.data_changed.emit()
    
    def _on_validate(self):
        """Handler za validaciju podataka."""
        data = self.view.get_data()
        errors_by_row = self.service.validate_all_items(data['items'])
        
        if not errors_by_row:
            self.handle_success("✅ Sve stavke su validne")
            return
        
        # Show errors and color rows
        for row, errors in errors_by_row.items():
            self.view.set_validation_state(row, 'invalid')
        
        total_errors = sum(len(e) for e in errors_by_row.values())
        self.view.show_warning(f"Pronađeno {total_errors} grešaka u {len(errors_by_row)} stavki")
    
    def _on_calc_masses(self):
        """Handler za kalkulaciju masa."""
        # TODO: Implement mass calculation
        self.view.show_warning("Kalkulacija masa (biće implementirano)")
    
    def _on_auto_fill(self):
        """Handler za auto-fill."""
        # TODO: Implement auto-fill from master list
        self.view.show_warning("Auto-fill (biće implementirano)")

    def _on_load_mappings(self):
        """Handler za učitavanje XML mapiranja."""
        # TODO: Implement XML mapping load
        self.view.show_warning("Učitavanje XML mapiranja (biće implementirano)")

    def _on_create_naimenovanja(self):
        """Handler za kreiranje naimenovanja."""
        if not self.draft:
            self.view.show_warning("Prvo učitajte fakturu")
            return
        
        try:
            naimenovanja = self.service.create_naimenovanja_from_faktura(self.draft)
            self.handle_success(f"Kreirano {len(naimenovanja)} naimenovanja")
            # TODO: Send to NaimenovanjaTab
        except Exception as e:
            self.handle_error(e, "create_naimenovanja")
    
    def _on_data_changed(self):
        """Handler za promjenu podataka."""
        # Update statistics
        data = self.view.get_data()
        totals = self.service.calculate_totals(data['items'])

        # Update status bar via view - koristi izračunate težine
        self.view.update_status_bar(
            item_count=len(data['items']),
            total_amount=totals.get('total_iznos', 0.0),
            total_quantity=int(totals.get('total_kolicina', 0)),
            total_bruto=totals.get('total_bruto_mass', 0.0),
            total_neto=totals.get('total_neto_mass', 0.0),
            validation_status="⚪ Neprovjereno",
            assembly_status="N/A"
        )
    
    # ============================================================
    # PRIVATE HELPERS
    # ============================================================
    
    def _validate_data(self, data: Dict[str, Any]) -> List[str]:
        """
        Validiraj sve podatke.
        
        Args:
            data: View data dict
        
        Returns:
            Lista error poruka
        """
        all_errors = []
        
        # Check if items exist
        if not data.get('items'):
            all_errors.append("Faktura nema stavki")
            return all_errors
        
        # Validate each item
        errors_by_row = self.service.validate_all_items(data['items'])
        for row, errors in errors_by_row.items():
            all_errors.extend([f"Stavka {row + 1}: {e}" for e in errors])
        
        return all_errors
    
    def _show_validation_errors(self, errors: List[str]):
        """
        Prikaži validation errors.
        
        Args:
            errors: Lista error poruka
        """
        msg = "Pronađene su sljedeće greške:\n\n" + "\n".join(f"• {e}" for e in errors)
        self.view.show_warning(msg)
