"""
database/import_inspection_rules.py

Uvozi inspekcijska pravila iz JSON fajlova u SQLite bazu inspection_rules.db.

Izvor: /home/radovan/Documents/inspekcije/Galvni-fajlovi/
Cilj:  database/inspection_rules.db

Pokretanje:
    python database/import_inspection_rules.py
"""

import json
import re
import sqlite3
from pathlib import Path

# Putanje
_SRC_DIR = Path("/home/radovan/Documents/inspekcije/Galvni-fajlovi")
_DB_PATH = Path(__file__).parent / "inspection_rules.db"

_RULES_JSON    = _SRC_DIR / "inspection_tariff_rules_master.json"
_LEGAL_JSON    = _SRC_DIR / "inspection_legal_context_master.json"
_MARKERS_JSON  = _SRC_DIR / "inspection_marker_lookup.json"


def _normalize_tariff(code: str) -> str:
    """Ukloni razmake iz tarifnog broja: '0603 11 00 00' → '0603110000'."""
    if not code:
        return ""
    return re.sub(r"\s+", "", code.strip())


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        DROP TABLE IF EXISTS inspection_tariff_rules;
        DROP TABLE IF EXISTS inspection_legal_context;
        DROP TABLE IF EXISTS inspection_marker_lookup;

        CREATE TABLE inspection_tariff_rules (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            inspection_type  TEXT NOT NULL,
            tariff_code      TEXT,
            tariff_code_norm TEXT,
            tariff_len       INTEGER,
            scope            TEXT,
            chapter          TEXT,
            description      TEXT,
            marker           TEXT,
            condition_text   TEXT,
            priority         INTEGER DEFAULT 1,
            match_strength   TEXT,
            can_auto_decide  INTEGER DEFAULT 0,
            decision_basis   TEXT,
            source_dataset   TEXT,
            source_page      INTEGER
        );

        CREATE INDEX idx_insp_tariff_norm
            ON inspection_tariff_rules (tariff_code_norm, tariff_len);
        CREATE INDEX idx_insp_type
            ON inspection_tariff_rules (inspection_type);

        CREATE TABLE inspection_legal_context (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            inspection_type  TEXT,
            legal_source     TEXT,
            tariff_reference TEXT,
            tariff_ref_norm  TEXT,
            part             TEXT,
            section          TEXT,
            item             TEXT,
            category         TEXT,
            description      TEXT,
            match_mode       TEXT,
            source_page      INTEGER
        );

        CREATE INDEX idx_legal_type
            ON inspection_legal_context (inspection_type);

        CREATE TABLE inspection_marker_lookup (
            marker  TEXT PRIMARY KEY,
            meaning TEXT
        );
    """)


def _import_rules(conn: sqlite3.Connection) -> int:
    data = json.loads(_RULES_JSON.read_text(encoding="utf-8"))
    rows = []
    for r in data:
        norm = _normalize_tariff(r.get("tariff_code") or "")
        rows.append((
            r.get("inspection_type"),
            r.get("tariff_code"),
            norm,
            len(norm) if norm else None,
            r.get("scope"),
            r.get("chapter"),
            r.get("description"),
            r.get("marker"),
            r.get("condition_text"),
            r.get("priority", 1),
            r.get("match_strength"),
            1 if r.get("can_auto_decide") else 0,
            r.get("decision_basis"),
            r.get("source_dataset"),
            r.get("source_page"),
        ))
    conn.executemany("""
        INSERT INTO inspection_tariff_rules
            (inspection_type, tariff_code, tariff_code_norm, tariff_len,
             scope, chapter, description, marker, condition_text,
             priority, match_strength, can_auto_decide, decision_basis,
             source_dataset, source_page)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, rows)
    return len(rows)


def _import_legal(conn: sqlite3.Connection) -> int:
    data = json.loads(_LEGAL_JSON.read_text(encoding="utf-8"))
    rows = []
    for r in data:
        ref = r.get("tariff_reference") or ""
        rows.append((
            r.get("inspection_type"),
            r.get("legal_source"),
            ref,
            _normalize_tariff(ref),
            r.get("part"),
            r.get("section"),
            r.get("item"),
            r.get("category"),
            r.get("description"),
            r.get("match_mode"),
            r.get("source_page"),
        ))
    conn.executemany("""
        INSERT INTO inspection_legal_context
            (inspection_type, legal_source, tariff_reference, tariff_ref_norm,
             part, section, item, category, description, match_mode, source_page)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, rows)
    return len(rows)


def _import_markers(conn: sqlite3.Connection) -> int:
    data = json.loads(_MARKERS_JSON.read_text(encoding="utf-8"))
    rows = [(r["marker"], r["meaning"]) for r in data]
    conn.executemany(
        "INSERT INTO inspection_marker_lookup (marker, meaning) VALUES (?,?)",
        rows,
    )
    return len(rows)


def run_import() -> None:
    print(f"Uvoz inspekcijskih pravila u {_DB_PATH}")

    if _DB_PATH.exists():
        _DB_PATH.unlink()
        print("  Stara baza obrisana.")

    conn = sqlite3.connect(_DB_PATH)
    try:
        _create_schema(conn)
        print("  Shema kreirana.")

        n_rules   = _import_rules(conn)
        n_legal   = _import_legal(conn)
        n_markers = _import_markers(conn)

        conn.commit()
        print(f"  inspection_tariff_rules : {n_rules} redova")
        print(f"  inspection_legal_context: {n_legal} redova")
        print(f"  inspection_marker_lookup: {n_markers} redova")
        print(f"✅ Uvoz završen: {_DB_PATH}")
    except Exception as e:
        conn.rollback()
        print(f"❌ Greška: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    run_import()
