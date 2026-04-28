#!/usr/bin/env python3
"""
Pokreni PostgreSQL migracije za catalogs shemu.

Kreira tabele:
- catalogs.declarations (istorija deklaracija)
- catalogs.declaration_items (stavke sa tarifnim brojevima)
"""

import sys
from pathlib import Path

# Dodaj root folder u path za import
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db import get_db_connection


def run_migrations():
    """Pokreni PostgreSQL migracije."""
    
    print("📦 Deklarant Pro - PostgreSQL Migracije")
    print("📍 Baza: catalogs shema")
    print("-" * 60)
    
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            # Učitaj SQL fajl
            migration_file = Path(__file__).parent / "migrations" / "001_declarations_history.sql"
            
            if not migration_file.exists():
                print(f"❌ Migracioni fajl ne postoji: {migration_file}")
                return False
            
            with open(migration_file, 'r', encoding='utf-8') as f:
                sql_script = f.read()
            
            # Podijeli na statemente i izvrši
            statements = sql_script.split(';')
            
            executed = 0
            for statement in statements:
                statement = statement.strip()
                if statement and not statement.startswith('--'):
                    try:
                        cur.execute(statement)
                        executed += 1
                    except Exception as e:
                        # Ignoriši greške za već postojeće objekte
                        if 'already exists' not in str(e).lower():
                            print(f"⚠️ Greška: {e}")
            
            conn.commit()
            print(f"✅ Izvršeno {executed} SQL statementa")
            
            # Verifikacija
            print("\n📊 Verifikacija:")
            cur.execute("SELECT COUNT(*) FROM catalogs.declarations")
            decl_count = cur.fetchone()[0]
            print(f"   catalogs.declarations: {decl_count} redova")
            
            cur.execute("SELECT COUNT(*) FROM catalogs.declaration_items")
            items_count = cur.fetchone()[0]
            print(f"   catalogs.declaration_items: {items_count} redova")
            
            return True
            
    except Exception as e:
        print(f"❌ Greška pri migraciji: {e}")
        return False


if __name__ == "__main__":
    success = run_migrations()
    sys.exit(0 if success else 1)
