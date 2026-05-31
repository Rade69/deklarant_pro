#!/usr/bin/env python3
"""
Migracija postojećih mapiranja iz catalogs.product_tariff_mapping u catalogs.declaration_items.

SVE KORISTI POSTGRESQL - nema SQLite!
"""

import sys
from pathlib import Path

# Dodaj root folder u path za import
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db import get_db_connection


def migrate_mappings():
    """Migrira mapiranja iz product_tariff_mapping u declaration_items."""
    
    print(f"📦 Migracija mapiranja u PostgreSQL")
    print(f"📍 Baza: catalogs shema")
    print("-" * 60)
    
    # 1. Prvo kreiraj tabele
    run_migrations()
    
    # 2. Migriraj podatke
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            # Preuzmi podatke iz product_tariff_mapping
            print("\n📌 Preuzimam podatke iz catalogs.product_tariff_mapping...")
            cur.execute("""
                SELECT product_code, naziv_robe, tarifni_broj, zemlja_porijekla, povlastica, usage_count, last_used
                FROM catalogs.product_tariff_mapping
                WHERE tarifni_broj IS NOT NULL
                LIMIT 1000
            """)
            
            rows = cur.fetchall()
            print(f"✅ Preuzeto {len(rows)} redova")
            
            # Insert u declaration_items
            print("\n📌 Migriram u catalogs.declaration_items...")
            migrated = 0
            
            for row in rows:
                product_code = row['product_code']
                naziv_robe = row['naziv_robe'] or ''
                tarifni_broj = row['tarifni_broj'] or ''
                zemlja_porijekla = row['zemlja_porijekla'] or ''
                povlastica = row['povlastica'] or ''
                
                # Prvo kreiraj dummy deklaraciju ili nađi postojeću
                cur.execute("""
                    INSERT INTO catalogs.declarations (invoice_number, vendor, datum)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (invoice_number) DO UPDATE SET datum = %s
                    RETURNING id
                """, (f"MIGRATED_{product_code}", "MIGRATION", "2026-03-17", "2026-03-17"))
                
                result = cur.fetchone()
                declaration_id = result['id'] if result else None
                
                if declaration_id:
                    # Insert stavku
                    cur.execute("""
                        INSERT INTO catalogs.declaration_items 
                        (declaration_id, tarifni_broj, naziv_robe, zemlja_porijekla, povlastica, confidence, ai_suggested)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (declaration_id, tarifni_broj, naziv_robe, zemlja_porijekla, povlastica, 0.9, False))
                    
                    migrated += 1
                    
                    if migrated % 100 == 0:
                        print(f"   Migrirano {migrated} redova...")
            
            conn.commit()
            print(f"\n✅ Migrirano {migrated} redova u catalogs.declaration_items")
            
    except Exception as e:
        print(f"❌ Greška pri migraciji: {e}")
        raise
    
    # 3. Verifikacija
    verify_migration()


def run_migrations():
    """Pokreni PostgreSQL migracije."""
    
    print("\n📌 Kreiram tabele...")
    
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            # Kreiraj declarations
            cur.execute("""
                CREATE TABLE IF NOT EXISTS catalogs.declarations (
                    id SERIAL PRIMARY KEY,
                    invoice_number VARCHAR(255) NOT NULL,
                    vendor VARCHAR(500),
                    buyer VARCHAR(500),
                    datum DATE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Dodaj UNIQUE index na invoice_number
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_declarations_invoice_unique ON catalogs.declarations(invoice_number)")
            
            # Kreiraj declaration_items
            cur.execute("""
                CREATE TABLE IF NOT EXISTS catalogs.declaration_items (
                    id SERIAL PRIMARY KEY,
                    declaration_id INTEGER NOT NULL REFERENCES catalogs.declarations(id) ON DELETE CASCADE,
                    tarifni_broj VARCHAR(20),
                    naziv_robe TEXT NOT NULL,
                    zemlja_porijekla VARCHAR(100),
                    povlastica VARCHAR(100),
                    confidence REAL DEFAULT 0.5,
                    ai_suggested BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Kreiraj indekse
            cur.execute("CREATE INDEX IF NOT EXISTS idx_declarations_invoice ON catalogs.declarations(invoice_number)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_items_declaration ON catalogs.declaration_items(declaration_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_items_tarifni_broj ON catalogs.declaration_items(tarifni_broj)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_items_naziv_robe_fts ON catalogs.declaration_items USING gin(to_tsvector('simple', naziv_robe))")
            
            conn.commit()
            print("✅ Tabele kreirane uspješno")
            
    except Exception as e:
        print(f"❌ Greška pri kreiranju tabela: {e}")
        raise


def verify_migration():
    """Verifikuj migraciju."""
    
    print("\n📊 Verifikacija migracije...")
    
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            cur.execute("SELECT COUNT(*) FROM catalogs.declarations")
            decl_count = cur.fetchone()[0]
            print(f"   catalogs.declarations: {decl_count} redova")
            
            cur.execute("SELECT COUNT(*) FROM catalogs.declaration_items")
            items_count = cur.fetchone()[0]
            print(f"   catalogs.declaration_items: {items_count} redova")
            
            # Uzorak podataka
            print("\n📋 Uzorak podataka:")
            cur.execute("""
                SELECT tarifni_broj, naziv_robe, zemlja_porijekla
                FROM catalogs.declaration_items
                LIMIT 5
            """)
            
            for row in cur.fetchall():
                print(f"   {row[0]} - {row[1][:50]}... ({row[2]})")
            
    except Exception as e:
        print(f"❌ Greška pri verifikaciji: {e}")


if __name__ == "__main__":
    migrate_mappings()
