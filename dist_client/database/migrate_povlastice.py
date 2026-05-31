# database/migrate_povlastice.py

"""
Migracija šifara povlastica u PostgreSQL bazu.

Kreira tabelu catalogs.povlastice i puni je svim važećim šiframa povlastica.
"""

import psycopg2
import psycopg2.extras
from database.db import POSTGRES_CONFIG


# Šifrarnik 12 — Polje 36: Povlastice BiH (zvanični ASYCUDA kodovi)
POVLASTICE = [
    # CEFTA
    ('CEFTAP', 'CEFTA 2006', 'CEFTA'),
    ('CEFTAR', 'CEFTA 2006 - Revidirana PEM pravila', 'CEFTA'),

    # EFTA — Švajcarska i Lihtenštajn (CH, LI)
    ('EFTA1',  'Švajcarska i Lihtenštajn', 'EFTA'),
    ('EFTA1R', 'Švajcarska i Lihtenštajn - Revidirana PEM pravila', 'EFTA'),

    # EFTA — Island (IS)
    ('EFTA2',  'Island', 'EFTA'),
    ('EFTA2R', 'Island - Revidirana PEM pravila', 'EFTA'),

    # EFTA — Norveška (NO)
    ('EFTA3',  'Norveška', 'EFTA'),
    ('EFTA3R', 'Norveška - Revidirana PEM pravila', 'EFTA'),

    # EU
    ('EUP',  'EU porijeklo', 'EU'),
    ('EUPR', 'EU porijeklo - Revidirana PEM pravila', 'EU'),

    # Turska
    ('TRP',  'Turska', 'TURSKA'),
    ('TRPR', 'Turska - Revidirana PEM pravila', 'TURSKA'),

    # Iran
    ('IRP', 'Iran', 'IRAN'),
]


def create_povlastice_table():
    """Kreiraj tabelu za povlastice ako ne postoji."""
    
    create_sql = """
        CREATE TABLE IF NOT EXISTS catalogs.povlastice (
            sifra TEXT PRIMARY KEY,
            opis TEXT NOT NULL,
            grupa TEXT NOT NULL,
            aktivan BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_povlastice_grupa 
        ON catalogs.povlastice(grupa);
        
        CREATE INDEX IF NOT EXISTS idx_povlastice_aktivan 
        ON catalogs.povlastice(aktivan) WHERE aktivan = TRUE;
        
        COMMENT ON TABLE catalogs.povlastice IS 
        'Šifre povlastica za preferencijalno poreklo robe';
        
        COMMENT ON COLUMN catalogs.povlastice.sifra IS 
        'Šifra povlastice (npr. CEFTAP, EUP, EUR1)';
        
        COMMENT ON COLUMN catalogs.povlastice.grupa IS 
        'Grupa povlastice: CEFTA, EU, EURO_MED, TURSKA, GSP, POSEBNO, NONE';
    """
    
    with psycopg2.connect(**POSTGRES_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(create_sql)
            conn.commit()
            print("✅ Tabela catalogs.povlastice kreirana")


def insert_povlastice():
    """Unesi povlastice u bazu."""
    
    insert_sql = """
        INSERT INTO catalogs.povlastice (sifra, opis, grupa)
        VALUES (%s, %s, %s)
        ON CONFLICT (sifra) DO UPDATE SET
            opis = EXCLUDED.opis,
            grupa = EXCLUDED.grupa,
            updated_at = CURRENT_TIMESTAMP
    """
    
    with psycopg2.connect(**POSTGRES_CONFIG) as conn:
        with conn.cursor() as cur:
            for sifra, opis, grupa in POVLASTICE:
                cur.execute(insert_sql, (sifra, opis, grupa))
            conn.commit()
            print(f"✅ Uneseno {len(POVLASTICE)} povlastica u bazu")


def show_povlastice():
    """Prikaži sve povlastice iz baze."""
    
    with psycopg2.connect(**POSTGRES_CONFIG) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT sifra, opis, grupa
                FROM catalogs.povlastice
                WHERE aktivan = TRUE
                ORDER BY grupa, sifra
            """)
            
            print("\n=== ŠIFRE POVLASTICA ===")
            current_grupa = None
            
            for row in cur.fetchall():
                if row['grupa'] != current_grupa:
                    current_grupa = row['grupa']
                    print(f"\n[{current_grupa}]")
                
                print(f"  {row['sifra']:10} - {row['opis'][:60]}")


def main():
    """Glavna funkcija za migraciju."""
    
    print("=" * 70)
    print("MIGRACIJA ŠIFARA POVLASTICA U POSTGRESQL")
    print("=" * 70)
    
    # 1. Kreiraj tabelu
    print("\\n1️⃣  Kreiranje tabele...")
    create_povlastice_table()
    
    # 2. Unesi povlastice
    print("\\n2️⃣  Unos povlastica...")
    insert_povlastice()
    
    # 3. Prikaži povlastice
    print("\\n3️⃣  Pregled unetih povlastica...")
    show_povlastice()
    
    print("\\n" + "=" * 70)
    print("✅ MIGRACIJA ZAVRŠENA")
    print("=" * 70)


if __name__ == "__main__":
    main()
