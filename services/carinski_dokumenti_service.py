"""
Servis za pretragu carinskih dokumenata iz SQLite FTS5 baze.
"""

import os
import sqlite3
from typing import List, Dict

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "database", "deklarant_sistem.db")

# Maksimalan broj znakova po odlomku koji se vraća agentu
_SNIPPET_LEN = 400
# Broj rezultata koje vraćamo agentu
_MAX_RESULTS = 3


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def dokumenti_indeksirani() -> bool:
    """Provjeri da li postoje indeksirani dokumenti."""
    try:
        conn = _get_conn()
        count = conn.execute("SELECT COUNT(*) FROM carinski_dokumenti").fetchone()[0]
        conn.close()
        return count > 0
    except Exception:
        return False


def pretrazi_dokumente(query: str, max_results: int = _MAX_RESULTS) -> List[Dict]:
    """
    Pretraži carinske dokumente po ključnoj riječi/frazi.

    Returns:
        Lista diktova sa: naziv, filename, odlomak, score
    """
    if not query or not query.strip():
        return []

    try:
        conn = _get_conn()

        # FTS5 pretraga sa snippet funkcijom
        rows = conn.execute("""
            SELECT
                cd.naziv,
                cd.filename,
                snippet(carinski_dokumenti_fts, 1, '**', '**', '...', 30) AS odlomak,
                rank
            FROM carinski_dokumenti_fts
            JOIN carinski_dokumenti cd ON cd.id = carinski_dokumenti_fts.rowid
            WHERE carinski_dokumenti_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (query, max_results)).fetchall()

        conn.close()

        return [
            {
                "naziv": row["naziv"],
                "filename": row["filename"],
                "odlomak": row["odlomak"],
            }
            for row in rows
        ]

    except Exception as e:
        print(f"⚠️ Greška pri pretrazi dokumenata: {e}")
        return []


def formatiraj_za_agenta(rezultati: List[Dict]) -> str:
    """Formatiraj rezultate pretrage za uključivanje u agent kontekst."""
    if not rezultati:
        return ""

    linije = ["📋 RELEVANTNI CARINSKI PROPISI:"]
    for r in rezultati:
        linije.append(f"\n— {r['naziv']}")
        linije.append(f"  {r['odlomak']}")

    return "\n".join(linije)


def pretrazi_i_formatiraj(query: str) -> str:
    """Pretraži i odmah vrati formatiran string za agenta."""
    rezultati = pretrazi_dokumente(query)
    return formatiraj_za_agenta(rezultati)
