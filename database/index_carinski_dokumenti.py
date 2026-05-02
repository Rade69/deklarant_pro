"""
Skript za indeksiranje carinskih dokumenata (PDF) u SQLite FTS5 bazu.

Pokretanje:
    python3 database/index_carinski_dokumenti.py

Dodaje/ažurira tabelu carinski_dokumenti u deklarant_sistem.db.
"""

import os
import sys
import sqlite3
import hashlib

# Dodaj root projekta u path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "docs", "Carinski dokumenti")
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deklarant_sistem.db")


def extract_text_pdfminer(path: str) -> str:
    from pdfminer.high_level import extract_text
    try:
        text = extract_text(path)
        return text or ""
    except Exception as e:
        print(f"  ⚠️  Greška pri ekstrakciji {os.path.basename(path)}: {e}")
        return ""


def clean_text(text: str) -> str:
    import re
    # Ukloni višestruke razmake i prazne linije
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text.strip()


def file_hash(path: str) -> str:
    h = hashlib.md5()
    with open(path, 'rb') as f:
        h.update(f.read(65536))
    return h.hexdigest()


def friendly_name(filename: str) -> str:
    name = os.path.splitext(filename)[0]
    name = name.replace('-', ' ').replace('_', ' ')
    # Skrati prevelika imena
    if len(name) > 120:
        name = name[:120] + '...'
    return name


def ensure_tables(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS carinski_dokumenti (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            naziv           TEXT NOT NULL,
            filename        TEXT NOT NULL UNIQUE,
            sadrzaj         TEXT NOT NULL,
            file_hash       TEXT NOT NULL,
            datum_indeksa   TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS carinski_dokumenti_fts
        USING fts5(
            naziv,
            sadrzaj,
            content='carinski_dokumenti',
            content_rowid='id',
            tokenize='unicode61'
        );

        CREATE TRIGGER IF NOT EXISTS cd_ai AFTER INSERT ON carinski_dokumenti BEGIN
            INSERT INTO carinski_dokumenti_fts(rowid, naziv, sadrzaj)
            VALUES (new.id, new.naziv, new.sadrzaj);
        END;

        CREATE TRIGGER IF NOT EXISTS cd_ad AFTER DELETE ON carinski_dokumenti BEGIN
            INSERT INTO carinski_dokumenti_fts(carinski_dokumenti_fts, rowid, naziv, sadrzaj)
            VALUES ('delete', old.id, old.naziv, old.sadrzaj);
        END;

        CREATE TRIGGER IF NOT EXISTS cd_au AFTER UPDATE ON carinski_dokumenti BEGIN
            INSERT INTO carinski_dokumenti_fts(carinski_dokumenti_fts, rowid, naziv, sadrzaj)
            VALUES ('delete', old.id, old.naziv, old.sadrzaj);
            INSERT INTO carinski_dokumenti_fts(rowid, naziv, sadrzaj)
            VALUES (new.id, new.naziv, new.sadrzaj);
        END;
    """)
    conn.commit()


def index_documents():
    if not os.path.isdir(DOCS_DIR):
        print(f"❌ Folder nije pronađen: {DOCS_DIR}")
        return

    pdf_files = sorted([
        f for f in os.listdir(DOCS_DIR)
        if f.lower().endswith('.pdf') and not f.startswith('.')
    ])

    if not pdf_files:
        print("❌ Nema PDF fajlova u folderu.")
        return

    print(f"📂 Folder: {DOCS_DIR}")
    print(f"📄 Pronađeno {len(pdf_files)} PDF fajlova\n")

    conn = sqlite3.connect(DB_PATH)
    ensure_tables(conn)

    dodano = 0
    azurirano = 0
    preskoceno = 0

    for filename in pdf_files:
        path = os.path.join(DOCS_DIR, filename)
        naziv = friendly_name(filename)
        h = file_hash(path)

        # Provjeri da li je već indeksiran sa istim hash-om
        row = conn.execute(
            "SELECT id, file_hash FROM carinski_dokumenti WHERE filename = ?",
            (filename,)
        ).fetchone()

        if row and row[1] == h:
            print(f"  ⏭️  Preskačem (nije promijenjen): {filename[:60]}")
            preskoceno += 1
            continue

        print(f"  📖 Ekstrahujem: {filename[:60]}")
        tekst = clean_text(extract_text_pdfminer(path))

        if not tekst:
            print(f"  ⚠️  Prazan tekst, preskačem.")
            preskoceno += 1
            continue

        if row:
            conn.execute(
                "UPDATE carinski_dokumenti SET naziv=?, sadrzaj=?, file_hash=?, datum_indeksa=datetime('now') WHERE id=?",
                (naziv, tekst, h, row[0])
            )
            azurirano += 1
            print(f"  ✅ Ažurirano ({len(tekst):,} znakova)")
        else:
            conn.execute(
                "INSERT INTO carinski_dokumenti (naziv, filename, sadrzaj, file_hash) VALUES (?,?,?,?)",
                (naziv, filename, tekst, h)
            )
            dodano += 1
            print(f"  ✅ Dodano ({len(tekst):,} znakova)")

        conn.commit()

    print(f"\n📊 Rezultat: {dodano} dodano, {azurirano} ažurirano, {preskoceno} preskočeno")
    print(f"🗄️  Baza: {DB_PATH}")
    conn.close()


if __name__ == "__main__":
    index_documents()
