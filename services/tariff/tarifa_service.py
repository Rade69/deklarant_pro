# services/tarifa_service.py

"""
TarifaService — pretraga carinske tarife 2026 iz SQLite baze.

Metode:
  pretrazi(upit)         — FTS pretraga po nazivu robe
  trazi_po_kodu(kod)     — exacta/prefix pretraga po tarifnoj oznaci
  opis_poglavlja(br)     — naziv poglavlja (npr. "33" → "Ulja...")
"""

import sqlite3
import re
import os
import logging
from functools import lru_cache
from typing import List, Dict, Optional

logger = logging.getLogger("deklarant_pro.tarifa_service")

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'database', 'deklarant_sistem.db')

# Jedna dijeljenja read-only konekcija — tarifa_2026 se nikad ne mijenja za vrijeme rada
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
    Minimalni stemmer za bosanski/srpski — uzima korijen riječi
    uklanjajući česte nastavke kako bi LIKE pretraga radila bolje.
    Npr: "kozmetika" → "kozmet", "lijekovi" → "lijek", "krema" → "krem"
    """
    word = word.lower()
    suffixes = [
        'ičkih', 'ičke', 'ičko', 'ički', 'ička',
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
    Koristi AND-LIKE pretragu po svakoj riječi (bolje za bosanski/srpski jezik).

    Args:
        upit: Tekst za pretragu (npr. "medicinski gel", "kozmetika krema")
        limit: Maks broj rezultata
        samo_podbroj: Ako True, vraća samo pune tarifne oznake (10 cifara)

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

        # AND pretraga — sve riječi moraju biti u nazivu
        where_and = " AND ".join(["naziv LIKE ?" for _ in words])
        rows = conn.execute(
            f"SELECT kod,poglavlje,naziv,dopunska_jm,stopa_uvozna,stopa_eu,stopa_cefta,nivo "
            f"FROM tarifa_2026 WHERE {where_and} {nivo_filter} {order_by}",
            [f"%{w}%" for w in words] + [limit]
        ).fetchall()

        # Ako nema AND rezultata, OR pretraga po svakoj riječi zasebno
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
        logger.error(f"Greška pri pretrazi tarife: {e}")
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
    Pronađi tarifnu oznaku po kodu (exact ili prefix).

    Args:
        kod: Tarifna oznaka (npr. "3304990000" ili "330499")

    Returns:
        Dict sa podacima ili None ako nije pronađeno
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
            # Prefix match — uzmi najduži koji počinje sa tim kodom
            row = conn.execute("""
                SELECT * FROM tarifa_2026
                WHERE kod LIKE ?
                ORDER BY LENGTH(kod) DESC
                LIMIT 1
            """, (kod_clean + '%',)).fetchone()

        return _row_to_dict(row) if row else None

    except Exception as e:
        logger.error(f"Greška pri pretrazi koda {kod}: {e}")
        return None


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
        logger.error(f"Greška pri pretrazi poglavlja {poglavlje}: {e}")
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
            'poruka': f"Tarifna oznaka {kod} nije pronađena u tarifi 2026."
        }

    return {
        'valid': True,
        'kod': rezultat['kod'],
        'naziv': rezultat['naziv'],
        'stopa_uvozna': rezultat['stopa_uvozna'],
        'stopa_eu': rezultat['stopa_eu'],
        'stopa_cefta': rezultat['stopa_cefta'],
        'poruka': f"✅ Pronađeno: {rezultat['naziv']}"
    }


def formatiraj_rezultate(rows: List[Dict], max_rows: int = 8) -> str:
    """
    Formatira rezultate pretrage za prikaz u chat panelu.
    """
    if not rows:
        return "Nije pronađen nijedan rezultat u carinskoj tarifi."

    lines = []
    prikazano = rows[:max_rows]

    for r in prikazano:
        stopa = r['stopa_uvozna'] or '—'
        eu = r['stopa_eu'] or '—'
        # Dodaj % ako je broj
        if stopa and stopa != '—' and not stopa.endswith('%'):
            stopa = stopa + '%'
        if eu and eu != '—' and not eu.endswith('%'):
            eu = eu + '%'

        nivo_oznaka = ''
        if r['nivo'] == 'glava':
            nivo_oznaka = ' 📂'
        elif r['nivo'] == 'podglava':
            nivo_oznaka = ' 📁'

        lines.append(
            f"<b>{r['kod']}</b>{nivo_oznaka} — {r['naziv']}<br>"
            f"&nbsp;&nbsp;Stopa: <b>{stopa}</b> | EU: {eu}"
            + (f" | JM: {r['dopunska_jm']}" if r['dopunska_jm'] else "")
        )

    result = "<br><br>".join(lines)
    if len(rows) > max_rows:
        result += f"<br><br><i>... i još {len(rows) - max_rows} rezultata. Precizniraj pretragu.</i>"

    return result
