#!/usr/bin/env python3
"""
Skripta za migraciju partnera iz jedinstvene tabele u posebne tabele za izvoznike i uvoznike.
"""

import sys
import os
import json
import psycopg2

# Dodaj root direktorijum u PYTHONPATH
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from database.db import POSTGRES_CONFIG


def setup_tables():
    """Kreiranje potrebnih tabela ako ne postoje."""
    conn = psycopg2.connect(**POSTGRES_CONFIG)
    cursor = conn.cursor()

    # Kreiraj shemu ako ne postoji
    cursor.execute("CREATE SCHEMA IF NOT EXISTS catalogs;")

    # Kreiraj tabele za izvoznike i uvoznike
    create_exporters_sql = '''
    CREATE TABLE IF NOT EXISTS catalogs.izvoznici (
        jib VARCHAR(13) PRIMARY KEY,
        naziv TEXT NOT NULL,
        adresa TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    '''

    create_consignees_sql = '''
    CREATE TABLE IF NOT EXISTS catalogs.uvoznici (
        jib VARCHAR(13) PRIMARY KEY,
        naziv TEXT NOT NULL,
        adresa TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    '''

    cursor.execute(create_exporters_sql)
    cursor.execute(create_consignees_sql)

    conn.commit()
    conn.close()
    print("✅ Tabele catalogs.izvoznici i catalogs.uvoznici su kreirane.")


def migrate_partners():
    """Migracija partnera iz catalogs.partneri u nove tabele."""

    # Učitaj podatke iz JSON fajla da bi znao koji su izvoznici a koji primalaci
    with open('database/traders.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Poveži se sa bazom
    conn = psycopg2.connect(**POSTGRES_CONFIG)
    cursor = conn.cursor()

    print("Migracija izvoznika...")

    # Dodaj sve izvoznike u novu tabelu
    added_count = 0
    for exporter in data['exporters']:
        name = exporter['name'].strip()
        code = exporter['code'].strip() if exporter['code'] else ''

        # Ako nema šifre, generiši jedinstveni JIB na osnovu imena
        if not code:
            # Kreiraj jednostavan JIB na osnovu imena (prvih 13 karaktera, dopuni nulama ako je kraće)
            clean_name = ''.join(c for c in name if c.isalnum()).upper()[:13]
            code = clean_name.ljust(13, '0')[:13]

        # Ubaci u bazu (ili ažuriraj ako već postoji)
        try:
            cursor.execute(
                "INSERT INTO catalogs.izvoznici (jib, naziv, adresa) VALUES (%s, %s, '') ON CONFLICT (jib) DO UPDATE SET naziv = EXCLUDED.naziv",
                (code, name)
            )
            added_count += 1
        except Exception as e:
            print(f'Greška pri dodavanju {name}: {e}')

    conn.commit()
    print(f'Ukupno migrirano izvoznika: {added_count}')

    # Ako imamo i podatke o primalacima, migrirali bismo i njih
    # (u ovom slučaju nemamo u JSON fajlu, ali bi bilo slično)

    # Proveri broj redova nakon migracije
    cursor.execute('SELECT COUNT(*) FROM catalogs.izvoznici;')
    total_exporters = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM catalogs.uvoznici;')
    total_consignees = cursor.fetchone()[0]

    conn.close()

    print(f'Ukupan broj izvoznika u novoj tabeli: {total_exporters}')
    print(f'Ukupan broj uvoznika u novoj tabeli: {total_consignees}')
    print('✅ Migracija završena.')


if __name__ == "__main__":
    setup_tables()
    migrate_partners()