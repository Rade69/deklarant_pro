# services/sifarnici_service_refactored.py

"""
Refactored SifarniciService that extends BaseTabService.
"""

import logging
from typing import Dict, Any, List, Optional
from database.db import get_db_connection
from services.base_service import BaseTabService
from utils.exceptions import ValidationError, DatabaseError
from utils.cache import cache_database_query, get_database_cache


class SifarniciService(BaseTabService):
    """
    Refactored SifarniciService that extends BaseTabService.
    Handles CRUD operations for all reference data (valute, drzave, dokumenti, etc.)
    """
    
    def __init__(self):
        """Initialize SifarniciService."""
        super().__init__()
        self.logger = logging.getLogger(__name__)
    
    def validate(self, data: Dict[str, Any]) -> bool:
        """
        Validate reference data.
        
        Args:
            data: Dictionary with reference data
            
        Returns:
            bool: True if data is valid
            
        Raises:
            ValidationError: If data is not valid
        """
        # Base validation from BaseTabService
        if not data:
            raise ValidationError("Data cannot be empty")
        
        # Validate based on data type
        if 'sifra' not in data:
            raise ValidationError("Sifra is required", field="sifra")
        
        if 'naziv' not in data:
            raise ValidationError("Naziv is required", field="naziv")
        
        return True
    
    @cache_database_query(ttl=3600)  # Cache for 1 hour (currencies rarely change)
    def get_all_valute(self) -> List[Dict[str, Any]]:
        """Get all currencies."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT sifra, naziv, opis 
                        FROM catalogs.valute 
                        ORDER BY sifra
                    """)
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            self._log_operation("get_all_valute", success=False, details=str(e))
            raise DatabaseError(f"Error getting currencies: {e}")
    
    @cache_database_query(ttl=3600)  # Cache for 1 hour
    def get_valuta_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """Get currency by code."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT sifra, naziv, opis 
                        FROM catalogs.valute 
                        WHERE sifra = %s
                    """, (code,))
                    row = cur.fetchone()
                    return dict(row) if row else None
        except Exception as e:
            self._log_operation("get_valuta_by_code", success=False, details=str(e))
            raise DatabaseError(f"Error getting currency: {e}")
    
    @cache_database_query(ttl=3600)  # Cache for 1 hour (countries rarely change)
    def get_all_drzave(self) -> List[Dict[str, Any]]:
        """Get all countries."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT sifra, naziv, opis 
                        FROM catalogs.drzave 
                        ORDER BY naziv
                    """)
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            self._log_operation("get_all_drzave", success=False, details=str(e))
            raise DatabaseError(f"Error getting countries: {e}")
    
    @cache_database_query(ttl=3600)  # Cache for 1 hour
    def get_drzava_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """Get country by code."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT sifra, naziv, opis 
                        FROM catalogs.drzave 
                        WHERE sifra = %s
                    """, (code,))
                    row = cur.fetchone()
                    return dict(row) if row else None
        except Exception as e:
            self._log_operation("get_drzava_by_code", success=False, details=str(e))
            raise DatabaseError(f"Error getting country: {e}")
    
    @cache_database_query(ttl=3600)  # Cache for 1 hour
    def get_all_dokumenti(self) -> List[Dict[str, Any]]:
        """Get all document types."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT sifra, naziv, opis 
                        FROM catalogs.dokumenti 
                        ORDER BY naziv
                    """)
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            self._log_operation("get_all_dokumenti", success=False, details=str(e))
            raise DatabaseError(f"Error getting documents: {e}")
    
    @cache_database_query(ttl=3600)  # Cache for 1 hour
    def get_all_vrste_prijevoza(self) -> List[Dict[str, Any]]:
        """Get all transport types."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT sifra, naziv, opis 
                        FROM catalogs.vrste_prijevoza 
                        ORDER BY sifra
                    """)
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            self._log_operation("get_all_vrste_prijevoza", success=False, details=str(e))
            raise DatabaseError(f"Error getting transport types: {e}")
    
    @cache_database_query(ttl=3600)  # Cache for 1 hour
    def get_all_tipovi_deklaracija(self) -> List[Dict[str, Any]]:
        """Get all declaration types."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT sifra, naziv, opis 
                        FROM catalogs.tipovi_deklaracija 
                        ORDER BY sifra
                    """)
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            self._log_operation("get_all_tipovi_deklaracija", success=False, details=str(e))
            raise DatabaseError(f"Error getting declaration types: {e}")
    
    def add_valuta(self, sifra: str, naziv: str, opis: str = "") -> bool:
        """Add new currency."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO catalogs.valute (sifra, naziv, opis) 
                        VALUES (%s, %s, %s)
                        ON CONFLICT (sifra) DO UPDATE SET
                            naziv = EXCLUDED.naziv,
                            opis = EXCLUDED.opis
                    """, (sifra, naziv, opis))
                    conn.commit()
                    self._log_operation("add_valuta", success=True)
                    return True
        except Exception as e:
            self._log_operation("add_valuta", success=False, details=str(e))
            raise DatabaseError(f"Error adding currency: {e}")
    
    def add_drzava(self, sifra: str, naziv: str, opis: str = "") -> bool:
        """Add new country."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO catalogs.drzave (sifra, naziv, opis) 
                        VALUES (%s, %s, %s)
                        ON CONFLICT (sifra) DO UPDATE SET
                            naziv = EXCLUDED.naziv,
                            opis = EXCLUDED.opis
                    """, (sifra, naziv, opis))
                    conn.commit()
                    self._log_operation("add_drzava", success=True)
                    return True
        except Exception as e:
            self._log_operation("add_drzava", success=False, details=str(e))
            raise DatabaseError(f"Error adding country: {e}")
    
    def add_dokument(self, sifra: str, naziv: str, opis: str = "") -> bool:
        """Add new document type."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO catalogs.dokumenti (sifra, naziv, opis) 
                        VALUES (%s, %s, %s)
                        ON CONFLICT (sifra) DO UPDATE SET
                            naziv = EXCLUDED.naziv,
                            opis = EXCLUDED.opis
                    """, (sifra, naziv, opis))
                    conn.commit()
                    self._log_operation("add_dokument", success=True)
                    return True
        except Exception as e:
            self._log_operation("add_dokument", success=False, details=str(e))
            raise DatabaseError(f"Error adding document type: {e}")
    
    def add_vrsta_prijevoza(self, sifra: str, naziv: str, opis: str = "") -> bool:
        """Add new transport type."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO catalogs.vrste_prijevoza (sifra, naziv, opis) 
                        VALUES (%s, %s, %s)
                        ON CONFLICT (sifra) DO UPDATE SET
                            naziv = EXCLUDED.naziv,
                            opis = EXCLUDED.opis
                    """, (sifra, naziv, opis))
                    conn.commit()
                    self._log_operation("add_vrsta_prijevoza", success=True)
                    return True
        except Exception as e:
            self._log_operation("add_vrsta_prijevoza", success=False, details=str(e))
            raise DatabaseError(f"Error adding transport type: {e}")
    
    def delete_valuta(self, sifra: str) -> bool:
        """Delete currency."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM catalogs.valute WHERE sifra = %s", (sifra,))
                    conn.commit()
                    deleted = cur.rowcount > 0
                    self._log_operation("delete_valuta", success=deleted)
                    return deleted
        except Exception as e:
            self._log_operation("delete_valuta", success=False, details=str(e))
            raise DatabaseError(f"Error deleting currency: {e}")
    
    def delete_drzava(self, sifra: str) -> bool:
        """Delete country."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM catalogs.drzave WHERE sifra = %s", (sifra,))
                    conn.commit()
                    deleted = cur.rowcount > 0
                    self._log_operation("delete_drzava", success=deleted)
                    return deleted
        except Exception as e:
            self._log_operation("delete_drzava", success=False, details=str(e))
            raise DatabaseError(f"Error deleting country: {e}")
    
    def delete_dokument(self, sifra: str) -> bool:
        """Delete document type."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM catalogs.dokumenti WHERE sifra = %s", (sifra,))
                    conn.commit()
                    deleted = cur.rowcount > 0
                    self._log_operation("delete_dokument", success=deleted)
                    return deleted
        except Exception as e:
            self._log_operation("delete_dokument", success=False, details=str(e))
            raise DatabaseError(f"Error deleting document type: {e}")
    
    def delete_vrsta_prijevoza(self, sifra: str) -> bool:
        """Delete transport type."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM catalogs.vrste_prijevoza WHERE sifra = %s", (sifra,))
                    conn.commit()
                    deleted = cur.rowcount > 0
                    self._log_operation("delete_vrsta_prijevoza", success=deleted)
                    return deleted
        except Exception as e:
            self._log_operation("delete_vrsta_prijevoza", success=False, details=str(e))
            raise DatabaseError(f"Error deleting transport type: {e}")
    
    @cache_database_query(ttl=300)  # Cache for 5 minutes
    def search_valute(self, search_term: str) -> List[Dict[str, Any]]:
        """Search currencies by name or code."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT sifra, naziv, opis 
                        FROM catalogs.valute 
                        WHERE sifra ILIKE %s OR naziv ILIKE %s
                        ORDER BY sifra
                    """, (f"%{search_term}%", f"%{search_term}%"))
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            self._log_operation("search_valute", success=False, details=str(e))
            raise DatabaseError(f"Error searching currencies: {e}")
    
    @cache_database_query(ttl=300)  # Cache for 5 minutes
    def search_drzave(self, search_term: str) -> List[Dict[str, Any]]:
        """Search countries by name or code."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT sifra, naziv, opis 
                        FROM catalogs.drzave 
                        WHERE sifra ILIKE %s OR naziv ILIKE %s
                        ORDER BY naziv
                    """, (f"%{search_term}%", f"%{search_term}%"))
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            self._log_operation("search_drzave", success=False, details=str(e))
            raise DatabaseError(f"Error searching countries: {e}")
    
    @cache_database_query(ttl=300)  # Cache for 5 minutes
    def search_dokumenti(self, search_term: str) -> List[Dict[str, Any]]:
        """Search document types by name or code."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT sifra, naziv, opis 
                        FROM catalogs.dokumenti 
                        WHERE sifra ILIKE %s OR naziv ILIKE %s
                        ORDER BY naziv
                    """, (f"%{search_term}%", f"%{search_term}%"))
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            self._log_operation("search_dokumenti", success=False, details=str(e))
            raise DatabaseError(f"Error searching document types: {e}")
    
    @cache_database_query(ttl=300)  # Cache for 5 minutes
    def search_vrste_prijevoza(self, search_term: str) -> List[Dict[str, Any]]:
        """Search transport types by name or code."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT sifra, naziv, opis 
                        FROM catalogs.vrste_prijevoza 
                        WHERE sifra ILIKE %s OR naziv ILIKE %s
                        ORDER BY sifra
                    """, (f"%{search_term}%", f"%{search_term}%"))
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            self._log_operation("search_vrste_prijevoza", success=False, details=str(e))
            raise DatabaseError(f"Error searching transport types: {e}")
    
    @cache_database_query(ttl=300)  # Cache for 5 minutes
    def get_statistika(self) -> Dict[str, Any]:
        """Get statistics for reference data."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Count of currencies
                    cur.execute("SELECT COUNT(*) FROM catalogs.valute")
                    valute_count = cur.fetchone()[0]
                    
                    # Count of countries
                    cur.execute("SELECT COUNT(*) FROM catalogs.drzave")
                    drzave_count = cur.fetchone()[0]
                    
                    # Count of document types
                    cur.execute("SELECT COUNT(*) FROM catalogs.dokumenti")
                    dokumenti_count = cur.fetchone()[0]
                    
                    # Count of transport types
                    cur.execute("SELECT COUNT(*) FROM catalogs.vrste_prijevoza")
                    prijevoz_count = cur.fetchone()[0]
                    
                    return {
                        'valute': valute_count,
                        'drzave': drzave_count,
                        'dokumenti': dokumenti_count,
                        'vrste_prijevoza': prijevoz_count,
                        'total': valute_count + drzave_count + dokumenti_count + prijevoz_count
                    }
        except Exception as e:
            self._log_operation("get_statistika", success=False, details=str(e))
            raise DatabaseError(f"Error getting statistics: {e}")
    
    def export_to_csv(self, table_name: str, filepath: str) -> str:
        """
        Export reference data to CSV.
        
        Args:
            table_name: Name of the table to export
            filepath: Path to save the CSV file
            
        Returns:
            Path to the created CSV file
        """
        try:
            import csv
            import os
            
            # Get data
            if table_name == 'valute':
                data = self.get_all_valute()
            elif table_name == 'drzave':
                data = self.get_all_drzave()
            elif table_name == 'dokumenti':
                data = self.get_all_dokumenti()
            elif table_name == 'vrste_prijevoza':
                data = self.get_all_vrste_prijevoza()
            else:
                raise ValidationError(f"Unknown table: {table_name}")
            
            if not data:
                raise ValidationError(f"No data to export for {table_name}")
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            # Write to CSV
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                if data:
                    fieldnames = data[0].keys()
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(data)
            
            self._log_operation("export_to_csv", success=True, 
                              details=f"Exported {len(data)} records to {filepath}")
            return filepath
            
        except Exception as e:
            self._log_operation("export_to_csv", success=False, details=str(e))
            raise Exception(f"Error exporting to CSV: {e}")
    
    def validate_reference_data(self, data: Dict[str, Any], 
                             required_fields: List[str] = None) -> List[str]:
        """
        Validate reference data.
        
        Args:
            data: Data to validate
            required_fields: List of required field names
            
        Returns:
            List of validation errors (empty list if valid)
        """
        errors = []
        
        # Check required fields
        for field in required_fields or []:
            if field not in data or not data[field]:
                errors.append(f"Polje '{field}' je obavezno")
        
        # Validate sifra format (if present)
        if 'sifra' in data and data['sifra']:
            sifra = str(data['sifra']).strip()
            if not sifra:
                errors.append("Šifra ne može biti prazna")
            elif len(sifra) > 20:
                errors.append("Šifra ne smije biti duža od 20 karaktera")
        
        # Validate naziv
        if 'naziv' in data:
            naziv = data['naziv']
            if not naziv or not str(naziv).strip():
                errors.append("Naziv je obavezan")
            elif len(str(naziv)) > 200:
                errors.append("Naziv ne smije biti duži od 200 karaktera")
        
        return errors