# database/migrate_izjave_o_poreklu.py

"""
Migracija izjava o poreklu iz JSON fajla u PostgreSQL bazu.

Kreira tabelu catalogs.izjave_o_poreklu i puni je šablonima izjava
na različitim jezicima za detekciju prilikom parsiranja PDF faktura.
"""

import json
import re
import psycopg2
import psycopg2.extras
from pathlib import Path
from database.db import POSTGRES_CONFIG


def create_izjave_table():
    """Kreiraj tabelu za izjave o poreklu ako ne postoji."""
    
    create_sql = """
        CREATE TABLE IF NOT EXISTS catalogs.izjave_o_poreklu (
            id SERIAL PRIMARY KEY,
            jezik TEXT NOT NULL,
            tip_izjave TEXT NOT NULL,  -- 'standard' ili 'ovlaseni_izvoznik'
            tekst_izjave TEXT NOT NULL,  -- Šablon izjave
            regex_pattern TEXT NOT NULL,  -- Regex za detekciju u PDF-u
            origin_placeholder TEXT DEFAULT '[origin]',  -- Placeholder za zemlju
            broj_placeholder TEXT DEFAULT '[broj]',  -- Placeholder za broj ovlašćenja
            aktivan BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_izjave_jezik 
        ON catalogs.izjave_o_poreklu(jezik);
        
        CREATE INDEX IF NOT EXISTS idx_izjave_tip 
        ON catalogs.izjave_o_poreklu(tip_izjave);
        
        CREATE INDEX IF NOT EXISTS idx_izjave_aktivan 
        ON catalogs.izjave_o_poreklu(aktivan) WHERE aktivan = TRUE;
        
        COMMENT ON TABLE catalogs.izjave_o_poreklu IS 
        'Šabloni izjava o preferencijalnom poreklu robe na različitim jezicima';
    """
    
    with psycopg2.connect(**POSTGRES_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(create_sql)
            conn.commit()
            print("✅ Tabela catalogs.izjave_o_poreklu kreirana")


def generate_regex_pattern(template: str, origin_placeholder: str = "[origin]") -> str:
    """
    Generiše regex pattern iz šablona izjave.
    
    Primer:
    - Template: "The exporter ... declares that ... these products are of [origin] preferential origin"
    - Regex: "The exporter .*? declares that .*? these products are of (?P<origin>\\w+) preferential origin"
    """
    # Escape special regex characters except placeholder
    pattern = re.escape(template)
    
    # Replace escaped placeholder with named capture group
    origin_escaped = re.escape(origin_placeholder)
    pattern = pattern.replace(origin_escaped, r"(?P<origin>\w+)")
    
    # Make pattern more flexible:
    # - Allow extra spaces
    # - Make punctuation optional
    # - Allow case-insensitive matching
    pattern = pattern.replace(r"\ ", r"\s+")  # Flexible spaces
    pattern = pattern.replace(r"\,", r"\,?")  # Optional comma
    pattern = pattern.replace(r"\.", r"\.?")  # Optional period
    
    # Add word boundaries
    pattern = r"\b" + pattern + r"\b"
    
    return pattern


def load_izjave_from_json(json_path: str) -> list:
    """Učitaj izjave iz JSON fajla i pripremi za unos u bazu."""
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    izjave = []
    
    # Process standard izjave
    standard_templates = data['invoice_declarations']['standard']
    for jezik, template in standard_templates.items():
        regex_pattern = generate_regex_pattern(template)
        izjave.append({
            'jezik': jezik,
            'tip_izjave': 'standard',
            'tekst_izjave': template,
            'regex_pattern': regex_pattern,
        })
    
    # Process izjave ovlašćenog izvoznika
    approved_templates = data['invoice_declarations']['approved_exporter']
    for jezik, template in approved_templates.items():
        regex_pattern = generate_regex_pattern(template)
        izjave.append({
            'jezik': jezik,
            'tip_izjave': 'ovlaseni_izvoznik',
            'tekst_izjave': template,
            'regex_pattern': regex_pattern,
        })
    
    return izjave


def insert_izjave(izjave: list):
    """Unesi izjave u bazu."""
    
    insert_sql = """
        INSERT INTO catalogs.izjave_o_poreklu 
        (jezik, tip_izjave, tekst_izjave, regex_pattern, origin_placeholder, broj_placeholder)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
    """
    
    with psycopg2.connect(**POSTGRES_CONFIG) as conn:
        with conn.cursor() as cur:
            for izjava in izjave:
                cur.execute(insert_sql, (
                    izjava['jezik'],
                    izjava['tip_izjave'],
                    izjava['tekst_izjave'],
                    izjava['regex_pattern'],
                    '[origin]',
                    '[broj]'
                ))
            conn.commit()
            print(f"✅ Uneseno {len(izjave)} izjava u bazu")


def test_regex_patterns():
    """Testiraj generisane regex pattern-e na primerima."""
    
    test_cases = [
        # Standard izjava - srpski
        (
            "Izvoznik proizvoda obuhvaćenih ovom ispravom izjavljuje da su, osim ako je to drugačije izričito navedeno, ovi proizvodi Serbian preferencijalnog porekla.",
            "serbian",
            "standard"
        ),
        # Standard izjava - engleski
        (
            "The exporter of the products covered by this document declares that, except where otherwise clearly indicated, these products are of Slovenian preferential origin.",
            "english",
            "standard"
        ),
        # Approved exporter - nemački
        (
            "Der Ausführer (Ermächtigter Ausführer; Bewilligungs-Nr. 12345) der Waren, auf die sich dieses Handelspapier bezieht, erklärt, dass diese Waren, soweit nicht anders angegeben, Croatian Präferenzursprungswaren sind.",
            "german",
            "ovlaseni_izvoznik"
        ),
    ]
    
    print("\n=== TEST REGEX PATTERNS ===")
    
    with psycopg2.connect(**POSTGRES_CONFIG) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            for test_text, expected_jezik, expected_tip in test_cases:
                cur.execute("""
                    SELECT id, jezik, tip_izjave, regex_pattern
                    FROM catalogs.izjave_o_poreklu
                    WHERE aktivan = TRUE
                    ORDER BY id
                """)
                
                found = False
                for row in cur.fetchall():
                    pattern = row['regex_pattern']
                    match = re.search(pattern, test_text, re.IGNORECASE)
                    if match:
                        origin = match.group('origin') if 'origin' in match.groupdict() else 'N/A'
                        print(f"✅ MATCH: {row['jezik']} / {row['tip_izjave']}")
                        print(f"   Origin: {origin}")
                        print(f"   Pattern: {pattern[:80]}...")
                        found = True
                        break
                
                if not found:
                    print(f"❌ NO MATCH: {expected_jezik} / {expected_tip}")
                    print(f"   Text: {test_text[:80]}...")
                print()


def main():
    """Glavna funkcija za migraciju."""
    
    print("=" * 70)
    print("MIGRACIJA IZJAVA O POREKLU U POSTGRESQL")
    print("=" * 70)
    
    # 1. Kreiraj tabelu
    print("\n1️⃣  Kreiranje tabele...")
    create_izjave_table()
    
    # 2. Učitaj iz JSON
    print("\n2️⃣  Učitavanje iz JSON fajla...")
    json_path = Path(__file__).parent / "izjave_na_fakturi.json"
    izjave = load_izjave_from_json(str(json_path))
    print(f"   Pronađeno {len(izjave)} šablona izjava")
    
    # 3. Unesi u bazu
    print("\n3️⃣  Unos u bazu...")
    insert_izjave(izjave)
    
    # 4. Testiraj pattern-e
    print("\n4️⃣  Testiranje regex pattern-a...")
    test_regex_patterns()
    
    # 5. Prikaži statistiku
    print("\n5️⃣  Statistika:")
    with psycopg2.connect(**POSTGRES_CONFIG) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT jezik, tip_izjave, COUNT(*) as broj
                FROM catalogs.izjave_o_poreklu
                GROUP BY jezik, tip_izjave
                ORDER BY jezik, tip_izjave
            """)
            
            print("   Jezik | Tip izjave | Broj")
            print("   " + "-" * 40)
            for row in cur.fetchall():
                print(f"   {row['jezik']:10} | {row['tip_izjave']:20} | {row['broj']}")
    
    print("\n" + "=" * 70)
    print("✅ MIGRACIJA ZAVRŠENA")
    print("=" * 70)


if __name__ == "__main__":
    main()
