"""
Premjesta zapise iz catalogs.izvoznici koji su zapravo BiH firme
(pogresno zavrsile u katalogu stranih partnera) u catalogs.uvoznici,
sa ispravljenom drzavom='BIH' i realignovanim adresa/grad poljima.

Kontekst: catalogs.izvoznici (Posiljaoci) smiju sadrzavati samo STRANE firme;
catalogs.uvoznici (Primaoci/Uvoznici) smije sadrzavati samo BiH firme. Korisnik
je primijetio da u izvoznicima ima domacih (BiH) firmi i zatrazio brisanje —
po analogiji sa [[strane-firme-u-uvoznicima-premjestene]] ispravan pristup je
PREMJESTANJE u odgovarajuci katalog (ne brisanje), jer su to validni partneri
sa ispravnim BiH podacima — samo su zavrsili u pogresnoj tabeli.

Identifikacija: zapisi sa ispravnim 12-cifrenim numerickim BiH JIB-om
(jib ~ '^[0-9]{12}$') — domaca konvencija, nikad se ne dodjeljuje stranim
partnerima (oni dobijaju EX##### kod) — plus eksplicitan slucaj gdje je
drzava='BOSNA I HERCEGOVINA' upisana doslovno (EX00994).

Poznat data-quality bug u izvornim podacima ovih zapisa: polje 'drzava' cesto
sadrzi STVARNU ULICU/ADRESU (npr. drzava='BANJALUČKI PUT 21') umjesto naziva
drzave, dok adresa/grad oba sadrze isti naziv grada. Skripta to realignuje:
  - ako 'drzava' NIJE prepoznatljiv naziv drzave (BIH/Bosna i Hercegovina) =>
    tretira se kao stvarna ulica -> postaje nova 'adresa', a grad ostaje grad
  - ako 'drzava' JESTE naziv drzave (npr. 'BOSNA I HERCEGOVINA') => adresa/grad
    ostaju kako jesu (bez duplikata), drzava postaje 'BIH'

dry-run je default; --execute pokrece stvarnu izmjenu (INSERT u uvoznici + DELETE
iz izvoznici), uz CSV backup obrisanih zapisa prije brisanja.
"""
import sys
import csv
import argparse
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

from database.db import get_db_connection

# Nazivi koji doslovno znace "Bosna i Hercegovina" (ne ulica/adresa)
COUNTRY_NAME_VARIANTS = {
    "BIH", "B&H", "BOSNA I HERCEGOVINA", "BOSNA", "BOSNIA AND HERZEGOVINA",
    "REPUBLIKA SRPSKA", "FEDERACIJA BIH",
}


def is_country_name(s):
    return (s or "").strip().upper() in COUNTRY_NAME_VARIANTS


def build_plan(cur):
    cur.execute(
        "SELECT jib, naziv, adresa, grad, drzava, telefon, email, kontakt, "
        "pdv_broj, maticni FROM catalogs.izvoznici "
        "WHERE jib ~ '^[0-9]{12}$' OR drzava ILIKE '%BOSNA%' OR drzava ILIKE '%HERCEGOVIN%' "
        "ORDER BY naziv"
    )
    rows = [dict(r) for r in cur.fetchall()]

    plan = []
    for r in rows:
        if is_country_name(r["drzava"]):
            new_adresa = r["adresa"] if (r["adresa"] or "") != (r["grad"] or "") else ""
            new_grad = r["grad"]
        else:
            # 'drzava' polje sadrzi stvarnu ulicu/adresu (data-quality bug iz izvora)
            new_adresa = r["drzava"]
            new_grad = r["grad"] or r["adresa"]
        plan.append((r, new_adresa, new_grad))
    return plan


def next_uv_codes(cur, n):
    cur.execute("SELECT jib FROM catalogs.uvoznici WHERE jib ~ '^UV[0-9]{5}$'")
    existing = {r["jib"] for r in cur.fetchall()}
    codes = []
    i = 1
    while len(codes) < n:
        code = f"UV{i:05d}"
        if code not in existing:
            codes.append(code)
        i += 1
    return codes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true", help="Stvarno izvrsi premjestanje (default: dry-run)")
    args = ap.parse_args()

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            plan = build_plan(cur)

            print(f"Plan premjestanja: {len(plan)} zapisa iz izvoznici -> uvoznici (BIH)\n")
            for r, new_adresa, new_grad in plan:
                print(f"  {r['jib']} {r['naziv']!r:36} drzava: {r['drzava']!r} -> 'BIH'   "
                      f"adresa: {r['adresa']!r} -> {new_adresa!r}   grad: {r['grad']!r} -> {new_grad!r}")

            if not args.execute:
                print("\n[DRY-RUN] Nista nije izmijenjeno. Pokreni sa --execute za stvarno premjestanje.")
                return

            uv_codes = next_uv_codes(cur, len(plan))

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"scripts/_izvoznici_move_backup_deleted_{ts}.csv"
            with open(backup_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["jib", "naziv", "adresa", "grad", "drzava", "telefon", "email",
                            "kontakt", "pdv_broj", "maticni", "novi_uv_jib", "nova_adresa", "novi_grad"])
                for (r, new_adresa, new_grad), new_jib in zip(plan, uv_codes):
                    w.writerow([r["jib"], r["naziv"], r["adresa"], r["grad"], r["drzava"],
                                r["telefon"], r["email"], r["kontakt"], r["pdv_broj"], r["maticni"],
                                new_jib, new_adresa, new_grad])
            print(f"\nBackup obrisanih/premjestenih zapisa: {backup_path}")

            for (r, new_adresa, new_grad), new_jib in zip(plan, uv_codes):
                cur.execute(
                    "INSERT INTO catalogs.uvoznici "
                    "(jib, naziv, adresa, grad, drzava, telefon, email, kontakt, pdv_broj, maticni) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (new_jib, r["naziv"], new_adresa, new_grad, "BIH",
                     r["telefon"], r["email"], r["kontakt"], r["pdv_broj"], r["maticni"]),
                )
                cur.execute("DELETE FROM catalogs.izvoznici WHERE jib = %s", (r["jib"],))

            conn.commit()
            print(f"\nGotovo: premjesteno {len(plan)} zapisa (izvoznici -> uvoznici, novi UV-kodovi dodijeljeni).")


if __name__ == "__main__":
    main()
