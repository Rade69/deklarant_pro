# gui/tabs/naimenovanja_controller_refactored.py

"""
Refaktorisani NaimenovanjaController koji koristi BaseTabController.
"""

import logging
from typing import Optional, Dict, Any, List
from gui.tabs.base_controller import BaseTabController
from gui.tabs.naimenovanja_view import NaimenovanjaView
from services.naimenovanja_service_refactored import NaimenovanjaService
from core.draft.draft import DeclarationDraft
from utils.exceptions import ValidationError


class NaimenovanjaController(BaseTabController):
    """
    Refaktorisani NaimenovanjaController koji nasljeđuje BaseTabController.
    """
    
    def __init__(self, view: NaimenovanjaView, service: NaimenovanjaService):
        """
        Inicijalizacija NaimenovanjaController-a.
        
        Args:
            view: NaimenovanjaView instanca
            service: NaimenovanjaService instanca
        """
        super().__init__(view, service)
        self.logger = logging.getLogger(__name__)
        self.draft: Optional[DeclarationDraft] = None
        self.current_index = 0
        self.items_data: List[Dict[str, Any]] = []
        
        # Poveži signale
        self._connect_signals()
    
    def _connect_signals(self):
        """Poveži signale iz view-a sa handler metodama."""
        # Ovdje će se povezati signali kada budu dostupni u view-u
        # Na primjer: self.view.some_signal.connect(self._on_some_signal)
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
            data = self.view.get_data()
            
            # Validacija podataka
            errors = self.service.get_validation_errors(data)
            if errors:
                self.view.show_error("Greške u podacima:\n" + "\n".join(errors))
                return None
            
            # Konvertuj u draft
            if not self.draft:
                from core.draft.draft import DeclarationDraft
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
    
    def suggest_tariff_codes(self, product_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Predloži tarifne brojeve za proizvod.
        
        Args:
            product_name: Naziv proizvoda
            limit: Maksimalan broj predloga
            
        Returns:
            Lista predloženih tarifnih brojeva
        """
        try:
            suggestions = self.service.suggest_tariff_codes(product_name, limit)
            return suggestions
        except Exception as e:
            self.logger.error(f"Greška pri predlaganju tarifnih brojeva: {e}")
            return []
    
    def detect_origin_statements(self, product_name: str) -> List[Dict[str, Any]]:
        """
        Detektuj izjave o poreklu u nazivu proizvoda.
        
        Args:
            product_name: Naziv proizvoda
            
        Returns:
            Lista detektovanih izjava o poreklu
        """
        try:
            return self.service.detect_origin_statements(product_name)
        except Exception as e:
            self.logger.error(f"Greška pri detekciji izjava o poreklu: {e}")
            return []
    
    def validate_tariff_code(self, tariff_code: str) -> Dict[str, Any]:
        """
        Validiraj tarifni broj.
        
        Args:
            tariff_code: Tarifni broj za validaciju
            
        Returns:
            Rezultati validacije
        """
        try:
            return self.service.validate_tariff_code(tariff_code)
        except Exception as e:
            self.logger.error(f"Greška pri validaciji tarifnog broja: {e}")
            return {"is_valid": False, "error": str(e)}
    
    def calculate_totals(self, items: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Izračunaj ukupne vrijednosti.
        
        Args:
            items: Lista stavki
            
        Returns:
            Ukupne vrijednosti
        """
        try:
            return self.service.calculate_totals(items)
        except Exception as e:
            self.logger.error(f"Greška pri računanju totala: {e}")
            return {'total_value': 0.0, 'total_weight': 0.0, 'item_count': 0}
    
    def add_item(self, item_data: Dict[str, Any]) -> bool:
        """
        Dodaj stavku u listu.
        
        Args:
            item_data: Podaci stavke
            
        Returns:
            True ako je uspješno dodano
        """
        try:
            # Validacija stavke
            errors = self.service.validate_item(item_data)
            if errors:
                self.view.show_error("Greške u podacima stavke:\n" + "\n".join(errors))
                return False
            
            # Dodaj stavku u view
            self.view.add_item(item_data)
            return True
            
        except Exception as e:
            self.handle_error(e, "add_item")
            return False
    
    def remove_item(self, item_index: int) -> bool:
        """
        Ukloni stavku iz liste.
        
        Args:
            item_index: Indeks stavke za uklanjanje
            
        Returns:
            True ako je uspješno uklonjeno
        """
        try:
            return self.view.remove_item(item_index)
        except Exception as e:
            self.handle_error(e, "remove_item")
            return False
    
    def get_validation_errors(self) -> List[str]:
        """
        Dobavi greške u validaciji trenutnih podataka.
        
        Returns:
            Lista grešaka u validaciji
        """
        try:
            data = self.view.get_data()
            return self.service.get_validation_errors(data)
        except Exception as e:
            self.logger.error(f"Greška pri validaciji: {e}")
            return [f"Greška pri validaciji: {str(e)}"]
    
    def export_to_excel(self, filepath: str) -> bool:
        """
        Izvezi podatke u Excel.
        
        Args:
            filepath: Putanja do Excel fajla
            
        Returns:
            True ako je uspješno izvezeno
        """
        try:
            data = self.view.get_data()
            return self.service.export_to_excel(data, filepath)
        except Exception as e:
            self.handle_error(e, "export_to_excel")
            return False
    
    def clear_form(self):
        """Očisti formu."""
        try:
            self.view.clear_form()
            self.draft = None
            self.items_data = []
        except Exception as e:
            self.handle_error(e, "clear_form")
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Dobavi sažetak trenutnih podataka.
        
        Returns:
            Sažetak podataka
        """
        try:
            data = self.view.get_data()
            totals = self.calculate_totals(data.get('items', []))
            
            return {
                'item_count': len(data.get('items', [])),
                'total_value': totals.get('total_value', 0),
                'total_weight': totals.get('total_weight', 0),
                'status': 'DRAFT'
            }
        except Exception as e:
            self.logger.error(f"Greška pri dobavljanju sažetka: {e}")
            return {}