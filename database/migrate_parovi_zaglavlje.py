#!/usr/bin/env python3
"""
Migracija: Kreira tabelu parovi_zaglavlje i uvozi parsirane podatke iz XML fajlova.

Ova tabela čuva "parove" - svaki XML fajl ima svog izvoznika i uvoznika (consignee).
Korisnik je konsolidovao XML fajlove po consignee grupama (790 grupa).

Pokretanje:
    python database/migrate_parovi_zaglavlje.py
"""

import sys
import os
import re
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db import get_db_connection

# Putanje do XML foldera
XML_FOLDERS = [
    Path("/home/radovan/Desktop/asycuda_pro/data/xml_deklaracije"),
    Path("/home/radovan/Desktop/asycuda_pro/docs/NOVA ASIKUDA"),
]

# Pravne forme za normalizaciju
_LEGAL_FORMS = re.compile(
    r'\b(D\.O\.O|DOO|D\.D\.|DD|A\.D\.|AD|S\.P\.|SP|J\.D\.O\.O\.|JDOO|LLC|LTD|GMBH|CO)\b',
    re.IGNORECASE,
)


def normalize_naziv(naziv: str) -> str:
    """Normalizuje naziv firme za poređenje."""
    n = naziv.upper().strip()
    n = _LEGAL_FORMS.sub("", n)
    n = re.sub(r'[."\',\-]', " ", n)
    n = re.sub(r'\s+', " ", n).strip()
    return n


def parse_name_field(text: str) -> tuple:
    """Rastavlja višelinijsko polje u (naziv, grad, drzava)."""
    if not text:
        return ("", "", "")
    parts = [p.strip() for p in text.strip().split("\n")]
    naziv = parts[0] if len(parts) > 0 else ""
    grad = parts[1] if len(parts) > 1 else ""
    drzava = parts[2] if len(parts) > 2 else ""
    return naziv, grad, drzava


def parse_xml(file_path: Path) -> dict:
    """Parsira jedan ASYCUDA XML fajl."""
    try:
        import xml.etree.ElementTree as ET
        tree = ET.parse(file_path)
        root = tree.getroot()
    except Exception:
        return None

    traders = root.find("Traders")
    if traders is None:
        return None

    result = {"exporter": None, "consignee": None, "xml_file": str(file_path)}

    # Exporter
    exp = traders.find("Exporter")
    if exp is not None:
        raw = (exp.findtext("Exporter_name") or "").strip()
        if raw:
            naziv, grad, drzava = parse_name_field(raw)
            if naziv:
                result["exporter"] = {
                    "naziv": naziv,
                    "grad": grad,
                    "drzava": drzava,
                    "normalized": normalize_naziv(naziv),
                }

    # Consignee
    con = traders.find("Consignee")
    if con is not None:
        jib = (con.findtext("Consignee_code") or "").strip()
        raw = (con.findtext("Consignee_name") or "").strip()
        if raw:
            naziv, grad, adresa = parse_name_field(raw)
            if naziv:
                result["consignee"] = {
                    "jib": jib,
                    "naziv": naziv,
                    "grad": grad,
                    "adresa": adresa,
                    "normalized": normalize_naziv(naziv),
                }

    return result


def create_table(conn):
    """Kreira tabelu parovi_zaglavlje ako ne postoji."""
    cur = conn.cursor()
    
    # Prvo proveri da li tabela već postoji
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'catalogs' 
            AND table_name = 'parovi_zaglavlje'
        )
    """)
    exists = list(cur.fetchone().values())[0]
    
    if exists:
        print("Tabela catalogs.parovi_zaglavlje vec postoji.")
        # Pitaj da li da obrise
        odgovor = input("Da li zelis da obrises postojece podatke i uvezes ponovo? (d/n): ").strip().lower()
        if odgovor == 'd':
            cur.execute("TRUNCATE TABLE catalogs.parovi_zaglavlje CASCADE")
            conn.commit()
            print("Tabela ispraznjena.")
        else:
            print("Preskacem...")
            return False
    else:
        # Kreiraj tabelu
        cur.execute("""
            CREATE TABLE catalogs.parovi_zaglavlje (
                id SERIAL PRIMARY KEY,
                consignee_jib VARCHAR(50),
                consignee_naziv TEXT NOT NULL,
                consignee_grad TEXT,
                consignee_adresa TEXT,
                consignee_drzava VARCHAR(10) DEFAULT 'BIH',
                consignee_normalized TEXT,
                exporter_naziv TEXT,
                exporter_grad TEXT,
                exporter_drzava TEXT,
                exporter_normalized TEXT,
                xml_file TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        print("Kreirana tabela catalogs.parovi_zaglavlje")
    
    return True


def scan_all_xml_folders() -> list:
    """Skenira sve XML foldere i vraca listu parova."""
    all_pairs = []
    total_files = 0
    ok_count = 0
    fail_count = 0
    
    for folder in XML_FOLDERS:
        if not folder.exists():
            print(f"Folder ne postoji: {folder}")
            continue
        
        xml_files = list(folder.glob("*.xml"))
        total_files += len(xml_files)
        print(f"Folder: {folder.name} - {len(xml_files)} XML fajlova")
        
        for f in xml_files:
            data = parse_xml(f)
            if data and data.get("exporter") and data.get("consignee"):
                all_pairs.append(data)
                ok_count += 1
            else:
                fail_count += 1
    
    print(f"\nUkupno: {total_files} fajlova, {ok_count} uspesno, {fail_count} neuspesno")
    return all_pairs


def import_pairs(conn, pairs: list) -> int:
    """Uvozi parove u bazu."""
    cur = conn.cursor()
    
    inserted = 0
    for pair in pairs:
        exp = pair.get("exporter", {})
        con = pair.get("consignee", {})
        
        try:
            cur.execute("""
                INSERT INTO catalogs.parovi_zaglavlje (
                    consignee_jib, consignee_naziv, consignee_grad, 
                    consignee_adresa, consignee_drzava, consignee_normalized,
                    exporter_naziv, exporter_grad, exporter_drzava, exporter_normalized,
                    xml_file
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                con.get("jib", ""),
                con.get("naziv", ""),
                con.get("grad", ""),
                con.get("adresa", ""),
                "BIH" if con.get("jib") else con.get("drzava", ""),
                con.get("normalized", ""),
                exp.get("naziv", ""),
                exp.get("grad", ""),
                exp.get("drzava", ""),
                exp.get("normalized", ""),
                pair.get("xml_file", ""),
            ))
            inserted += 1
        except Exception as e:
            print(f"Greksa pri unosu: {e}")
    
    conn.commit()
    return inserted


def consolidate_pairs(pairs: list) -> dict:
    """Konsoliduje parove po consignee grupama."""
    groups = {}
    for pair in pairs:
        con = pair.get("consignee", {})
        norm = con.get("normalized", "")
        
        if norm not in groups:
            groups[norm] = {
                "consignee": {
                    "jib": con.get("jib", ""),
                    "naziv": con.get("naziv", ""),
                    "grad": con.get("grad", ""),
                    "adresa": con.get("adresa", ""),
                    "drzava": con.get("drzava", "BIH"),
                },
                "xml_files": [],
                "exporters": [],
            }
        
        groups[norm]["xml_files"].append(pair.get("xml_file", ""))
        exp = pair.get("exporter", {})
        exp_naziv = exp.get("naziv", "")
        if exp_naziv and exp_naziv not in [e["naziv"] for e in groups[norm]["exporters"]]:
            groups[norm]["exporters"].append({
                "naziv": exp_naziv,
                "grad": exp.get("grad", ""),
                "drzava": exp.get("drzava", ""),
            })
    
    return groups


def main():
    print("=" * 60)
    print("MIGRACIJA: parovi_zaglavlje")
    print("=" * 60)
    print()
    
    # 1. Skeniraj XML fajlove
    print("Skeniram XML fajlove...")
    pairs = scan_all_xml_folders()
    
    if not pairs:
        print("Nema parsiranih parova!")
        return
    
    print()
    
    # 2. Konsolidacija po consignee
    print("Konsolidacija po consignee grupama...")
    groups = consolidate_pairs(pairs)
    print(f"Jedinstvenih consignee grupa: {len(groups)}")
    print()
    
    # 3. Sacuvaj konsolidovane podatke
    output_file = Path(__file__).parent / "parovi_konsolidovano.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "metadata": {
                "total_pairs": len(pairs),
                "unique_consignees": len(groups),
                "generated_at": datetime.now().isoformat(),
            },
            "groups": groups,
        }, f, ensure_ascii=False, indent=2)
    print(f"Konsolidovani podaci sacuvani: {output_file}")
    print()
    
    # 4. Kreiraj tabelu i uvezi
    with get_db_connection() as conn:
        if create_table(conn):
            print("Uvoz parova u bazu...")
            inserted = import_pairs(conn, pairs)
            print(f"Uvezeno {inserted} parova")
    
    print()
    print("Migracija zavrsena!")
    
    # 5. Prikazi statistiku
    print()
    print("STATISTIKA:")
    print(f"   Ukupno XML fajlova: {len(pairs)}")
    print(f"   Jedinstvenih consignee: {len(groups)}")
    
    # Top 5 consignee po broju XML
    top5 = sorted(groups.items(), key=lambda x: len(x[1]["xml_files"]), reverse=True)[:5]
    print()
    print("   TOP 5 consignee:")
    for i, (name, data) in enumerate(top5, 1):
        print(f"   {i}. {name[:50]}... ({len(data['xml_files'])} XML)")


if __name__ == "__main__":
    main()
