"""
Servis za pretragu carinskih dokumenata iz PostgreSQL baze.
Koristi tsvector full-text search sa ts_headline za snippete.
"""

from typing import List, Dict


_MAX_RESULTS = 3


def dokumenti_indeksirani() -> bool:
    """Provjeri da li postoje indeksirani dokumenti."""
    try:
        from database.db import get_db_connection
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS cnt FROM catalogs.carinski_dokumenti")
                return cur.fetchone()['cnt'] > 0
    except Exception:
        return False


def pretrazi_dokumente(query: str, max_results: int = _MAX_RESULTS) -> List[Dict]:
    """
    Pretraži carinske dokumente po ključnoj riječi.

    Koristi PostgreSQL to_tsquery sa 'simple' rječnikom (radi za bosanski/srpski).
    ts_headline vraća odlomak sa označenim ključnim riječima.

    Returns:
        Lista diktova sa: naziv, filename, odlomak
    """
    if not query or not query.strip():
        return []

    try:
        from database.db import get_db_connection

        # Pretvori query u tsquery format — svaka riječ prefiks-matchuje
        words = query.strip().split()
        ts_query = ' & '.join(w + ':*' for w in words if w)

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        naziv,
                        filename,
                        ts_headline(
                            'simple', sadrzaj,
                            to_tsquery('simple', %s),
                            'MaxWords=50, MinWords=20, ShortWord=2,
                             HighlightAll=false, MaxFragments=2,
                             FragmentDelimiter='' ... '''
                        ) AS odlomak,
                        ts_rank(fts_vektor, to_tsquery('simple', %s)) AS rank
                    FROM catalogs.carinski_dokumenti
                    WHERE fts_vektor @@ to_tsquery('simple', %s)
                    ORDER BY rank DESC
                    LIMIT %s
                """, (ts_query, ts_query, ts_query, max_results))

                rows = cur.fetchall()

        return [
            {
                "naziv": r['naziv'],
                "filename": r['filename'],
                "odlomak": r['odlomak'],
            }
            for r in rows
        ]

    except Exception as e:
        print(f"⚠️ Greška pri pretrazi carinskih dokumenata: {e}")
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
    return formatiraj_za_agenta(pretrazi_dokumente(query))
