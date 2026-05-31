"""
Skript za indeksiranje carinskih dokumenata (PDF) u PostgreSQL.

Pokretanje:
    python3 database/index_carinski_dokumenti.py

Popunjava tabelu catalogs.carinski_dokumenti u PostgreSQL bazi.
Ako dokument nije promijenjen (isti hash), preskače ga.
"""

import os
import sys
import hashlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "docs", "Carinski dokumenti")


def extract_text(path: str) -> str:
    from pdfminer.high_level import extract_text as _extract
    try:
        return _extract(path) or ""
    except Exception as e:
        print(f"  ⚠️  Greška pri ekstrakciji {os.path.basename(path)}: {e}")
        return ""


def clean_text(text: str) -> str:
    import re
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
    return name[:120] + ('...' if len(name) > 120 else '')


def index_documents():
    from database.db import get_db_connection

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

    dodano = azurirano = preskoceno = 0

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for filename in pdf_files:
                path = os.path.join(DOCS_DIR, filename)
                naziv = friendly_name(filename)
                h = file_hash(path)

                cur.execute(
                    "SELECT id, file_hash FROM catalogs.carinski_dokumenti WHERE filename = %s",
                    (filename,)
                )
                row = cur.fetchone()

                if row and row['file_hash'] == h:
                    print(f"  ⏭️  Preskačem (nije promijenjen): {filename[:65]}")
                    preskoceno += 1
                    continue

                print(f"  📖 Ekstrahujem: {filename[:65]}")
                tekst = clean_text(extract_text(path))

                if not tekst:
                    print(f"  ⚠️  Prazan tekst, preskačem.")
                    preskoceno += 1
                    continue

                if row:
                    cur.execute("""
                        UPDATE catalogs.carinski_dokumenti
                        SET naziv=%s, sadrzaj=%s, file_hash=%s, datum_indeksa=now()
                        WHERE id=%s
                    """, (naziv, tekst, h, row['id']))
                    azurirano += 1
                else:
                    cur.execute("""
                        INSERT INTO catalogs.carinski_dokumenti (naziv, filename, sadrzaj, file_hash)
                        VALUES (%s, %s, %s, %s)
                    """, (naziv, filename, tekst, h))
                    dodano += 1

                print(f"  ✅ {'Ažurirano' if row else 'Dodano'} ({len(tekst):,} znakova)")

    print(f"\n📊 Rezultat: {dodano} dodano, {azurirano} ažurirano, {preskoceno} preskočeno")


if __name__ == "__main__":
    index_documents()
