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
from psycopg2 import sql


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
                    
                    parts = table_name.split(".")
                    table_id = sql.Identifier(*parts) if len(parts) == 2 else sql.Identifier(parts[0])
                    cur.execute(
                        sql.SQL("SELECT * FROM {} ORDER BY {}").format(
                            table_id,
                            sql.Identifier(order_by)
                        )
                    )
                    results = cur.fetchall()
                    return [dict(row) for row in results]
        except Exception as e:
            self._log_error(f"load_category_data_{table_name}", e)
            return []
    
    # ============================================================
    # POŠILJAOCI (Exporters)
    # ============================================================
    
    def load_posiljaoci_data(self, search_query: str = "") -> List[Dict[str, Any]]:
        """Dohvati podatke o pošiljaocima sa opcionom pretragom."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    if search_query:
                        search_pattern = f"%{search_query}%"
                        cur.execute("""
                            SELECT jib, naziv, adresa, grad, drzava, telefon, email, kontakt, pdv_broj, maticni
                            FROM catalogs.izvoznici
                            WHERE naziv ILIKE %s OR jib ILIKE %s OR grad ILIKE %s
                            ORDER BY naziv
                        """, (search_pattern, search_pattern, search_pattern))
                    else:
                        cur.execute("""
                            SELECT jib, naziv, adresa, grad, drzava, telefon, email, kontakt, pdv_broj, maticni
                            FROM catalogs.izvoznici
                            ORDER BY naziv
                        """)
                    results = cur.fetchall()
                    return [dict(row) for row in results]
        except Exception as e:
            self._log_error("load_posiljaoci_data", e)
            return []
    
    def add_posiljalac(self, data: Dict[str, str]) -> bool:
        """Dodaj novog pošiljaoca."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO catalogs.izvoznici 
                        (jib, naziv, adresa, grad, drzava, telefon, email, kontakt, pdv_broj, maticni)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (jib) DO UPDATE SET
                            naziv = EXCLUDED.naziv,
                            adresa = EXCLUDED.adresa,
                            grad = EXCLUDED.grad,
                            drzava = EXCLUDED.drzava,
                            telefon = EXCLUDED.telefon,
                            email = EXCLUDED.email,
                            kontakt = EXCLUDED.kontakt,
                            pdv_broj = EXCLUDED.pdv_broj,
                            maticni = EXCLUDED.maticni
                    """, (
                        data.get("jib", ""),
                        data.get("naziv", ""),
                        data.get("adresa", ""),
                        data.get("grad", ""),
                        data.get("drzava", ""),
                        data.get("telefon", ""),
                        data.get("email", ""),
                        data.get("kontakt", ""),
                        data.get("pdv_broj", ""),
                        data.get("maticni", "")
                    ))
                    conn.commit()
                    return cur.rowcount > 0
        except Exception as e:
            self._log_error("add_posiljalac", e)
            return False
    
    def delete_posiljalac(self, jib: str) -> bool:
        """Obriši pošiljaoca po JIB-u."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM catalogs.izvoznici WHERE jib = %s", (jib,))
                    conn.commit()
                    return cur.rowcount > 0
        except Exception as e:
            self._log_error("delete_posiljalac", e)
            return False
    
    # ============================================================
    # UVOZNICI (Importers)
    # ============================================================
    
    def load_uvoznici_data(self, search_query: str = "") -> List[Dict[str, Any]]:
        """Dohvati podatke o uvoznicima sa opcionom pretragom."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    if search_query:
                        search_pattern = f"%{search_query}%"
                        cur.execute("""
                            SELECT jib, naziv, adresa, grad, drzava, telefon, email, kontakt, pdv_broj, maticni
                            FROM catalogs.uvoznici
                            WHERE naziv ILIKE %s OR jib ILIKE %s OR grad ILIKE %s
                            ORDER BY naziv
                        """, (search_pattern, search_pattern, search_pattern))
                    else:
                        cur.execute("""
                            SELECT jib, naziv, adresa, grad, drzava, telefon, email, kontakt, pdv_broj, maticni
                            FROM catalogs.uvoznici
                            ORDER BY naziv
                        """)
                    results = cur.fetchall()
                    return [dict(row) for row in results]
        except Exception as e:
            self._log_error("load_uvoznici_data", e)
            return []
    
    def add_uvoznik(self, data: Dict[str, str]) -> bool:
        """Dodaj novog uvoznika."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO catalogs.uvoznici 
                        (jib, naziv, adresa, grad, drzava, telefon, email, kontakt, pdv_broj, maticni)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (jib) DO UPDATE SET
                            naziv = EXCLUDED.naziv,
                            adresa = EXCLUDED.adresa,
                            grad = EXCLUDED.grad,
                            drzava = EXCLUDED.drzava,
                            telefon = EXCLUDED.telefon,
                            email = EXCLUDED.email,
                            kontakt = EXCLUDED.kontakt,
                            pdv_broj = EXCLUDED.pdv_broj,
                            maticni = EXCLUDED.maticni
                    """, (
                        data.get("jib", ""),
                        data.get("naziv", ""),
                        data.get("adresa", ""),
                        data.get("grad", ""),
                        data.get("drzava", ""),
                        data.get("telefon", ""),
                        data.get("email", ""),
                        data.get("kontakt", ""),
                        data.get("pdv_broj", ""),
                        data.get("maticni", "")
                    ))
                    conn.commit()
                    return cur.rowcount > 0
        except Exception as e:
            self._log_error("add_uvoznik", e)
            return False
    
    def delete_uvoznik(self, jib: str) -> bool:
        """Obriši uvoznika po JIB-u."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM catalogs.uvoznici WHERE jib = %s", (jib,))
                    conn.commit()
                    return cur.rowcount > 0
        except Exception as e:
            self._log_error("delete_uvoznik", e)
            return False
    
    # ============================================================
    # TRGOVAČKI NAZIVI (Trade Names)
    # ============================================================
    
    def load_trgovacki_nazivi_data(self, search_query: str = "") -> List[Dict[str, Any]]:
        """Dohvati podatke o trgovačkim nazivima robe."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    if search_query:
                        search_pattern = f"%{search_query}%"
                        cur.execute("""
                            SELECT tarifni_kod, naziv
                            FROM catalogs.tarifa_nazivi
                            WHERE tarifni_kod ILIKE %s OR naziv ILIKE %s
                            ORDER BY tarifni_kod
                        """, (search_pattern, search_pattern))
                    else:
                        cur.execute("""
                            SELECT tarifni_kod, naziv
                            FROM catalogs.tarifa_nazivi
                            ORDER BY tarifni_kod
                        """)
                    results = cur.fetchall()
                    return [dict(row) for row in results]
        except Exception as e:
            self._log_error("load_trgovacki_nazivi_data", e)
            return []
    
    # ============================================================
    # CARINARNICE (Customs Offices)
    # ============================================================
    
    def load_carinarnice_data(self) -> List[Dict[str, Any]]:
        """Dohvati podatke o carinarnicama."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT sifra, naziv
                        FROM catalogs.carinske_ispostave
                        ORDER BY sifra
                    """)
                    results = cur.fetchall()
                    return [dict(row) for row in results]
        except Exception as e:
            self._log_error("load_carinarnice_data", e)
            return []
    
    # ============================================================
    # CARINSKI POSTUPCI (Customs Procedures)
    # ============================================================
    
    def load_carinski_postupci_data(self) -> List[Dict[str, Any]]:
        """Dohvati podatke o carinskim postupcima."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT sifra, opis
                        FROM catalogs.carinski_postupci
                        ORDER BY sifra
                    """)
                    results = cur.fetchall()
                    return [dict(row) for row in results]
        except Exception as e:
            self._log_error("load_carinski_postupci_data", e)
            return []
    
    # ============================================================
    # ZEMLJE (Countries)
    # ============================================================
    
    def load_zemlje_data(self, search_query: str = "") -> List[Dict[str, Any]]:
        """Dohvati podatke o zemljama sa opcionom pretragom."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    if search_query:
                        search_pattern = f"%{search_query}%"
                        cur.execute("""
                            SELECT sifra, naziv
                            FROM catalogs.drzave
                            WHERE naziv ILIKE %s OR sifra ILIKE %s
                            ORDER BY naziv
                        """, (search_pattern, search_pattern))
                    else:
                        cur.execute("""
                            SELECT sifra, naziv
                            FROM catalogs.drzave
                            ORDER BY naziv
                        """)
                    results = cur.fetchall()
                    return [dict(row) for row in results]
        except Exception as e:
            self._log_error("load_zemlje_data", e)
            return []
    
    # ============================================================
    # GENERIČKA PRETRAGA (Generic Search)
    # ============================================================
    
    def search_generic(self, table_name: str, search_query: str) -> List[Dict[str, Any]]:
        """Generička pretraga po tabeli."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    search_pattern = f"%{search_query}%"
                    
                    # Odredi kolone za pretragu na osnovu tabele
                    if table_name == "catalogs.izvoznici":
                        columns = ["naziv", "jib", "grad", "drzava"]
                    elif table_name == "catalogs.uvoznici":
                        columns = ["naziv", "jib", "grad", "drzava"]
                    elif table_name == "catalogs.tarifa_2026":
                        columns = ["tarifni_kod", "naziv_robe", "opis"]
                    elif table_name == "catalogs.drzave":
                        columns = ["naziv", "sifra"]
                    else:
                        columns = ["naziv", "sifra"]
                    
                    # Kreiraj WHERE uslov
                    where_conditions = " OR ".join([f"{col} ILIKE %s" for col in columns])
                    query = f"SELECT * FROM {table_name} WHERE {where_conditions}"
                    
                    cur.execute(query, [search_pattern] * len(columns))
                    results = cur.fetchall()
                    return [dict(row) for row in results]
        except Exception as e:
            self._log_error(f"search_generic_{table_name}", e)
            return []

    def _log_error(self, operation: str, error: Exception):
        """Logovanje grešaka."""
        import logging
        logger = logging.getLogger("asycuda_pro.services.sifarnici")
        logger.error(f"Greška u {operation}: {error}")

    # ============================================================
    # DEKLARANTI (Declarants)
    # ============================================================

    def load_deklaranti_data(self, search_query: str = "") -> List[Dict[str, Any]]:
        """Dohvati podatke o deklarantima sa opcionom pretragom."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    if search_query:
                        search_pattern = f"%{search_query}%"
                        cur.execute("""
                            SELECT jib, naziv, adresa, grad, drzava, telefon, email, kontakt, pdv_broj, maticni
                            FROM catalogs.deklaranti
                            WHERE naziv ILIKE %s OR jib ILIKE %s OR grad ILIKE %s
                            ORDER BY naziv
                        """, (search_pattern, search_pattern, search_pattern))
                    else:
                        cur.execute("""
                            SELECT jib, naziv, adresa, grad, drzava, telefon, email, kontakt, pdv_broj, maticni
                            FROM catalogs.deklaranti
                            ORDER BY naziv
                        """)
                    results = cur.fetchall()
                    return [dict(row) for row in results]
        except Exception as e:
            self._log_error("load_deklaranti_data", e)
            return []

    def add_deklarant(self, data: Dict[str, str]) -> bool:
        """Dodaj novog deklaranta."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO catalogs.deklaranti 
                        (jib, naziv, adresa, grad, drzava, telefon, email, kontakt, pdv_broj, maticni)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (jib) DO UPDATE SET
                            naziv = EXCLUDED.naziv,
                            adresa = EXCLUDED.adresa,
                            grad = EXCLUDED.grad,
                            drzava = EXCLUDED.drzava,
                            telefon = EXCLUDED.telefon,
                            email = EXCLUDED.email,
                            kontakt = EXCLUDED.kontakt,
                            pdv_broj = EXCLUDED.pdv_broj,
                            maticni = EXCLUDED.maticni
                    """, (
                        data.get("jib", ""),
                        data.get("naziv", ""),
                        data.get("adresa", ""),
                        data.get("grad", ""),
                        data.get("drzava", ""),
                        data.get("telefon", ""),
                        data.get("email", ""),
                        data.get("kontakt", ""),
                        data.get("pdv_broj", ""),
                        data.get("maticni", "")
                    ))
                    conn.commit()
                    return cur.rowcount > 0
        except Exception as e:
            self._log_error("add_deklarant", e)
            return False

    def delete_deklarant(self, jib: str) -> bool:
        """Obriši deklaranta po JIB-u."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM catalogs.deklaranti WHERE jib = %s", (jib,))
                    conn.commit()
                    return cur.rowcount > 0
        except Exception as e:
            self._log_error("delete_deklarant", e)
            return False

    # ============================================================
    # CARINARNICE - CRUD OPERACIJE
    # ============================================================

    def add_carinarnica(self, sifra: str, naziv: str, opis: str = "") -> bool:
        """Dodaj novu carinarnicu."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO catalogs.carinske_ispostave (sifra, naziv, opis)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (sifra) DO UPDATE SET
                            naziv = EXCLUDED.naziv,
                            opis = EXCLUDED.opis
                    """, (sifra, naziv, opis))
                    conn.commit()
                    return cur.rowcount > 0
        except Exception as e:
            self._log_error("add_carinarnica", e)
            return False

    def delete_carinarnica(self, sifra: str) -> bool:
        """Obriši carinarnicu po šifri."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM catalogs.carinske_ispostave WHERE sifra = %s", (sifra,))
                    conn.commit()
                    return cur.rowcount > 0
        except Exception as e:
            self._log_error("delete_carinarnica", e)
            return False

    # ============================================================
    # CARINSKI POSTUPCI - CRUD OPERACIJE
    # ============================================================

    def add_carinski_postupak(self, sifra: str, naziv: str, opis: str = "") -> bool:
        """Dodaj novi carinski postupak."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO catalogs.carinski_postupci (sifra, naziv, opis)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (sifra) DO UPDATE SET
                            naziv = EXCLUDED.naziv,
                            opis = EXCLUDED.opis
                    """, (sifra, naziv, opis))
                    conn.commit()
                    return cur.rowcount > 0
        except Exception as e:
            self._log_error("add_carinski_postupak", e)
            return False

    def delete_carinski_postupak(self, sifra: str) -> bool:
        """Obriši carinski postupak po šifri."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM catalogs.carinski_postupci WHERE sifra = %s", (sifra,))
                    conn.commit()
                    return cur.rowcount > 0
        except Exception as e:
            self._log_error("delete_carinski_postupak", e)
            return False

    # ============================================================
    # ZEMLJE - CRUD OPERACIJE
    # ============================================================

    def add_zemlja(self, sifra: str, naziv: str, opis: str = "") -> bool:
        """Dodaj novu zemlju."""
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
                    return cur.rowcount > 0
        except Exception as e:
            self._log_error("add_zemlja", e)
            return False

    def delete_zemlja(self, sifra: str) -> bool:
        """Obriši zemlju po šifri."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM catalogs.drzave WHERE sifra = %s", (sifra,))
                    conn.commit()
                    return cur.rowcount > 0
        except Exception as e:
            self._log_error("delete_zemlja", e)
            return False

    # ============================================================
    # TRGOVAČKI NAZIVI - CRUD OPERACIJE
    # ============================================================

    def add_trgovacki_naziv(self, tarifni_kod: str, naziv_robe: str, opis: str = "", 
                           stopa_pdv: float = 0.0, stopa_uvoz: float = 0.0, stopa_akciza: float = 0.0) -> bool:
        """Dodaj novi trgovački naziv."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO catalogs.tarifa_2026 
                        (tarifni_kod, naziv_robe, opis, stopa_pdv, stopa_uvoz, stopa_akciza)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (tarifni_kod) DO UPDATE SET
                            naziv_robe = EXCLUDED.naziv_robe,
                            opis = EXCLUDED.opis,
                            stopa_pdv = EXCLUDED.stopa_pdv,
                            stopa_uvoz = EXCLUDED.stopa_uvoz,
                            stopa_akciza = EXCLUDED.stopa_akciza
                    """, (tarifni_kod, naziv_robe, opis, stopa_pdv, stopa_uvoz, stopa_akciza))
                    conn.commit()
                    return cur.rowcount > 0
        except Exception as e:
            self._log_error("add_trgovacki_naziv", e)
            return False

    def delete_trgovacki_naziv(self, tarifni_kod: str) -> bool:
        """Obriši trgovački naziv po tarifnom kodu."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM catalogs.tarifa_2026 WHERE tarifni_kod = %s", (tarifni_kod,))
                    conn.commit()
                    return cur.rowcount > 0
        except Exception as e:
            self._log_error("delete_trgovacki_naziv", e)
            return False

    # ============================================================
    # VALIDACIJA SPECIFIČNA ZA KATEGORIJE
    # ============================================================

    def validate_posiljalac_data(self, data: Dict[str, str]) -> List[str]:
        """Validiraj podatke za pošiljaoca."""
        errors = []
        
        # JIB validacija
        jib = data.get("jib", "").strip()
        if not jib:
            errors.append("JIB je obavezan")
        elif not jib.isdigit() or len(jib) != 13:
            errors.append("JIB mora imati 13 cifara")
        
        # Naziv validacija
        naziv = data.get("naziv", "").strip()
        if not naziv:
            errors.append("Naziv je obavezan")
        elif len(naziv) < 2:
            errors.append("Naziv mora imati najmanje 2 karaktera")
        
        return errors

    def validate_uvoznik_data(self, data: Dict[str, str]) -> List[str]:
        """Validiraj podatke za uvoznika."""
        errors = []
        
        # JIB validacija
        jib = data.get("jib", "").strip()
        if not jib:
            errors.append("JIB je obavezan")
        elif not jib.isdigit() or len(jib) != 13:
            errors.append("JIB mora imati 13 cifara")
        
        # Naziv validacija
        naziv = data.get("naziv", "").strip()
        if not naziv:
            errors.append("Naziv je obavezan")
        elif len(naziv) < 2:
            errors.append("Naziv mora imati najmanje 2 karaktera")
        
        return errors

    def validate_deklarant_data(self, data: Dict[str, str]) -> List[str]:
        """Validiraj podatke za deklaranta."""
        errors = []
        
        # JIB validacija
        jib = data.get("jib", "").strip()
        if not jib:
            errors.append("JIB je obavezan")
        elif not jib.isdigit() or len(jib) != 13:
            errors.append("JIB mora imati 13 cifara")
        
        # Naziv validacija
        naziv = data.get("naziv", "").strip()
        if not naziv:
            errors.append("Naziv je obavezan")
        elif len(naziv) < 2:
            errors.append("Naziv mora imati najmanje 2 karaktera")
        
        return errors

    def validate_carinarnica_data(self, sifra: str, naziv: str) -> List[str]:
        """Validiraj podatke za carinarnicu."""
        errors = []
        
        if not sifra or not sifra.strip():
            errors.append("Šifra je obavezna")
        elif len(sifra) != 8:
            errors.append("Šifra carinarnice mora imati 8 karaktera")
        
        if not naziv or not naziv.strip():
            errors.append("Naziv je obavezan")
        elif len(naziv) < 2:
            errors.append("Naziv mora imati najmanje 2 karaktera")
        
        return errors

    def validate_carinski_postupak_data(self, sifra: str, naziv: str) -> List[str]:
        """Validiraj podatke za carinski postupak."""
        errors = []
        
        if not sifra or not sifra.strip():
            errors.append("Šifra je obavezna")
        elif len(sifra) != 2:
            errors.append("Šifra carinskog postupka mora imati 2 karaktera")
        
        if not naziv or not naziv.strip():
            errors.append("Naziv je obavezan")
        elif len(naziv) < 2:
            errors.append("Naziv mora imati najmanje 2 karaktera")
        
        return errors

    def validate_zemlja_data(self, sifra: str, naziv: str) -> List[str]:
        """Validiraj podatke za zemlju."""
        errors = []
        
        if not sifra or not sifra.strip():
            errors.append("Šifra je obavezna")
        elif len(sifra) != 2:
            errors.append("Šifra zemlje mora imati 2 karaktera")
        
        if not naziv or not naziv.strip():
            errors.append("Naziv je obavezan")
        elif len(naziv) < 2:
            errors.append("Naziv mora imati najmanje 2 karaktera")
        
        return errors

    def validate_trgovacki_naziv_data(self, tarifni_kod: str, naziv_robe: str) -> List[str]:
        """Validiraj podatke za trgovački naziv."""
        errors = []
        
        if not tarifni_kod or not tarifni_kod.strip():
            errors.append("Tarifni kod je obavezan")
        elif len(tarifni_kod) != 10:
            errors.append("Tarifni kod mora imati 10 karaktera")
        
        if not naziv_robe or not naziv_robe.strip():
            errors.append("Naziv robe je obavezan")
        elif len(naziv_robe) < 2:
            errors.append("Naziv robe mora imati najmanje 2 karaktera")
        
        return errors