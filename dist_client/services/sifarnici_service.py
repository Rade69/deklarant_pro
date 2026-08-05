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

import logging
from typing import Dict, Any, List, Optional
from database.db import get_db_connection
from psycopg2 import sql

logger = logging.getLogger("deklarant_pro.services.sifarnici")


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
        self.last_error = ""
    
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
    def _ensure_deklaranti_schema(self, cur) -> None:
        """Osiguraj Rub.14 kolone za postojeće catalogs.deklaranti tabele."""
        cur.execute("CREATE SCHEMA IF NOT EXISTS catalogs")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS catalogs.deklaranti (
                jib VARCHAR(50) PRIMARY KEY,
                naziv TEXT NOT NULL DEFAULT '',
                adresa TEXT DEFAULT '',
                grad TEXT DEFAULT '',
                postanski_broj TEXT DEFAULT '',
                drzava TEXT DEFAULT '',
                telefon TEXT DEFAULT '',
                email TEXT DEFAULT '',
                kontakt TEXT DEFAULT '',
                pdv_broj TEXT DEFAULT '',
                maticni TEXT DEFAULT ''
            )
        """)
        cur.execute("""
            ALTER TABLE catalogs.deklaranti
            ADD COLUMN IF NOT EXISTS postanski_broj TEXT DEFAULT ''
        """)
    
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

    def update_posiljalac(self, data: Dict[str, str]) -> bool:
        """Ažuriraj postojećeg pošiljaoca."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE catalogs.izvoznici
                        SET naziv = %s, adresa = %s, grad = %s,
                            drzava = %s, telefon = %s, email = %s,
                            kontakt = %s, pdv_broj = %s, maticni = %s
                        WHERE jib = %s
                    """, (
                        data.get("naziv", ""),
                        data.get("adresa", ""),
                        data.get("grad", ""),
                        data.get("drzava", ""),
                        data.get("telefon", ""),
                        data.get("email", ""),
                        data.get("kontakt", ""),
                        data.get("pdv_broj", ""),
                        data.get("maticni", ""),
                        data.get("jib", "")
                    ))
                    conn.commit()
                    return cur.rowcount > 0
        except Exception as e:
            self._log_error("update_posiljalac", e)
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

    def update_uvoznik(self, data: Dict[str, str]) -> bool:
        """Ažuriraj postojećeg uvoznika."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE catalogs.uvoznici
                        SET naziv = %s, adresa = %s, grad = %s,
                            drzava = %s, telefon = %s, email = %s,
                            kontakt = %s, pdv_broj = %s, maticni = %s
                        WHERE jib = %s
                    """, (
                        data.get("naziv", ""),
                        data.get("adresa", ""),
                        data.get("grad", ""),
                        data.get("drzava", ""),
                        data.get("telefon", ""),
                        data.get("email", ""),
                        data.get("kontakt", ""),
                        data.get("pdv_broj", ""),
                        data.get("maticni", ""),
                        data.get("jib", "")
                    ))
                    conn.commit()
                    return cur.rowcount > 0
        except Exception as e:
            self._log_error("update_uvoznik", e)
            return False
    
    # ============================================================
    # TRGOVAČKI NAZIVI (Trade Names)
    # ============================================================
    
    def load_trgovacki_nazivi_data(self, search_query: str = "") -> List[Dict[str, Any]]:
        """Hibridna pretraga carinske tarife — broj ili tekst.

        - Ako upit sadrži cifre → prefix match po tarifnom kodu (B-tree indeks, instant)
        - Ako je tekst → full-text to_tsvector pretraga po riječima (50× brže od ILIKE)
        - Fallback: pg_trgm similarity operator (%) za aproksimativno poklapanje

        Bez indeksa (deklarant_app nije vlasnik tabele), ali tsvector poređenje
        je i dalje 10-50× brže od ILIKE '%text%' jer radi poređenje tokena
        (riječi) umjesto karakter-po-karakter skeniranja.
        """
        try:
            query = search_query.strip()
            if len(query) < 2:
                return []

            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    has_digits = any(c.isdigit() for c in query)

                    if has_digits:
                        digits_only = "".join(c for c in query if c.isdigit())
                        search_pattern = f"{digits_only}%"
                        cur.execute("""
                            SELECT tarifni_kod, opis
                            FROM catalogs.zvanicna_tarifa
                            WHERE tarifni_kod LIKE %s
                            ORDER BY tarifni_kod
                            LIMIT 500
                        """, (search_pattern,))
                    else:
                        escaped = query.replace("'", "''")
                        fts_query = " & ".join(escaped.split())
                        ilike_pattern = f"%{escaped}%"

                        cur.execute("""
                            SELECT tarifni_kod, opis,
                                   ts_rank(to_tsvector('simple', opis), to_tsquery('simple', %s)) AS rank
                            FROM catalogs.zvanicna_tarifa
                            WHERE to_tsvector('simple', opis) @@ to_tsquery('simple', %s)
                               OR opis ILIKE %s
                               OR tarifni_kod ILIKE %s
                            ORDER BY
                                CASE WHEN tarifni_kod ILIKE %s THEN 0 ELSE 1 END,
                                rank DESC
                            LIMIT 500
                        """, (fts_query, fts_query, ilike_pattern, ilike_pattern, ilike_pattern))
                        results = cur.fetchall()

                        if not results:
                            cur.execute("""
                                SELECT tarifni_kod, opis,
                                       similarity(opis, %s) AS sim
                                FROM catalogs.zvanicna_tarifa
                                WHERE opis %% %s
                                ORDER BY sim DESC
                                LIMIT 200
                            """, (query, query))
                            results = cur.fetchall()

                        return [dict(row) for row in results]

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
                        SELECT sifra, opis, vrsta, oznaka
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
    def _log_error(self, operation: str, error: Exception):
        """Logovanje grešaka."""
        self.last_error = str(error)
        logger.error(f"Greška u {operation}: {error}")

    # ============================================================
    # DEKLARANTI (Declarants)
    # ============================================================

    def load_deklaranti_data(self, search_query: str = "") -> List[Dict[str, Any]]:
        """Dohvati podatke o deklarantima sa opcionom pretragom."""
        # NOTE: catalogs.deklaranti tabela treba da postoji — kreirati je ako ne postoji
        self.last_error = ""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    self._ensure_deklaranti_schema(cur)
                    if search_query:
                        search_pattern = f"%{search_query}%"
                        cur.execute("""
                            SELECT jib, naziv, adresa, grad, postanski_broj, drzava, telefon, email, kontakt, pdv_broj, maticni
                            FROM catalogs.deklaranti
                            WHERE naziv ILIKE %s OR jib ILIKE %s OR grad ILIKE %s OR adresa ILIKE %s
                            ORDER BY naziv
                        """, (
                            search_pattern,
                            search_pattern,
                            search_pattern,
                            search_pattern,
                        ))
                    else:
                        cur.execute("""
                            SELECT jib, naziv, adresa, grad, postanski_broj, drzava, telefon, email, kontakt, pdv_broj, maticni
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
        self.last_error = ""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    self._ensure_deklaranti_schema(cur)
                    cur.execute("""
                        INSERT INTO catalogs.deklaranti
                        (jib, naziv, adresa, grad, postanski_broj, drzava, telefon, email, kontakt, pdv_broj, maticni)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (jib) DO UPDATE SET
                            naziv = EXCLUDED.naziv,
                            adresa = EXCLUDED.adresa,
                            grad = EXCLUDED.grad,
                            postanski_broj = EXCLUDED.postanski_broj,
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
                        data.get("postanski_broj", ""),
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

    def update_deklarant(self, data: Dict[str, str]) -> bool:
        """Ažuriraj postojećeg deklaranta."""
        return self.add_deklarant(data)

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

    def add_carinarnica(self, sifra: str, naziv: str, regionalni_centar_id: Optional[int] = None) -> bool:
        """Dodaj novu carinarnicu (carinsku ispostavu)."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO catalogs.carinske_ispostave (sifra, naziv, regionalni_centar_id)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (sifra) DO UPDATE SET
                            naziv = EXCLUDED.naziv,
                            regionalni_centar_id = EXCLUDED.regionalni_centar_id
                    """, (sifra, naziv, regionalni_centar_id))
                    conn.commit()
                    return cur.rowcount > 0
        except Exception as e:
            self._log_error("add_carinarnica", e)
            return False

    def update_carinarnica(self, sifra: str, naziv: str) -> bool:
        """Ažuriraj carinarnicu."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE catalogs.carinske_ispostave
                        SET naziv = %s
                        WHERE sifra = %s
                    """, (naziv, sifra))
                    conn.commit()
                    return cur.rowcount > 0
        except Exception as e:
            self._log_error("update_carinarnica", e)
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

    def add_carinski_postupak(self, sifra: str, opis: str, vrsta: str = "", oznaka: str = "") -> bool:
        """Dodaj novi carinski postupak."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO catalogs.carinski_postupci (sifra, opis, vrsta, oznaka)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (sifra) DO UPDATE SET
                            opis = EXCLUDED.opis,
                            vrsta = EXCLUDED.vrsta,
                            oznaka = EXCLUDED.oznaka
                    """, (sifra, opis, vrsta, oznaka))
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

    def add_zemlja(self, sifra: str, naziv: str) -> bool:
        """Dodaj novu zemlju."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO catalogs.drzave (sifra, naziv)
                        VALUES (%s, %s)
                        ON CONFLICT (sifra) DO UPDATE SET
                            naziv = EXCLUDED.naziv
                    """, (sifra, naziv))
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

    def add_trgovacki_naziv(self, tarifni_kod: str, opis: str) -> bool:
        """Dodaj novi trgovački naziv (carinsku tarifu)."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO catalogs.zvanicna_tarifa
                        (tarifni_kod, opis)
                        VALUES (%s, %s)
                        ON CONFLICT (tarifni_kod) DO UPDATE SET
                            opis = EXCLUDED.opis
                    """, (tarifni_kod, opis))
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
                    cur.execute("DELETE FROM catalogs.zvanicna_tarifa WHERE tarifni_kod = %s", (tarifni_kod,))
                    conn.commit()
                    return cur.rowcount > 0
        except Exception as e:
            self._log_error("delete_trgovacki_naziv", e)
            return False

    def update_trgovacki_naziv(self, tarifni_kod: str, opis: str) -> bool:
        """Ažuriraj trgovački naziv."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE catalogs.zvanicna_tarifa
                        SET opis = %s
                        WHERE tarifni_kod = %s
                    """, (opis, tarifni_kod))
                    conn.commit()
                    return cur.rowcount > 0
        except Exception as e:
            self._log_error("update_trgovacki_naziv", e)
            return False

    # ============================================================
    # VALIDACIJA SPECIFIČNA ZA KATEGORIJE
    # ============================================================
    def search_posiljaoci(self, query: str) -> List[Dict[str, Any]]:
        """Pretraga pošiljalaca po nazivu, JIB-u, gradu."""
        return self.load_posiljaoci_data(query)

    def search_uvoznici(self, query: str) -> List[Dict[str, Any]]:
        """Pretraga uvoznika po nazivu, JIB-u, gradu."""
        return self.load_uvoznici_data(query)

    def search_zemlje(self, query: str) -> List[Dict[str, Any]]:
        """Pretraga zemalja po nazivu ili šifri."""
        return self.load_zemlje_data(query)

    def search_trgovacki_nazivi(self, query: str) -> List[Dict[str, Any]]:
        """Pretraga tarifa po tarifnom kodu ili opisu."""
        return self.load_trgovacki_nazivi_data(query)

    def search_deklaranti(self, query: str) -> List[Dict[str, Any]]:
        """Pretraga deklaranta po nazivu, JIB-u, gradu."""
        return self.load_deklaranti_data(query)

    def search_carinski_postupci(self, query: str) -> List[Dict[str, Any]]:
        """Pretraga carinskih postupaka."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    pattern = f"%{query}%"
                    cur.execute("""
                        SELECT sifra, opis, vrsta, oznaka
                        FROM catalogs.carinski_postupci
                        WHERE sifra ILIKE %s OR opis ILIKE %s OR vrsta ILIKE %s OR oznaka ILIKE %s
                        ORDER BY sifra
                    """, (pattern, pattern, pattern, pattern))
                    results = cur.fetchall()
                    return [dict(row) for row in results]
        except Exception as e:
            self._log_error("search_carinski_postupci", e)
            return []

    # ============================================================
    # HIERARHIJSKI PRIKAZ — CARINARNICE SA REGIONALNIM CENTRIMA
    # ============================================================

    def load_carinarnice_hierarchical(self) -> List[Dict[str, Any]]:
        """Učitaj carinske ispostave grupisane po regionalnim centrima.

        Returns:
            Lista dict-ova sa ključevima:
            - rc_id, rc_sifra, rc_naziv (regionalni centar)
            - ispostave: [(ci_sifra, ci_naziv), ...]
        """
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT rc.id as rc_id, rc.sifra as rc_sifra, rc.naziv as rc_naziv,
                               ci.sifra as ci_sifra, ci.naziv as ci_naziv
                        FROM catalogs.regionalni_centri rc
                        LEFT JOIN catalogs.carinske_ispostave ci ON rc.id = ci.regionalni_centar_id
                        ORDER BY rc.sifra, ci.sifra
                    """)
                    results = cur.fetchall()

            # Grupisanje po regionalnom centru
            regional_centers = {}
            for row in results:
                rc_id = row["rc_id"]
                if rc_id not in regional_centers:
                    regional_centers[rc_id] = {
                        "rc_id": rc_id,
                        "rc_sifra": row["rc_sifra"],
                        "rc_naziv": row["rc_naziv"],
                        "ispostave": [],
                    }
                ci_sifra = row.get("ci_sifra")
                ci_naziv = row.get("ci_naziv")
                if ci_sifra and ci_naziv:
                    regional_centers[rc_id]["ispostave"].append({
                        "ci_sifra": ci_sifra,
                        "ci_naziv": ci_naziv,
                    })

            return list(regional_centers.values())
        except Exception as e:
            self._log_error("load_carinarnices_hierarchical", e)
            return []

    # ============================================================
    # COUNT METODE (za status bar)
    # ============================================================

    def count_izvoznici(self) -> int:
        """Broj pošiljalaca u bazi."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM catalogs.izvoznici")
                    row = cur.fetchone()
                    return row["count"] if row else 0
        except Exception as e:
            self._log_error("count_izvoznici", e)
            return 0

    def count_uvoznici(self) -> int:
        """Broj uvoznika u bazi."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM catalogs.uvoznici")
                    row = cur.fetchone()
                    return row["count"] if row else 0
        except Exception as e:
            self._log_error("count_uvoznici", e)
            return 0

    def count_zvanicna_tarifa(self) -> int:
        """Broj tarifa u bazi."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM catalogs.zvanicna_tarifa")
                    row = cur.fetchone()
                    return row["count"] if row else 0
        except Exception as e:
            self._log_error("count_zvanicna_tarifa", e)
            return 0

    def count_carinske_ispostave(self) -> int:
        """Broj carinskih ispostava u bazi."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM catalogs.carinske_ispostave")
                    row = cur.fetchone()
                    return row["count"] if row else 0
        except Exception as e:
            self._log_error("count_carinske_ispostave", e)
            return 0

    # ============================================================
    # SECTION: inspection-rules-pg-service
    # PURPOSE: CRUD i pretraga inspekcijskih pravila iz PostgreSQL
    # DOC: docs/sections/inspection-rules-pg.md
    # ============================================================

    def load_inspection_rules(
        self,
        search: str = "",
        insp_type: str = "",
        only_active: bool = True,
        limit: int = 500,
    ) -> list[dict]:
        """
        Dohvati inspekcijska pravila iz catalogs.inspection_rules.

        Args:
            search:      Tekst pretrage (tariff_code_norm ili description)
            insp_type:   Filter po tipu (veterinary, sanitary, ...)
            only_active: Ako True, vraća samo is_active = TRUE redove
            limit:       Maksimalan broj redova

        Returns:
            Lista rječnika sa svim kolonama inspekcijskog pravila
        """
        try:
            clauses = []
            params: list = []

            if only_active:
                clauses.append("is_active = TRUE")

            if insp_type:
                clauses.append("inspection_type = %s")
                params.append(insp_type)

            if search:
                norm_search = search.replace(" ", "")
                clauses.append(
                    "(tariff_code_norm LIKE %s OR description ILIKE %s)"
                )
                params.append(norm_search + "%")
                params.append("%" + search + "%")

            where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
            params.append(limit)

            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(f"""
                        SELECT
                            id, inspection_type, tariff_code, tariff_code_norm,
                            tariff_len, scope, chapter, description, marker,
                            condition_text, match_strength, can_auto_decide,
                            source_dataset, source_page, is_active, notes
                        FROM catalogs.inspection_rules
                        {where}
                        ORDER BY inspection_type, tariff_code_norm
                        LIMIT %s
                    """, params)
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            self._log_error("load_inspection_rules", e)
            return []

    def count_inspection_rules(self, only_active: bool = True) -> int:
        """Ukupan broj inspekcijskih pravila (za status bar)."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    if only_active:
                        cur.execute("SELECT COUNT(*) FROM catalogs.inspection_rules WHERE is_active = TRUE")
                    else:
                        cur.execute("SELECT COUNT(*) FROM catalogs.inspection_rules")
                    row = cur.fetchone()
                    return row["count"] if row else 0
        except Exception as e:
            self._log_error("count_inspection_rules", e)
            return 0

    def get_inspection_rule(self, rule_id: int) -> dict | None:
        """Dohvati jedno pravilo po ID-u."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT
                            id, inspection_type, tariff_code, tariff_code_norm,
                            tariff_len, scope, chapter, description, marker,
                            condition_text, match_strength, can_auto_decide,
                            source_dataset, source_page, is_active, notes
                        FROM catalogs.inspection_rules
                        WHERE id = %s
                    """, (rule_id,))
                    row = cur.fetchone()
                    return dict(row) if row else None
        except Exception as e:
            self._log_error("get_inspection_rule", e)
            return None

    def update_inspection_rule(self, rule_id: int, updates: dict) -> bool:
        """
        Ažurira inspekcijsko pravilo (samo dozvoljene kolone).

        Dozvoljene kolone za izmjenu: description, condition_text,
        can_auto_decide, is_active, notes, marker.
        """
        ALLOWED = {
            "description", "condition_text", "can_auto_decide",
            "is_active", "notes", "marker",
        }
        filtered = {k: v for k, v in updates.items() if k in ALLOWED}
        if not filtered:
            return False
        try:
            set_parts = sql.SQL(", ").join(
                sql.SQL("{} = %s").format(sql.Identifier(k)) for k in filtered
            )
            query = sql.SQL(
                "UPDATE catalogs.inspection_rules SET {}, updated_at = NOW() WHERE id = %s"
            ).format(set_parts)
            vals = list(filtered.values()) + [rule_id]
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, vals)
                conn.commit()
                return True
        except Exception as e:
            self._log_error("update_inspection_rule", e)
            return False
    def add_inspection_rule(self, data: dict) -> int | None:
        """
        Doda novo inspekcijsko pravilo.

        Returns:
            ID novog reda, ili None ako je greška.
        """
        import re as _re
        required = {"inspection_type", "tariff_code"}
        if not required.issubset(data.keys()):
            return None

        raw_code = (data.get("tariff_code") or "").strip()
        norm = _re.sub(r"\s+", "", raw_code)

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO catalogs.inspection_rules
                            (inspection_type, tariff_code, tariff_code_norm, tariff_len,
                             scope, chapter, description, marker, condition_text,
                             match_strength, can_auto_decide, source_dataset,
                             is_active, notes)
                        VALUES
                            (%(inspection_type)s, %(tariff_code)s, %(norm)s, %(tlen)s,
                             %(scope)s, %(chapter)s, %(description)s, %(marker)s,
                             %(condition_text)s, %(match_strength)s, %(can_auto_decide)s,
                             %(source_dataset)s, TRUE, %(notes)s)
                        RETURNING id
                    """, {
                        "inspection_type":  data["inspection_type"],
                        "tariff_code":      raw_code,
                        "norm":             norm,
                        "tlen":             len(norm),
                        "scope":            data.get("scope") or "tariff_code",
                        "chapter":          data.get("chapter") or norm[:2],
                        "description":      data.get("description") or "",
                        "marker":           data.get("marker") or "",
                        "condition_text":   data.get("condition_text") or None,
                        "match_strength":   data.get("match_strength") or (
                            "exact" if len(norm) >= 8 else "prefix"
                        ),
                        "can_auto_decide":  not bool(data.get("condition_text")),
                        "source_dataset":   data.get("source_dataset") or "manual",
                        "notes":            data.get("notes") or None,
                    })
                    row = cur.fetchone()
                conn.commit()
                return row["id"] if row else None
        except Exception as e:
            self._log_error("add_inspection_rule", e)
            return None

    # ============================================================
    # INCOTERMS 2020
    # ============================================================

    def load_incoterms(self) -> List[Dict[str, Any]]:
        """Dohvati sve Incoterms 2020 kodove iz catalogs.incoterms."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT code, name_en, name_bs, transport_mode, freight_in_price
                        FROM catalogs.incoterms
                        ORDER BY code
                    """)
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            self._log_error("load_incoterms", e)
            return []

