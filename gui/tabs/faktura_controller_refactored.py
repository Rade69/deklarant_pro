# gui/tabs/faktura_controller_refactored.py

"""
Refaktorisani FakturaController koji koristi BaseTabController.
"""

import logging
from typing import Optional, Dict, Any, List
from gui.tabs.base_controller import BaseTabController
from gui.tabs.faktura_view import FakturaView
from services.faktura_service_refactored import FakturaService
from core.draft.draft import DeclarationDraft
from utils.exceptions import ValidationError
from gui.tabs.base_controller import BaseTabController


class FakturaController(BaseTabController):
    """
    Refaktorisani FakturaController koji nasljeđuje BaseTabController.
    
    Odgovornosti:
    - Orchestration između View i Service layera
    - Event handling
    - Error handling
    - Progress tracking
    """
    
    def __init__(self, view: 'FakturaView', service: 'FakturaService'):
        """
        Inicijalizacija FakturaController-a.
        
        Args:
            view: FakturaView instanca
            service: FakturaService instanca
        """
        super().__init__(view, service)
        self.logger = logging.getLogger(__name__)
        self.draft: Optional[DeclarationDraft] = None
        
        # Poveži signale
        self._connect_signals()
    
    def _connect_signals(self):
        """Poveži signale iz view-a sa handler metodama."""
        # Ovdje ćemo povezati signale kada View bude spreman
        # Na primjer: self.view.save_requested.connect(self._on_save_requested)
        pass
    
    def load_draft(self, draft: DeclarationDraft):
        """
        Učitaj draft u view.
        
        Args:
            draft: DeclarationDraft objekat
        """
        try:
            self.draft = draft
            data = self.service.load_from_draft(draft)
            self.view.set_data(data)
            self.log_operation("load_draft", success=True)
        except Exception as e:
            self.handle_error(e, "load_draft")
    
    def save_draft(self) -> Optional[DeclarationDraft]:
        """
        Sačuvaj podatke u draft.
        
        Returns:
            Ažurirani draft ili None ako nije uspjelo
        """
        try:
            # Dobavi podatke iz view-a
            data = self.view.get_data()
            
            # Validacija podataka
            errors = self.service.get_validation_errors(data)
            if errors:
                self.view.show_error("Greške u podacima:\n" + "\n".join(errors))
                return None
            
            # Konvertuj u draft
            if not self.draft:
                self.draft = DeclarationDraft()
            
            updated_draft = self.service.save_to_draft(self.draft, data)
            self.draft = updated_draft
            
            self.log_operation("save_draft", success=True)
            return updated_draft
            
        except ValidationError as e:
            self.handle_validation_error(e)
            return None
        except Exception as e:
            self.handle_error(e, "save_draft")
            return None
    
    def import_invoice(self, file_path: str) -> Dict[str, Any]:
        """
        Uvezi fakturu iz fajla.
        
        Args:
            file_path: Putanja do fajla za import
            
        Returns:
            Rezultat importa
        """
        try:
            result = self.service.import_invoice(file_path)
            if result.get('success'):
                # Ažuriraj view sa uvezenim podacima
                self.view.set_data(result.get('data', {}))
                self.handle_success("Faktura uspješno uvezena")
            return result
        except Exception as e:
            self.handle_error(e, "import_invoice")
            return {'success': False, 'error': str(e)}
    
    def calculate_totals(self, items: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Izračunaj ukupne vrijednosti.
        
        Args:
            items: Lista stavki fakture
            
        Returns:
            Dictionary sa ukupnim vrijednostima
        """
        try:
            return self.service.calculate_totals(items)
        except Exception as e:
            self.handle_error(e, "calculate_totals")
            return {'total_value': 0.0, 'total_weight': 0.0, 'item_count': 0}
    
    def validate_invoice(self, data: Dict[str, Any]) -> List[str]:
        """
        Validiraj podatke fakture.
        
        Args:
            data: Podaci fakture za validaciju
            
        Returns:
            Lista grešaka (prazna lista ako nema grešaka)
        """
        try:
            return self.service.get_validation_errors(data)
        except Exception as e:
            self.logger.error(f"Greška pri validaciji: {e}")
            return ["Greška pri validaciji podataka"]
    
    def export_to_excel(self, file_path: str, data: Dict[str, Any]) -> bool:
        """
        Izvezi fakturu u Excel.
        
        Args:
            file_path: Putanja za čuvanje Excel fajla
            data: Podaci za izvoz
            
        Returns:
            True ako je uspješno, False inače
        """
        try:
            result = self.service.export_to_excel(file_path, data)
            if result:
                self.handle_success("Faktura uspješno izvezena u Excel")
            return result
        except Exception as e:
            self.handle_error(e, "export_to_excel")
            return False
    
    def add_invoice_item(self, item_data: Dict[str, Any]) -> bool:
        """
        Dodaj stavku fakture.
        
        Args:
            item_data: Podaci stavke
            
        Returns:
            True ako je uspješno dodano
        """
        try:
            # Validacija stavke
            errors = self.service.validate_invoice_item(item_data)
            if errors:
                self.view.show_warning("\n".join(errors))
                return False
            
            # Dodaj stavku u view
            self.view.add_invoice_item(item_data)
            return True
            
        except Exception as e:
            self.handle_error(e, "add_invoice_item")
            return False
    
    def remove_invoice_item(self, item_index: int) -> bool:
        """
        Ukloni stavku fakture.
        
        Args:
            item_index: Indeks stavke za uklanjanje
            
        Returns:
            True ako je uspješno uklonjeno
        """
        try:
            return self.view.remove_invoice_item(item_index)
        except Exception as e:
            self.handle_error(e, "remove_invoice_item")
            return False
    
    def calculate_totals_async(self, items: List[Dict[str, Any]]) -> None:
        """
        Asinhrono izračunaj ukupne vrijednosti.
        
        Args:
            items: Lista stavki fakture
        """
        try:
            totals = self.service.calculate_totals(items)
            self.view.update_totals_display(totals)
        except Exception as e:
            self.handle_error(e, "calculate_totals_async")
    
    def validate_and_save(self) -> bool:
        """
        Validiraj i sačuvaj fakturu.
        
        Returns:
            True ako je uspješno sačuvano
        """
        try:
            # Dobavi podatke iz view-a
            data = self.view.get_data()
            
            # Validacija
            errors = self.service.get_validation_errors(data)
            if errors:
                self.view.show_error("Greške u podacima:\n" + "\n".join(errors))
                return False
            
            # Sačuvaj
            if self.save_draft():
                self.handle_success("Faktura uspješno sačuvana")
                return True
            return False
            
        except Exception as e:
            self.handle_error(e, "validate_and_save")
            return False
    
    def get_invoice_summary(self) -> Dict[str, Any]:
        """
        Dobavi sažetak fakture.
        
        Returns:
            Dictionary sa sažetkom fakture
        """
        try:
            data = self.view.get_data()
            totals = self.service.calculate_totals(data.get('items', []))
            
            return {
                'total_items': len(data.get('items', [])),
                'total_value': totals.get('total_value', 0),
                'total_weight': totals.get('total_weight', 0),
                'currency': data.get('currency', 'EUR'),
                'status': 'DRAFT'
            }
        except Exception as e:
            self.handle_error(e, "get_invoice_summary")
            return {}
    
    def reset_form(self):
        """Resetuj formu na početno stanje."""
        try:
            self.view.clear_form()
            self.draft = None
            self.handle_success("Forma resetovana")
        except Exception as e:
            self.handle_error(e, "reset_form")
    
    def print_invoice(self) -> bool:
        """
        Printaj fakturu.
        
        Returns:
            True ako je uspješno printano
        """
        try:
            data = self.view.get_data()
            # Ovdje bi se pozvao servis za printanje
            # print_service.print_invoice(data)
            self.handle_success("Faktura poslana na print")
            return True
        except Exception as e:
            self.handle_error(e, "print_invoice")
            return False