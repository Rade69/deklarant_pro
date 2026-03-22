# services/faktura_service_refactored.py

"""
Refaktorisani FakturaService koji koristi BaseTabService.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from services.base_service import BaseTabService
from utils.exceptions import ValidationError, DatabaseError
from core.draft.draft import DeclarationDraft, InvoiceLine
from importers.import_result import ImportResult


class FakturaService(BaseTabService):
    """
    Refaktorisani FakturaService koji nasljeđuje BaseTabService.
    
    Odgovornosti:
    - Business logic za fakture (validacija, kalkulacije)
    - Data conversion (Draft ↔ View data)
    - Import/Export orchestration
    - Assembly (Faktura → Naimenovanja)
    """
    
    def __init__(self):
        """Inicijalizacija FakturaService sa BaseTabService."""
        super().__init__()
        self.logger = logging.getLogger(__name__)
    
    def validate(self, data: Dict[str, Any]) -> bool:
        """
        Validacija podataka fakture.
        
        Args:
            data: Dictionary sa podacima fakture
            
        Returns:
            True ako su podaci validni
            
        Raises:
            ValidationError: Ako podaci nisu validni
        """
        # Validacija osnovnih polja
        required_fields = [
            'broj_fakture',
            'datum_fakture',
            'izvoznik_id',
            'primalac_id'
        ]
        
        for field in required_fields:
            if not data.get(field):
                raise ValidationError(
                    f"Obavezno polje '{field}' je prazno",
                    field=field
                )
        
        # Validacija broja fakture
        broj_fakture = data.get('broj_fakture', '')
        if not broj_fakture or not broj_fakture.strip():
            raise ValidationError(
                "Broj fakture je obavezno polje",
                field="broj_fakture"
            )
        
        # Validacija datuma fakture
        datum_fakture = data.get('datum_fakture')
        if datum_fakture:
            try:
                if isinstance(datum_fakture, str):
                    datetime.strptime(datum_fakture, '%Y-%m-%d')
            except ValueError:
                raise ValidationError(
                    f"Nevalidan format datuma fakture: {datum_fakture}",
                    field="datum_fakture"
                )
        
        # Validacija stavki fakture
        stavke = data.get('stavke', [])
        if not stavke or len(stavke) == 0:
            raise ValidationError(
                "Faktura mora imati barem jednu stavku",
                field="stavke"
            )
        
        # Validacija svake stavke
        for i, stavka in enumerate(stavke):
            if not stavka.get('naziv_proizvoda'):
                raise ValidationError(
                    f"Stavka {i+1}: Naziv proizvoda je obavezan",
                    field=f"stavke[{i}].naziv_proizvoda"
                )
            
            if not stavka.get('kolicina') or float(stavka.get('kolicina', 0)) <= 0:
                raise ValidationError(
                    f"Stavka {i+1}: Količina mora biti veća od 0",
                    field=f"stavke[{i}].kolicina"
                )
            
            if not stavka.get('cijena') or float(stavka.get('cijena', 0)) <= 0:
                raise ValidationError(
                    f"Stavka {i+1}: Cijena mora biti veća od 0",
                    field=f"stavke[{i}].cijena"
                )
        
        return True
    
    def load_from_draft(self, draft: DeclarationDraft) -> Dict[str, Any]:
        """
        Konvertuje DeclarationDraft u dictionary za UI prikaz.
        
        Args:
            draft: DeclarationDraft objekat
            
        Returns:
            Dictionary sa podacima za prikaz u UI
        """
        if not draft:
            return {}
        
        # Konvertuj stavke fakture
        stavke = []
        for line in draft.invoice_lines:
            stavka = {
                'redni_broj': line.line_number,
                'naziv_proizvoda': line.product_name,
                'tarifni_broj': line.tariff_code,
                'kolicina': line.quantity,
                'jedinica_mjere': line.unit_of_measure,
                'cijena': line.unit_price,
                'ukupna_vrijednost': line.total_value,
                'tezina': line.weight,
                'zemlja_porekla': line.origin_country,
                'valuta': line.currency
            }
            stavke.append(stavka)
        
        return {
            'broj_fakture': draft.invoice_number,
            'datum_fakture': draft.invoice_date,
            'izvoznik_id': draft.exporter_id,
            'primalac_id': draft.consignee_id,
            'valuta': draft.currency,
            'ukupna_vrijednost': draft.total_invoice_value,
            'ukupna_tezina': draft.total_weight,
            'broj_stavki': len(stavke),
            'stavke': stavke,
            'status': draft.status
        }
    
    def save_to_draft(self, draft: DeclarationDraft, data: Dict[str, Any]) -> DeclarationDraft:
        """
        Konvertuje UI podatke u DeclarationDraft.
        
        Args:
            draft: Postojeći draft (može biti prazan)
            data: Podaci iz UI forme
            
        Returns:
            Ažurirani DeclarationDraft
        """
        if draft is None:
            draft = DeclarationDraft()
        
        # Osnovni podaci fakture
        draft.invoice_number = data.get('broj_fakture', '')
        draft.invoice_date = data.get('datum_fakture')
        draft.exporter_id = data.get('izvoznik_id')
        draft.consignee_id = data.get('primalac_id')
        draft.currency = data.get('valuta')
        draft.total_invoice_value = data.get('ukupna_vrijednost', 0.0)
        draft.total_weight = data.get('ukupna_tezina', 0.0)
        draft.status = data.get('status', 'DRAFT')
        
        # Stavke fakture
        draft.invoice_lines = []
        stavke = data.get('stavke', [])
        
        for i, stavka in enumerate(stavke):
            line = InvoiceLine()
            line.line_number = i + 1
            line.product_name = stavka.get('naziv_proizvoda', '')
            line.tariff_code = stavka.get('tarifni_broj', '')
            line.quantity = stavka.get('kolicina', 0.0)
            line.unit_of_measure = stavka.get('jedinica_mjere', '')
            line.unit_price = stavka.get('cijena', 0.0)
            line.total_value = stavka.get('ukupna_vrijednost', 0.0)
            line.weight = stavka.get('tezina', 0.0)
            line.origin_country = stavka.get('zemlja_porekla', '')
            line.currency = stavka.get('valuta', '')
            
            draft.invoice_lines.append(line)
        
        return draft
    
    def calculate_totals(self, stavke: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Izračunaj ukupne vrijednosti za fakturu.
        
        Args:
            stavke: Lista stavki fakture
            
        Returns:
            Dictionary sa ukupnim vrijednostima
        """
        ukupna_vrijednost = 0.0
        ukupna_tezina = 0.0
        
        for stavka in stavke:
            # Ukupna vrijednost stavke
            kolicina = float(stavka.get('kolicina', 0))
            cijena = float(stavka.get('cijena', 0))
            vrijednost_stavke = kolicina * cijena
            ukupna_vrijednost += vrijednost_stavke
            
            # Ukupna težina
            tezina = float(stavka.get('tezina', 0))
            ukupna_tezina += tezina
        
        return {
            'ukupna_vrijednost': round(ukupna_vrijednost, 2),
            'ukupna_tezina': round(ukupna_tezina, 2),
            'broj_stavki': len(stavke)
        }
    
    def validate_stavka(self, stavka: Dict[str, Any]) -> List[str]:
        """
        Validiraj pojedinačnu stavku fakture.
        
        Args:
            stavka: Dictionary sa podacima stavke
            
        Returns:
            Lista grešaka (prazna lista ako nema grešaka)
        """
        errors = []
        
        # Validacija naziva proizvoda
        if not stavka.get('naziv_proizvoda'):
            errors.append("Naziv proizvoda je obavezan")
        
        # Validacija količine
        kolicina = stavka.get('kolicina')
        if not kolicina or float(kolicina) <= 0:
            errors.append("Količina mora biti veća od 0")
        
        # Validacija cijene
        cijena = stavka.get('cijena')
        if not cijena or float(cijena) <= 0:
            errors.append("Cijena mora biti veća od 0")
        
        # Validacija tarifnog broja (ako je unesen)
        tarifni_broj = stavka.get('tarifni_broj', '')
        if tarifni_broj and len(tarifni_broj) < 4:
            errors.append("Tarifni broj mora imati najmanje 4 karaktera")
        
        return errors
    
    def get_validation_errors(self, data: Dict[str, Any]) -> List[str]:
        """
        Vrati listu grešaka u validaciji.
        
        Args:
            data: Podaci za validaciju
            
        Returns:
            Lista grešaka (prazna lista ako nema grešaka)
        """
        errors = []
        
        # Provjera obaveznih polja
        required_fields = [
            'broj_fakture',
            'datum_fakture',
            'izvoznik_id',
            'primalac_id'
        ]
        
        for field in required_fields:
            if not data.get(field):
                errors.append(f"Polje '{field}' je obavezno")
        
        # Validacija broja fakture
        broj_fakture = data.get('broj_fakture', '')
        if broj_fakture and not broj_fakture.strip():
            errors.append("Broj fakture ne može biti prazan")
        
        # Validacija datuma
        datum_fakture = data.get('datum_fakture')
        if datum_fakture:
            try:
                datetime.strptime(datum_fakture, '%Y-%m-%d')
            except ValueError:
                errors.append("Datum fakture mora biti u formatu YYYY-MM-DD")
        
        # Validacija stavki
        stavke = data.get('stavke', [])
        if not stavke:
            errors.append("Faktura mora imati barem jednu stavku")
        else:
            for i, stavka in enumerate(stavke):
                stavka_errors = self.validate_stavka(stavka)
                for error in stavka_errors:
                    errors.append(f"Stavka {i+1}: {error}")
        
        return errors
    
    def process_import_result(self, import_result: ImportResult) -> Dict[str, Any]:
        """
        Procesuiraj rezultat importa za prikaz u UI.
        
        Args:
            import_result: Rezultat importa
            
        Returns:
            Dictionary sa podacima za prikaz
        """
        if not import_result or not import_result.success:
            return {
                'success': False,
                'error': import_result.error if import_result else "Import nije uspio",
                'stavke': []
            }
        
        # Konvertuj importovane stavke u format za UI
        stavke = []
        for line in import_result.invoice_lines:
            stavka = {
                'redni_broj': line.line_number,
                'naziv_proizvoda': line.product_name,
                'tarifni_broj': line.tariff_code or '',
                'kolicina': line.quantity,
                'jedinica_mjere': line.unit_of_measure or '',
                'cijena': line.unit_price,
                'ukupna_vrijednost': line.total_value,
                'tezina': line.weight or 0.0,
                'zemlja_porekla': line.origin_country or '',
                'valuta': line.currency or ''
            }
            stavke.append(stavka)
        
        # Izračunaj ukupne vrijednosti
        totals = self.calculate_totals(stavke)
        
        return {
            'success': True,
            'broj_fakture': import_result.invoice_number or '',
            'datum_fakture': import_result.invoice_date or '',
            'izvoznik_naziv': import_result.exporter_name or '',
            'primalac_naziv': import_result.consignee_name or '',
            'valuta': import_result.currency or '',
            'stavke': stavke,
            'ukupna_vrijednost': totals['ukupna_vrijednost'],
            'ukupna_tezina': totals['ukupna_tezina'],
            'broj_stavki': totals['broj_stavki']
        }
    
    def prepare_for_assembly(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pripremi podatke fakture za assembly (kreiranje naimenovanja).
        
        Args:
            data: Podaci fakture
            
        Returns:
            Pripremljeni podaci za assembly
        """
        # Validacija podataka
        errors = self.get_validation_errors(data)
        if errors:
            raise ValidationError(
                "Faktura nije validna za assembly",
                details="\n".join(errors)
            )
        
        # Izračunaj ukupne vrijednosti
        totals = self.calculate_totals(data.get('stavke', []))
        
        # Pripremi podatke za assembly
        assembly_data = {
            'broj_fakture': data.get('broj_fakture'),
            'datum_fakture': data.get('datum_fakture'),
            'izvoznik_id': data.get('izvoznik_id'),
            'primalac_id': data.get('primalac_id'),
            'valuta': data.get('valuta'),
            'ukupna_vrijednost': totals['ukupna_vrijednost'],
            'ukupna_tezina': totals['ukupna_tezina'],
            'stavke': data.get('stavke', []),
            'metadata': {
                'created_at': datetime.now().isoformat(),
                'total_items': totals['broj_stavki'],
                'status': 'READY_FOR_ASSEMBLY'
            }
        }
        
        return assembly_data
    
    def export_to_excel(self, data: Dict[str, Any], filepath: str) -> str:
        """
        Izvezi fakturu u Excel format.
        
        Args:
            data: Podaci fakture
            filepath: Putanja do Excel fajla
            
        Returns:
            Putanja do kreiranog Excel fajla
        """
        try:
            import pandas as pd
            import os
            
            # Kreiraj DataFrame za stavke
            stavke = data.get('stavke', [])
            if not stavke:
                raise ValidationError("Nema stavki za izvoz")
            
            # Konvertuj u DataFrame
            df = pd.DataFrame(stavke)
            
            # Dodaj osnovne podatke fakture kao prvi sheet
            osnovni_podaci = {
                'Broj fakture': [data.get('broj_fakture', '')],
                'Datum fakture': [data.get('datum_fakture', '')],
                'Izvoznik ID': [data.get('izvoznik_id', '')],
                'Primalac ID': [data.get('primalac_id', '')],
                'Valuta': [data.get('valuta', '')],
                'Ukupna vrijednost': [data.get('ukupna_vrijednost', 0)],
                'Ukupna težina': [data.get('ukupna_tezina', 0)]
            }
            
            # Kreiraj direktorijum ako ne postoji
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            # Kreiraj Excel writer
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                # Sheet sa osnovnim podacima
                pd.DataFrame(osnovni_podaci).to_excel(
                    writer, sheet_name='Osnovni podaci', index=False
                )
                
                # Sheet sa stavkama
                df.to_excel(writer, sheet_name='Stavke', index=False)
            
            self._log_operation("export_to_excel", success=True, 
                              details=f"Exported to {filepath}")
            return filepath
            
        except Exception as e:
            self._log_operation("export_to_excel", success=False, details=str(e))
            raise Exception(f"Greška pri izvozu u Excel: {str(e)}")
    
    def merge_fakture(self, fakture_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Spoji više faktura u jednu.
        
        Args:
            fakture_data: Lista podataka faktura
            
        Returns:
            Spojeni podaci fakture
        """
        if not fakture_data:
            raise ValidationError("Nema faktura za spajanje")
        
        # Koristi prvu fakturu kao osnovu
        merged = fakture_data[0].copy()
        
        # Spoji sve stavke
        all_stavke = []
        for faktura in fakture_data:
            all_stavke.extend(faktura.get('stavke', []))
        
        # Ažuriraj redne brojeve
        for i, stavka in enumerate(all_stavke):
            stavka['redni_broj'] = i + 1
        
        merged['stavke'] = all_stavke
        
        # Izračunaj nove ukupne vrijednosti
        totals = self.calculate_totals(all_stavke)
        merged['ukupna_vrijednost'] = totals['ukupna_vrijednost']
        merged['ukupna_tezina'] = totals['ukupna_tezina']
        merged['broj_stavki'] = totals['broj_stavki']
        
        # Dodaj metadata
        merged['metadata'] = {
            'merged_from': len(fakture_data),
            'merged_at': datetime.now().isoformat(),
            'original_fakture': [f.get('broj_fakture', '') for f in fakture_data]
        }
        
        return merged