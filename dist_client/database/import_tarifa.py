#!/usr/bin/env python3
"""
Import carinske tarife za 2026 iz PDF-a u PostgreSQL bazu.
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import get_db_connection

PDF_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'docs', 'Carinska_tarifa_za_2026_-_bosanski.pdf')

def parse_tarifa():
    import pdfplumber
    tarife = {}

    with pdfplumber.open(PDF_PATH) as pdf:
        total = len(pdf.pages)
        print(f"📄 PDF: {total} stranica")

        for i, page in enumerate(pdf.pages[20:], start=21):
            if i % 50 == 0:
                print(f"  Obrađujem stranicu {i}/{total}...")

            words = page.extract_words()
            if not words:
                continue

            # Grupiši words po y koordinati (isti red)
            rows = {}
            for w in words:
                y = round(w['top'], 0)
                if y not in rows:
                    rows[y] = []
                rows[y].append(w['text'])

            prev_kod = None
            prev_naziv = None

            for y in sorted(rows.keys()):
                line = ' '.join(rows[y])

                # Puna tarifna oznaka: 4+2+2+2 cifre
                m = re.match(r'^(\d{4}\s\d{2}\s\d{2}\s\d{2})\s(.+)', line)
                if m:
                    if prev_kod and prev_naziv:
                        tarife[prev_kod] = prev_naziv
                    prev_kod = m.group(1).replace(' ', '')
                    naziv = m.group(2).strip()
                    naziv = re.sub(r'\s+\d[\d\.\s]+$', '', naziv).strip()
                    naziv = re.sub(r'\s+(kd|kg|l|m|p/st|ce/el|g|c/k|ct/l)\s*$', '', naziv).strip()
                    prev_naziv = naziv
                    continue

                # Podglava: 4+2 ili 4+2+2 cifre
                m2 = re.match(r'^(\d{4}\s\d{2}(?:\s\d{2})?)\s[–\-]\s*(.+)', line)
                if m2:
                    if prev_kod and prev_naziv:
                        tarife[prev_kod] = prev_naziv
                    prev_kod = m2.group(1).replace(' ', '')
                    naziv = m2.group(2).strip()
                    naziv = re.sub(r'\s+\d[\d\.\s]+$', '', naziv).strip()
                    prev_naziv = naziv
                    prev_kod = None  # Podglave ne upisujemo bez punog koda
                    continue

                # Nastavak prethodnog naziva (višeredni tekst)
                if prev_kod and not re.match(r'^\d', line) and not re.match(r'^[1-9]\s', line):
                    if len(line) > 3 and not re.match(r'^(EU|CEFTA|IRN|TUR|EFTA|CHE|ISL|NOR)', line):
                        prev_naziv = (prev_naziv + ' ' + line).strip()

            if prev_kod and prev_naziv:
                tarife[prev_kod] = prev_naziv

    return tarife


def run():
    print("📦 Import carinske tarife 2026")
    print("=" * 50)

    tarife = parse_tarifa()
    print(f"\n✅ Parsiranih oznaka: {len(tarife)}")

    if not tarife:
        print("❌ Nema podataka za uvoz!")
        return

    with get_db_connection() as conn:
        cur = conn.cursor()

        # Obriši stare podatke
        cur.execute("DELETE FROM catalogs.zvanicna_tarifa")
        conn.commit()
        print("🗑️  Stari podaci obrisani")

        # Upiši nove
        count = 0
        batch = []
        for kod, naziv in tarife.items():
            batch.append((kod, naziv[:1000]))
            if len(batch) >= 500:
                cur.executemany("""
                    INSERT INTO catalogs.zvanicna_tarifa (tarifni_kod, opis)
                    VALUES (%s, %s) ON CONFLICT (tarifni_kod) DO UPDATE SET opis=EXCLUDED.opis
                """, batch)
                count += len(batch)
                batch = []

        if batch:
            cur.executemany("""
                INSERT INTO catalogs.zvanicna_tarifa (tarifni_kod, opis)
                VALUES (%s, %s) ON CONFLICT (tarifni_kod) DO UPDATE SET opis=EXCLUDED.opis
            """, batch)
            count += len(batch)

        conn.commit()
        print(f"✅ Uvezeno {count} tarifnih oznaka")
        print("\n🎉 Tarifa je uvezena u bazu!")


if __name__ == "__main__":
    run()
