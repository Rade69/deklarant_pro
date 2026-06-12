"""
Ispravlja pogresan naucen mapping u catalogs.product_tariff_mapping:

  product_code='540 101', naziv_robe='Plamenik fi 75mm'
  je bio mapiran na commodity_code='72254090' (Pljosnati valjani proizvodi
  od ostalih legiranih celika / "TV TABLA") - POGRESNO.

Korisnik je uvozio fakturu za Atos (preko Blagic Loren) i dobio za
"Plamenik fi 75mm" tarifu za celicni lim, sto je nemoguce za taj proizvod.
find_mapping() ima prioritet #1 = tacan match po product_code, pa je ovaj
jedan los zapis nadjacao fuzzy/majority-vote logiku.

Sestrinski proizvod product_code='540 103' ("Plamenik fi 100mm", isti
dobavljac, ista faktura-serija) je ispravno mapiran na commodity_code
'85169000' (dijelovi elektricnih grejnih uredjaja) - kao i svi ostali
"PLAMENIK"/"GRIJAC..." zapisi istog dobavljaca (ATOS) u bazi.

Oba zapisa su kreirana u istoj sekundi (2026-04-14 15:51:18) - vjerovatno
je u toj ranijoj deklaraciji "Plamenik fi 75mm" rucno dobio tarifu sa
susjedne "TV TABLA" stavke (copy-paste greska), pa je learn_from_draft
to "naucio" i usage_count je od tada rastao do 13 kroz _increment_usage.

Ispravka: UPDATE commodity_code 72254090 -> 85169000. zemlja_porijekla,
povlastica i usage_count ostaju kako jesu (RS / bez povlastice / 13).

dry-run je default; --execute pokrece UPDATE, uz CSV backup stanja prije izmjene.
"""
import sys
import csv
import argparse
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

from database.db import get_db_connection

TARGET_PRODUCT_CODE = "540 101"
TARGET_NAZIV = "Plamenik fi 75mm"
WRONG_CODE = "72254090"
CORRECT_CODE = "85169000"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true", help="Stvarno izvrsi ispravku (default: dry-run)")
    args = ap.parse_args()

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT product_code, naziv_robe, commodity_code, precision_1, "
                "zemlja_porijekla, povlastica, usage_count, supplier, source "
                "FROM catalogs.product_tariff_mapping "
                "WHERE product_code = %s AND naziv_robe = %s AND commodity_code = %s",
                (TARGET_PRODUCT_CODE, TARGET_NAZIV, WRONG_CODE),
            )
            row = cur.fetchone()

            if not row:
                print(f"Nema zapisa za product_code={TARGET_PRODUCT_CODE!r}, "
                      f"naziv={TARGET_NAZIV!r}, commodity_code={WRONG_CODE!r} - nista za ispraviti.")
                return

            print("Pronadjen pogresan zapis:")
            print(f"  {dict(row)}")
            print(f"\nPlan: commodity_code {WRONG_CODE!r} -> {CORRECT_CODE!r} "
                  f"(precision_1, zemlja_porijekla, povlastica, usage_count ostaju nepromijenjeni)")

            if not args.execute:
                print("\n[DRY-RUN] Nista nije izmijenjeno. Pokreni sa --execute za stvarnu ispravku.")
                return

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"scripts/_tariff_mapping_fix_backup_{ts}.csv"
            with open(backup_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["product_code", "naziv_robe", "commodity_code", "precision_1",
                            "zemlja_porijekla", "povlastica", "usage_count", "supplier", "source"])
                w.writerow([row["product_code"], row["naziv_robe"], row["commodity_code"],
                            row["precision_1"], row["zemlja_porijekla"], row["povlastica"],
                            row["usage_count"], row["supplier"], row["source"]])
            print(f"\nBackup stanja prije izmjene: {backup_path}")

            cur.execute(
                "UPDATE catalogs.product_tariff_mapping "
                "SET commodity_code = %s "
                "WHERE product_code = %s AND naziv_robe = %s AND commodity_code = %s",
                (CORRECT_CODE, TARGET_PRODUCT_CODE, TARGET_NAZIV, WRONG_CODE),
            )
            conn.commit()
            print(f"\nGotovo: azurirano {cur.rowcount} zapis(a). "
                  f"commodity_code je sada {CORRECT_CODE!r}.")


if __name__ == "__main__":
    main()
