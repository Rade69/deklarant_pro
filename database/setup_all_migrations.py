#!/usr/bin/env python3
"""
Pokreni sve PostgreSQL migracije za Deklarant Pro.

Koristi se pri instalaciji novog servera ili nakon git pull-a.
Svaka migracija je idempotentna (CREATE TABLE IF NOT EXISTS).

Pokretanje:
    uv run python database/setup_all_migrations.py
"""

import subprocess
import sys
from pathlib import Path

DB_DIR = Path(__file__).parent

# Redosljed migracija: osnove → šifarnici → partneri i historija → znanje
MIGRATIONS = [
    # Osnove — referentne tabele bez zavisnosti
    "migrate_drzave.py",
    "migrate_incoterms.py",
    "migrate_vrste_prevoza.py",
    "migrate_vrste_deklaracija.py",
    "migrate_pakovanja.py",
    "migrate_carinski_dokumenti.py",
    "migrate_carinski_postupci.py",
    # Šifarnici za deklaracije
    "migrate_povlastice.py",
    "migrate_prilozeni_dokumenti_sifre.py",
    "migrate_izjave_o_poreklu.py",
    # Poslovni subjekti
    "migrate_deklaranti.py",
    "migrate_partners.py",
    # Baza znanja i mapiranja
    "migrate_tariff_kb.py",
    "migrate_knowledge_base.py",
    "migrate_mappings.py",
    "migrate_product_similarity_memory.py",
    # Složene tabele
    "migrate_inspection_rules_to_pg.py",
]


def run_migration(script_name: str) -> bool:
    script = DB_DIR / script_name
    if not script.exists():
        print(f"  ⚠️  Fajl ne postoji: {script_name} — preskačem")
        return True

    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"  ❌ GREŠKA ({result.returncode})")
        if result.stderr:
            for line in result.stderr.strip().splitlines()[-5:]:
                print(f"     {line}")
        return False

    # Prikaži zadnje dvije linije outputa (status)
    lines = (result.stdout or "").strip().splitlines()
    for line in lines[-2:]:
        if line.strip():
            print(f"     {line}")
    return True


def main() -> int:
    print("=" * 60)
    print("  Deklarant Pro — Setup migracija")
    print("=" * 60)

    passed = 0
    failed = 0

    for script in MIGRATIONS:
        print(f"\n▶  {script}")
        ok = run_migration(script)
        if ok:
            passed += 1
        else:
            failed += 1

    print("\n" + "=" * 60)
    print(f"  Završeno: {passed} uspješno, {failed} neuspješno")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
