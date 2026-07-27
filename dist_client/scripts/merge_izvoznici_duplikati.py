"""Spoji duplikate u catalogs.izvoznici (grupisane po normalizovanom nazivu).

Pravilo izbora "kanonskog" zapisa unutar grupe:
  1. Najviše popunjenih polja (telefon/email/kontakt/pdv_broj/maticni)
  2. Duži/potpuniji naziv (npr. "X DOO" radije nego "X")
  3. JIB kao tie-breaker (manji JIB = stariji unos)

Kanonski zapis se dopunjava praznim poljima iz duplikata (ne gazi postojeće
vrijednosti), a ostali zapisi iz grupe se brišu. Pošto `catalogs.izvoznici`
nema FK reference iz drugih tabela (vendor/buyer u deklaracijama su plain-text
kopije), brisanje je bezbjedno za referencijalni integritet — ovo je čisto
katalog/autocomplete tabela.

Prije svakog brisanja, obrisani zapisi se eksportuju u CSV backup
(scripts/_izvoznici_merge_backup_<timestamp>.csv) radi mogućnosti vraćanja.

Pokretanje:
    python scripts/merge_izvoznici_duplikati.py            # dry-run (samo ispis)
    python scripts/merge_izvoznici_duplikati.py --execute  # stvarno spaja i briše
"""
import csv
import sys
import os
import argparse
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import get_db_connection

MERGE_FIELDS = ["adresa", "grad", "drzava", "telefon", "email", "kontakt", "pdv_broj", "maticni"]


def normalize(text: str) -> str:
    if not text:
        return ""
    text = text.upper()
    for ch in [".", ",", "-", "  "]:
        text = text.replace(ch, " ")
    for suffix in [" DOO", " DD", " AD", " D O O"]:
        text = text.replace(suffix, "")
    return " ".join(text.split())


def completeness_score(row: dict) -> int:
    return sum(1 for f in MERGE_FIELDS if (row.get(f) or "").strip())


def pick_canonical(items: list) -> dict:
    return sorted(
        items,
        key=lambda r: (
            -completeness_score(r),
            -len(r.get("naziv") or ""),
            r.get("jib") or "",
        ),
    )[0]


def build_merge_plan(rows: list):
    groups = {}
    for row in rows:
        key = normalize(row["naziv"])
        groups.setdefault(key, []).append(row)

    plan = []
    for key, items in groups.items():
        if len(items) < 2:
            continue
        canonical = pick_canonical(items)
        duplicates = [r for r in items if r["jib"] != canonical["jib"]]

        merged_fields = {}
        for field in MERGE_FIELDS:
            if not (canonical.get(field) or "").strip():
                for dup in duplicates:
                    val = (dup.get(field) or "").strip()
                    if val:
                        merged_fields[field] = val
                        break

        plan.append({
            "key": key,
            "canonical": canonical,
            "duplicates": duplicates,
            "merged_fields": merged_fields,
        })
    return plan


def print_plan(plan):
    print(f"Plan spajanja: {len(plan)} grupa\n")
    for entry in plan:
        c = entry["canonical"]
        print(f"--- '{entry['key']}' — zadržava se JIB={c['jib']} ({c['naziv']!r}) ---")
        if entry["merged_fields"]:
            print(f"    Dopuna polja iz duplikata: {entry['merged_fields']}")
        for dup in entry["duplicates"]:
            print(f"    BRIŠE SE: JIB={dup['jib']} naziv={dup['naziv']!r} adresa={dup['adresa']!r}")
        print()


def export_backup(rows: list, suffix: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(os.path.dirname(__file__), f"_izvoznici_merge_backup_{suffix}_{ts}.csv")
    if not rows:
        return ""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


def execute_plan(plan, conn):
    all_duplicates = []
    with conn.cursor() as cur:
        for entry in plan:
            canonical = entry["canonical"]
            if entry["merged_fields"]:
                set_clause = ", ".join(f"{field} = %s" for field in entry["merged_fields"])
                values = list(entry["merged_fields"].values()) + [canonical["jib"]]
                cur.execute(
                    f"UPDATE catalogs.izvoznici SET {set_clause} WHERE jib = %s",
                    values,
                )
            for dup in entry["duplicates"]:
                all_duplicates.append(dup)
                cur.execute("DELETE FROM catalogs.izvoznici WHERE jib = %s", (dup["jib"],))
    return all_duplicates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Stvarno izvrši spajanje (default: dry-run)")
    args = parser.parse_args()

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT jib, naziv, adresa, grad, drzava, telefon, email, kontakt, pdv_broj, maticni
                FROM catalogs.izvoznici
                ORDER BY naziv
            """)
            rows = [dict(r) for r in cur.fetchall()]

        plan = build_merge_plan(rows)
        print_plan(plan)

        if not args.execute:
            print(f"\n[DRY-RUN] Ništa nije promijenjeno. Pokreni sa --execute da stvarno spojiš ({len(plan)} grupa, "
                  f"{sum(len(e['duplicates']) for e in plan)} zapisa za brisanje).")
            return

        all_duplicates = []
        for entry in plan:
            all_duplicates.extend(entry["duplicates"])

        backup_path = export_backup(all_duplicates, "deleted")
        if backup_path:
            print(f"\nBackup obrisanih zapisa sačuvan: {backup_path}")

        deleted = execute_plan(plan, conn)
        conn.commit()
        print(f"\n✅ Spojeno {len(plan)} grupa, obrisano {len(deleted)} duplikata.")


if __name__ == "__main__":
    main()
