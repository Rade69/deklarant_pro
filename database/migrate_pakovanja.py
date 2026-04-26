#!/usr/bin/env python3
"""Migracija šifara pakovanja iz SQLite u PostgreSQL."""

import sqlite3
import psycopg2

# PostgreSQL config
PG_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "deklarant_pro",
    "user": "postgres",
    "password": "!sofija#22$jelena%25&"
}

# SQLite path
SQLITE_DB = "/home/radovan/Desktop/PythonProjects/deklarant_pro/database/deklarant_sistem.db"


def migrate_pakovanja():
    """Migriraj šifre pakovanja iz SQLite u PostgreSQL."""

    print("=" * 70)
    print("MIGRACIJA ŠIFARA PAKOVANJA")
    print("=" * 70)

    # 1. Konektuj se na obe baze
    print("\n1️⃣  Konektujem na baze podataka...")
    sqlite_conn = sqlite3.connect(SQLITE_DB)
    pg_conn = psycopg2.connect(**PG_CONFIG)
    pg_cursor = pg_conn.cursor()

    # 2. Kreiraj tabelu u PostgreSQL ako ne postoji
    print("2️⃣  Kreiram tabelu catalogs.pakovanja...")
    pg_cursor.execute("""
        CREATE TABLE IF NOT EXISTS catalogs.pakovanja (
            sifra VARCHAR(10) PRIMARY KEY,
            opis TEXT NOT NULL
        )
    """)
    pg_conn.commit()
    print("   ✅ Tabela kreirana")

    # 3. Provjeri da li tabela već ima podatke
    pg_cursor.execute("SELECT COUNT(*) FROM catalogs.pakovanja")
    existing_count = pg_cursor.fetchone()[0]

    if existing_count > 0:
        print(f"\n⚠️  Tabela već ima {existing_count} redova!")
        response = input("   Da li da obrišem postojeće podatke i migriram iznova? (da/ne): ")
        if response.lower() in ['da', 'd', 'yes', 'y']:
            pg_cursor.execute("DELETE FROM catalogs.pakovanja")
            pg_conn.commit()
            print("   ✅ Stari podaci obrisani")
        else:
            print("   ❌ Migracija otkazana")
            sqlite_conn.close()
            pg_conn.close()
            return

    # 4. Učitaj podatke iz SQLite
    print("\n3️⃣  Učitavam podatke iz SQLite...")
    sqlite_cursor = sqlite_conn.cursor()
    sqlite_cursor.execute("SELECT kod, opis FROM pakovanja ORDER BY kod")
    pakovanja = sqlite_cursor.fetchall()
    print(f"   ✅ Učitano {len(pakovanja)} šifara pakovanja")

    # 5. Migracija u PostgreSQL
    print("\n4️⃣  Migriram podatke u PostgreSQL...")

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
                print(f"   📦 {migrated}/{len(pakovanja)} migrirano...")

        except Exception as e:
            errors += 1
            print(f"   ⚠️  Greška kod šifre {kod}: {e}")

    pg_conn.commit()

    # 6. Verifikacija
    print("\n5️⃣  Verifikacija...")
    pg_cursor.execute("SELECT COUNT(*) FROM catalogs.pakovanja")
    final_count = pg_cursor.fetchone()[0]

    print(f"\n   ✅ Migrirano: {migrated} redova")
    print(f"   ❌ Greške: {errors}")
    print(f"   📊 Ukupno u PostgreSQL: {final_count} redova")

    # 7. Prikaži primjer podataka
    print("\n6️⃣  Primjer migriranih podataka:")
    pg_cursor.execute("SELECT sifra, opis FROM catalogs.pakovanja LIMIT 5")
    samples = pg_cursor.fetchall()
    for sifra, opis in samples:
        print(f"   • {sifra:5s} → {opis}")

    # Zatvori konekcije
    sqlite_conn.close()
    pg_conn.close()

    print("\n" + "=" * 70)
    print("✅ MIGRACIJA ZAVRŠENA!")
    print("=" * 70)


if __name__ == "__main__":
    try:
        migrate_pakovanja()
    except Exception as e:
        print(f"\n❌ FATALNA GREŠKA: {e}")
        import traceback
        traceback.print_exc()
