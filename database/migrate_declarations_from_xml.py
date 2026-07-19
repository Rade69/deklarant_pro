#!/usr/bin/env python3
"""
Migracija: parsira stvarne ASYCUDA XML deklaracije (NOVA ASIKUDA arhiva) u
catalogs.declarations / catalogs.declaration_items (PostgreSQL) — puni podatke
za MCP historijsku pretragu (mcp_server/tools/*.py).

Razlika od database/migrate_mappings.py: ta skripta je samo omotavala
catalogs.product_tariff_mapping u lažne "MIGRATED_*" deklaracije (isti podaci,
druga šema). Ova skripta čita STVARNE XML fajlove — isti korpus koji već
koristi services/agent/chat/declaration_search_service.py za svoj (lokalni,
SQLite) indeks — i upisuje stvarne invoice/exporter/item podatke.

Pokretanje:
    uv run python database/migrate_declarations_from_xml.py [--limit N]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db import get_db_connection
from services.agent.chat.declaration_search_service import DeclarationSearchService

PROJECT_ROOT = Path(__file__).resolve().parent.parent
XML_DIR = PROJECT_ROOT / "data" / "knowledge_base" / "NOVA ASIKUDA"


def ensure_schema(cur):
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
    cur.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_declarations_invoice_unique "
        "ON catalogs.declarations(invoice_number)"
    )
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
    cur.execute("CREATE INDEX IF NOT EXISTS idx_declarations_invoice ON catalogs.declarations(invoice_number)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_items_declaration ON catalogs.declaration_items(declaration_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_items_tarifni_broj ON catalogs.declaration_items(tarifni_broj)")
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_items_naziv_robe_fts "
        "ON catalogs.declaration_items USING gin(to_tsvector('simple', naziv_robe))"
    )


def main(limit: int = 0) -> int:
    if not XML_DIR.exists():
        print(f"GRESKA: XML folder ne postoji: {XML_DIR}")
        return 1

    xml_files = sorted(XML_DIR.glob("*.xml"))
    if limit:
        xml_files = xml_files[:limit]
    print(f"Pronadjeno {len(xml_files)} XML fajlova u {XML_DIR}")

    # Instanciran samo radi pristupa dokazanoj _parse_xml logici — ne gradi
    # SQLite indeks (_ensure_index se ne poziva).
    parser = DeclarationSearchService()

    decl_count = 0
    item_count = 0
    skipped = 0

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            ensure_schema(cur)
            # Ocisti eventualne stare/lazne redove (npr. "MIGRATED_*" iz migrate_mappings.py)
            cur.execute("DELETE FROM catalogs.declaration_items")
            cur.execute("DELETE FROM catalogs.declarations")
        conn.commit()

        for xml_path in xml_files:
            try:
                decl, items = parser._parse_xml(xml_path)
            except Exception:
                skipped += 1
                continue

            if not decl or not items:
                skipped += 1
                continue

            filename, decl_type, exporter, consignee, jib = decl

            rows = []
            for hs_code, commercial, description, country, preference in items:
                naziv = " ".join(part for part in (commercial, description) if part).strip()[:500]
                if not naziv:
                    continue
                rows.append((hs_code or "", naziv, country or "", preference or "", 1.0, False))

            if not rows:
                skipped += 1
                continue

            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO catalogs.declarations (invoice_number, vendor, buyer, datum)
                    VALUES (%s, %s, %s, NULL)
                    ON CONFLICT (invoice_number) DO UPDATE SET vendor = EXCLUDED.vendor
                    RETURNING id
                """, (filename, exporter or "", consignee or ""))
                declaration_id = cur.fetchone()["id"]

                cur.executemany("""
                    INSERT INTO catalogs.declaration_items
                    (declaration_id, tarifni_broj, naziv_robe, zemlja_porijekla, povlastica, confidence, ai_suggested)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, [(declaration_id,) + row for row in rows])

            decl_count += 1
            item_count += len(rows)

            if decl_count % 200 == 0:
                conn.commit()
                print(f"  ... {decl_count} deklaracija, {item_count} stavki")

        conn.commit()

    print(f"Zavrseno: {decl_count} deklaracija, {item_count} stavki, {skipped} preskoceno (bez stavki ili greska u parsiranju)")
    return 0


if __name__ == "__main__":
    lim = 0
    if len(sys.argv) > 1 and sys.argv[1] == "--limit" and len(sys.argv) > 2:
        lim = int(sys.argv[2])
    sys.exit(main(limit=lim))
