#!/usr/bin/env python3
"""
database/migrate_tariff_kb.py

Kreira tabelu catalogs.tariff_knowledge_base za čuvanje tarifnih podataka
iz XML deklaracija (rubrika 31 + tariff + origin + preference).

Struktura:
  - tarifni_broj (8-cifreni kod)
  - naziv_robe (opis robe iz Commercial_Description ili Description_of_goods)
  - zemlja_porijekla (2-slovni kod)
  - povlastica (preference code: EUP, 000, itd.)

Unikatni constraint: UNIQUE(tarifni_broj, naziv_robe, zemlja_porijekla, povlastica)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import get_db_connection


def create_table():
    """Kreira tabelu ako ne postoji."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DROP TABLE IF EXISTS catalogs.tariff_knowledge_base CASCADE;
                
                CREATE TABLE catalogs.tariff_knowledge_base (
                    id SERIAL PRIMARY KEY,
                    tarifni_broj VARCHAR(10) NOT NULL,
                    naziv_robe TEXT NOT NULL,
                    zemlja_porijekla VARCHAR(3) NOT NULL DEFAULT '',
                    povlastica VARCHAR(10) NOT NULL DEFAULT '',
                    source_file VARCHAR(255) DEFAULT '',
                    created_at TIMESTAMP DEFAULT NOW(),
                    
                    CONSTRAINT uq_tariff_entry UNIQUE (tarifni_broj, naziv_robe, zemlja_porijekla, povlastica)
                );
                
                CREATE INDEX IF NOT EXISTS idx_tariff_kb_tarifni 
                    ON catalogs.tariff_knowledge_base(tarifni_broj);
                
                CREATE INDEX IF NOT EXISTS idx_tariff_kb_naziv 
                    ON catalogs.tariff_knowledge_base USING gin(to_tsvector('serbian', naziv_robe));
                
                CREATE INDEX IF NOT EXISTS idx_tariff_kb_zemlja 
                    ON catalogs.tariff_knowledge_base(zemlja_porijekla);
                
                CREATE INDEX IF NOT EXISTS idx_tariff_kb_povlastica 
                    ON catalogs.tariff_knowledge_base(povlastica);
                
                COMMENT ON TABLE catalogs.tariff_knowledge_base IS 
                    'Knowledge base tarifnih podataka iz XML deklaracija (rubrika 31)';
                COMMENT ON COLUMN catalogs.tariff_knowledge_base.tarifni_broj IS 
                    'Tarifni broj (8-cifreni format bez tačaka)';
                COMMENT ON COLUMN catalogs.tariff_knowledge_base.naziv_robe IS 
                    'Opis robe iz rubrike 31 (Commercial_Description)';
                COMMENT ON COLUMN catalogs.tariff_knowledge_base.zemlja_porijekla IS 
                    'Zemlja porijekla (2-slovni kod: IT, SI, RS, ...)';
                COMMENT ON COLUMN catalogs.tariff_knowledge_base.povlastica IS 
                    'Preference code (EUP, 000, NMF, ...)';
            """)
            print("✅ Tabela catalogs.tariff_knowledge_base kreirana")


def count_entries():
    """Prikazuje broj unesenih zapisa."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM catalogs.tariff_knowledge_base")
            cnt = cur.fetchone()['cnt']
            print(f"Ukupno unosa: {cnt}")
            
            if cnt > 0:
                cur.execute("""
                    SELECT tarifni_broj, LEFT(naziv_robe, 60), zemlja_porijekla, povlastica
                    FROM catalogs.tariff_knowledge_base LIMIT 5
                """)
                for r in cur.fetchall():
                    print(f"  {r[0]} | {r[1]} | {r[2]} | {r[3]}")


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'count':
        count_entries()
    else:
        print("Kreiranje tabele catalogs.tariff_knowledge_base...")
        create_table()
        count_entries()
