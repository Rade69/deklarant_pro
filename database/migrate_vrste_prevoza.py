"""
database/migrate_vrste_prevoza.py

Ažuriranje naziva vrsta prevoza u catalogs.vrste_prijevoza:
- Zamjena hrvatskih naziva srpskim (prijevoz → prevoz, Zračni → Vazdušni, itd.)
- Dodavanje šifre 31 (prikolica)
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import get_db_connection

UPDATES = [
    ("10", "Prevoz morem"),
    ("20", "Prevoz željeznicom"),
    ("30", "Drumski prevoz"),
    ("40", "Vazdušni prevoz"),
    ("50", "Poštanska pošiljka (način prevoza nepoznat)"),
    ("70", "Prevoz fiksnim instalacijama"),
    ("80", "Prevoz unutrašnjim riječnim putem"),
    ("90", "Nepoznata vrsta prevoza (vlastiti pogon)"),
]

INSERT_31 = ("31", "Drumski prevoz — prikolica")


def migrate():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for sifra, opis in UPDATES:
                cur.execute(
                    "UPDATE catalogs.vrste_prijevoza SET opis = %s WHERE sifra = %s",
                    (opis, sifra)
                )
                print(f"  ✅ {sifra}: {opis}")

            # Dodaj šifru 31 ako ne postoji
            cur.execute(
                "INSERT INTO catalogs.vrste_prijevoza (sifra, opis) VALUES (%s, %s) "
                "ON CONFLICT (sifra) DO UPDATE SET opis = EXCLUDED.opis",
                INSERT_31
            )
            print(f"  ✅ {INSERT_31[0]}: {INSERT_31[1]}")

        conn.commit()
    print("\n✅ Migracija vrste prevoza završena.")


if __name__ == "__main__":
    migrate()
