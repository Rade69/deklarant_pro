#!/usr/bin/env python3
"""
ASYCUDA Pro - Kompletni setup baze podataka
Kreira sve tabele i popunjava ih iz JSON fajlova.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import get_db_connection

BASE = os.path.dirname(os.path.abspath(__file__))

def load(f):
    with open(os.path.join(BASE, f), encoding='utf-8') as fp:
        return json.load(fp)

def run():
    print("🗄️  ASYCUDA Pro - Setup baze podataka")
    print("=" * 50)

    with get_db_connection() as conn:
        cur = conn.cursor()

        # ── Schema ────────────────────────────────────────
        cur.execute("CREATE SCHEMA IF NOT EXISTS catalogs;")
        conn.commit()
        print("✅ Schema catalogs")

        # ── Kreiranje tabela ──────────────────────────────
        cur.execute("""
            CREATE TABLE IF NOT EXISTS catalogs.drzave (
                sifra VARCHAR(5) PRIMARY KEY,
                naziv TEXT NOT NULL DEFAULT ''
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS catalogs.pakovanja (
                sifra VARCHAR(10) PRIMARY KEY,
                opis TEXT NOT NULL DEFAULT ''
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS catalogs.vrste_prijevoza (
                sifra VARCHAR(5) PRIMARY KEY,
                opis TEXT NOT NULL DEFAULT ''
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS catalogs.carinski_postupci (
                sifra VARCHAR(10) PRIMARY KEY,
                vrsta VARCHAR(5) NOT NULL DEFAULT '',
                oznaka VARCHAR(5) NOT NULL DEFAULT '',
                opis TEXT NOT NULL DEFAULT ''
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS catalogs.povlastice (
                sifra TEXT PRIMARY KEY,
                opis TEXT NOT NULL DEFAULT '',
                grupa TEXT NOT NULL DEFAULT '',
                aktivan BOOLEAN DEFAULT TRUE
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS catalogs.prilozeni_dokumenti_sifre (
                sifra TEXT PRIMARY KEY,
                opis TEXT NOT NULL DEFAULT '',
                aktivan BOOLEAN DEFAULT TRUE
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS catalogs.prethodni_dokumenti (
                skracenica VARCHAR(20) PRIMARY KEY,
                vrsta_dokumenta TEXT NOT NULL DEFAULT ''
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS catalogs.izjave_o_poreklu (
                id SERIAL PRIMARY KEY,
                sifra TEXT UNIQUE,
                jezik TEXT NOT NULL DEFAULT 'bs',
                tip_izjave TEXT NOT NULL DEFAULT 'standard',
                tekst_izjave TEXT NOT NULL DEFAULT '',
                regex_pattern TEXT NOT NULL DEFAULT '',
                origin_placeholder TEXT DEFAULT '[origin]',
                broj_placeholder TEXT DEFAULT '[broj]',
                aktivan BOOLEAN DEFAULT TRUE
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS catalogs.vrste_deklaracija (
                id SERIAL PRIMARY KEY,
                sifra VARCHAR(2) NOT NULL,
                oznaka VARCHAR(5) NOT NULL DEFAULT '',
                opis TEXT NOT NULL DEFAULT '',
                UNIQUE(sifra, oznaka)
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS catalogs.regionalni_centri (
                id SERIAL PRIMARY KEY,
                sifra VARCHAR(20) NOT NULL UNIQUE,
                naziv TEXT NOT NULL DEFAULT ''
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS catalogs.carinske_ispostave (
                id SERIAL PRIMARY KEY,
                sifra VARCHAR(20) NOT NULL UNIQUE,
                naziv TEXT NOT NULL DEFAULT '',
                regionalni_centar_id INTEGER REFERENCES catalogs.regionalni_centri(id)
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS catalogs.izvoznici (
                jib VARCHAR(50) PRIMARY KEY,
                naziv TEXT NOT NULL DEFAULT '',
                adresa TEXT DEFAULT '',
                grad TEXT DEFAULT '',
                drzava TEXT DEFAULT '',
                telefon TEXT DEFAULT '',
                email TEXT DEFAULT '',
                kontakt TEXT DEFAULT '',
                pdv_broj TEXT DEFAULT '',
                maticni TEXT DEFAULT ''
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS catalogs.uvoznici (
                jib VARCHAR(50) PRIMARY KEY,
                naziv TEXT NOT NULL DEFAULT '',
                adresa TEXT DEFAULT '',
                grad TEXT DEFAULT '',
                postanski_broj TEXT DEFAULT '',
                drzava TEXT DEFAULT '',
                telefon TEXT DEFAULT '',
                email TEXT DEFAULT '',
                kontakt TEXT DEFAULT '',
                pdv_broj TEXT DEFAULT '',
                maticni TEXT DEFAULT ''
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS catalogs.declarations (
                id SERIAL PRIMARY KEY,
                invoice_number VARCHAR(255) NOT NULL,
                vendor VARCHAR(500),
                buyer VARCHAR(500),
                datum DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS catalogs.declaration_items (
                id SERIAL PRIMARY KEY,
                declaration_id INTEGER REFERENCES catalogs.declarations(id) ON DELETE CASCADE,
                tarifni_broj VARCHAR(20),
                naziv_robe TEXT NOT NULL DEFAULT '',
                zemlja_porijekla VARCHAR(100),
                povlastica VARCHAR(100),
                confidence REAL DEFAULT 0.5,
                ai_suggested BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS catalogs.zvanicna_tarifa (
                tarifni_kod VARCHAR(20) PRIMARY KEY,
                opis TEXT NOT NULL DEFAULT ''
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS catalogs.tarifa_nazivi (
                id SERIAL PRIMARY KEY,
                tarifni_kod VARCHAR(20) NOT NULL,
                naziv TEXT NOT NULL DEFAULT ''
            );
        """)
        # Knowledge Base tabele (za zakonsku regulativu / PDF chunking)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.knowledge_base_docs (
                id          SERIAL PRIMARY KEY,
                filename    TEXT UNIQUE NOT NULL,
                title       TEXT NOT NULL DEFAULT '',
                file_path   TEXT NOT NULL DEFAULT '',
                file_hash   TEXT NOT NULL DEFAULT '',
                page_count  INTEGER DEFAULT 0,
                chunk_count INTEGER DEFAULT 0,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.knowledge_base_chunks (
                id          SERIAL PRIMARY KEY,
                doc_id      INTEGER REFERENCES public.knowledge_base_docs(id) ON DELETE CASCADE,
                chunk_index INTEGER NOT NULL DEFAULT 0,
                page_number INTEGER NOT NULL DEFAULT 0,
                chunk_text  TEXT NOT NULL DEFAULT ''
            );
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_kb_chunks_doc_id
            ON public.knowledge_base_chunks(doc_id);
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS catalogs.product_tariff_mapping (
                id SERIAL PRIMARY KEY,
                product_code TEXT,
                naziv_robe TEXT,
                tarifni_broj VARCHAR(20),
                confidence REAL DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        print("✅ Sve tabele kreirane")

        # ── Punjenje podataka ─────────────────────────────
        print("\n📦 Punjenje podataka...")

        # Drzave
        data = load('drzave.json')
        for r in data:
            cur.execute("""
                INSERT INTO catalogs.drzave (sifra, naziv)
                VALUES (%s, %s) ON CONFLICT (sifra) DO UPDATE SET naziv=EXCLUDED.naziv
            """, (r['sifra'], r['naziv']))
        conn.commit()
        print(f"✅ Države: {len(data)}")

        # Pakovanja
        data = load('sifra_pakovanja.json')
        for r in data:
            cur.execute("""
                INSERT INTO catalogs.pakovanja (sifra, opis)
                VALUES (%s, %s) ON CONFLICT (sifra) DO UPDATE SET opis=EXCLUDED.opis
            """, (r['sifra'], r.get('naziv', '')))
        conn.commit()
        print(f"✅ Pakovanja: {len(data)}")

        # Vrste prijevoza
        data = load('sifre_vrste_prijevoza_polje25_26.json')
        for r in data:
            cur.execute("""
                INSERT INTO catalogs.vrste_prijevoza (sifra, opis)
                VALUES (%s, %s) ON CONFLICT (sifra) DO UPDATE SET opis=EXCLUDED.opis
            """, (str(r['sifra']), r.get('opis', r.get('naziv', ''))))
        conn.commit()
        print(f"✅ Vrste prijevoza: {len(data)}")

        # Carinski postupci
        data = load('carinski_postupci.json')
        for r in data:
            cur.execute("""
                INSERT INTO catalogs.carinski_postupci (sifra, vrsta, oznaka, opis)
                VALUES (%s, %s, %s, %s) ON CONFLICT (sifra) DO UPDATE
                SET vrsta=EXCLUDED.vrsta, oznaka=EXCLUDED.oznaka, opis=EXCLUDED.opis
            """, (r.get('sifra',''), r.get('vrsta',''), r.get('oznaka',''), r.get('opis','')))
        conn.commit()
        print(f"✅ Carinski postupci: {len(data)}")

        # Povlastice
        data = load('povlastice.json')
        for r in data:
            cur.execute("""
                INSERT INTO catalogs.povlastice (sifra, opis, grupa)
                VALUES (%s, %s, %s) ON CONFLICT (sifra) DO UPDATE SET opis=EXCLUDED.opis
            """, (r.get('sifra',''), r.get('opis',''), r.get('grupa', '')))
        conn.commit()
        print(f"✅ Povlastice: {len(data)}")

        # Priloženi dokumenti
        data = load('prilozbeni_dokumenti_sifre.json')
        for r in data:
            cur.execute("""
                INSERT INTO catalogs.prilozeni_dokumenti_sifre (sifra, opis)
                VALUES (%s, %s) ON CONFLICT (sifra) DO UPDATE SET opis=EXCLUDED.opis
            """, (r.get('sifra',''), r.get('opis','')))
        conn.commit()
        print(f"✅ Priloženi dokumenti: {len(data)}")

        # Prethodni dokumenti (Rb.40)
        data = load('popis_skracenica_dokumenta_polje40.json')
        for r in data:
            cur.execute("""
                INSERT INTO catalogs.prethodni_dokumenti (skracenica, vrsta_dokumenta)
                VALUES (%s, %s) ON CONFLICT (skracenica) DO UPDATE SET vrsta_dokumenta=EXCLUDED.vrsta_dokumenta
            """, (r['skracenica'], r['vrsta_dokumenta']))
        conn.commit()
        print(f"✅ Prethodni dokumenti (Rb.40): {len(data)}")

        # Izjave o porijeklu
        data = load('izjave_na_fakturi.json')
        count = 0
        decls = data.get('invoice_declarations', {})
        for tip, jezici in decls.items():
            for jezik, tekst in jezici.items():
                sifra = f"{tip}_{jezik}"
                cur.execute("""
                    INSERT INTO catalogs.izjave_o_poreklu (sifra, jezik, tip_izjave, tekst_izjave, regex_pattern)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (sifra) DO UPDATE SET tekst_izjave=EXCLUDED.tekst_izjave
                """, (sifra, jezik, tip, tekst, tekst[:500]))
                count += 1
        conn.commit()
        print(f"✅ Izjave o porijeklu: {count}")

        # Vrste deklaracija
        data = load('sifre_vrste_carinske_deklaracije_polje1_v2.json')
        count = 0
        for stavka in data.get('polje_1_1', {}).get('sifre', []):
            sifra = stavka['sifra']
            oznaka = stavka.get('oznaka_vrste_postupka_mrn', '')
            opis = stavka.get('opis', '')
            cur.execute("""
                INSERT INTO catalogs.vrste_deklaracija (sifra, oznaka, opis)
                VALUES (%s, %s, %s) ON CONFLICT (sifra, oznaka) DO UPDATE SET opis=EXCLUDED.opis
            """, (sifra, oznaka, opis))
            count += 1
        conn.commit()
        print(f"✅ Vrste deklaracija: {count}")
        
        # Tipovi deklaracija
        count = 0
        for stavka in data.get('polje_1_2', {}).get('sifre', []):
            sifra = stavka['sifra']
            opis = stavka.get('opis', '')
            cur.execute("""
                INSERT INTO catalogs.tipovi_deklaracija (sifra, opis)
                VALUES (%s, %s) ON CONFLICT (sifra) DO UPDATE SET opis=EXCLUDED.opis
            """, (sifra, opis))
            count += 1
        conn.commit()
        print(f"✅ Tipovi deklaracija: {count}")

        # Regionalni centri i carinske ispostave
        data = load('organizacija.json')
        rc_count = 0
        ci_count = 0
        for region in data:
            rc_text = region['regionalni_centar']
            rc_sifra = rc_text.split()[-1]
            rc_naziv = ' '.join(rc_text.split()[:-1])
            cur.execute("""
                INSERT INTO catalogs.regionalni_centri (sifra, naziv)
                VALUES (%s, %s) ON CONFLICT (sifra) DO UPDATE SET naziv=EXCLUDED.naziv
                RETURNING id
            """, (rc_sifra, rc_naziv))
            row = cur.fetchone()
            if row:
                rc_id = row['id']
            else:
                cur.execute("SELECT id FROM catalogs.regionalni_centri WHERE sifra=%s", (rc_sifra,))
                rc_id = cur.fetchone()['id']
            rc_count += 1
            for i in region.get('ispostave', []):
                cur.execute("""
                    INSERT INTO catalogs.carinske_ispostave (sifra, naziv, regionalni_centar_id)
                    VALUES (%s, %s, %s) ON CONFLICT (sifra) DO UPDATE
                    SET naziv=EXCLUDED.naziv, regionalni_centar_id=EXCLUDED.regionalni_centar_id
                """, (i['sifra'], i['naziv'], rc_id))
                ci_count += 1
        conn.commit()
        print(f"✅ Regionalni centri: {rc_count}, Carinske ispostave: {ci_count}")

        # Izvoznici iz exporters.json
        data = load('exporters.json')
        count = 0
        for i, r in enumerate(data):
            jib = str(r.get('code') or f"EX{i+1:05d}")[:50]
            cur.execute("""
                INSERT INTO catalogs.izvoznici (jib, naziv, adresa, grad, drzava)
                VALUES (%s, %s, %s, %s, %s) ON CONFLICT (jib) DO UPDATE
                SET naziv=EXCLUDED.naziv, adresa=EXCLUDED.adresa
            """, (jib, r.get('name','')[:500], r.get('address','')[:500],
                  r.get('city','')[:200], r.get('country','')[:100]))
            count += 1
        conn.commit()
        print(f"✅ Izvoznici (pošiljaoci): {count}")

        # Uvoznici iz consignees.json
        data = load('consignees.json')
        count = 0
        for i, r in enumerate(data):
            jib = str(r.get('code') or f"UV{i+1:05d}")[:50]
            cur.execute("""
                INSERT INTO catalogs.uvoznici (jib, naziv, adresa, grad, drzava)
                VALUES (%s, %s, %s, %s, %s) ON CONFLICT (jib) DO UPDATE
                SET naziv=EXCLUDED.naziv, adresa=EXCLUDED.adresa
            """, (jib, r.get('name','')[:500], r.get('address','')[:500],
                  r.get('city','')[:200], r.get('country','')[:100]))
            count += 1
        conn.commit()
        print(f"✅ Uvoznici (primaoci): {count}")

        print("\n🎉 Setup završen! Baza je spremna.")

if __name__ == "__main__":
    run()
