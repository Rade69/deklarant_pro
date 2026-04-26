# services/tarifa_service.py

"""
TarifaService â€” pretraga carinske tarife 2026 iz SQLite baze.

Metode:
  pretrazi(upit)         â€” FTS pretraga po nazivu robe
  trazi_po_kodu(kod)     â€” exacta/prefix pretraga po tarifnoj oznaci
  opis_poglavlja(br)     â€” naziv poglavlja (npr. "33" â†’ "Ulja...")
"""

import sqlite3
import re
import os
import logging
from functools import lru_cache
from typing import List, Dict, Optional

logger = logging.getLogger("deklarant_pro.tarifa_service")


def _resolve_db_path() -> str:
    """
    PronaÄ‘i deklarant_sistem.db: probaj viÅ¡e lokacija jer compiled .pyd
    moÅ¾e imati __file__ koji pokazuje na dist_client/services/*.pyd, pa
    relativna putanja vodi u dist_client/database/ umjesto database/.
    """
    candidates = [
        # Standardna lokacija: 2 nivoa gore od services/tariff/
        os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', 'database', 'deklarant_sistem.db')),
        # Compiled .pyd lokacija: 1 nivo gore od services/
        os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'database', 'deklarant_sistem.db')),
        # Relativno od CWD
        os.path.join('database', 'deklarant_sistem.db'),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    # Fallback â€” prva kandidat putanja (sqlite3.connect je lax sa create)
    return candidates[0]


DB_PATH = _resolve_db_path()

# Jedna dijeljenja read-only konekcija â€” tarifa_2026 se nikad ne mijenja za vrijeme rada
_shared_conn: sqlite3.Connection | None = None


def _get_conn() -> sqlite3.Connection:
    global _shared_conn
    if _shared_conn is None:
        _shared_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _shared_conn.row_factory = sqlite3.Row
    return _shared_conn


def _row_to_dict(row) -> Dict:
    return {
        'kod': row['kod'],
        'poglavlje': row['poglavlje'],
        'naziv': row['naziv'],
        'dopunska_jm': row['dopunska_jm'],
        'stopa_uvozna': row['stopa_uvozna'],
        'stopa_eu': row['stopa_eu'],
        'stopa_cefta': row['stopa_cefta'],
        'nivo': row['nivo'],
    }


def _stem_word(word: str) -> str:
    """
    Minimalni stemmer za bosanski/srpski â€” uzima korijen rijeÄi
    uklanjajuÄ‡i Äeste nastavke kako bi LIKE pretraga radila bolje.
    Npr: "kozmetika" â†’ "kozmet", "lijekovi" â†’ "lijek", "krema" â†’ "krem"
    """
    word = word.lower()
    suffixes = [
        'iÄkih', 'iÄke', 'iÄko', 'iÄki', 'iÄka',
        'skih', 'ske', 'sko', 'ski', 'ska',
        'nih', 'nog', 'nom', 'nih', 'nim',
        'ima', 'ama', 'ovi', 'evi', 'ova', 'eva',
        'ika', 'ike', 'ici', 'iku',
        'ama', 'ima', 'om', 'em',
        'ih', 'im', 'og', 'om',
        'ni', 'na', 'ne', 'no',
        'ki', 'ka', 'ke', 'ko',
        'vi', 'va', 've', 'vo',
        'li', 'la', 'le', 'lo',
        'i', 'a', 'e', 'u',
    ]
    for suffix in suffixes:
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[:-len(suffix)]
    return word


def pretrazi(upit: str, limit: int = 10, samo_podbroj: bool = False) -> List[Dict]:
    """
    Pretraga tarife po opisu robe.
    Koristi AND-LIKE pretragu po svakoj rijeÄi (bolje za bosanski/srpski jezik).

    Args:
        upit: Tekst za pretragu (npr. "medicinski gel", "kozmetika krema")
        limit: Maks broj rezultata
        samo_podbroj: Ako True, vraÄ‡a samo pune tarifne oznake (10 cifara)

    Returns:
        Lista dict sa: kod, poglavlje, naziv, stopa_uvozna, stopa_eu, stopa_cefta, nivo
    """
    if not upit or not upit.strip():
        return []

    words = [_stem_word(w) for w in upit.strip().split() if len(w) >= 3]
    if not words:
        return []

    try:
        conn = _get_conn()
        nivo_filter = "AND nivo = 'podbroj'" if samo_podbroj else ""

        order_by = f"""
            ORDER BY
                CASE nivo
                    WHEN 'podbroj' THEN 1
                    WHEN 'tarifni_broj' THEN 2
                    WHEN 'podglava' THEN 3
                    ELSE 4
                END,
                LENGTH(naziv)
            LIMIT ?
        """

        # AND pretraga â€” sve rijeÄi moraju biti u nazivu
        where_and = " AND ".join(["naziv LIKE ?" for _ in words])
        rows = conn.execute(
            f"SELECT kod,poglavlje,naziv,dopunska_jm,stopa_uvozna,stopa_eu,stopa_cefta,nivo "
            f"FROM tarifa_2026 WHERE {where_and} {nivo_filter} {order_by}",
            [f"%{w}%" for w in words] + [limit]
        ).fetchall()

        # Ako nema AND rezultata, OR pretraga po svakoj rijeÄi zasebno
        if not rows:
            seen = set()
            or_rows = []
            for w in words:
                partial = conn.execute(
                    f"SELECT kod,poglavlje,naziv,dopunska_jm,stopa_uvozna,stopa_eu,stopa_cefta,nivo "
                    f"FROM tarifa_2026 WHERE naziv LIKE ? {nivo_filter} {order_by}",
                    (f"%{w}%", limit)
                ).fetchall()
                for r in partial:
                    if r['kod'] not in seen:
                        seen.add(r['kod'])
                        or_rows.append(r)
            rows = or_rows[:limit]

        return [_row_to_dict(r) for r in rows]

    except Exception as e:
        logger.error(f"GreÅ¡ka pri pretrazi tarife: {e}")
        return _pretrazi_like(upit, limit, samo_podbroj)


def _pretrazi_like(upit: str, limit: int = 10, samo_podbroj: bool = False) -> List[Dict]:
    """Fallback LIKE pretraga ako FTS ne radi."""
    try:
        conn = _get_conn()
        nivo_filter = "AND nivo = 'podbroj'" if samo_podbroj else ""
        pattern = f"%{upit.strip()}%"
        rows = conn.execute(f"""
            SELECT kod, poglavlje, naziv, dopunska_jm,
                   stopa_uvozna, stopa_eu, stopa_cefta, nivo
            FROM tarifa_2026
            WHERE naziv LIKE ? {nivo_filter}
            LIMIT ?
        """, (pattern, limit)).fetchall()
        return [_row_to_dict(r) for r in rows]
    except Exception as e:
        logger.error(f"LIKE pretraga nije uspjela: {e}")
        return []


@lru_cache(maxsize=512)
def trazi_po_kodu(kod: str) -> Optional[Dict]:
    """
    PronaÄ‘i tarifnu oznaku po kodu (exact ili prefix).

    Args:
        kod: Tarifna oznaka (npr. "3304990000" ili "330499")

    Returns:
        Dict sa podacima ili None ako nije pronaÄ‘eno
    """
    kod_clean = re.sub(r'\s+', '', kod.strip())
    if not kod_clean or not re.match(r'^\d{4,12}$', kod_clean):
        return None

    try:
        conn = _get_conn()

        # Exact match
        row = conn.execute(
            "SELECT * FROM tarifa_2026 WHERE kod = ?", (kod_clean,)
        ).fetchone()

        if not row and len(kod_clean) < 10:
            # Prefix match â€” uzmi najduÅ¾i koji poÄinje sa tim kodom
            row = conn.execute("""
                SELECT * FROM tarifa_2026
                WHERE kod LIKE ?
                ORDER BY LENGTH(kod) DESC
                LIMIT 1
            """, (kod_clean + '%',)).fetchone()

        return _row_to_dict(row) if row else None

    except Exception as e:
        # Re-raise umjesto return None â€” lru_cache ne keÅ¡iruje exception,
        # pa sljedeÄ‡i poziv ponovo proba (bitno kad DB nije bila dostupna)
        logger.debug(f"GreÅ¡ka pri pretrazi koda {kod}: {e}")
        raise


def trazi_poglavlje(poglavlje: str, limit: int = 50) -> List[Dict]:
    """
    Vrati sve stavke jednog poglavlja.

    Args:
        poglavlje: Broj poglavlja kao string (npr. "33", "01")
    """
    poglavlje = poglavlje.strip().zfill(2)
    try:
        conn = _get_conn()
        rows = conn.execute("""
            SELECT kod, poglavlje, naziv, dopunska_jm,
                   stopa_uvozna, stopa_eu, stopa_cefta, nivo
            FROM tarifa_2026
            WHERE poglavlje = ?
            ORDER BY kod
            LIMIT ?
        """, (poglavlje, limit)).fetchall()
        return [_row_to_dict(r) for r in rows]
    except Exception as e:
        logger.error(f"GreÅ¡ka pri pretrazi poglavlja {poglavlje}: {e}")
        return []


def naziv_poglavlja(poglavlje: str) -> str:
    """Vrati naziv poglavlja (nivo='glava', 4-cifreni kod)."""
    poglavlje = poglavlje.strip().zfill(2)
    try:
        conn = _get_conn()
        row = conn.execute("""
            SELECT naziv FROM tarifa_2026
            WHERE poglavlje = ? AND nivo = 'glava' AND LENGTH(kod) = 4
            LIMIT 1
        """, (poglavlje,)).fetchone()
        return row['naziv'] if row else f"Poglavlje {poglavlje}"
    except Exception:
        return f"Poglavlje {poglavlje}"


@lru_cache(maxsize=512)
def validiraj_tarifni_broj(kod: str) -> Dict:
    """
    Provjeri da li tarifna oznaka postoji u tarifi i vrati detalje.

    Returns:
        Dict sa: valid (bool), kod, naziv, stopa_uvozna, poruka
    """
    rezultat = trazi_po_kodu(kod)
    if not rezultat:
        return {
            'valid': False,
            'kod': kod,
            'naziv': '',
            'stopa_uvozna': '',
            'poruka': f"Tarifna oznaka {kod} nije pronaÄ‘ena u tarifi 2026."
        }

    return {
        'valid': True,
        'kod': rezultat['kod'],
        'naziv': rezultat['naziv'],
        'stopa_uvozna': rezultat['stopa_uvozna'],
        'stopa_eu': rezultat['stopa_eu'],
        'stopa_cefta': rezultat['stopa_cefta'],
        'poruka': f"âœ… PronaÄ‘eno: {rezultat['naziv']}"
    }


def formatiraj_rezultate(rows: List[Dict], max_rows: int = 8) -> str:
    """
    Formatira rezultate pretrage za prikaz u chat panelu.
    """
    if not rows:
        return "Nije pronaÄ‘en nijedan rezultat u carinskoj tarifi."

    lines = []
    prikazano = rows[:max_rows]

    for r in prikazano:
        stopa = r['stopa_uvozna'] or 'â€”'
        eu = r['stopa_eu'] or 'â€”'
        # Dodaj % ako je broj
        if stopa and stopa != 'â€”' and not stopa.endswith('%'):
            stopa = stopa + '%'
        if eu and eu != 'â€”' and not eu.endswith('%'):
            eu = eu + '%'

        nivo_oznaka = ''
        if r['nivo'] == 'glava':
            nivo_oznaka = ' ðŸ“‚'
        elif r['nivo'] == 'podglava':
            nivo_oznaka = ' ðŸ“'

        lines.append(
            f"<b>{r['kod']}</b>{nivo_oznaka} â€” {r['naziv']}<br>"
            f"&nbsp;&nbsp;Stopa: <b>{stopa}</b> | EU: {eu}"
            + (f" | JM: {r['dopunska_jm']}" if r['dopunska_jm'] else "")
        )

    result = "<br><br>".join(lines)
    if len(rows) > max_rows:
        result += f"<br><br><i>... i joÅ¡ {len(rows) - max_rows} rezultata. Precizniraj pretragu.</i>"

    return result

