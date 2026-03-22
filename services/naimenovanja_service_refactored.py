# services/naimenovanja_service_refactored.py

"""
Refactored NaimenovanjaService that extends BaseTabService.
"""

import logging
from typing import Dict, Any, List, Optional
from services.base_service import BaseTabService
from utils.exceptions import ValidationError
from core.draft import DeclarationDraft, NaimenovanjeDraft
from services.naimenovanja.tariff_service import TariffService
from services.origin_statement_detector import OriginStatementDetector
from services.tariff_mapping_service import TariffMappingService, TariffMapping


class NaimenovanjaService(BaseTabService):
    """
    Refactored NaimenovanjaService that extends BaseTabService.
    """
    
    def __init__(self, tab=None):
        """Initialize the service with tariff and origin detection services."""
        super().__init__()
        self.tab = tab
        self.tariff_service = TariffService(tab) if tab else None
        self.origin_detector = OriginStatementDetector()
        self.tariff_mapping_service = TariffMappingService()
        self.logger = logging.getLogger(__name__)
    
    def validate(self, data: Dict[str, Any]) -> bool:
        """
        Validate naimenovanje data.
        
        Args:
            data: Dictionary with naimenovanje data
            
        Returns:
            bool: True if data is valid
        """
        # Validation logic here
        return True
    
    def load_from_draft(self, draft: DeclarationDraft) -> Dict[str, Any]:
        """
        Convert DeclarationDraft to UI data format.
        """
        if not draft:
            return {}
        
        stavke = []
        for naimenovanje in draft.naimenovanja:
            stavka = {
                'redni_broj': naimenovanje.line_number,
                'tarifni_broj': naimenovanje.tariff_code,
                'naziv_proizvoda': naimenovanje.product_name,
                'kolicina': naimenovanje.quantity,
                'jedinica_mjere': naimenovanje.unit_of_measure,
                'cijena': naimenovanje.unit_price,
                'ukupna_vrijednost': naimenovanje.total_value,
                'tezina': naimenovanje.weight,
                'zemlja_porekla': naimenovanje.origin_country,
                'valuta': naimenovanje.currency,
                'status': naimenovanje.status
            }
            stavke.append(stavka)
        
        return {
            'broj_deklaracije': draft.broj_deklaracije,
            'datum_deklaracije': draft.datum,
            'vrsta_deklaracije': draft.vrsta_deklaracije,
            'stavke': stavke
        }
    
    def save_to_draft(self, draft: DeclarationDraft, data: Dict[str, Any]) -> DeclarationDraft:
        """
        Convert UI data to DeclarationDraft.
        """
        if draft is None:
            draft = DeclarationDraft()
        
        draft.broj_deklaracije = data.get('broj_deklaracije', '')
        draft.datum = data.get('datum_deklaracije')
        draft.vrsta_deklaracije = data.get('vrsta_deklaracije')
        
        # Process stavke
        draft.naimenovanja = []
        for stavka_data in data.get('stavke', []):
            naimenovanje = NaimenovanjeDraft()
            naimenovanje.line_number = stavka_data.get('redni_broj', 0)
            naimenovanje.tariff_code = stavka_data.get('tarifni_broj', '')
            naimenovanje.product_name = stavka_data.get('naziv_proizvoda', '')
            naimenovanje.quantity = stavka_data.get('kolicina', 0.0)
            naimenovanje.unit_of_measure = stavka_data.get('jedinica_mjere', '')
            naimenovanje.unit_price = stavka_data.get('cijena', 0.0)
            naimenovanje.total_value = stavka_data.get('ukupna_vrijednost', 0.0)
            naimenovanje.weight = stavka_data.get('tezina', 0.0)
            naimenovanje.origin_country = stavka_data.get('zemlja_porekla', '')
            naimenovanje.currency = stavka_data.get('valuta', '')
            naimenovanje.status = stavka_data.get('status', 'DRAFT')
            
            draft.naimenovanja.append(naimenovanje)
        
        return draft
    
    def suggest_tariff_codes(self, product_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Suggest tariff codes for a product.
        """
        try:
            if not self.tariff_service:
                return []
            
            # Use the existing suggest_tariff method
            suggestions = self.tariff_service.suggest_tariff(
                goods_trade_name=product_name,
                origin_country_code=""
            )
            
            # Convert TariffMapping objects to dictionaries
            result = []
            for mapping in suggestions:
                if hasattr(mapping, 'tariff_code'):
                    result.append({
                        'tariff_code': mapping.tariff_code,
                        'description': getattr(mapping, 'description', ''),
                        'similarity': getattr(mapping, 'similarity', 0.0)
                    })
            
            return result[:limit]
        except Exception as e:
            self.logger.error(f"Error suggesting tariff codes: {e}")
            return []
    
    def detect_origin_statements(self, product_name: str) -> List[Dict[str, Any]]:
        """
        Detect origin statements in product name.
        """
        try:
            # OriginStatementDetector doesn't have a method for product names
            # Return empty list for now
            return []
        except Exception as e:
            self.logger.error(f"Error detecting origin statements: {e}")
            return []
    
    def validate_tariff_code(self, tariff_code: str) -> Dict[str, Any]:
        """
        Validate a tariff code.
        """
        try:
            if not self.tariff_service:
                return {"is_valid": False, "error": "Tariff service not available"}
            
            is_valid = self.tariff_service.validate_tariff(tariff_code)
            return {"is_valid": is_valid, "error": None}
        except Exception as e:
            self.logger.error(f"Error validating tariff code: {e}")
            return {"is_valid": False, "error": str(e)}
    
    def calculate_totals(self, stavke: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Calculate totals for naimenovanje items.
        """
        total_value = 0.0
        total_weight = 0.0
        
        for stavka in stavke:
            total_value += float(stavka.get('ukupna_vrijednost', 0))
            total_weight += float(stavka.get('tezina', 0))
        
        return {
            'ukupna_vrijednost': total_value,
            'ukupna_tezina': total_weight,
            'broj_stavki': len(stavke)
        }
    
    def get_validation_errors(self, data: Dict[str, Any]) -> List[str]:
        """
        Get validation errors for naimenovanje data.
        """
        errors = []
        
        # Validate required fields
        required_fields = ['broj_deklaracije', 'datum_deklaracije', 'vrsta_deklaracije']
        for field in required_fields:
            if not data.get(field):
                errors.append(f"Polje '{field}' je obavezno")
        
        # Validate stavke
        stavke = data.get('stavke', [])
        if not stavke:
            errors.append("Naimenovanje mora imati barem jednu stavku")
        else:
            for i, stavka in enumerate(stavke, 1):
                if not stavka.get('naziv_proizvoda'):
                    errors.append(f"Stavka {i}: Naziv proizvoda je obavezan")
                if not stavka.get('tarifni_broj'):
                    errors.append(f"Stavka {i}: Tarifni broj je obavezan")
                if not stavka.get('kolicina') or float(stavka.get('kolicina', 0)) <= 0:
                    errors.append(f"Stavka {i}: Količina mora biti veća od 0")
        
        return errors
    
    def validate_item(self, item_data: Dict[str, Any]) -> List[str]:
        """
        Validate a single naimenovanje item.
        
        Args:
            item_data: Dictionary with item data
            
        Returns:
            List of validation errors (empty list if valid)
        """
        errors = []
        
        # Validate required fields
        if not item_data.get('naziv_proizvoda'):
            errors.append("Naziv proizvoda je obavezan")
        
        if not item_data.get('tarifni_broj'):
            errors.append("Tarifni broj je obavezan")
        
        if not item_data.get('kolicina') or float(item_data.get('kolicina', 0)) <= 0:
            errors.append("Količina mora biti veća od 0")
        
        if not item_data.get('cijena') or float(item_data.get('cijena', 0)) <= 0:
            errors.append("Cijena mora biti veća od 0")
        
        return errors
    
    def export_to_excel(self, data: Dict[str, Any], filepath: str) -> bool:
        """
        Export naimenovanje data to Excel.
        
        Args:
            data: Naimenovanje data
            filepath: Path to Excel file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            import pandas as pd
            import os
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            # Create DataFrame for stavke
            stavke = data.get('stavke', [])
            if not stavke:
                raise ValidationError("Nema stavki za izvoz")
            
            df = pd.DataFrame(stavke)
            
            # Add basic data as first sheet
            basic_data = {
                'Broj deklaracije': [data.get('broj_deklaracije', '')],
                'Datum deklaracije': [data.get('datum_deklaracije', '')],
                'Vrsta deklaracije': [data.get('vrsta_deklaracije', '')]
            }
            
            # Create Excel writer
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                # Basic data sheet
                pd.DataFrame(basic_data).to_excel(
                    writer, sheet_name='Osnovni podaci', index=False
                )
                
                # Stavke sheet
                df.to_excel(writer, sheet_name='Stavke', index=False)
            
            self._log_operation("export_to_excel", success=True, 
                              details=f"Exported to {filepath}")
            return True
            
        except Exception as e:
            self._log_operation("export_to_excel", success=False, details=str(e))
            self.logger.error(f"Error exporting to Excel: {e}")
            return False