#!/usr/bin/env python3
"""
Import skripte za punjenje tabele catalogs.tariff_controls
iz PDFa: B-H-Objededinjeni-spisak-03-2015.pdf

Koristi extract_words() pristup (isti kao import_tarifa.py):
  - Rijeci se grupisu po y koordinati (isti red)
  - Kolona se odredjuje po x koordinati (kalibracija iz analize PDFa)

Pokretanje:
    cd /home/radovan/Desktop/deklarant_pro
    .venv/bin/python3 database/import_tariff_controls.py [--dry-run] [--csv]
"""

import sys
import re
import csv
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

PDF_PATH = ROOT / "docs" / "Carinski dokumenti" / "B-H-Objededinjeni-spisak-03-2015.pdf"

# X-granice kolona kalibrirane iz analize PDFa (str.1):
#   Col 2  Tar.broj (4-cif.heading): x ≈ 65–115  (npr. "0301" na x=71)
#   Col 3  Tarifna oznaka (10-cif.): x ≈ 115–190 (npr. "0407","19","90","00" na x=116–154)
#   Col 4  Naimenovanje:             x ≈ 190–420 (tekst pocinje na x=190)
#   Col 5  SAN:                      x ≈ 420–510 ("+" na x=440)
#   Col 6  VET:                      x ≈ 510–575 ("+" na x=521)
#   Col 7  FIT:                      x ≈ 575–630 ("+" na x=588)
#   Col 8  UVK:                      x ≈ 630–695 ("+" na x=648)
#   Col 9  Agencija:                 x ≈ 695–750 ("+" na x=709)
#   Col 10 Dozvole:                  x ≈ 750–842 (tekst na x=763)
COL_X = [
    ("glava",   0,    65),
    ("tar_br",  65,   115),
    ("tar_oz",  115,  190),
    ("naziv",   190,  420),
    ("san",     420,  510),
    ("vet",     510,  575),
    ("fit",     575,  630),
    ("uvk",     630,  695),
    ("agencija",695,  750),
    ("dozvola", 750,  900),
]


def col_for(x: float) -> str:
    for name, x0, x1 in COL_X:
        if x0 <= x < x1:
            return name
    return "dozvola"


def parse_pdf(pdf_path: str) -> list[dict]:
    """
    Parsira PDF koristeci extract_words() i vrati listu redova:
    {tarifni_broj, naimenovanje, san, vet, fit, uvk, agencija, dozvola, napomena}
    """
    try:
        import pdfplumber
    except ImportError:
        print("❌ pdfplumber nije instaliran.")
        sys.exit(1)

    results = []

    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)
        print(f"📄 PDF ima {total} stranica")

        for page_num, page in enumerate(pdf.pages, 1):
            if page_num > 22:   # stranice 23-25 su legenda
                break

            words = page.extract_words(x_tolerance=3, y_tolerance=3)
            if not words:
                print(f"  str. {page_num}: prazna")
                continue

            # Grupiši rijeci po y (zaokruži na 2pt za stabilnost)
            lines: dict[float, list] = {}
            for w in words:
                y = round(w["top"] / 2) * 2
                lines.setdefault(y, []).append(w)

            page_rows = _parse_lines(lines)
            results.extend(page_rows)
            print(f"  str. {page_num}/{total}: {len(page_rows)} redova")

    print(f"✅ Ukupno: {len(results)} redova")
    return results


def _parse_lines(lines: dict) -> list[dict]:
    results = []
    pending = None   # Akumulira podatke dok ne dodjemo do novog tarifnog broja

    for y in sorted(lines.keys()):
        words = sorted(lines[y], key=lambda w: w["x0"])

        # Rasporedi rijeci u kolone
        cols: dict[str, list[str]] = {n: [] for n, *_ in COL_X}
        for w in words:
            cols[col_for(w["x0"])].append(w["text"])

        tar_br  = "".join(cols["tar_br"]).strip()    # 4-cifreni heading
        tar_oz  = "".join(cols["tar_oz"]).strip()    # dijelovi 10-cifrenog broja
        naziv   = " ".join(cols["naziv"]).strip()

        has_san = "+" in " ".join(cols["san"])
        has_vet = "+" in " ".join(cols["vet"])
        has_fit = "+" in " ".join(cols["fit"])
        has_uvk = "+" in " ".join(cols["uvk"])
        has_agc = "+" in " ".join(cols["agencija"])
        has_doz = "+" in " ".join(cols["dozvola"])
        any_ctrl = any([has_san, has_vet, has_fit, has_uvk, has_agc, has_doz])

        # Preskoci zaglavlje tabele (redovi s brojevima 2-10 ili textovima kolona)
        if re.match(r'^[2-9]$|^10$', tar_br) and not naziv:
            continue
        if naziv in ("Naimenovanje", "4") or tar_br in ("Tar.", "broj"):
            continue

        # ---- Slucaj 1: Puna tarifna oznaka (10 cifara u tar_oz koloni) ----
        digits_oz = re.sub(r'\D', '', tar_oz)
        if re.match(r'^\d{10}$', digits_oz):
            _flush(pending, results)
            pending = {
                "tarifni_broj": digits_oz,
                "naimenovanje": naziv,
                "san": has_san, "vet": has_vet, "fit": has_fit,
                "uvk": has_uvk, "agencija": has_agc, "dozvola": has_doz,
                "_notes": _collect_notes(cols),
            }
            continue

        # ---- Slucaj 2: Heading (4 cifre u tar_br koloni) ----
        digits_br = re.sub(r'\D', '', tar_br)
        if re.match(r'^\d{4}$', digits_br):
            _flush(pending, results)
            pending = {
                "tarifni_broj": digits_br,
                "naimenovanje": naziv if naziv else "Kompletan tarifni broj",
                "san": has_san, "vet": has_vet, "fit": has_fit,
                "uvk": has_uvk, "agencija": has_agc, "dozvola": has_doz,
                "_notes": _collect_notes(cols),
            }
            continue

        # ---- Slucaj 3: Nastavak prethodnog reda (višeredni naziv ili kontrole) ----
        if pending:
            if naziv:
                pending["naimenovanje"] = (pending["naimenovanje"] + " " + naziv).strip()
            if any_ctrl:
                pending["san"] = pending["san"] or has_san
                pending["vet"] = pending["vet"] or has_vet
                pending["fit"] = pending["fit"] or has_fit
                pending["uvk"] = pending["uvk"] or has_uvk
                pending["agencija"] = pending["agencija"] or has_agc
                pending["dozvola"] = pending["dozvola"] or has_doz
                extra = _collect_notes(cols)
                if extra:
                    pending["_notes"] = (pending["_notes"] + " | " + extra).strip(" |")
            continue

        # Redovi bez tarifnog broja i bez prethodnog konteksta — preskoci
    _flush(pending, results)
    return results


def _collect_notes(cols: dict) -> str:
    """Prikupi neobičan tekst iz kontrolnih kolona (uvjetovane napomene)."""
    parts = []
    for col in ["san", "vet", "fit", "uvk", "agencija", "dozvola"]:
        text = " ".join(cols[col]).replace("+", "").replace("*", "").strip()
        if text and len(text) > 1:
            parts.append(text)
    return "; ".join(parts)


def _flush(pending: dict | None, results: list) -> None:
    """Spremi pending red u results ako ima barem jednu kontrolu."""
    if pending is None:
        return
    notes = pending.pop("_notes", "")
    if any([pending["san"], pending["vet"], pending["fit"],
            pending["uvk"], pending["agencija"], pending["dozvola"]]):
        pending["napomena"] = notes[:300]
        pending["naimenovanje"] = pending["naimenovanje"][:500]
        results.append(pending)


def export_csv(rows: list[dict], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "tarifni_broj", "naimenovanje", "san", "vet", "fit", "uvk",
            "agencija", "dozvola", "napomena"
        ])
        writer.writeheader()
        writer.writerows(rows)
    print(f"📊 CSV sačuvan: {path}")


def run_migration(conn) -> None:
    migration_file = ROOT / "database" / "migrations" / "003_tariff_controls.sql"
    if not migration_file.exists():
        print("⚠️  Migracijski fajl 003 nije pronađen")
        return
    sql = migration_file.read_text(encoding="utf-8")

    # Ukloni komentare (linije koje počinju sa --) PRIJE splita po ";"
    # Bug: ako SQL počinje komentarima, cijeli prvi blok bi bio filtriran
    lines_no_comments = "\n".join(
        line for line in sql.splitlines()
        if not line.strip().startswith("--")
    )
    statements = [s.strip() for s in lines_no_comments.split(";") if s.strip()]

    for stmt in statements:
        try:
            with conn.cursor() as cur:
                cur.execute(stmt)
            conn.commit()
        except Exception as e:
            conn.rollback()
            if "already exists" in str(e):
                print(f"  ℹ️  Vec postoji (OK)")
            else:
                print(f"  ⚠️  SQL greška: {e}")
    print("✅ Migracija 003 primijenjena")


def import_to_db(rows: list[dict]) -> None:
    from database.db import get_db_connection

    with get_db_connection() as conn:
        run_migration(conn)

        inserted = updated = skipped = 0
        for row in rows:
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO catalogs.tariff_controls
                            (tarifni_broj, naimenovanje, san, vet, fit, uvk,
                             agencija, dozvola, napomena)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (tarifni_broj) DO UPDATE SET
                            naimenovanje = EXCLUDED.naimenovanje,
                            san      = EXCLUDED.san      OR catalogs.tariff_controls.san,
                            vet      = EXCLUDED.vet      OR catalogs.tariff_controls.vet,
                            fit      = EXCLUDED.fit      OR catalogs.tariff_controls.fit,
                            uvk      = EXCLUDED.uvk      OR catalogs.tariff_controls.uvk,
                            agencija = EXCLUDED.agencija OR catalogs.tariff_controls.agencija,
                            dozvola  = EXCLUDED.dozvola  OR catalogs.tariff_controls.dozvola,
                            napomena = EXCLUDED.napomena
                    """, (
                        row["tarifni_broj"], row["naimenovanje"],
                        row["san"], row["vet"], row["fit"], row["uvk"],
                        row["agencija"], row["dozvola"], row["napomena"],
                    ))
                conn.commit()
                inserted += 1
            except Exception as e:
                conn.rollback()
                print(f"  ⚠️  Greška za {row.get('tarifni_broj')}: {e}")
                skipped += 1

        print(f"\n✅ Import završen: {inserted} uneseno, {skipped} preskočeno")


def verify(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) as n FROM catalogs.tariff_controls")
        total = cur.fetchone()["n"]
        cur.execute("""
            SELECT COUNT(*) as n FROM catalogs.tariff_controls
            WHERE san OR vet OR fit OR uvk OR agencija OR dozvola
        """)
        with_ctrl = cur.fetchone()["n"]
    print(f"📊 Tabela tariff_controls: {total} redova, {with_ctrl} sa kontrolom")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    to_csv  = "--csv"     in sys.argv

    print("=" * 60)
    print("BiH UIO Objedinjen spisak — parser i import")
    print("=" * 60)

    if not PDF_PATH.exists():
        print(f"❌ PDF nije pronađen: {PDF_PATH}")
        sys.exit(1)

    rows = parse_pdf(str(PDF_PATH))

    with_ctrl = [r for r in rows if any([r["san"],r["vet"],r["fit"],
                                         r["uvk"],r["agencija"],r["dozvola"]])]
    print(f"\n📋 Statistika:")
    print(f"   Ukupno redova:  {len(rows)}")
    print(f"   Sa kontrolom:   {len(with_ctrl)}")

    print(f"\n   Primjer (prvih 15 sa kontrolom):")
    for r in with_ctrl[:15]:
        ctrl = "/".join(k.upper() for k in ["san","vet","fit","uvk","agencija","dozvola"] if r[k])
        print(f"   {r['tarifni_broj']:10} | {ctrl:28} | {r['naimenovanje'][:38]}")

    if to_csv:
        export_csv(rows, str(ROOT / "database" / "tariff_controls_export.csv"))

    if dry_run:
        print("\n⚠️  Dry run — baza nije ažurirana")
    else:
        print("\n📥 Uvoz u PostgreSQL...")
        import_to_db(rows)
        from database.db import get_db_connection
        with get_db_connection() as conn:
            verify(conn)
