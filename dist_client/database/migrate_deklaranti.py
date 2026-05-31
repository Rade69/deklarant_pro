"""
Kreiranje catalogs.deklaranti tabele

Deklaranti (carinski zastupnici) — entiteti koji podnose carinske deklaracije.
Ista struktura kao izvoznici/uvoznici.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import get_db_connection


def create_deklaranti_table():
    """Kreira deklaranti tabelu ako ne postoji."""
    with get_db_connection() as conn:
        cur = conn.cursor()

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
            );
        """)
        cur.execute("""
            ALTER TABLE catalogs.deklaranti
            ADD COLUMN IF NOT EXISTS postanski_broj TEXT DEFAULT ''
        """)
        conn.commit()
        print("✅ catalogs.deklaranti tabela kreirana (ili već postoji)")


def seed_deklaranti():
    """Unosi par primjera deklaranta ako su prazni."""
    with get_db_connection() as conn:
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM catalogs.deklaranti")
        count = cur.fetchone()
        count_val = count["count"] if isinstance(count, dict) else count[0]

        if count_val == 0:
            primjeri = [
                ("1234567890123", "Carinski zastupnik DOO", "Ulica bb", "Sarajevo", "71000", "BA", "033/123-456", "info@cz.ba", "Marko Marković", "4987654321098", "MZ-001"),
                ("9876543210987", "Logistics Partners", "Put 1", "Banja Luka", "78000", "BA", "051/987-654", "office@lp.ba", "Ana Anić", "4123456789012", "MZ-002"),
            ]
            for jib, naziv, adresa, grad, postanski_broj, drzava, telefon, email, kontakt, pdv, maticni in primjeri:
                cur.execute("""
                    INSERT INTO catalogs.deklaranti
                    (jib, naziv, adresa, grad, postanski_broj, drzava, telefon, email, kontakt, pdv_broj, maticni)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (jib) DO NOTHING
                """, (jib, naziv, adresa, grad, postanski_broj, drzava, telefon, email, kontakt, pdv, maticni))
            conn.commit()
            print(f"✅ Uneseno {len(primjeri)} primjera deklaranta")
        else:
            print(f"ℹ️ Deklaranti već imaju {count_val} zapisa — preskačam seed")


if __name__ == "__main__":
    create_deklaranti_table()
    seed_deklaranti()
