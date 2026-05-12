#!/usr/bin/env python3
"""
Deklarant Pro — Health Check

Provjerava da je sistem spreman za rad:
  1. config.ini postoji i ima DB parametre
  2. PostgreSQL konekcija radi
  3. Ključne tabele postoje u bazi
  4. Licenca je prisutna i validna
  5. Ključni Python paketi su dostupni

Pokretanje:
    uv run python health_check.py

Exit code 0 = sve OK, 1 = ima problema.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

PASS = "✅"
FAIL = "❌"
WARN = "⚠️ "

results: list[tuple[bool, str]] = []


def check(ok: bool, label: str, detail: str = "") -> bool:
    icon = PASS if ok else FAIL
    msg = f"  {icon}  {label}"
    if detail:
        msg += f"  ({detail})"
    print(msg)
    results.append((ok, label))
    return ok


# ── 1. Config ──────────────────────────────────────────────────────────────
print("\n▶  Konfiguracija")

config_path = ROOT / "config.ini"
if check(config_path.exists(), "config.ini postoji"):
    try:
        from config.settings import get_db_settings
        s = get_db_settings()
        check(bool(s.host), "DB host konfigurisan", s.host)
        check(bool(s.database), "DB ime konfigurisano", s.database)
        check(bool(s.user), "DB korisnik konfigurisan", s.user)
        check(bool(s.password), "DB lozinka konfigurirana")
    except Exception as e:
        check(False, "Čitanje DB postavki", str(e))

# ── 2. PostgreSQL konekcija ────────────────────────────────────────────────
print("\n▶  Baza podataka")

try:
    from database.db import get_db_connection
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version()")
            row = cur.fetchone()
            ver = str(row[0] if row else "?").split(",")[0]
    check(True, "PostgreSQL konekcija", ver)
except Exception as e:
    check(False, "PostgreSQL konekcija", str(e))

# ── 3. Ključne tabele ──────────────────────────────────────────────────────
print("\n▶  Tabele u bazi")

REQUIRED_TABLES = [
    ("catalogs", "drzave"),
    ("catalogs", "povlastice"),
    ("catalogs", "prilozeni_dokumenti_sifre"),
    ("catalogs", "izjave_o_poreklu"),
    ("catalogs", "carinski_dokumenti"),
    ("catalogs", "vrste_prevoza"),
    ("catalogs", "declarations"),
    ("catalogs", "product_tariff_mapping"),
]

try:
    from database.db import get_db_connection
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for schema, table in REQUIRED_TABLES:
                cur.execute(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = %s AND table_name = %s)",
                    (schema, table),
                )
                row = cur.fetchone()
                exists = bool(row[0]) if row else False
                check(exists, f"{schema}.{table}")
except Exception as e:
    check(False, "Provjera tabela", str(e))

# ── 4. Licenca ─────────────────────────────────────────────────────────────
print("\n▶  Licenca")

try:
    from core.licensing.license_paths import get_license_path
    from core.licensing.license_validator import validate_license_file

    lic_path = get_license_path()
    if check(lic_path.exists(), "Licencni fajl postoji", str(lic_path)):
        result = validate_license_file(lic_path)
        ok = result.is_valid
        status_str = result.status.value if hasattr(result.status, "value") else str(result.status)
        check(ok, "Licenca validna", status_str)
        if ok and result.payload:
            exp = getattr(result.payload, "expires_on", None)
            if exp:
                check(True, "Licenca ističe", str(exp))
except Exception as e:
    check(False, "Provjera licence", str(e))

# ── 5. Python paketi ───────────────────────────────────────────────────────
print("\n▶  Python paketi")

PACKAGES = [
    ("PySide6", "PySide6"),
    ("psycopg2", "psycopg2"),
    ("pdfplumber", "pdfplumber"),
    ("openpyxl", "openpyxl"),
    ("lxml", "lxml"),
]

for label, module in PACKAGES:
    try:
        __import__(module)
        check(True, label)
    except ImportError:
        check(False, label, "nije instaliran")

# ── Sažetak ────────────────────────────────────────────────────────────────
print()
print("=" * 50)
total = len(results)
failed = [r for r in results if not r[0]]

if not failed:
    print(f"  {PASS}  Sve provjere prošle ({total}/{total})")
    exit_code = 0
else:
    print(f"  {FAIL}  {len(failed)} od {total} provjera nije prošlo:")
    for _, label in failed:
        print(f"        – {label}")
    exit_code = 1

print("=" * 50)
print()
sys.exit(exit_code)
