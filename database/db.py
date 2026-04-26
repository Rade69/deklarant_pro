import re
import time
import threading
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool, PoolError
from contextlib import contextmanager
from typing import Optional

_POOL_WAIT_TIMEOUT = 30  # sekundi Äekanja kad je pool iscrpljen

from config.settings import get_db_settings


# =========================================================
# CIRCUIT BREAKER â€” sprjeÄava uzastopne timeout blokade
# =========================================================
# Ako se konekcija ne moÅ¾e uspostaviti, Äekamo _CB_COOLDOWN sekundi
# prije sljedeÄ‡eg pokuÅ¡aja. Bez ovoga svaka operacija Äeka connect_timeout.

_CB_COOLDOWN = 15.0       # sekundi pauze nakon neuspjeha
_cb_open_until: float = 0.0   # monotonic timestamp do kada je circuit otvoren
_cb_lock = threading.Lock()


def _circuit_open() -> bool:
    """Vrati True ako circuit breaker blokira konekcije."""
    return time.monotonic() < _cb_open_until


def _trip_circuit() -> None:
    """Otvori circuit breaker na _CB_COOLDOWN sekundi."""
    global _cb_open_until
    with _cb_lock:
        _cb_open_until = time.monotonic() + _CB_COOLDOWN


def _reset_circuit() -> None:
    """Zatvori circuit breaker (uspjeÅ¡na konekcija)."""
    global _cb_open_until
    _cb_open_until = 0.0


# =========================================================
# CONNECTION POOL
# =========================================================

_connection_pool: Optional[ThreadedConnectionPool] = None
_pool_lock = threading.Lock()


def get_connection_pool() -> ThreadedConnectionPool:
    """
    Dohvata ili kreira connection pool.
    Baca psycopg2.OperationalError ako server nije dostupan.
    """
    global _connection_pool

    if _connection_pool is None:
        with _pool_lock:
            if _connection_pool is None:
                settings = get_db_settings()
                try:
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
                except psycopg2.OperationalError:
                    _trip_circuit()
                    raise

    return _connection_pool


def get_connection():
    """
    Dohvata konekciju iz pool-a.
    
    VAÅ½NO: Konekcija se MORA vratiti u pool pozivom pool.putconn(conn).
    PreporuÄuje se koriÅ¡tenje get_db_connection() context manager-a umjesto ove funkcije.
    
    Returns:
        psycopg2.connection: DB konekcija
    """
    pool = get_connection_pool()
    return pool.getconn()


@contextmanager
def get_db_connection():
    """
    Context manager za DB konekcije.
    Automatski commit/rollback i vraÄ‡anje u pool.
    Circuit breaker: ako je DB nedostupan, odmah baci greÅ¡ku bez Äekanja.

    Usage:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(...)
    """
    # Circuit breaker â€” ne Äekaj timeout ako znamo da DB nije dostupan
    if _circuit_open():
        raise PoolError("DB circuit breaker aktivan â€” server privremeno nedostupan")

    conn = None
    try:
        pool = get_connection_pool()
        deadline = time.monotonic() + _POOL_WAIT_TIMEOUT
        while True:
            try:
                conn = pool.getconn()
                break
            except PoolError:
                if time.monotonic() >= deadline:
                    raise PoolError(
                        f"Connection pool iscrpljen â€” konekcija nije dostupna za {_POOL_WAIT_TIMEOUT}s"
                    )
                time.sleep(0.1)

        if conn.closed:
            pool.putconn(conn, close=True)
            conn = pool.getconn()

        yield conn
        conn.commit()
        _reset_circuit()  # uspjeÅ¡na konekcija â€” zatvori circuit

    except (psycopg2.OperationalError, psycopg2.DatabaseError) as e:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        if "timeout" in str(e).lower() or "connect" in str(e).lower():
            _trip_circuit()  # otvori circuit na _CB_COOLDOWN sekundi
        raise
    except Exception:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        raise
    finally:
        if conn:
            try:
                get_connection_pool().putconn(conn)
            except Exception:
                pass


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
    GeneriÅ¡e listu fallback kodova od najpreciznijeg ka opÅ¡tijem.
    """
    codes = []
    code = normalize_tarifni_kod(tarifni_kod)

    while len(code) >= 6:
        codes.append(code)
        code = code[:-1]

    # osiguraj da 8-cifreni + 000 uvijek bude ukljuÄen
    if len(tarifni_kod) >= 8:
        base = tarifni_kod[:8] + "000"
        if base not in codes:
            codes.append(base)

    return list(dict.fromkeys(codes))  # bez duplikata, zadrÅ¾i redoslijed


# =========================================================
# ZVANIÄŒNA TARIFA (ZAKON)
# =========================================================


def get_tarifa_opis(tarifni_kod: str):
    """
    VraÄ‡a zakonski opis tarife iz catalogs.zvanicna_tarifa.

    Ako taÄan tarifni kod ne postoji, koristi fallback (viÅ¡i nivo tarife).
    Sve kandidate traÅ¾i u jednom upitu, sortira po specifiÄnosti (duÅ¾i kod = specifiÄniji).
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
    Pretraga zvaniÄne tarife po opisu (ILIKE).
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
# TARIFA â†” NAZIV ROBE (PRAKSA) â€” C2
# =========================================================


def get_nazivi_robe_za_tarifu(tarifni_kod: str, limit: int = 10):
    """
    VraÄ‡a nazive robe za tarifni kod (iz prakse).
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
    VraÄ‡a partnera po JIB-u iz zajedniÄke tabele.
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
    Pretraga partnera po nazivu iz zajedniÄke tabele.
    """
    q = (query or "").strip()
    if not q:
        # Ako je query prazan, uÄitaj sve partnere
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
    VraÄ‡a trgovca po Å¡ifri i opcionalno tipu.
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
        # Ako je query prazan, uÄitaj sve trgovce (ili sve odreÄ‘enog tipa)
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
        # Ako postoji query, pretraÅ¾i po nazivu
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
    VraÄ‡a izvoznika po JIB-u.
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
    VraÄ‡a uvoznika po JIB-u.
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

