"""
Ispravlja pogresan naucen mapping u catalogs.product_tariff_mapping:

  product_code='417UN079', naziv_robe='GREJAC SPIRALA 600W'
  je bio mapiran na commodity_code='19023010' (Tjestenina/pasta) - POGRESNO.

Korisnik je uvozio fakture za Blagic Loren i dobio tarifu za tjestenine na
elektricnom grejnom elementu (nemoguce za tu firmu). find_mapping() ima
prioritet #1 = tacan match po product_code, pa je ovaj jedan los zapis
nadjacao i fuzzy i majority-vote logiku (koja ispravno predlaze 85168080
sa 81% glasova - vidi sve ostale 'GREJAC ...' zapise u bazi, svi mapirani
na 85168080).

Naziv proizvoda i product_code su tacni - samo je commodity_code pogresan
(vjerovatno rucno pogresno unesen u ranijoj deklaraciji pa "naucen" preko
learn_from_draft, i ojacavan _increment_usage-om do usage_count=7).

Ispravka: UPDATE commodity_code 19023010 -> 85168080 (elektricni grejni
elementi - ista tarifa kao svi ostali GREJAC proizvodi). zemlja_porijekla
i povlastica ostaju kako jesu (CN / bez povlastice) jer odgovaraju stvarnim
podacima sa fakture.

dry-run je default; --execute pokrece UPDATE, uz CSV backup stanja prije izmjene.
"""
import sys
import csv
import argparse
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

from database.db import get_db_connection

TARGET_PRODUCT_CODE = "417UN079"
TARGET_NAZIV = "GREJAC SPIRALA 600W"
WRONG_CODE = "19023010"
CORRECT_CODE = "85168080"


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
