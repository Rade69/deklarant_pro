#!/usr/bin/env python3
"""
Kreira catalogs.product_similarity_memory za pgvector pretragu slicnih proizvoda.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db import get_db_connection


def main() -> int:
    migration_file = Path(__file__).parent / "migrations" / "005_product_similarity_memory.sql"
    sql = migration_file.read_text(encoding="utf-8")

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
        print("✅ catalogs.product_similarity_memory migracija završena")
        return 0
    except Exception as exc:
        detail = str(exc) or exc.__class__.__name__
        print(f"❌ product_similarity_memory migracija nije uspjela: {detail}")
        print("   Provjeri da li je pgvector instaliran na PostgreSQL serveru.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
