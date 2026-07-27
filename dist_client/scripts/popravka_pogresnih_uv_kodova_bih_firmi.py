"""
Ispravlja gresku napravljenu u move_bih_izvoznike_u_uvoznike.py: ta skripta je
za 28 BiH firmi (koje su VEC imale ispravne 12-cifrene BiH JIB-ove) generisala
NOVE auto-kodove UV00001-UV00028 umjesto da zadrzi njihov pravi JIB. Posljedica:

  (A) 18 firmi je vec postojalo u catalogs.uvoznici sa pravim JIB-om -> nastao
      je DUPLIKAT (identicni podaci, dva razlicita JIB-a — jedan pravi, jedan
      izmisljeni UV#####). Korisnik je primijetio ovo na primjeru ENMON DOO
      (402283900008 vs UV00010) i trazio brisanje "firmi bez JIB-a".
  (B) 9 firmi je imalo SAMO svoj pravi JIB, koji vise ne postoji nigdje (obrisan
      je iz izvoznici, a u uvoznici je upisan pod laznim UV kodom) -> treba
      VRATITI pravi JIB (UPDATE), ne brisati zapis (gubitak podataka).
  (C) 1 firma (GRAND AUTOMOTIVE, EX00994) nikad nije imala pravi BiH JIB - njen
      auto-kod (UV00016) je ispravan i ostaje.

Plan se gradi automatski: za svaki UV0000X zapis iz backup CSV-a provjerava se
da li njegov "pravi" JIB (iz CSV kolone 'jib') vec postoji u uvoznici:
  - DA  -> ovo je duplikat -> DELETE UV0000X zapisa
  - NE i pravi JIB je 12-cifren broj -> UPDATE: vrati pravi JIB na UV0000X zapis
  - NE i pravi JIB nije BiH format (npr. EX#####) -> ne diraj (auto-kod je ispravan)

dry-run je default; --execute pokrece stvarnu izmjenu. CSV backup pravi se
prije DELETE-a.
"""
import sys
import csv
import re
import glob
import argparse
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

from database.db import get_db_connection

BIH_JIB_RE = re.compile(r"^[0-9]{12}$")

# Poseban slucaj: isti pravi JIB i ista adresa, ali drugaciji naziv -> firma je
# promijenila ime, ne radi se o duplikatu. Umjesto brisanja noveg zapisa,
# azuriramo naziv na postojecem (po korisnikovoj odluci "Azuriraj naziv").
RENAME_OVERRIDES = {
    # fake_jib (UV#####) -> novi naziv koji treba upisati na postojeci real_jib zapis
    "UV00020": "KappaStar Recycling BH d.o.o.",  # bivsi naziv: BOVA DOO
}


def load_backup_plan():
    files = sorted(glob.glob("scripts/_izvoznici_move_backup_deleted_*.csv"))
    if not files:
        raise SystemExit("Backup CSV od move_bih_izvoznike_u_uvoznike.py nije pronadjen.")
    rows = []
    with open(files[-1], encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    return rows


def build_plan(cur, backup_rows):
    deletes = []
    restores = []
    untouched = []
    renames = []
    for row in backup_rows:
        real_jib = row["jib"]
        fake_jib = row["novi_uv_jib"]
        naziv = row["naziv"]

        cur.execute(
            "SELECT jib, naziv, adresa, grad FROM catalogs.uvoznici WHERE jib = %s",
            (real_jib,),
        )
        existing = cur.fetchone()
        if existing:
            if fake_jib in RENAME_OVERRIDES:
                renames.append((fake_jib, real_jib, RENAME_OVERRIDES[fake_jib], dict(existing)))
            else:
                deletes.append((fake_jib, real_jib, naziv, dict(existing)))
        elif BIH_JIB_RE.match(real_jib):
            restores.append((fake_jib, real_jib, naziv))
        else:
            untouched.append((fake_jib, real_jib, naziv))
    return deletes, restores, untouched, renames


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true", help="Stvarno izvrsi popravku (default: dry-run)")
    args = ap.parse_args()

    backup_rows = load_backup_plan()

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            deletes, restores, untouched, renames = build_plan(cur, backup_rows)

            print(f"(A) DUPLIKATI za brisanje (laznI UV-kod, pravi JIB vec postoji): {len(deletes)}")
            for fake_jib, real_jib, naziv, existing in deletes:
                print(f"  DELETE {fake_jib}  {naziv!r:36}  (pravi zapis ostaje: {real_jib} {existing['naziv']!r})")

            print(f"\n(B) VRACANJE pravog JIB-a (UPDATE jib): {len(restores)}")
            for fake_jib, real_jib, naziv in restores:
                print(f"  UPDATE {fake_jib} -> {real_jib}  {naziv!r}")

            print(f"\n(C) Bez izmjene (auto-kod je ispravan, firma nema pravi BiH JIB): {len(untouched)}")
            for fake_jib, real_jib, naziv in untouched:
                print(f"  ZADRŽI {fake_jib}  {naziv!r}  (stari kod bio: {real_jib})")

            print(f"\n(D) PROMJENA NAZIVA (ista firma, isti JIB i adresa, drugaciji naziv -> rebrand): {len(renames)}")
            for fake_jib, real_jib, novi_naziv, existing in renames:
                print(f"  UPDATE naziv na {real_jib}: {existing['naziv']!r} -> {novi_naziv!r}  (obrisi duplikat {fake_jib})")

            if not args.execute:
                print("\n[DRY-RUN] Nista nije izmijenjeno. Pokreni sa --execute za stvarnu popravku.")
                return

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"scripts/_uvoznici_fix_backup_deleted_{ts}.csv"
            with open(backup_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["fake_jib", "naziv", "real_jib_kept_record"])
                for fake_jib, real_jib, naziv, existing in deletes:
                    w.writerow([fake_jib, naziv, real_jib])
                for fake_jib, real_jib, novi_naziv, existing in renames:
                    w.writerow([fake_jib, existing["naziv"], real_jib])
            print(f"\nBackup obrisanih duplikata: {backup_path}")

            for fake_jib, real_jib, naziv, existing in deletes:
                cur.execute("DELETE FROM catalogs.uvoznici WHERE jib = %s", (fake_jib,))

            for fake_jib, real_jib, naziv in restores:
                cur.execute("UPDATE catalogs.uvoznici SET jib = %s WHERE jib = %s", (real_jib, fake_jib))

            for fake_jib, real_jib, novi_naziv, existing in renames:
                cur.execute("UPDATE catalogs.uvoznici SET naziv = %s WHERE jib = %s", (novi_naziv, real_jib))
                cur.execute("DELETE FROM catalogs.uvoznici WHERE jib = %s", (fake_jib,))

            conn.commit()
            print(f"\nGotovo: obrisano {len(deletes)} duplikata, vraceno {len(restores)} pravih JIB-ova, "
                  f"azurirano {len(renames)} naziva (rebrand), netaknuto {len(untouched)}.")


if __name__ == "__main__":
    main()
