"""
Migracija: kreira tabelu catalogs.carinski_dokumenti u PostgreSQL
sa full-text search vektorom (tsvector).

Pokretanje:
    python3 database/migrate_carinski_dokumenti.py
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import get_db_connection


def migrate():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS catalogs.carinski_dokumenti (
                    id              SERIAL PRIMARY KEY,
                    naziv           TEXT NOT NULL,
                    filename        TEXT NOT NULL UNIQUE,
                    sadrzaj         TEXT NOT NULL,
                    file_hash       TEXT NOT NULL,
                    fts_vektor      tsvector GENERATED ALWAYS AS (
                                        to_tsvector('simple', naziv || ' ' || sadrzaj)
                                    ) STORED,
                    datum_indeksa   TIMESTAMPTZ NOT NULL DEFAULT now()
                );

                CREATE INDEX IF NOT EXISTS ix_carinski_dokumenti_fts
                    ON catalogs.carinski_dokumenti USING GIN (fts_vektor);
            """)
        print("OK: Tabela catalogs.carinski_dokumenti kreirana (ili vec postoji).")


if __name__ == "__main__":
    migrate()
