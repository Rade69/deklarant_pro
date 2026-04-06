#!/usr/bin/env python3
"""
services/tariff_kb_ingestor.py

Batch parser koji čita XML fajlove iz docs/NOVA ASIKUDA/,
ekstraktuje tarifne podatke (tarifni_broj, naziv_robe, zemlja_porijekla, povlastica)
i upisuje u catalogs.tariff_knowledge_base bez duplikata.
"""

import os
import sys
import xml.etree.ElementTree as ET
import logging
from pathlib import Path
from typing import List, Dict, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import get_db_connection

logger = logging.getLogger(__name__)


class TariffKBIngestor:
    """Parsira XML fajlove i puni tariff knowledge base."""

    def __init__(self, xml_dir: str = None):
        if xml_dir is None:
            xml_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'docs', 'NOVA ASIKUDA'
            )
        self.xml_dir = Path(xml_dir)
        self.stats = {
            'total_files': 0,
            'parsed_files': 0,
            'error_files': 0,
            'total_items': 0,
            'inserted': 0,
            'duplicates_skipped': 0,
        }

    def _txt(self, parent: ET.Element, tag: str) -> str:
        """Sigurno čita tekst iz XML elementa."""
        el = parent.find(tag)
        if el is not None and el.text:
            return el.text.strip()
        return ""

    def _find(self, parent: ET.Element, tag: str):
        """Sigurno nalazi element."""
        return parent.find(tag)

    def extract_items_from_xml(self, filepath: Path) -> List[Dict[str, str]]:
        """
        Ekstraktuje tarifne podatke iz svih <Item> sekcija XML fajla.

        Returns:
            Lista dict-ova: {tarifni_broj, naziv_robe, zemlja_porijekla, povlastica}
        """
        items = []
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()

            # Namespace handling
            ns = {}
            if root.tag.startswith('{'):
                uri = root.tag.split('}')[0][1:]
                ns['n'] = uri

            def _find_ns(parent, tag):
                if ns:
                    result = parent.find(f"n:{tag}", ns)
                    if result is not None:
                        return result
                return parent.find(tag)

            def _txt_ns(parent, tag):
                el = _find_ns(parent, tag)
                if el is not None and el.text:
                    return el.text.strip()
                return ""

            # Find all Item elements
            item_elements = root.findall("Item")
            if ns:
                item_elements = root.findall(f"n:Item", ns)

            for item_el in item_elements:
                # Tarifni broj
                hscode = _find_ns(item_el, "HScode") or item_el
                tarifni_broj = _txt_ns(hscode, "Commodity_code") if hscode != item_el else ""
                if not tarifni_broj:
                    # Try direct
                    hscode_direct = _find_ns(item_el, "HScode")
                    if hscode_direct is not None:
                        tarifni_broj = _txt_ns(hscode_direct, "Commodity_code")

                # Naziv robe (Commercial_Description > Description_of_goods)
                goods_desc = _find_ns(item_el, "Goods_description")
                naziv_robe = ""
                if goods_desc is not None:
                    naziv_robe = _txt_ns(goods_desc, "Commercial_Description")
                    if not naziv_robe:
                        naziv_robe = _txt_ns(goods_desc, "Description_of_goods")

                # Zemlja porijekla
                zemlja_porijekla = ""
                if goods_desc is not None:
                    zemlja_porijekla = _txt_ns(goods_desc, "Country_of_origin_code")

                # Povlastica
                tarifacija = _find_ns(item_el, "Tarification") or item_el
                povlastica = ""
                if tarifacija != item_el:
                    povlastica = _txt_ns(tarifacija, "Preference_code")
                else:
                    povlastica = _txt_ns(item_el, "Preference_code")

                # Normalizacija tarifnog broja (samo cifre, max 10)
                if tarifni_broj:
                    tarifni_broj = ''.join(c for c in tarifni_broj if c.isdigit())[:10]

                if tarifni_broj and naziv_robe:
                    items.append({
                        'tarifni_broj': tarifni_broj,
                        'naziv_robe': naziv_robe,
                        'zemlja_porijekla': zemlja_porijekla or '',
                        'povlastica': povlastica or '',
                    })

        except ET.ParseError as e:
            logger.warning(f"XML parse error: {filepath}: {e}")
        except Exception as e:
            logger.error(f"Error parsing {filepath}: {e}")

        return items

    def ingest_all(self, batch_size: int = 500):
        """
        Parsira sve XML fajlove i upisuje u bazu.

        Args:
            batch_size: Batch size za INSERT (ON CONFLICT radi deduplikaciju)
        """
        xml_files = sorted(self.xml_dir.glob('*.xml'))
        self.stats['total_files'] = len(xml_files)

        print(f"📂 Pronađeno {len(xml_files)} XML fajlova u {self.xml_dir}")
        print(f"⏳ Parsiranje i upis u bazu...")

        batch: List[Tuple[str, str, str, str, str]] = []

        for idx, xml_file in enumerate(xml_files, 1):
            items = self.extract_items_from_xml(xml_file)
            if items:
                self.stats['parsed_files'] += 1
                self.stats['total_items'] += len(items)

                for item in items:
                    batch.append((
                        item['tarifni_broj'],
                        item['naziv_robe'],
                        item['zemlja_porijekla'],
                        item['povlastica'],
                        xml_file.name,
                    ))

                    if len(batch) >= batch_size:
                        self._insert_batch(batch)
                        batch = []
            else:
                self.stats['error_files'] += 1

            # Progress
            if idx % 500 == 0:
                print(f"  ... {idx}/{len(xml_files)} fajlova "
                      f"({self.stats['total_items']} stavki, "
                      f"{self.stats['inserted']} upisano)")

        # Finalni batch
        if batch:
            self._insert_batch(batch)

        print(f"\n{'='*60}")
        print(f"✅ KOMPLETE")
        print(f"{'='*60}")
        print(f"  Ukupno fajlova:     {self.stats['total_files']}")
        print(f"  Parsirano fajlova:  {self.stats['parsed_files']}")
        print(f"  Greške:             {self.stats['error_files']}")
        print(f"  Ukupno stavki:      {self.stats['total_items']}")
        print(f"  Upisano u bazu:     {self.stats['inserted']}")
        print(f"  Duplikati:          {self.stats['duplicates_skipped']}")
        print(f"{'='*60}")

    def _insert_batch(self, batch: List[Tuple[str, str, str, str, str]]):
        """Upisuje batch u bazu sa ON CONFLICT DO NOTHING - optimizovano."""
        if not batch:
            return

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Koristimo execute_batch za brži insert
                from psycopg2.extras import execute_batch
                
                def _insert_one(cur, item):
                    tarifni_broj, naziv_robe, zemlja, povlastica, source = item
                    cur.execute("""
                        INSERT INTO catalogs.tariff_knowledge_base 
                            (tarifni_broj, naziv_robe, zemlja_porijekla, povlastica, source_file)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (tarifni_broj, naziv_robe, zemlja_porijekla, povlastica) 
                        DO NOTHING
                    """, item)
                    return cur.rowcount > 0

                inserted = 0
                for item in batch:
                    try:
                        if _insert_one(cur, item):
                            inserted += 1
                    except Exception as e:
                        logger.warning(f"Insert failed: {e}")
                
                self.stats['inserted'] += inserted
                self.stats['duplicates_skipped'] += len(batch) - inserted
            conn.commit()  # Eksplicitni commit

    def search(self, naziv_robe: str, zemlja_porijekla: str = None) -> List[Dict]:
        """
        Pretražuje knowledge base po nazivu robe i opciono zemlji porijekla.

        Args:
            naziv_robe: Dio naziva robe za pretragu
            zemlja_porijekla: Opcioni filter po zemlji

        Returns:
            Lista match-anih stavki sa tarifnim brojem, povlasticom, itd.
        """
        results = []
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                if zemlja_porijekla:
                    cur.execute("""
                        SELECT tarifni_broj, naziv_robe, zemlja_porijekla, povlastica
                        FROM catalogs.tariff_knowledge_base
                        WHERE zemlja_porijekla = %s
                          AND to_tsvector('simple', naziv_robe) @@ plainto_tsquery('simple', %s)
                        ORDER BY tarifni_broj
                        LIMIT 20
                    """, (zemlja_porijekla, naziv_robe))
                else:
                    cur.execute("""
                        SELECT tarifni_broj, naziv_robe, zemlja_porijekla, povlastica
                        FROM catalogs.tariff_knowledge_base
                        WHERE to_tsvector('simple', naziv_robe) @@ plainto_tsquery('simple', %s)
                        ORDER BY tarifni_broj
                        LIMIT 20
                    """, (naziv_robe,))

                for row in cur.fetchall():
                    results.append({
                        'tarifni_broj': row['tarifni_broj'],
                        'naziv_robe': row['naziv_robe'],
                        'zemlja_porijekla': row['zemlja_porijekla'],
                        'povlastica': row['povlastica'],
                    })
        return results

    def search_exact(self, naziv_robe: str, zemlja_porijekla: str) -> List[Dict]:
        """
        Egzaktna pretraga za auto-popuni: traži POTPUNO isti naziv + zemlju.

        Returns:
            Lista match-anih povlastica i tarifnih brojeva.
        """
        results = []
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Exact match
                cur.execute("""
                    SELECT tarifni_broj, naziv_robe, zemlja_porijekla, povlastica
                    FROM catalogs.tariff_knowledge_base
                    WHERE naziv_robe = %s AND zemlja_porijekla = %s
                    ORDER BY povlastica
                """, (naziv_robe, zemlja_porijekla))

                for row in cur.fetchall():
                    results.append({
                        'tarifni_broj': row['tarifni_broj'],
                        'naziv_robe': row['naziv_robe'],
                        'zemlja_porijekla': row['zemlja_porijekla'],
                        'povlastica': row['povlastica'],
                    })

                # Fuzzy match ako nema egzaktnog (contains)
                if not results:
                    cur.execute("""
                        SELECT tarifni_broj, naziv_robe, zemlja_porijekla, povlastica
                        FROM catalogs.tariff_knowledge_base
                        WHERE zemlja_porijekla = %s
                          AND LOWER(naziv_robe) LIKE LOWER(%s)
                        ORDER BY tarifni_broj
                        LIMIT 10
                    """, (zemlja_porijekla, f"%{naziv_robe}%"))

                    for row in cur.fetchall():
                        results.append({
                            'tarifni_broj': row['tarifni_broj'],
                            'naziv_robe': row['naziv_robe'],
                            'zemlja_porijekla': row['zemlja_porijekla'],
                            'povlastica': row['povlastica'],
                        })

        return results


if __name__ == '__main__':
    ingestor = TariffKBIngestor()
    ingestor.ingest_all()
