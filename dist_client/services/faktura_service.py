# services/faktura_service.py

"""
Faktura Service - Business Logic Layer

Service layer za Faktura tab - potpuno Qt-independent.
Odgovoran za:
- PDF/Excel/XML parsing (kroz ImportWorker)
- Validaciju podataka
- Kalkulacije (ukupne mase, vrijednosti)
- Data conversion (Draft ↔ View data)
- Assembly (kreiranje Naimenovanja iz Faktura)
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from core.draft.draft import DeclarationDraft, InvoiceLine
from importers.import_result import ImportResult


class FakturaService:
    """
    Service layer za Faktura tab - Qt independent!
    
    Odgovornosti:
    - Business logic (validacija, kalkulacije)
    - Data conversion (Draft ↔ View data)
    - Assembly (Faktura → Naimenovanja)
    - Import/Export orchestration
    
    NEMA:
    - UI kreiranje
    - Signal/Slot mehanizam
    - Direct database pristup (koristi get_db_connection)
    """
    
    def __init__(self):
        """Inicijalizacija bez Qt dependency."""
        pass
    
    # ============================================================
    # KRITIČNE METODE - DRAFT CONVERSION
    # ============================================================
    
    def load_from_draft(self, draft: DeclarationDraft) -> Dict[str, Any]:
        """
        Konvertuj DeclarationDraft → View data format.

        Args:
            draft: DeclarationDraft objekat

        Returns:
            Dict sa podacima spremnim za View.set_data()
        """
        data = {
            'invoice_name': getattr(draft, 'invoice_name', ''),
            'invoice_date': getattr(draft, 'invoice_date', ''),
            'currency': getattr(draft, 'currency', 'EUR'),
            'items': [],
            'total_bruto': 0.0,
            'total_neto': 0.0,
        }

        # Convert InvoiceLine items to dict format for View
        if hasattr(draft, 'items') and draft.items:
            for item in draft.items:
                item_data = {
                    'line_no': getattr(item, 'line_no', 0),
                    'tariff_code': getattr(item, 'tarifni_broj', ''),
                    'description': getattr(item, 'naziv_robe', ''),
                    'quantity': getattr(item, 'kolicina', 0.0),
                    'unit_price': getattr(item, 'cijena_jed', 0.0),
                    'total_price': getattr(item, 'iznos', 0.0),
                    'bruto_mass': getattr(item, 'bruto_kg', 0.0),
                    'neto_mass': getattr(item, 'neto_kg', 0.0),
                    'currency': getattr(item, 'valuta', 'EUR'),
                    'origin_country': getattr(item, 'zemlja_porijekla', ''),
                    'country_confidence': getattr(item, 'country_confidence', ''),
                }
                data['items'].append(item_data)
                data['total_bruto'] += item_data['bruto_mass']
                data['total_neto'] += item_data['neto_mass']

        self._log_operation("load_from_draft", True, len(data['items']))
        return data
    
    def save_to_draft(
        self,
        draft: DeclarationDraft,
        data: Dict[str, Any]
    ) -> DeclarationDraft:
        """
        Konvertuj View data → DeclarationDraft.
        
        Args:
            draft: DeclarationDraft objekat
            data: View data dict
        
        Returns:
            Ažurirani Draft objekat
        """
        # Update header fields
        draft.invoice_name = data.get('invoice_name', '')
        draft.invoice_date = data.get('invoice_date', '')
        draft.currency = data.get('currency', 'EUR')
        
        # Update items (ako su promijenjeni)
        if 'items' in data:
            from core.draft.draft import InvoiceLine
            draft.items = []
            for item_data in data['items']:
                item = InvoiceLine(
                    line_no=item_data.get('line_no', 0),
                    tarifni_broj=item_data.get('tariff_code', ''),
                    naziv_robe=item_data.get('description', ''),
                    kolicina=item_data.get('quantity', 0.0),
                    cijena_jed=item_data.get('unit_price', 0.0),
                    iznos=item_data.get('total_price', 0.0),
                    bruto_kg=item_data.get('bruto_mass', 0.0),
                    neto_kg=item_data.get('neto_mass', 0.0),
                    valuta=item_data.get('currency', 'EUR'),
                    zemlja_porijekla=item_data.get('origin_country', ''),
                    country_confidence=item_data.get('country_confidence', ''),
                )
                draft.items.append(item)
        
        self._log_operation("save_to_draft", True, len(draft.items))
        return draft
    
    # ============================================================
    # BUSINESS LOGIC - VALIDATION
    # ============================================================
    
    def validate_item(self, item_data: Dict[str, Any]) -> List[str]:
        """
        Validiraj stavku fakture.
        
        Args:
            item_data: Dict sa podacima stavke
        
        Returns:
            Lista error poruka (prazna ako nema errora)
        """
        errors = []
        
        # Required fields
        if not item_data.get('tariff_code'):
            errors.append("Tarifni broj je obavezan")
        
        if not item_data.get('description'):
            errors.append("Opis robe je obavezan")
        
        # Quantity validation
        quantity = item_data.get('quantity', 0)
        if quantity <= 0:
            errors.append("Količina mora biti veća od 0")
        
        # Price validation
        unit_price = item_data.get('unit_price', 0)
        if unit_price < 0:
            errors.append("Jedinična cijena ne može biti negativna")
        
        # Mass validation
        bruto = item_data.get('bruto_mass', 0)
        neto = item_data.get('neto_mass', 0)
        if bruto < neto:
            errors.append("Bruto masa ne može biti manja od neto mase")
        
        return errors
    
    def validate_all_items(self, items: List[Dict[str, Any]]) -> Dict[int, List[str]]:
        """
        Validiraj sve stavke.
        
        Args:
            items: Lista stavki
        
        Returns:
            Dict {row_index: [error_messages]}
        """
        errors_by_row = {}
        
        for i, item in enumerate(items):
            errors = self.validate_item(item)
            if errors:
                errors_by_row[i] = errors
        
        return errors_by_row
    
    # ============================================================
    # BUSINESS LOGIC - CALCULATIONS
    # ============================================================
    
    def calculate_totals(self, items: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Kalkulacija ukupnih vrijednosti.
        
        Args:
            items: Lista stavki
        
        Returns:
            Dict sa ukupnim vrijednostima
        """
        totals = {
            'total_quantity': 0.0,
            'total_value': 0.0,
            'total_bruto_mass': 0.0,
            'total_neto_mass': 0.0,
        }
        
        for item in items:
            totals['total_quantity'] += float(item.get('quantity', 0) or 0)
            totals['total_value'] += float(item.get('total_price', 0) or 0)
            totals['total_bruto_mass'] += float(item.get('bruto_mass', 0) or 0)
            totals['total_neto_mass'] += float(item.get('neto_mass', 0) or 0)
        
        return totals
    
    def calculate_item_total(self, quantity: float, unit_price: float) -> float:
        """
        Kalkulacija iznosa za stavku.
        
        Args:
            quantity: Količina
            unit_price: Jedinična cijena
        
        Returns:
            Ukupan iznos
        """
        return quantity * unit_price
    
    def accumulate_weights(
        self,
        items: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        Akumulacija masa po vrstama.
        
        Args:
            items: Lista stavki
        
        Returns:
            Dict sa akumulisanim masama
        """
        weights = {
            'bruto': 0.0,
            'neto': 0.0,
        }
        
        for item in items:
            weights['bruto'] += float(item.get('bruto_mass', 0) or 0)
            weights['neto'] += float(item.get('neto_mass', 0) or 0)
        
        return weights
    
    # ============================================================
    # ASSEMBLY - FAKTURA → NAIMENOVANJA
    # ============================================================
    
    def create_naimenovanja_from_faktura(
        self,
        draft: DeclarationDraft
    ) -> List[Dict[str, Any]]:
        """
        Kreiraj Naimenovanja iz Faktura stavki.
        
        Args:
            draft: DeclarationDraft sa Faktura stavkama
        
        Returns:
            Lista podataka za Naimenovanja
        """
        naimenovanja = []
        
        if not hasattr(draft, 'items') or not draft.items:
            return naimenovanja
        
        # Group items by tariff code
        items_by_tariff = {}
        for item in draft.items:
            tariff = item.tarifni_broj  # Use correct field name
            if tariff not in items_by_tariff:
                items_by_tariff[tariff] = []
            items_by_tariff[tariff].append(item)
        
        # Create naimenovanje for each tariff group
        for tariff, items in items_by_tariff.items():
            naimenovanje_data = {
                'tariff_code': tariff,
                'items': items,
                'total_quantity': sum(item.kolicina for item in items),
                'total_value': sum(item.iznos for item in items),
                'total_bruto': sum(item.bruto_kg for item in items),
                'total_neto': sum(item.neto_kg for item in items),
            }
            naimenovanja.append(naimenovanje_data)
        
        self._log_operation("create_naimenovanja", True, len(naimenovanja))
        return naimenovanja
    
    # ============================================================
    # IMPORT/EXPORT HELPERS
    # ============================================================
    
    def process_import_result(self, result: ImportResult) -> Dict[str, Any]:
        """
        Procesuiraj ImportResult za View.

        Args:
            result: ImportResult from ImportWorker

        Returns:
            Dict sa podacima za View
        """
        data = {
            'invoice_name': getattr(result, 'invoice_name', ''),
            'items': [],
            'total_value': 0.0,
            'total_bruto': getattr(result, 'bruto_kg', 0.0),  # Ukupna bruto težina iz PDF-a
            'total_neto': getattr(result, 'neto_kg', 0.0),    # Ukupna neto težina iz PDF-a
        }

        if hasattr(result, 'items') and result.items:
            for item in result.items:
                item_data = {
                    'ordinal_no': getattr(item, 'ordinal_no', ''),
                    'tariff_code': getattr(item, 'tariff_code', ''),
                    'description': getattr(item, 'description', ''),
                    'quantity': getattr(item, 'kolicina', 0.0),
                    'unit_price': getattr(item, 'cijena_jed', 0.0),
                    'total_price': getattr(item, 'iznos', 0.0),  # Koristi 'iznos' field
                    'bruto_mass': getattr(item, 'bruto_kg', 0.0),
                    'neto_mass': getattr(item, 'neto_kg', 0.0),
                }
                data['items'].append(item_data)
                data['total_value'] += item_data['total_price']

        return data
    
    def extract_invoice_name(self, filepath: str) -> str:
        """
        Ekstraktuj naziv fakture iz filepath-a.
        
        Args:
            filepath: Putanja do fajla
        
        Returns:
            Naziv fakture
        """
        from pathlib import Path
        return Path(filepath).stem
    
    # ============================================================
    # PRIVATE HELPERS
    # ============================================================
    
    def _log_operation(self, operation: str, success: bool, count: int = 0):
        """Logging helper."""
        import logging
        logger = logging.getLogger("deklarant_pro.services.faktura")
        status = "✅" if success else "❌"
        logger.info(f"{status} {operation}: {count} items")
    
    def _format_number(self, value: float, decimals: int = 3) -> str:
        """Helper za formatiranje brojeva."""
        return f"{value:,.{decimals}f}".replace(',', 'X').replace('.', ',').replace('X', '.')
