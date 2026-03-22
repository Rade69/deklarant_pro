# database/migrate_prilozeni_dokumenti_sifre.py

"""
Migracija šifara priloženih dokumenata iz JSON fajla u PostgreSQL bazu.

Kreira tabelu catalogs.prilozeni_dokumenti_sifre sa svim šiframa
za Rub.44 (Priložene isprave).
"""

import json
import psycopg2
import psycopg2.extras
from pathlib import Path
from database.db import POSTGRES_CONFIG


def load_from_json() -> list:
    """Učitaj šifre iz JSON fajla."""
    json_path = Path(__file__).parent / "prilozbeni_dokumenti_sifre.json"
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return data


def create_prilozeni_dokumenti_table():
    """Kreiraj tabelu za šifre priloženih dokumenata."""
    
    create_sql = """
        DROP TABLE IF EXISTS catalogs.prilozeni_dokumenti_sifre CASCADE;
        
        CREATE TABLE catalogs.prilozeni_dokumenti_sifre (
            sifra TEXT PRIMARY KEY,
            opis TEXT NOT NULL,
            aktivan BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_prilozeni_dokumenti_aktivan 
        ON catalogs.prilozeni_dokumenti_sifre(aktivan) WHERE aktivan = TRUE;
        
        COMMENT ON TABLE catalogs.prilozeni_dokumenti_sifre IS 
        'Šifre priloženih dokumenata za Rub.44';
        
        COMMENT ON COLUMN catalogs.prilozeni_dokumenti_sifre.sifra IS 
        'Šifra dokumenta (npr. EUR1, FAKT, N380)';
        
        COMMENT ON COLUMN catalogs.prilozeni_dokumenti_sifre.opis IS 
        'Opis dokumenta';
    """
    
    with psycopg2.connect(**POSTGRES_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(create_sql)
            conn.commit()
            print("✅ Tabela catalogs.prilozeni_dokumenti_sifre kreirana")


def insert_prilozeni_dokumenti(dokumenti: list):
    """Unesi šifre priloženih dokumenata u bazu."""
    
    insert_sql = """
        INSERT INTO catalogs.prilozeni_dokumenti_sifre (sifra, opis)
        VALUES (%s, %s)
        ON CONFLICT (sifra) DO UPDATE SET
            opis = EXCLUDED.opis,
            updated_at = CURRENT_TIMESTAMP
    """
    
    with psycopg2.connect(**POSTGRES_CONFIG) as conn:
        with conn.cursor() as cur:
            for doc in dokumenti:
                cur.execute(insert_sql, (doc['sifra'], doc['opis']))
            conn.commit()
            print(f"✅ Uneseno {len(dokumenti)} šifara dokumenata u bazu")


def show_prilozeni_dokumenti():
    """Prikaži sve šifre priloženih dokumenata."""
    
    with psycopg2.connect(**POSTGRES_CONFIG) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT sifra, opis
                FROM catalogs.prilozeni_dokumenti_sifre
                WHERE aktivan = TRUE
                ORDER BY sifra
            """)
            
            print("\n=== ŠIFRE PRILOŽENIH DOKUMENATA (Rub.44) ===")
            
            rows = cur.fetchall()
            print(f"Ukupno šifara: {len(rows)}\n")
            
            # Prikaži prvih 20
            for i, row in enumerate(rows[:20]):
                print(f"  {row['sifra']:10} - {row['opis'][:60]}")
            
            if len(rows) > 20:
                print(f"  ... i još {len(rows) - 20} šifara")


def main():
    """Glavna funkcija za migraciju."""
    
    print("=" * 70)
    print("MIGRACIJA ŠIFARA PRILOŽENIH DOKUMENATA U POSTGRESQL")
    print("=" * 70)
    
    # 1. Učitaj iz JSON
    print("\n1️⃣  Učitavanje iz JSON fajla...")
    dokumenti = load_from_json()
    print(f"   Pronađeno {len(dokumenti)} šifara")
    
    # 2. Kreiraj tabelu
    print("\n2️⃣  Kreiranje tabele...")
    create_prilozeni_dokumenti_table()
    
    # 3. Unesi dokumente
    print("\n3️⃣  Unos šifara dokumenata...")
    insert_prilozeni_dokumenti(dokumenti)
    
    # 4. Prikaži dokumente
    print("\n4️⃣  Pregled unetih šifara...")
    show_prilozeni_dokumenti()
    
    print("\n" + "=" * 70)
    print("✅ MIGRACIJA ZAVRŠENA")
    print("=" * 70)


if __name__ == "__main__":
    main()
