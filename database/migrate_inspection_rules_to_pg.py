"""
database/migrate_inspection_rules_to_pg.py

Migrira inspekcijska pravila iz JSON fajlova u PostgreSQL tabelu
catalogs.inspection_rules.

Razlike u odnosu na stari SQLite import:
  - tariff_code_norm NE sadrži markere (**, *, +) — oni idu u marker kolonu
  - is_active kolona za soft-delete (korisnik može deaktivirati pravilo)
  - notes kolona za korisničke napomene

Pokretanje:
    python database/migrate_inspection_rules_to_pg.py

Ponovljeno pokretanje: briše i ponovo kreira sve redove (idempotentno).
"""

# ============================================================
# SECTION: inspection-rules-pg-migration
# PURPOSE: Inicijalni uvoz inspekcijskih pravila iz JSON u PostgreSQL
# DOC: docs/sections/inspection-rules-pg.md
# ============================================================

import json
import re
import sys
from pathlib import Path

# Dodaj project root u path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db import get_db_connection

_SRC_DIR = Path(__file__).parent.parent / "docs" / "Galvni-fajlovi" / "inspekcije"

# JSON fajlovi po tipu inspekcije
_SOURCES = {
    "sanitary":        _SRC_DIR / "bih_sanitary_iz_objedinjenog_spiska_flat.json",
    "veterinary":      _SRC_DIR / "bih_veterinarska_kontrola_prilog_I_flat.json",
    "quality_control": _SRC_DIR / "bih_quality_control_iz_objedinjenog_spiska_flat.json",
    "medicines_agency":_SRC_DIR / "bih_medicines_agency_iz_objedinjenog_spiska_flat.json",
    "phytosanitary":   _SRC_DIR / "bih_fitosanitarna_lista_v_flat.json",
}

# Markeri koji se pojavljuju kao prefiks u tarifnom kodu (iz originalnog dokumenta)
_MARKER_PATTERN = re.compile(r'^(\*{1,2}\+?|\+\*{0,2})')


def _strip_marker(code: str) -> tuple[str, str]:
    """
    Odvoji marker (**, *, +) od tarifnog broja.
    Vraća (clean_code, marker).
    Npr: '**1806' → ('1806', '**')
         '+0101'  → ('0101', '+')
         '0101'   → ('0101', '')
    """
    if not code:
        return "", ""
    m = _MARKER_PATTERN.match(code.strip())
    if m:
        marker = m.group(1)
        clean = code.strip()[len(marker):]
        return clean.strip(), marker
    return code.strip(), ""


def _normalize(code: str) -> str:
    """Ukloni razmake: '0603 11 00 00' → '0603110000'."""
    return re.sub(r"\s+", "", (code or "").strip())


def _create_pg_table(conn) -> None:
    """Kreira tabelu catalogs.inspection_rules u PostgreSQL."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS catalogs.inspection_rules (
                id               SERIAL PRIMARY KEY,
                inspection_type  VARCHAR(50)  NOT NULL,
                tariff_code      VARCHAR(40),
                tariff_code_norm VARCHAR(20),
                tariff_len       SMALLINT,
                scope            VARCHAR(30),
                chapter          VARCHAR(10),
                description      TEXT,
                marker           VARCHAR(10),
                condition_text   TEXT,
                match_strength   VARCHAR(20),
                can_auto_decide  BOOLEAN      DEFAULT TRUE,
                source_dataset   VARCHAR(60),
                source_page      SMALLINT,
                is_active        BOOLEAN      DEFAULT TRUE,
                notes            TEXT,
                updated_at       TIMESTAMP    DEFAULT NOW()
            );
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_insp_rules_norm
                ON catalogs.inspection_rules (tariff_code_norm, tariff_len)
                WHERE is_active = TRUE;
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_insp_rules_type
                ON catalogs.inspection_rules (inspection_type)
                WHERE is_active = TRUE;
        """)
    conn.commit()
    print("✅ Tabela catalogs.inspection_rules kreirana/potvrđena")


def _clear_existing(conn) -> None:
    """Briše sve redove — reimport je idempotent."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM catalogs.inspection_rules")
    conn.commit()
    print("🗑️  Stari redovi obrisani")


def _parse_veterinary(path: Path) -> list[dict]:
    """
    Parsira bih_veterinarska_kontrola_prilog_I_flat.json.
    Polja: code, chapter_number, chapter_title, description, qualification, source_page
    """
    rows = json.loads(path.read_text(encoding="utf-8"))
    result = []
    for r in rows:
        raw_code = r.get("code") or ""
        clean_code, marker = _strip_marker(raw_code)
        norm = _normalize(clean_code)
        if not norm:
            continue
        condition = r.get("qualification") or ""
        # Ako qualification počinje s "Svi." ili je prazno → automatski
        # Inače → uslovno (condition_text postoji)
        is_auto = condition.strip().lower() in ("svi.", "svi", "", "sve.")
        result.append({
            "inspection_type": "veterinary",
            "tariff_code":     clean_code,
            "tariff_code_norm": norm,
            "tariff_len":      len(norm),
            "scope":           "tariff_code",
            "chapter":         str(r.get("chapter_number") or ""),
            "description":     r.get("description") or "",
            "marker":          marker,
            "condition_text":  None if is_auto else condition,
            "match_strength":  "exact" if len(norm) >= 8 else "prefix",
            "can_auto_decide": is_auto,
            "source_dataset":  "veterinary_prilog_I",
            "source_page":     r.get("source_page"),
        })
    return result


def _parse_objedinjeni(path: Path, insp_type: str, source_name: str) -> list[dict]:
    """
    Parsira flat JSON fajlove iz objedinjenog spiska.
    Polja: inspection_type, chapter, chapter_title, tariff_code, scope,
           description, marker, condition_text, raw_cell, source_page
    """
    rows = json.loads(path.read_text(encoding="utf-8"))
    result = []
    for r in rows:
        raw_code = r.get("tariff_code") or ""
        clean_code, file_marker = _strip_marker(raw_code)
        # marker iz JSON polja ima prednost nad prefiks-markerom
        doc_marker = r.get("marker") or file_marker or ""
        norm = _normalize(clean_code)
        if not norm:
            continue
        condition = r.get("condition_text") or ""
        is_auto = not bool(condition.strip())
        result.append({
            "inspection_type":  insp_type,
            "tariff_code":      clean_code,
            "tariff_code_norm": norm,
            "tariff_len":       len(norm),
            "scope":            r.get("scope") or "tariff_code",
            "chapter":          str(r.get("chapter") or ""),
            "description":      r.get("description") or "",
            "marker":           doc_marker,
            "condition_text":   condition or None,
            "match_strength":   "exact" if len(norm) >= 8 else "prefix",
            "can_auto_decide":  is_auto,
            "source_dataset":   source_name,
            "source_page":      r.get("source_page"),
        })
    return result


def _parse_phytosanitary(path: Path) -> list[dict]:
    """
    Parsira bih_fitosanitarna_lista_v_flat.json.
    Nema direktnih tarifnih kodova — mapira kategorije na grube prefikse.
    """
    rows = json.loads(path.read_text(encoding="utf-8"))
    # Fitosanitarna lista nema tariff_code — koristimo chapter-level prefixe
    # iz poznatih kategorija (bilje, sjeme, drvo...)
    CATEGORY_PREFIXES = {
        "bilje_namijenjeno_sadnji": ["0601", "0602", "0603", "0604"],
        "sjeme":                    ["1209"],
        "drvo_i_drvni_materijal":   ["44"],
        "zemlja_i_supstrat":        ["2505", "2508"],
        "voce_i_povrce":            ["07", "08"],
        "zitarice":                 ["10"],
        "industrijsko_bilje":       ["12"],
    }
    result = []
    seen = set()
    for r in rows:
        cat = r.get("category") or ""
        prefixes = CATEGORY_PREFIXES.get(cat, [])
        for prefix in prefixes:
            if prefix in seen:
                continue
            seen.add(prefix)
            result.append({
                "inspection_type":  "phytosanitary",
                "tariff_code":      prefix,
                "tariff_code_norm": _normalize(prefix),
                "tariff_len":       len(_normalize(prefix)),
                "scope":            "chapter" if len(prefix) <= 2 else "prefix",
                "chapter":          prefix[:2],
                "description":      r.get("description") or cat,
                "marker":           "",
                "condition_text":   None,
                "match_strength":   "prefix",
                "can_auto_decide":  True,
                "source_dataset":   "phytosanitary_lista_v",
                "source_page":      r.get("source_page"),
            })
    return result


def _insert_rows(conn, rows: list[dict]) -> int:
    """Umetne redove u catalogs.inspection_rules."""
    if not rows:
        return 0
    with conn.cursor() as cur:
        for r in rows:
            cur.execute("""
                INSERT INTO catalogs.inspection_rules
                    (inspection_type, tariff_code, tariff_code_norm, tariff_len,
                     scope, chapter, description, marker, condition_text,
                     match_strength, can_auto_decide, source_dataset, source_page,
                     is_active, notes)
                VALUES
                    (%(inspection_type)s, %(tariff_code)s, %(tariff_code_norm)s,
                     %(tariff_len)s, %(scope)s, %(chapter)s, %(description)s,
                     %(marker)s, %(condition_text)s, %(match_strength)s,
                     %(can_auto_decide)s, %(source_dataset)s, %(source_page)s,
                     TRUE, NULL)
            """, r)
    conn.commit()
    return len(rows)


def migrate() -> None:
    """Glavna funkcija migracije."""
    print("🚀 Migracija inspekcijskih pravila → PostgreSQL\n")

    with get_db_connection() as conn:
        _create_pg_table(conn)
        _clear_existing(conn)

        total = 0

        # Veterinarska — poseban parser (Prilog I format)
        print("🐄 Veterinarska inspekcija (Prilog I)...")
        rows = _parse_veterinary(_SOURCES["veterinary"])
        n = _insert_rows(conn, rows)
        total += n
        print(f"   → {n} redova umetnutih")

        # Sanitarna
        print("🔬 Sanitarna inspekcija (objedinjeni)...")
        rows = _parse_objedinjeni(_SOURCES["sanitary"], "sanitary", "sanitary_objedinjeni")
        n = _insert_rows(conn, rows)
        total += n
        print(f"   → {n} redova umetnutih")

        # Kontrola kvaliteta
        print("📊 Kontrola kvaliteta (objedinjeni)...")
        rows = _parse_objedinjeni(_SOURCES["quality_control"], "quality_control", "quality_control_objedinjeni")
        n = _insert_rows(conn, rows)
        total += n
        print(f"   → {n} redova umetnutih")

        # Agencija za lijekove
        print("⚕️  Agencija za lijekove (objedinjeni)...")
        rows = _parse_objedinjeni(_SOURCES["medicines_agency"], "medicines_agency", "medicines_agency_objedinjeni")
        n = _insert_rows(conn, rows)
        total += n
        print(f"   → {n} redova umetnutih")

        # Fitosanitarna — mapiranje kategorija na prefikse
        print("🌿 Fitosanitarna inspekcija (lista v)...")
        rows = _parse_phytosanitary(_SOURCES["phytosanitary"])
        n = _insert_rows(conn, rows)
        total += n
        print(f"   → {n} redova umetnutih")

        print(f"\n✅ UKUPNO: {total} redova u catalogs.inspection_rules")

        # Verifikacija po tipu
        with conn.cursor() as cur:
            cur.execute("""
                SELECT inspection_type, COUNT(*) as cnt,
                       COUNT(*) FILTER (WHERE condition_text IS NOT NULL) as conditional
                FROM catalogs.inspection_rules
                GROUP BY inspection_type ORDER BY inspection_type
            """)
            print("\n=== STATISTIKA ===")
            for row in cur.fetchall():
                print(f"  {row['inspection_type']:20s}: {row['cnt']:4d} redova ({row['conditional']} uslovnih)")


if __name__ == "__main__":
    migrate()
