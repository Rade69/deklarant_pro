"""Pronađi potencijalne duplikate u catalogs.izvoznici po sličnosti naziva/grada.

Pokretanje: python scripts/find_izvoznici_duplikati.py
"""
import sys
import os

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import get_db_connection


def normalize(text: str) -> str:
    if not text:
        return ""
    text = text.upper()
    for ch in [".", ",", "-", "  "]:
        text = text.replace(ch, " ")
    for suffix in [" DOO", " DD", " AD", " D O O"]:
        text = text.replace(suffix, "")
    return " ".join(text.split())


def main():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT jib, naziv, adresa, grad, drzava
                FROM catalogs.izvoznici
                ORDER BY naziv
            """)
            rows = [dict(r) for r in cur.fetchall()]

    print(f"Ukupno izvoznika u bazi: {len(rows)}\n")

    groups = {}
    for row in rows:
        key = normalize(row["naziv"])
        groups.setdefault(key, []).append(row)

    duplicates = {k: v for k, v in groups.items() if len(v) > 1}

    print(f"Grupa sa potencijalnim duplikatima (po normalizovanom nazivu): {len(duplicates)}\n")
    for key, items in duplicates.items():
        print(f"--- Normalizovani naziv: '{key}' ({len(items)} zapisa) ---")
        for it in items:
            print(f"  JIB={it['jib']!r:25} naziv={it['naziv']!r:30} adresa={it['adresa']!r:30} grad={it['grad']!r:20} drzava={it['drzava']!r}")
        print()


if __name__ == "__main__":
    main()
