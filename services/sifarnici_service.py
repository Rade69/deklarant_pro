# services/sifarnici_service.py

"""
Sifarnici Service - Business Logic Layer

Service layer za Sifarnici tab - potpuno Qt-independent.
Odgovoran za:
- CRUD operacije za šifrarnike (valute, države, dokumenti, itd.)
- Validacija podataka
- Database pristup (kroz get_db_connection)

OVAJ FAJL NE MIJENJA GUI - samo business logic extraction.
"""

from typing import Dict, Any, List, Optional
from database.db import get_db_connection


class SifarniciService:
    """
    Service layer za Sifarnici tab - Qt independent!
    
    Odgovornosti:
    - CRUD operacije (Create, Read, Update, Delete)
    - Validacija podataka
    - Database pristup
    
    NEMA:
    - UI kreiranje
    - Signal/Slot mehanizam
    """
    
    def __init__(self):
        """Inicijalizacija bez Qt dependency."""
        pass
    
    # ============================================================
    # VALUTE (Currencies)
    # ============================================================
    
    def get_all_valute(self) -> List[Dict[str, Any]]:
        """Dohvati sve valute iz baze."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT sifra, naziv, opis FROM catalogs.valute ORDER BY sifra")
                    results = cur.fetchall()
                    return [dict(row) for row in results]
        except Exception as e:
            self._log_error("get_all_valute", e)
            return []
    
    def get_valuta_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """Dohvati valutu po šifri."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT sifra, naziv, opis FROM catalogs.valute WHERE sifra = %s LIMIT 1", (code,))
                    row = cur.fetchone()
                    return dict(row) if row else None
        except Exception as e:
            self._log_error("get_valuta_by_code", e)
            return None
    
    def add_valuta(self, code: str, naziv: str, opis: str = "") -> bool:
        """Dodaj novu valutu."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO catalogs.valute (sifra, naziv, opis) VALUES (%s, %s, %s) ON CONFLICT (sifra) DO NOTHING", (code, naziv, opis))
                    conn.commit()
                    return cur.rowcount > 0
        except Exception as e:
            self._log_error("add_valuta", e)
            return False
    
    def delete_valuta(self, code: str) -> bool:
        """Obriši valutu."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM catalogs.valute WHERE sifra = %s", (code,))
                    conn.commit()
                    return cur.rowcount > 0
        except Exception as e:
            self._log_error("delete_valuta", e)
            return False
    
    # ============================================================
    # DRŽAVE (Countries)
    # ============================================================
    
    def get_all_drzave(self) -> List[Dict[str, Any]]:
        """Dohvati sve države iz baze."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT sifra, naziv, opis FROM catalogs.drzave ORDER BY naziv")
                    results = cur.fetchall()
                    return [dict(row) for row in results]
        except Exception as e:
            self._log_error("get_all_drzave", e)
            return []
    
    def get_drzava_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """Dohvati državu po šifri."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT sifra, naziv, opis FROM catalogs.drzave WHERE sifra = %s LIMIT 1", (code,))
                    row = cur.fetchone()
                    return dict(row) if row else None
        except Exception as e:
            self._log_error("get_drzava_by_code", e)
            return None
    
    # ============================================================
    # VRSTE PRIJEVOZA (Transport Types)
    # ============================================================
    
    def get_all_vrste_prijevoza(self) -> List[Dict[str, Any]]:
        """Dohvati sve vrste prijevoza."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT sifra, opis FROM catalogs.vrste_prijevoza ORDER BY sifra")
                    results = cur.fetchall()
                    return [dict(row) for row in results]
        except Exception as e:
            self._log_error("get_all_vrste_prijevoza", e)
            return []
    
    # ============================================================
    # CARINSKE ISPOSTAVE (Customs Offices)
    # ============================================================
    
    def get_all_carinske_ispostave(self) -> List[Dict[str, Any]]:
        """Dohvati sve carinske ispostave."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT sifra, naziv, opis FROM catalogs.carinske_ispostave ORDER BY sifra")
                    results = cur.fetchall()
                    return [dict(row) for row in results]
        except Exception as e:
            self._log_error("get_all_carinske_ispostave", e)
            return []
    
    def get_ured_odredista(self) -> str:
        """Dohvati ured odredišta (default: BA097012)."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT sifra, naziv FROM catalogs.carinske_ispostave WHERE sifra = 'BA097012' LIMIT 1")
                    row = cur.fetchone()
                    if row:
                        grad = row["naziv"].split()[-1]
                        return f"{row['sifra']} CI {grad}"
                    return ""
        except Exception as e:
            self._log_error("get_ured_odredista", e)
            return ""
    
    # ============================================================
    # PRONILOŽENI DOKUMENTI (Attached Documents)
    # ============================================================
    
    def get_all_prilozeni_dokumenti(self) -> List[Dict[str, Any]]:
        """Dohvati sve priložene dokumente."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT sifra, naziv, opis FROM catalogs.prilozeni_dokumenti_sifre ORDER BY sifra")
                    results = cur.fetchall()
                    return [dict(row) for row in results]
        except Exception as e:
            self._log_error("get_all_prilozeni_dokumenti", e)
            return []
    
    # ============================================================
    # VALIDATION
    # ============================================================
    
    def validate_sifra(self, code: str, required_length: int = 0) -> List[str]:
        """Validiraj šifru."""
        errors = []
        if not code or not code.strip():
            errors.append("Šifra je obavezna")
        if required_length > 0 and len(code) != required_length:
            errors.append(f"Šifra mora imati tačno {required_length} karaktera")
        return errors
    
    def validate_naziv(self, naziv: str, min_length: int = 2, max_length: int = 100) -> List[str]:
        """Validiraj naziv."""
        errors = []
        if not naziv or not naziv.strip():
            errors.append("Naziv je obavezan")
        elif len(naziv) < min_length:
            errors.append(f"Naziv mora imati najmanje {min_length} karaktera")
        elif len(naziv) > max_length:
            errors.append(f"Naziv može imati najviše {max_length} karaktera")
        return errors
    
    # ============================================================
    # PRIVATE HELPERS
    # ============================================================
    
    def _log_error(self, operation: str, error: Exception):
        """Logging helper za error-e."""
        import logging
        logger = logging.getLogger("asycuda_pro.services.sifarnici")
        logger.error(f"❌ {operation}: {error}")
    
    def _log_operation(self, operation: str, success: bool, count: int = 0):
        """Logging helper za operacije."""
        import logging
        logger = logging.getLogger("asycuda_pro.services.sifarnici")
        status = "✅" if success else "❌"
        logger.info(f"{status} {operation}: {count} records")
    
    def get_all_dokumenti(self) -> List[Dict[str, Any]]:
        """Dohvati sve dokumente iz baze."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT sifra, naziv, tip FROM catalogs.dokumenti ORDER BY naziv")
                    results = cur.fetchall()
                    return [dict(row) for row in results]
        except Exception as e:
            self._log_error("get_all_dokumenti", e)
            return []
    
    def get_all_pakovanja(self) -> List[Dict[str, Any]]:
        """Dohvati sva pakovanja iz baze."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT sifra, naziv, opis FROM catalogs.pakovanja ORDER BY sifra")
                    results = cur.fetchall()
                    return [dict(row) for row in results]
        except Exception as e:
            self._log_error("get_all_pakovanja", e)
            return []
    
    def get_all_povlastice(self) -> List[Dict[str, Any]]:
        """Dohvati sve povlastice iz baze."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT sifra, naziv, tip FROM catalogs.povlastice ORDER BY naziv")
                    results = cur.fetchall()
                    return [dict(row) for row in results]
        except Exception as e:
            self._log_error("get_all_povlastice", e)
            return []

    def load_category_data(self, table_name: str) -> List[Dict[str, Any]]:
        """
        Load data for a specific category/table.
        
        Args:
            table_name: Database table name (e.g., 'catalogs.izvoznici')
            
        Returns:
            List of records as dictionaries
        """
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Determine order by column based on table
                    if 'tarifa' in table_name:
                        order_by = 'tarifni_kod'
                    elif 'sifra' in table_name:
                        order_by = 'sifra'
                    else:
                        order_by = 'naziv'
                    
                    cur.execute(f"SELECT * FROM {table_name} ORDER BY {order_by}")
                    results = cur.fetchall()
                    return [dict(row) for row in results]
        except Exception as e:
            self._log_error(f"load_category_data_{table_name}", e)
            return []

    def _log_error(self, operation: str, error: Exception):
        """Logovanje grešaka."""
        import logging
        logger = logging.getLogger("asycuda_pro.services.sifarnici")
        logger.error(f"Greška u {operation}: {error}")