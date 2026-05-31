"""
Centralni cache zemalja — puni se jednom iz DB, fallback na hardkodirani spisak.
Ne blokira GUI pri nedostupnom DB serveru.
"""

import logging
from typing import List, Tuple, Optional

logger = logging.getLogger("deklarant_pro.countries_cache")

# (sifra, naziv)
_cache: Optional[List[Tuple[str, str]]] = None
_db_failed: bool = False

# Najčešće korišćene zemlje — fallback kad DB nije dostupan
_FALLBACK = [
    ("AL", "Albanija"), ("AT", "Austrija"), ("BA", "Bosna i Hercegovina"),
    ("BE", "Belgija"), ("BG", "Bugarska"), ("CH", "Švajcarska"),
    ("CN", "Kina"), ("CZ", "Češka"), ("DE", "Njemačka"),
    ("DK", "Danska"), ("EG", "Egipat"), ("ES", "Španija"),
    ("FR", "Francuska"), ("GB", "Velika Britanija"), ("GR", "Grčka"),
    ("HR", "Hrvatska"), ("HU", "Mađarska"), ("IN", "Indija"),
    ("IT", "Italija"), ("JP", "Japan"), ("KR", "Južna Koreja"),
    ("ME", "Crna Gora"), ("MK", "Sjeverna Makedonija"), ("NL", "Holandija"),
    ("PL", "Poljska"), ("PT", "Portugal"), ("RO", "Rumunija"),
    ("RS", "Srbija"), ("SE", "Švedska"), ("SI", "Slovenija"),
    ("SK", "Slovačka"), ("TR", "Turska"), ("UA", "Ukrajina"),
    ("US", "Sjedinjene Države"), ("XK", "Kosovo"),
]


def get_countries() -> List[Tuple[str, str]]:
    """Vrati listu (sifra, naziv) — iz DB ili fallback."""
    global _cache, _db_failed

    if _cache is not None:
        return _cache

    if _db_failed:
        return _FALLBACK

    try:
        from database.db import get_db_connection
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT sifra, naziv FROM catalogs.drzave "
                    "WHERE sifra IS NOT NULL ORDER BY naziv"
                )
                rows = cur.fetchall()
                _cache = [(r['sifra'], r['naziv']) for r in rows if r['sifra']]
                logger.debug(f"Countries cache: {len(_cache)} zemalja učitano iz DB")
                return _cache
    except Exception as e:
        logger.warning(f"DB nedostupan za učitavanje zemalja, koristim fallback: {e}")
        _db_failed = True
        return _FALLBACK


def reset_cache() -> None:
    """Resetuj cache — koristi se pri promjeni DB konekcije."""
    global _cache, _db_failed
    _cache = None
    _db_failed = False
