"""
Premjesta zapise iz catalogs.uvoznici koji su zapravo STRANE firme
(pogresno oznacene drzava='BIH') u catalogs.izvoznici, sa ispravljenom drzavom.

Kontekst: catalogs.uvoznici smije sadrzavati samo firme iz BiH (Uvoznici/Primaoci).
Import iz XML-a (database/import_partners_from_xml.py:105) je grijeskom postavljao
"drzava": "BIH" za svakog Consignee-a koji ima sifru (jib), bez obzira na stvarnu
drzavu porijekla. Greska se prenijela u seed fajl database/consignees.json (svih 733
zapisa ima country='BIH'). Posljedica: ~48 stranih firmi (Srbija, Crna Gora,
Makedonija, Hrvatska, Slovenija, Svedska, Cyprus) zavrsilo je u uvoznicima.

Identifikacija: zapisi sa auto-generisanom sifrom oblika UV##### (dodijeljena samo
kada izvor nije imao pravi BiH JIB) — ali NE svi takvi zapisi su strani: dva su
genuine BiH firme kojima samo nedostaje ispravan JIB u izvornim podacima
(Bisprom - Prnjavor, MODUL - Banja Luka), pa su EXPLICITNO iskljuceni.

Drzava se odredjuje:
  1) ako adresa/grad sadrze ime strane drzave (SRBIJA, CRNA GORA, MAKEDONIJA,
     HRVATSKA, SLOVENIJA, SVEDSKA, CYPRUS) -> ta drzava
  2) za preostale (gdje adresa/grad sadrze stvarnu ulicu/grad bez imena drzave)
     drzava je rucno odredjena na osnovu grada (DRZAVA_OVERRIDE)

dry-run je default; --execute pokrece stvarnu izmjenu (INSERT u izvoznici + DELETE
iz uvoznici), uz CSV backup obrisanih zapisa prije brisanja.
"""
import sys
import csv
import argparse
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

from database.db import get_db_connection

# Firme iz UV##### liste koje su GENUINE BiH (samo nemaju ispravan JIB) — ne diramo
EXCLUDE_JIBS = {"UV00133", "UV00148"}  # Bisprom (Prnjavor), MODUL (Banja Luka)

# Imena stranih drzava koja se mogu pojaviti u adresa/grad poljima
COUNTRY_KEYWORDS = {
    "SRBIJA": "Srbija",
    "REPUBLIKA SRBIJA": "Srbija",
    "MAKEDONIJA": "Makedonija",
    "S.MAKEDONIJA": "Makedonija",
    "CRNA GORA": "Crna Gora",
    "HRVATSKA": "Hrvatska",
    "R.HRVATSKA": "Hrvatska",
    "SLOVENIJA": "Slovenija",
    "SVEDSKA": "Svedska",
    "ŠVEDSKA": "Svedska",
    "CYPRUS": "Cyprus",
}

# Rucno odredjena drzava za zapise gdje adresa/grad NE sadrze ime drzave
# (vec stvarnu ulicu/grad) — odredjeno po poznatom sjedistu firme
DRZAVA_OVERRIDE = {
    "UV00146": "Srbija",       # AGROSOL DOO — Krusevac/Timocke bune
    "UV00591": "Srbija",       # BDR MEDIA DOO — Beograd
    "UV00277": "Srbija",       # ENMON BG — Beograd
    "UV00382": "Makedonija",   # FITLAJF DOOEL SKOPJE — Skopje
    "UV00326": "Srbija",       # GALEB ELECTRONICS doo — Sabac
    "UV00304": "Hrvatska",     # PONTUS PHARMA DOO — Zagreb
    "UV00287": "Srbija",       # RINGIER AXEL SPRINGER — Beograd
    "UV00350": "Srbija",       # SMURFIT KAPPA DOO — Beograd
}


def detect_country(adresa, grad):
    blob = ((adresa or "") + " " + (grad or "")).upper()
    for kw, country in COUNTRY_KEYWORDS.items():
        if kw in blob:
            return country
    return None


def build_plan(cur):
    cur.execute(
        "SELECT jib, naziv, adresa, grad, postanski_broj, drzava, telefon, "
        "email, kontakt, pdv_broj, maticni FROM catalogs.uvoznici "
        "WHERE jib ~ '^UV[0-9]{5}$' ORDER BY naziv"
    )
    rows = [dict(r) for r in cur.fetchall()]

    plan = []
    skipped = []
    for r in rows:
        jib = r["jib"]
        if jib in EXCLUDE_JIBS:
            skipped.append((jib, r["naziv"], "genuine BiH — JIB nedostaje u izvoru"))
            continue
        country = detect_country(r["adresa"], r["grad"]) or DRZAVA_OVERRIDE.get(jib)
        if not country:
            skipped.append((jib, r["naziv"], "drzava nije pouzdano odredjena — preskoceno"))
            continue
        plan.append((r, country))
    return plan, skipped


def next_ex_codes(cur, n):
    cur.execute("SELECT MAX(jib) AS m FROM catalogs.izvoznici WHERE jib ~ '^EX[0-9]{5}$'")
    cur.execute("SELECT jib FROM catalogs.izvoznici WHERE jib ~ '^EX[0-9]{5}$'")
    existing = {r["jib"] for r in cur.fetchall()}
    codes = []
    i = 1
    while len(codes) < n:
        code = f"EX{i:05d}"
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
            plan, skipped = build_plan(cur)

            print(f"Plan premjestanja: {len(plan)} zapisa iz uvoznici -> izvoznici\n")
            for r, country in plan:
                print(f"  {r['jib']} {r['naziv']!r:34} drzava: BIH -> {country}   "
                      f"(adresa={r['adresa']!r}, grad={r['grad']!r})")

            print(f"\nPreskoceno: {len(skipped)}")
            for jib, naziv, razlog in skipped:
                print(f"  {jib} {naziv!r:34} -- {razlog}")

            if not args.execute:
                print("\n[DRY-RUN] Nista nije izmijenjeno. Pokreni sa --execute za stvarno premjestanje.")
                return

            ex_codes = next_ex_codes(cur, len(plan))

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"scripts/_uvoznici_move_backup_deleted_{ts}.csv"
            with open(backup_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["jib", "naziv", "adresa", "grad", "postanski_broj", "drzava",
                            "telefon", "email", "kontakt", "pdv_broj", "maticni", "novi_ex_jib", "nova_drzava"])
                for (r, country), new_jib in zip(plan, ex_codes):
                    w.writerow([r["jib"], r["naziv"], r["adresa"], r["grad"], r["postanski_broj"],
                                r["drzava"], r["telefon"], r["email"], r["kontakt"], r["pdv_broj"],
                                r["maticni"], new_jib, country])
            print(f"\nBackup obrisanih/premjestenih zapisa: {backup_path}")

            for (r, country), new_jib in zip(plan, ex_codes):
                cur.execute(
                    "INSERT INTO catalogs.izvoznici "
                    "(jib, naziv, adresa, grad, drzava, telefon, email, kontakt, pdv_broj, maticni) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (new_jib, r["naziv"], r["adresa"], r["grad"], country,
                     r["telefon"], r["email"], r["kontakt"], r["pdv_broj"], r["maticni"]),
                )
                cur.execute("DELETE FROM catalogs.uvoznici WHERE jib = %s", (r["jib"],))

            conn.commit()
            print(f"\nGotovo: premjesteno {len(plan)} zapisa (uvoznici -> izvoznici, novi EX-kodovi dodijeljeni).")


if __name__ == "__main__":
    main()
