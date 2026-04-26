#!/usr/bin/env python3
"""
Migracija Å¡ifara vrsta carinskih deklaracija (polje 1) iz JSON fajla u PostgreSQL.

Kreira tri tabele u catalogs shemi:
  - vrste_deklaracija   : kombinacije EX/IM + oznaka (H, I, J, K, A, C, E)
  - postupci_rb37       : dozvoljene Å¡ifre polja 37 za svaku vrstu
  - tipovi_deklaracija  : tip deklaracije iz polja 1/2 (A, Z, B)
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

JSON_FILE = os.path.join(
    os.path.dirname(__file__),
    "sifre_vrste_carinske_deklaracije_polje1_v2.json",
)


def create_tables(cur):
    cur.execute("CREATE SCHEMA IF NOT EXISTS catalogs;")

    # --- vrste_deklaracija (polje 1/1) ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS catalogs.vrste_deklaracija (
            id      SERIAL PRIMARY KEY,
            sifra   VARCHAR(2)  NOT NULL,   -- EX ili IM
            oznaka  VARCHAR(1)  NOT NULL,   -- A, C, E, H, I, J, K
            opis    TEXT        NOT NULL,
            UNIQUE (sifra, oznaka)
        );
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_vrste_dek_sifra
            ON catalogs.vrste_deklaracija (sifra);
    """)
    print("âœ… Tabela catalogs.vrste_deklaracija kreirana")

    # --- postupci_rb37 (dozvoljeni postupci za svaku vrstu) ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS catalogs.postupci_rb37 (
            id        SERIAL PRIMARY KEY,
            vrsta_id  INTEGER NOT NULL
                          REFERENCES catalogs.vrste_deklaracija(id)
                          ON DELETE CASCADE,
            sifra     VARCHAR(4) NOT NULL,  -- npr. 4000, 5100
            opis      TEXT       NOT NULL
        );
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_postupci_rb37_vrsta
            ON catalogs.postupci_rb37 (vrsta_id);
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_postupci_rb37_sifra
            ON catalogs.postupci_rb37 (sifra);
    """)
    print("âœ… Tabela catalogs.postupci_rb37 kreirana")

    # --- tipovi_deklaracija (polje 1/2: A, Z, B) ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS catalogs.tipovi_deklaracija (
            sifra  VARCHAR(1) PRIMARY KEY,
            opis   TEXT       NOT NULL
        );
    """)
    print("âœ… Tabela catalogs.tipovi_deklaracija kreirana")


def migrate_polje_1_1(cur, data):
    """Unosi kombinacije EX/IM + oznaka i njihove postupke u Rb.37."""
    unose_vrsta = 0
    unose_postupaka = 0

    for stavka in data["polje_1_1"]["sifre"]:
        sifra   = stavka["sifra"]           # EX ili IM
        oznaka  = stavka["oznaka_vrste_postupka_mrn"]  # H, I, J, K, A, C, E
        opis    = stavka["opis"]

        cur.execute("""
            INSERT INTO catalogs.vrste_deklaracija (sifra, oznaka, opis)
            VALUES (%s, %s, %s)
            ON CONFLICT (sifra, oznaka) DO UPDATE SET opis = EXCLUDED.opis
            RETURNING id;
        """, (sifra, oznaka, opis))

        vrsta_id = cur.fetchone()["id"]
        unose_vrsta += 1

        # ObriÅ¡i stare postupke za ovu vrstu pa upiÅ¡i nove (idempotentno)
        cur.execute(
            "DELETE FROM catalogs.postupci_rb37 WHERE vrsta_id = %s;",
            (vrsta_id,)
        )

        for postupak in stavka.get("sifre_polja_37", []):
            cur.execute("""
                INSERT INTO catalogs.postupci_rb37 (vrsta_id, sifra, opis)
                VALUES (%s, %s, %s);
            """, (vrsta_id, postupak["sifra"], postupak["opis"]))
            unose_postupaka += 1

    print(f"âœ… Uneseno {unose_vrsta} vrsta deklaracija, "
          f"{unose_postupaka} postupaka Rb.37")


def migrate_polje_1_2(cur, data):
    """Unosi tipove deklaracija (A, Z, B) iz polja 1/2."""
    count = 0
    for stavka in data["polje_1_2"]["sifre"]:
        cur.execute("""
            INSERT INTO catalogs.tipovi_deklaracija (sifra, opis)
            VALUES (%s, %s)
            ON CONFLICT (sifra) DO UPDATE SET opis = EXCLUDED.opis;
        """, (stavka["sifra"], stavka["opis"]))
        count += 1
    print(f"âœ… Uneseno {count} tipova deklaracija (A/Z/B)")


def verify(cur):
    """IspiÅ¡i kratki pregled unesenih podataka."""
    cur.execute("""
        SELECT vd.sifra, vd.oznaka, vd.opis,
               COUNT(p.id) AS broj_postupaka
        FROM catalogs.vrste_deklaracija vd
        LEFT JOIN catalogs.postupci_rb37 p ON p.vrsta_id = vd.id
        GROUP BY vd.id, vd.sifra, vd.oznaka, vd.opis
        ORDER BY vd.sifra, vd.oznaka;
    """)
    rows = cur.fetchall()
    print("\nðŸ“‹ Pregled vrste_deklaracija:")
    print(f"  {'Å ifra':<6} {'Oz':<4} {'Postupaka':>10}  Opis")
    print("  " + "-" * 70)
    for r in rows:
        print(f"  {r['sifra']:<6} {r['oznaka']:<4} {r['broj_postupaka']:>10}  {r['opis'][:55]}")

    cur.execute("SELECT sifra, opis FROM catalogs.tipovi_deklaracija ORDER BY sifra;")
    print("\nðŸ“‹ Tipovi deklaracija (polje 1/2):")
    for r in cur.fetchall():
        print(f"  {r['sifra']}  {r['opis'][:80]}")


def main():
    if not os.path.exists(JSON_FILE):
        print(f"âŒ JSON fajl nije pronaÄ‘en: {JSON_FILE}")
        return

    with open(JSON_FILE, encoding="utf-8") as f:
        data = json.load(f)

    print(f"ðŸ“‚ UÄitan JSON: {os.path.basename(JSON_FILE)}")

    conn = psycopg2.connect(**_pg_config())
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                create_tables(cur)
                migrate_polje_1_1(cur, data)
                migrate_polje_1_2(cur, data)
                verify(cur)
        print("\nâœ… Migracija zavrÅ¡ena uspjeÅ¡no.")
    except Exception as e:
        print(f"\nâŒ GreÅ¡ka: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()

