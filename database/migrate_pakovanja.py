#!/usr/bin/env python3
"""Migracija Å¡ifara pakovanja iz SQLite u PostgreSQL."""

import sqlite3
import psycopg2

def _pg_config():
    from config.settings import get_db_settings
    s = get_db_settings()
    return {"host": s.host, "port": s.port, "dbname": s.database,
            "user": s.user, "password": s.password}

# SQLite path
SQLITE_DB = "/home/radovan/Desktop/PythonProjects/deklarant_pro/database/deklarant_sistem.db"


def migrate_pakovanja():
    """Migriraj Å¡ifre pakovanja iz SQLite u PostgreSQL."""

    print("=" * 70)
    print("MIGRACIJA Å IFARA PAKOVANJA")
    print("=" * 70)

    # 1. Konektuj se na obe baze
    print("\n1ï¸âƒ£  Konektujem na baze podataka...")
    sqlite_conn = sqlite3.connect(SQLITE_DB)
    pg_conn = psycopg2.connect(**_pg_config())
    pg_cursor = pg_conn.cursor()

    # 2. Kreiraj tabelu u PostgreSQL ako ne postoji
    print("2ï¸âƒ£  Kreiram tabelu catalogs.pakovanja...")
    pg_cursor.execute("""
        CREATE TABLE IF NOT EXISTS catalogs.pakovanja (
            sifra VARCHAR(10) PRIMARY KEY,
            opis TEXT NOT NULL
        )
    """)
    pg_conn.commit()
    print("   âœ… Tabela kreirana")

    # 3. Provjeri da li tabela veÄ‡ ima podatke
    pg_cursor.execute("SELECT COUNT(*) FROM catalogs.pakovanja")
    existing_count = pg_cursor.fetchone()[0]

    if existing_count > 0:
        print(f"\nâš ï¸  Tabela veÄ‡ ima {existing_count} redova!")
        response = input("   Da li da obriÅ¡em postojeÄ‡e podatke i migriram iznova? (da/ne): ")
        if response.lower() in ['da', 'd', 'yes', 'y']:
            pg_cursor.execute("DELETE FROM catalogs.pakovanja")
            pg_conn.commit()
            print("   âœ… Stari podaci obrisani")
        else:
            print("   âŒ Migracija otkazana")
            sqlite_conn.close()
            pg_conn.close()
            return

    # 4. UÄitaj podatke iz SQLite
    print("\n3ï¸âƒ£  UÄitavam podatke iz SQLite...")
    sqlite_cursor = sqlite_conn.cursor()
    sqlite_cursor.execute("SELECT kod, opis FROM pakovanja ORDER BY kod")
    pakovanja = sqlite_cursor.fetchall()
    print(f"   âœ… UÄitano {len(pakovanja)} Å¡ifara pakovanja")

    # 5. Migracija u PostgreSQL
    print("\n4ï¸âƒ£  Migriram podatke u PostgreSQL...")

    migrated = 0
    errors = 0

    for kod, opis in pakovanja:
        try:
            pg_cursor.execute("""
                INSERT INTO catalogs.pakovanja (sifra, opis)
                VALUES (%s, %s)
                ON CONFLICT (sifra) DO UPDATE SET opis = EXCLUDED.opis
            """, (kod, opis))
            migrated += 1

            # Progress bar
            if migrated % 50 == 0:
                print(f"   ðŸ“¦ {migrated}/{len(pakovanja)} migrirano...")

        except Exception as e:
            errors += 1
            print(f"   âš ï¸  GreÅ¡ka kod Å¡ifre {kod}: {e}")

    pg_conn.commit()

    # 6. Verifikacija
    print("\n5ï¸âƒ£  Verifikacija...")
    pg_cursor.execute("SELECT COUNT(*) FROM catalogs.pakovanja")
    final_count = pg_cursor.fetchone()[0]

    print(f"\n   âœ… Migrirano: {migrated} redova")
    print(f"   âŒ GreÅ¡ke: {errors}")
    print(f"   ðŸ“Š Ukupno u PostgreSQL: {final_count} redova")

    # 7. PrikaÅ¾i primjer podataka
    print("\n6ï¸âƒ£  Primjer migriranih podataka:")
    pg_cursor.execute("SELECT sifra, opis FROM catalogs.pakovanja LIMIT 5")
    samples = pg_cursor.fetchall()
    for sifra, opis in samples:
        print(f"   â€¢ {sifra:5s} â†’ {opis}")

    # Zatvori konekcije
    sqlite_conn.close()
    pg_conn.close()

    print("\n" + "=" * 70)
    print("âœ… MIGRACIJA ZAVRÅ ENA!")
    print("=" * 70)


if __name__ == "__main__":
    try:
        migrate_pakovanja()
    except Exception as e:
        print(f"\nâŒ FATALNA GREÅ KA: {e}")
        import traceback
        traceback.print_exc()

