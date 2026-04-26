#!/usr/bin/env python3
"""
database/ingest_tariff_kb.py

Batch ingest svih XML fajlova iz docs/NOVA ASIKUDA/ u 
catalogs.tariff_knowledge_base (tarifni_broj, naziv_robe, zemlja, povlastica).

Koristi istu logiku kao declaration_search_service.py za parsiranje.
"""

import sys
import os
import xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from database.db import get_db_connection


def _txt(parent: ET.Element, path: str, default: str = "") -> str:
    """Safe text extraction sa slash-separated path-om."""
    if parent is None:
        return default
    el = parent.find(path)
    if el is not None and el.text:
        return el.text.strip()
    return default


def _build_hs_code(commodity: str, precision: str = "000") -> str:
    """Gradi HS kod: 8 cifara + precision."""
    code = ''.join(c for c in commodity if c.isdigit())[:8]
    prec = ''.join(c for c in precision if c.isdigit())[:3]
    return code + prec if code else code


def extract_from_xml(filepath: Path):
    """Ekstraktuje sve stavke iz jednog XML fajla."""
    items = []
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()

        for item_el in root.findall("Item"):
            commodity = _txt(item_el, "Tarification/HScode/Commodity_code")
            precision = _txt(item_el, "Tarification/HScode/Precision_1", "000")
            hs_code = _build_hs_code(commodity, precision)

            commercial = _txt(item_el, "Goods_description/Commercial_Description")
            description = _txt(item_el, "Goods_description/Description_of_goods")
            naziv_robe = commercial if commercial else description
            naziv_robe = " ".join(naziv_robe.split())[:1000]  # Ograniči dužinu

            country = _txt(item_el, "Goods_description/Country_of_origin_code")
            preference = _txt(item_el, "Tarification/Preference_code")

            if hs_code and naziv_robe:
                items.append((hs_code, naziv_robe, country, preference))

    except ET.ParseError:
        pass
    except Exception as e:
        print(f"  ⚠️ Greška {filepath.name}: {e}")

    return items


def main():
    xml_dir = Path('/home/radovan/Desktop/deklarant_pro/docs/NOVA ASIKUDA')
    xml_files = sorted(xml_dir.glob('*.xml'))
    print(f"📂 {len(xml_files)} XML fajlova")

    total_items = 0
    error_files = 0
    batch = []
    BATCH_SIZE = 1000

    with get_db_connection() as conn:
        cur = conn.cursor()

        for idx, f in enumerate(xml_files, 1):
            items = extract_from_xml(f)
            if items:
                total_items += len(items)
                for hs, naziv, zemlja, pov in items:
                    batch.append((hs, naziv, zemlja or '', pov or '', f.name))

                if len(batch) >= BATCH_SIZE:
                    _flush_batch(cur, batch)
                    batch = []

            if idx % 1000 == 0:
                print(f"  ... {idx}/{len(xml_files)} ({total_items} stavki)")

        # Finalni batch
        if batch:
            _flush_batch(cur, batch)

        conn.commit()
        cur.close()

    print(f"\n✅ GOTVO")
    print(f"  Ukupno stavki iz XML: {total_items}")
    print(f"  Fajlova sa greškom:   {error_files}")


def _flush_batch(cur, batch):
    """Bulk insert sa ON CONFLICT."""
    from psycopg2.extras import execute_values
    
    args_str = b','.join(
        cur.mogrify("(%s,%s,%s,%s,%s)", x) for x in batch
    )
    
    cur.execute(
        b"""
        INSERT INTO catalogs.tariff_knowledge_base 
            (tarifni_broj, naziv_robe, zemlja_porijekla, povlastica, source_file)
        VALUES """ + args_str + b"""
        ON CONFLICT (tarifni_broj, naziv_robe, zemlja_porijekla, povlastica) 
        DO NOTHING
        """
    )
    
    inserted = cur.rowcount
    print(f"  💾 Inserted {inserted} od {len(batch)} (batch)")


if __name__ == '__main__':
    main()
