import re
import time
import threading
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool, PoolError
from contextlib import contextmanager
from typing import Optional

_POOL_WAIT_TIMEOUT = 30  # sekundi čekanja kad je pool iscrpljen

from config.settings import get_db_settings


# =========================================================
# CONNECTION POOL
# =========================================================

_connection_pool: Optional[ThreadedConnectionPool] = None
_pool_lock = threading.Lock()


def get_connection_pool() -> ThreadedConnectionPool:
    """
    Dohvata ili kreira connection pool.
    
    Returns:
        SimpleConnectionPool: Pool za DB konekcije
    """
    global _connection_pool
    
    if _connection_pool is None:
        with _pool_lock:
            if _connection_pool is None:
                settings = get_db_settings()
                _connection_pool = ThreadedConnectionPool(
                    minconn=1,
                    maxconn=10,
                    host=settings.host,
                    port=settings.port,
                    database=settings.database,
                    user=settings.user,
                    password=settings.password,
                    sslmode=settings.sslmode,
                    cursor_factory=RealDictCursor,
                    connect_timeout=1,
                    options="-c statement_timeout=15000",
                )
    
    return _connection_pool


def get_connection():
    """
    Dohvata konekciju iz pool-a.
    
    VAŽNO: Konekcija se MORA vratiti u pool pozivom pool.putconn(conn).
    Preporučuje se korištenje get_db_connection() context manager-a umjesto ove funkcije.
    
    Returns:
        psycopg2.connection: DB konekcija
    """
    pool = get_connection_pool()
    return pool.getconn()


@contextmanager
def get_db_connection():
    """
    Context manager za DB konekcije.
    Automatski commit/rollback i vraćanje u pool.
    
    Usage:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(...)
    """
    pool = get_connection_pool()
    conn = None
    deadline = time.monotonic() + _POOL_WAIT_TIMEOUT
    while True:
        try:
            conn = pool.getconn()
            break
        except PoolError:
            if time.monotonic() >= deadline:
                raise PoolError(
                    f"Connection pool iscrpljen — konekcija nije dostupna za {_POOL_WAIT_TIMEOUT}s"
                )
            time.sleep(0.1)
    try:
        if conn.closed:
            pool.putconn(conn, close=True)
            conn = pool.getconn()
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def close_all_connections():
    """
    Zatvori sve konekcije.
    Pozovi na shutdown.
    """
    global _connection_pool
    if _connection_pool:
        _connection_pool.closeall()
        _connection_pool = None


# =========================================================
# HELPERS
# =========================================================


def normalize_tarifni_kod(value: str) -> str:
    """
    Normalizuje tarifni kod u format kompatibilan sa XML-om:
    Commodity_code (8 cifara) + Precision_1 (3 cifre)

    Primjeri:
    - 18069031  -> 18069031000
    - 85437090  -> 85437090000
    - 18069031000 -> 18069031000
    """
    if not value:
        return ""

    digits = re.sub(r"\D+", "", str(value))
    if not digits:
        return ""

    if len(digits) == 8:
        return digits + "000"
    if len(digits) == 9:
        return digits + "00"
    if len(digits) == 10:
        return digits + "0"

    return digits


def generate_fallback_codes(tarifni_kod: str):
    """
    Generiše listu fallback kodova od najpreciznijeg ka opštijem.
    """
    codes = []
    code = normalize_tarifni_kod(tarifni_kod)

    while len(code) >= 6:
        codes.append(code)
        code = code[:-1]

    # osiguraj da 8-cifreni + 000 uvijek bude uključen
    if len(tarifni_kod) >= 8:
        base = tarifni_kod[:8] + "000"
        if base not in codes:
            codes.append(base)

    return list(dict.fromkeys(codes))  # bez duplikata, zadrži redoslijed


# =========================================================
# ZVANIČNA TARIFA (ZAKON)
# =========================================================


def get_tarifa_opis(tarifni_kod: str):
    """
    Vraća zakonski opis tarife iz catalogs.zvanicna_tarifa.

    Ako tačan tarifni kod ne postoji, koristi fallback (viši nivo tarife).
    Sve kandidate traži u jednom upitu, sortira po specifičnosti (duži kod = specifičniji).
    """
    fallback_codes = generate_fallback_codes(tarifni_kod)
    if not fallback_codes:
        return None

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT tarifni_kod, opis
                FROM catalogs.zvanicna_tarifa
                WHERE tarifni_kod = ANY(%s)
                ORDER BY LENGTH(tarifni_kod) DESC
                LIMIT 1
                """,
                (fallback_codes,),
            )
            return cur.fetchone()


def search_tarife_by_text(query: str, limit: int = 20):
    """
    Pretraga zvanične tarife po opisu (ILIKE).
    """
    q = (query or "").strip()
    if not q:
        return []

    sql = """
        SELECT tarifni_kod, opis
        FROM catalogs.zvanicna_tarifa
        WHERE opis ILIKE %s
        ORDER BY tarifni_kod
        LIMIT %s
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (f"%{q}%", limit))
            return cur.fetchall()


# =========================================================
# TARIFA ↔ NAZIV ROBE (PRAKSA) — C2
# =========================================================


def get_nazivi_robe_za_tarifu(tarifni_kod: str, limit: int = 10):
    """
    Vraća nazive robe za tarifni kod (iz prakse).
    """
    kod = normalize_tarifni_kod(tarifni_kod)
    if not kod:
        return []

    sql = """
        SELECT naziv_robe
        FROM catalogs.tarifa_nazivi
        WHERE tarifni_kod = %s
        ORDER BY naziv_robe
        LIMIT %s
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (kod, limit))
            rows = cur.fetchall()
            return [r["naziv_robe"] for r in rows]


def search_nazivi_robe(query: str, limit: int = 20):
    """
    Pretraga naziva robe (ILIKE).
    """
    q = (query or "").strip()
    if not q:
        return []

    sql = """
        SELECT tarifni_kod, naziv_robe
        FROM catalogs.tarifa_nazivi
        WHERE naziv_robe ILIKE %s
        ORDER BY tarifni_kod, naziv_robe
        LIMIT %s
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (f"%{q}%", limit))
            return cur.fetchall()


# =========================================================
# PARTNERI
# =========================================================


def get_partner_by_jib(jib: str):
    """
    Vraća partnera po JIB-u iz zajedničke tabele.
    """
    j = (jib or "").strip()
    if not j:
        return None

    sql = """
        SELECT jib, naziv, adresa
        FROM catalogs.partneri
        WHERE jib = %s
        LIMIT 1
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (j,))
            return cur.fetchone()


def search_partnere(query: str, limit: int = 20):
    """
    Pretraga partnera po nazivu iz zajedničke tabele.
    """
    q = (query or "").strip()
    if not q:
        # Ako je query prazan, učitaj sve partnere
        sql = """
            SELECT jib, naziv, adresa, grad, postanski_broj, drzava
            FROM catalogs.partneri
            ORDER BY naziv
            LIMIT %s
        """
        params = (limit,)
    else:
        sql = """
            SELECT jib, naziv, adresa, grad, postanski_broj, drzava
            FROM catalogs.partneri
            WHERE naziv ILIKE %s
            ORDER BY naziv
            LIMIT %s
        """
        params = (f"%{q}%", limit)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def get_trader_by_code(code: str, trader_type: str | None = None):
    """
    Vraća trgovca po šifri i opcionalno tipu.
    """
    c = (code or "").strip()
    if not c:
        return None

    if trader_type:
        sql = """
            SELECT id, partner_type, name, address, city, country, code
            FROM traders
            WHERE code = %s AND partner_type = %s
            LIMIT 1
        """
        params = (c, trader_type)
    else:
        sql = """
            SELECT id, partner_type, name, address, city, country, code
            FROM traders
            WHERE code = %s
            LIMIT 1
        """
        params = (c,)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()


def search_traders(query: str, trader_type: str | None = None, limit: int = 20):
    """
    Pretraga trgovaca po nazivu i opcionalno tipu.
    """
    q = (query or "").strip()
    if not q:
        # Ako je query prazan, učitaj sve trgovce (ili sve određenog tipa)
        if trader_type:
            sql = """
                SELECT code AS jib, name AS naziv, address AS adresa, city AS grad, '' AS postanski_broj, country AS drzava
                FROM traders
                WHERE partner_type = %s
                ORDER BY name
                LIMIT %s
            """
            params = (trader_type, limit)
        else:
            sql = """
                SELECT code AS jib, name AS naziv, address AS adresa, city AS grad, '' AS postanski_broj, country AS drzava
                FROM traders
                ORDER BY name
                LIMIT %s
            """
            params = (limit,)
    else:
        # Ako postoji query, pretraži po nazivu
        if trader_type:
            sql = """
                SELECT code AS jib, name AS naziv, address AS adresa, city AS grad, '' AS postanski_broj, country AS drzava
                FROM traders
                WHERE name ILIKE %s AND partner_type = %s
                ORDER BY name
                LIMIT %s
            """
            params = (f"%{q}%", trader_type, limit)
        else:
            sql = """
                SELECT code AS jib, name AS naziv, address AS adresa, city AS grad, '' AS postanski_broj, country AS drzava
                FROM traders
                WHERE name ILIKE %s
                ORDER BY name
                LIMIT %s
            """
            params = (f"%{q}%", limit)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def search_exporters(query: str, limit: int = 20):
    """
    Pretraga izvoznika po nazivu.
    """
    return search_traders(query, 'EXPORTER', limit)


def search_consignees(query: str, limit: int = 20):
    """
    Pretraga primalaca po nazivu.
    """
    return search_traders(query, 'CONSIGNEE', limit)


def get_izvoznik_by_jib(jib: str):
    """
    Vraća izvoznika po JIB-u.
    """
    j = (jib or "").strip()
    if not j:
        return None

    sql = """
        SELECT jib, naziv, adresa, grad, postanski_broj, drzava
        FROM catalogs.izvoznici
        WHERE jib = %s
        LIMIT 1
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (j,))
            return cur.fetchone()


def get_uvoznik_by_jib(jib: str):
    """
    Vraća uvoznika po JIB-u.
    """
    j = (jib or "").strip()
    if not j:
        return None

    sql = """
        SELECT jib, naziv, adresa, grad, postanski_broj, drzava
        FROM catalogs.uvoznici
        WHERE jib = %s
        LIMIT 1
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (j,))
            return cur.fetchone()


def search_izvoznike(query: str, limit: int = 20):
    """
    Pretraga izvoznika po nazivu ili JIB-u.
    """
    q = (query or "").strip()
    if not q:
        sql = """
            SELECT jib, naziv, adresa, grad, drzava
            FROM catalogs.izvoznici
            ORDER BY naziv NULLS LAST
            LIMIT %s
        """
        params = (limit,)
    else:
        sql = """
            SELECT jib, naziv, adresa, grad, drzava
            FROM catalogs.izvoznici
            WHERE naziv ILIKE %s OR jib ILIKE %s
            ORDER BY naziv NULLS LAST
            LIMIT %s
        """
        params = (f"%{q}%", f"%{q}%", limit)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def search_uvoznike(query: str, limit: int = 20):
    """
    Pretraga uvoznika po nazivu ili JIB-u.
    """
    q = (query or "").strip()
    if not q:
        sql = """
            SELECT jib, naziv, adresa, grad, postanski_broj, drzava
            FROM catalogs.uvoznici
            ORDER BY naziv NULLS LAST
            LIMIT %s
        """
        params = (limit,)
    else:
        sql = """
            SELECT jib, naziv, adresa, grad, postanski_broj, drzava
            FROM catalogs.uvoznici
            WHERE naziv ILIKE %s OR jib ILIKE %s
            ORDER BY naziv NULLS LAST
            LIMIT %s
        """
        params = (f"%{q}%", f"%{q}%", limit)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
