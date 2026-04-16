#!/usr/bin/env python3
"""
Migracija Incoterms 2020 u PostgreSQL (catalogs.incoterms).

Tabela je reference — koristi je i validacija zaglavlja (VOZ dokument)
i Šifrarnici tab za prikaz.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db import get_db_connection

# Incoterms 2020 — svi kodovi
# freight_in_price=True: vozarina je uključena u cijenu fakture (VOZ dokument nije obavezan)
INCOTERMS_DATA = [
    # (code, name_en, name_bs, transport_mode, freight_in_price)
    # Kodovi za sve vidove transporta
    ("EXW", "Ex Works",                       "Franko fabrika",                        "any",                 False),
    ("FCA", "Free Carrier",                   "Franko prevoznik",                      "any",                 False),
    ("CPT", "Carriage Paid To",               "Prevoz plaćen do",                      "any",                 True),
    ("CIP", "Carriage and Insurance Paid To", "Prevoz i osiguranje plaćeni do",         "any",                 True),
    ("DAP", "Delivered At Place",             "Isporučeno na odredištu",               "any",                 True),
    ("DPU", "Delivered at Place Unloaded",    "Isporučeno na odredištu — istovareno",  "any",                 True),
    ("DDP", "Delivered Duty Paid",            "Isporučeno, carina plaćena",            "any",                 True),
    # Kodovi samo za pomorski / unutrašnji vodeni transport
    ("FAS", "Free Alongside Ship",            "Franko uz bok broda",                   "sea_inland_waterway", False),
    ("FOB", "Free On Board",                  "Franko brod",                           "sea_inland_waterway", False),
    ("CFR", "Cost and Freight",               "Cijena i vozarina",                     "sea_inland_waterway", True),
    ("CIF", "Cost, Insurance and Freight",    "Cijena, osiguranje i vozarina",          "sea_inland_waterway", True),
]


def run():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS catalogs;")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS catalogs.incoterms (
                    code             CHAR(3)      PRIMARY KEY,
                    name_en          VARCHAR(80)  NOT NULL,
                    name_bs          VARCHAR(80)  NOT NULL DEFAULT '',
                    transport_mode   VARCHAR(30)  NOT NULL DEFAULT 'any',
                    freight_in_price BOOLEAN      NOT NULL DEFAULT FALSE,
                    standard         VARCHAR(20)  NOT NULL DEFAULT 'Incoterms 2020',
                    created_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Dodaj name_bs kolonu ako već postoji tabela bez nje
            cur.execute("""
                ALTER TABLE catalogs.incoterms
                ADD COLUMN IF NOT EXISTS name_bs VARCHAR(80) NOT NULL DEFAULT '';
            """)

            inserted = 0
            updated = 0
            for code, name_en, name_bs, transport_mode, freight_in_price in INCOTERMS_DATA:
                cur.execute("""
                    INSERT INTO catalogs.incoterms
                        (code, name_en, name_bs, transport_mode, freight_in_price)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (code) DO UPDATE
                        SET name_en          = EXCLUDED.name_en,
                            name_bs          = EXCLUDED.name_bs,
                            transport_mode   = EXCLUDED.transport_mode,
                            freight_in_price = EXCLUDED.freight_in_price
                    RETURNING (xmax = 0) AS was_insert
                """, (code, name_en, name_bs, transport_mode, freight_in_price))
                row = cur.fetchone()
                if row and row["was_insert"]:
                    inserted += 1
                else:
                    updated += 1

        conn.commit()
        print(f"✅ catalogs.incoterms: {inserted} novih, {updated} ažuriranih")


if __name__ == "__main__":
    run()
