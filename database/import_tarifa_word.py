#!/usr/bin/env python3
"""
Import carinske tarife 2026 iz Word dokumenta u SQLite bazu.

Struktura Word tabele (12 kolona):
  col0: prazno
  col1: tarifna oznaka (npr. "0101 21 00 00" ili "0101")
  col2: naziv robe
  col3: dopunska jedinica mjere
  col4: carinska stopa uvozna (%)
  col5: EU stopa
  col6: CEFTA stopa
  col7: IRN stopa
  col8: TUR stopa
  col9-11: EFTA (CHE, LIE, ISL, NOR)

Parsira sve tabele sa 12 kolona i ubacuje u SQLite tabelu tarifa_2026.
"""

import sys
import os
import re
import sqlite3
import docx

WORD_PATH = '/home/radovan/Downloads/Prijedlog odluke o utvrđivanju Carinske tarife za 2026. godinu.docx'
DB_PATH = os.path.join(os.path.dirname(__file__), 'deklarant_sistem.db')


def normalize_kod(raw: str) -> str:
    """Ukloni razmake iz tarifne oznake: '0101 21 00 00' → '0101210000'"""
    return re.sub(r'\s+', '', raw.strip())


def is_tariff_code(s: str) -> bool:
    """Provjeri da li je string tarifna oznaka (4-12 cifara, opciono razmaci)."""
    clean = normalize_kod(s)
    return bool(re.match(r'^\d{4,12}$', clean))


def parse_stopa(s: str) -> str:
    """Normalizuj stopu: '0' → '0%', '5' → '5%', '' → ''"""
    s = s.strip()
    if not s:
        return ''
    # Može biti broj ili "0" ili posebne oznake
    return s


def parse_word_tarifa():
    """Parsira Word dokument i vraća listu redova tarife."""
    print(f"📖 Otvaranje Word dokumenta...")
    doc = docx.Document(WORD_PATH)
    print(f"   {len(doc.tables)} tabela pronađeno")

    rows = []
    current_chapter = ''
    current_chapter_name = ''

    for ti, table in enumerate(doc.tables):
        ncol = len(table.columns)
        if ncol < 10:
            continue  # Preskoči ne-tarifne tabele

        # Izvuci poglavlje iz paragrafa ispred tabele (ako postoji)
        # Prođi kroz redove tabele (preskoči header redove - prve 3-4)
        data_start = 0
        for ri, row in enumerate(table.rows[:6]):
            cells = [c.text.strip() for c in row.cells]
            # Header red ima "Tarifna oznaka", "Naziv" itd.
            if 'Naziv' in cells or 'naziv' in cells[2] if len(cells) > 2 else False:
                data_start = ri + 1
            # Red s brojevima (1, 2, 3...) je zadnji header red
            if cells[0] == '1' or (len(cells) > 1 and cells[1] == '1'):
                data_start = ri + 1
                break

        for ri in range(data_start, len(table.rows)):
            row = table.rows[ri]
            cells = [c.text.strip() for c in row.cells]
            if len(cells) < 10:
                continue

            kod_raw = cells[1]
            naziv = cells[2]
            dopunska_jm = cells[3] if len(cells) > 3 else ''
            stopa_uvozna = cells[4] if len(cells) > 4 else ''
            stopa_eu = cells[5] if len(cells) > 5 else ''
            stopa_cefta = cells[6] if len(cells) > 6 else ''

            # Preskoči prazne i header redove
            if not kod_raw or not naziv:
                continue
            if naziv in ('Naziv', 'naziv', '2', 'Dopunska jedinica'):
                continue
            if not is_tariff_code(kod_raw):
                continue

            kod = normalize_kod(kod_raw)

            # Odredi nivo (glava, podglava, tarifni broj)
            nivo = len(kod)
            if nivo <= 4:
                nivo_naziv = 'glava'
                # Ažuriraj trenutno poglavlje
                current_chapter = kod[:2]
                current_chapter_name = naziv
            elif nivo <= 6:
                nivo_naziv = 'podglava'
            elif nivo <= 8:
                nivo_naziv = 'tarifni_broj'
            else:
                nivo_naziv = 'podbroj'

            rows.append({
                'kod': kod,
                'poglavlje': kod[:2].zfill(2),
                'naziv': naziv,
                'dopunska_jm': dopunska_jm,
                'stopa_uvozna': parse_stopa(stopa_uvozna),
                'stopa_eu': parse_stopa(stopa_eu),
                'stopa_cefta': parse_stopa(stopa_cefta),
                'nivo': nivo_naziv,
            })

    return rows


def create_table(conn: sqlite3.Connection):
    conn.execute("DROP TABLE IF EXISTS tarifa_2026")
    conn.execute("""
        CREATE TABLE tarifa_2026 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kod TEXT NOT NULL,
            poglavlje TEXT NOT NULL,
            naziv TEXT NOT NULL,
            dopunska_jm TEXT DEFAULT '',
            stopa_uvozna TEXT DEFAULT '',
            stopa_eu TEXT DEFAULT '',
            stopa_cefta TEXT DEFAULT '',
            nivo TEXT DEFAULT 'podbroj'
        )
    """)
    conn.execute("CREATE INDEX idx_tarifa_kod ON tarifa_2026(kod)")
    conn.execute("CREATE INDEX idx_tarifa_poglavlje ON tarifa_2026(poglavlje)")
    # FTS tabela za pretragu po nazivu
    conn.execute("DROP TABLE IF EXISTS tarifa_2026_fts")
    conn.execute("""
        CREATE VIRTUAL TABLE tarifa_2026_fts USING fts5(
            kod,
            naziv,
            content=tarifa_2026,
            content_rowid=id
        )
    """)
    conn.commit()


def import_rows(conn: sqlite3.Connection, rows: list):
    conn.executemany("""
        INSERT INTO tarifa_2026 (kod, poglavlje, naziv, dopunska_jm, stopa_uvozna, stopa_eu, stopa_cefta, nivo)
        VALUES (:kod, :poglavlje, :naziv, :dopunska_jm, :stopa_uvozna, :stopa_eu, :stopa_cefta, :nivo)
    """, rows)
    # Popuni FTS
    conn.execute("""
        INSERT INTO tarifa_2026_fts(rowid, kod, naziv)
        SELECT id, kod, naziv FROM tarifa_2026
    """)
    conn.commit()


def main():
    print("🚀 Import carinske tarife 2026 u SQLite\n")

    rows = parse_word_tarifa()
    print(f"\n✅ Parsirano: {len(rows)} redova tarife")

    if not rows:
        print("❌ Nema redova za uvoz!")
        sys.exit(1)

    # Statistika
    by_nivo = {}
    for r in rows:
        by_nivo[r['nivo']] = by_nivo.get(r['nivo'], 0) + 1
    for nivo, count in sorted(by_nivo.items()):
        print(f"   {nivo}: {count}")

    # Provjeri duplikate
    kodovi = [r['kod'] for r in rows]
    unique = len(set(kodovi))
    print(f"   Jedinstveni kodovi: {unique} / {len(rows)}")

    print(f"\n💾 Uvoz u SQLite: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    create_table(conn)
    import_rows(conn, rows)

    # Provjera
    count = conn.execute("SELECT COUNT(*) FROM tarifa_2026").fetchone()[0]
    sample = conn.execute(
        "SELECT kod, naziv, stopa_uvozna FROM tarifa_2026 WHERE nivo='podbroj' LIMIT 5"
    ).fetchall()

    print(f"\n✅ Uvezeno {count} redova u tarifa_2026")
    print("\nPrimjeri (podbroj):")
    for kod, naziv, stopa in sample:
        print(f"  {kod:12s} | {naziv[:50]:50s} | {stopa}%")

    conn.close()
    print("\n🎉 Gotovo!")


if __name__ == '__main__':
    main()
