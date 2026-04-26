#!/usr/bin/env python3
"""
Migracija carinskih postupaka iz JSON fajla u PostgreSQL bazu.
"""

import json
import os
import psycopg2
from psycopg2.extras import RealDictCursor

def _pg_config():
    from config.settings import get_db_settings
    s = get_db_settings()
    return {"host": s.host, "port": s.port, "dbname": s.database,
            "user": s.user, "password": s.password}

# Putanja do JSON fajla
JSON_FILE = os.path.join(os.path.dirname(__file__), "carinski_postupci.json")


def create_table(cursor):
    """Kreira tabelu catalogs.carinski_postupci ako ne postoji."""
    
    # Kreiraj shemu ako ne postoji
    cursor.execute("CREATE SCHEMA IF NOT EXISTS catalogs;")
    
    # Kreiraj tabelu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS catalogs.carinski_postupci (
            id SERIAL PRIMARY KEY,
            sifra VARCHAR(10) NOT NULL,
            vrsta VARCHAR(5) NOT NULL,
            oznaka VARCHAR(5) NOT NULL,
            opis TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(sifra)
        );
    """)
    
    # Kreiraj indekse
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_carinski_postupci_sifra 
        ON catalogs.carinski_postupci (sifra);
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_carinski_postupci_vrsta 
        ON catalogs.carinski_postupci (vrsta);
    """)
    
    print("âœ… Tabela catalogs.carinski_postupci kreirana")


def migrate_data(cursor, conn):
    """Migrira podatke iz JSON fajla."""
    
    # Proveri da li fajl postoji
    if not os.path.exists(JSON_FILE):
        print(f"âŒ GreÅ¡ka: Fajl {JSON_FILE} ne postoji!")
        return
    
    # UÄitaj JSON podatke
    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        postupci = json.load(f)
    
    print(f"ðŸ“Š UÄitano {len(postupci)} carinskih postupaka iz JSON fajla")
    
    # Proveri koliko veÄ‡ ima podataka u bazi
    cursor.execute("SELECT COUNT(*) FROM catalogs.carinski_postupci")
    result = cursor.fetchone()
    existing_count = result['count'] if result else 0
    
    if existing_count > 0:
        print(f"âš ï¸  Tabela veÄ‡ ima {existing_count} redova!")
        response = input("   Da li da obriÅ¡em postojeÄ‡e podatke i migriram iznova? (da/ne): ")
        if response.lower() in ['da', 'd', 'yes', 'y']:
            cursor.execute("DELETE FROM catalogs.carinski_postupci")
            conn.commit()
            print("   âœ… Stari podaci obrisani")
        else:
            print("   âŒ Migracija otkazana")
            return
    
    # Migracija podataka
    migrated = 0
    errors = 0
    
    for postupak in postupci:
        try:
            cursor.execute("""
                INSERT INTO catalogs.carinski_postupci (sifra, vrsta, oznaka, opis)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (sifra) DO UPDATE SET
                    vrsta = EXCLUDED.vrsta,
                    oznaka = EXCLUDED.oznaka,
                    opis = EXCLUDED.opis
            """, (
                postupak.get('sifra', ''),
                postupak.get('vrsta', ''),
                postupak.get('oznaka', ''),
                postupak.get('opis', '')
            ))
            migrated += 1
            
            # Progress
            if migrated % 50 == 0:
                print(f"   ðŸ“¦ {migrated}/{len(postupci)} migrirano...")
                
        except Exception as e:
            errors += 1
            print(f"   âš ï¸  GreÅ¡ka kod Å¡ifre {postupak.get('sifra', 'NEPoznato')}: {e}")
    
    conn.commit()
    return migrated, errors


def verify_data(cursor):
    """Verifikuje migrirane podatke."""
    
    # Ukupno redova
    cursor.execute("SELECT COUNT(*) FROM catalogs.carinski_postupci")
    result = cursor.fetchone()
    total = result['count'] if result else 0
    
    # Broj po vrsti
    cursor.execute("""
        SELECT vrsta, COUNT(*) as broj 
        FROM catalogs.carinski_postupci 
        GROUP BY vrsta
    """)
    by_type = cursor.fetchall()
    
    # Prvi primerci
    cursor.execute("SELECT sifra, vrsta, oznaka, opis FROM catalogs.carinski_postupci LIMIT 5")
    samples = cursor.fetchall()
    
    print("\n" + "=" * 50)
    print("ðŸ“‹ VERIFIKACIJA PODATAKA")
    print("=" * 50)
    print(f"   âœ… Ukupno redova: {total}")
    print("\n   Po vrsti (EX/IM):")
    for row in by_type:
        print(f"      â€¢ {row['vrsta']}: {row['broj']}")
    
    print("\n   Primerci (prvih 5):")
    for row in samples:
        print(f"      â€¢ {row['sifra']} ({row['vrsta']}) - {row['opis'][:50]}...")


def main():
    """Glavna funkcija."""
    
    print("=" * 60)
    print("MIGRACIJA CARINSKIH POSTUPAKA")
    print("=" * 60)
    
    try:
        # Konekcija na bazu
        print("\n1ï¸âƒ£  Povezujem na PostgreSQL bazu...")
        conn = psycopg2.connect(**_pg_config())
        conn.autocommit = False
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        print("   âœ… Povezano!")
        
        # Kreiraj tabelu
        print("\n2ï¸âƒ£  Kreiram tabelu...")
        create_table(cursor)
        conn.commit()
        
        # Migriraj podatke
        print("\n3ï¸âƒ£  Migriram podatke...")
        migrated, errors = migrate_data(cursor, conn)
        
        # Verifikuj
        print("\n4ï¸âƒ£  Verifikujem podatke...")
        verify_data(cursor)
        
        # Zatvori konekciju
        cursor.close()
        conn.close()
        
        print("\n" + "=" * 60)
        print("âœ… MIGRACIJA ZAVRÅ ENA USPEÅ NO!")
        print(f"   Migrirano: {migrated}")
        print(f"   GreÅ¡ke: {errors}")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nâŒ GREÅ KA: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

