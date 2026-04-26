"""
DeclarationSearchService — pretraga istorijskih XML deklaracija.

Indeksira 2500+ XML fajlova iz NOVA ASIKUDA foldera u SQLite bazu
(gradi se jednom, obnavljuje se samo kad ima novih fajlova).

Podržava pretragu po:
- Tarifnom broju (HScode)
- Nazivu/opisu robe (Commercial_Description, Description_of_goods)
- Izvozniku / primaocu
- Zemlji porijekla
- Povlastici
"""

import logging
import os
import re
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger("deklarant_pro.agent.declaration_search")

# Putanja do XML fajlova
XML_DIR = Path(__file__).parent.parent.parent / "data" / "knowledge_base" / "NOVA ASIKUDA"

# SQLite index — u istom folderu kao XML-ovi
INDEX_DB = Path(__file__).parent.parent.parent / "data" / "knowledge_base" / "declaration_index.db"


def _txt(element, path: str, default: str = "") -> str:
    """Sigurno čita text iz XML elementa po xpath-u."""
    try:
        el = element.find(path)
        if el is not None and el.text:
            return el.text.strip()
    except Exception:
        pass
    return default


def _build_hs_code(commodity: str, precision: str) -> str:
    """Sastavlja 11-cifreni HS kod iz Commodity_code + Precision_1."""
    c = (commodity or "").strip()
    p = (precision or "000").strip()
    if not c:
        return ""
    return c + p if p else c + "000"


class DeclarationSearchService:
    """
    Servis za pretragu istorijskih XML deklaracija.

    Pri prvom pozivu gradi SQLite indeks (30-60s za 2500 fajlova).
    Svaki naredni poziv koristi keširan indeks (brz).
    """

    def __init__(self):
        self._db: Optional[sqlite3.Connection] = None
        self._indexed = False

    # ─── PUBLIC API ────────────────────────────────────────────────────────────

    def search_by_goods(self, query: str, limit: int = 8) -> List[Dict]:
        """
        Pretraga po opisu / komercijalnom nazivu robe.
        Vraća stavke sa tarifnim brojem, zemljom, povlasticom.
        """
        self._ensure_index()
        words = [w for w in re.split(r'\s+', query.strip()) if len(w) >= 3]
        if not words:
            return []

        like_clauses = " OR ".join(
            ["i.commercial_desc LIKE ? OR i.description LIKE ?"] * len(words)
        )
        params = []
        for w in words:
            p = f"%{w}%"
            params.extend([p, p])

        sql = f"""
            SELECT i.hs_code, i.commercial_desc, i.description,
                   i.country_origin, i.preference,
                   d.exporter_name, d.consignee_name, d.filename
            FROM items i
            JOIN declarations d ON i.decl_id = d.id
            WHERE {like_clauses}
            ORDER BY length(i.commercial_desc)
            LIMIT ?
        """
        params.append(limit)
        return self._fetchall(sql, params)

    def search_by_tariff(self, tariff_code: str, limit: int = 10) -> List[Dict]:
        """Pronalazi sve istorijske stavke sa određenim tarifnim brojem."""
        self._ensure_index()
        clean = re.sub(r'\D', '', tariff_code)
        prefix = clean[:8] if len(clean) >= 8 else clean
        sql = """
            SELECT i.hs_code, i.commercial_desc, i.description,
                   i.country_origin, i.preference,
                   d.exporter_name, d.consignee_name, d.filename
            FROM items i
            JOIN declarations d ON i.decl_id = d.id
            WHERE i.hs_code LIKE ?
            GROUP BY i.hs_code, i.commercial_desc, i.country_origin
            LIMIT ?
        """
        return self._fetchall(sql, [f"{prefix}%", limit])

    def search_by_partner(self, query: str, limit: int = 8) -> List[Dict]:
        """Pretraga po imenu izvoznika ili primaoca."""
        self._ensure_index()
        words = [w for w in re.split(r'\s+', query.strip()) if len(w) >= 3]
        if not words:
            return []

        like_clauses = " OR ".join(
            ["d.exporter_name LIKE ? OR d.consignee_name LIKE ?"] * len(words)
        )
        params = []
        for w in words:
            p = f"%{w}%"
            params.extend([p, p])

        sql = f"""
            SELECT DISTINCT d.exporter_name, d.consignee_name,
                   d.consignee_jib, d.decl_type, d.filename,
                   COUNT(i.id) as item_count
            FROM declarations d
            LEFT JOIN items i ON i.decl_id = d.id
            WHERE {like_clauses}
            GROUP BY d.id
            ORDER BY item_count DESC
            LIMIT ?
        """
        params.append(limit)
        return self._fetchall(sql, params)

    def search_by_country(self, country_code: str, limit: int = 10) -> List[Dict]:
        """Pretraga stavki po zemlji porijekla (ISO kod ili naziv)."""
        self._ensure_index()
        code = country_code.strip().upper()
        sql = """
            SELECT i.hs_code, i.commercial_desc, i.country_origin,
                   i.preference, d.exporter_name, d.filename
            FROM items i
            JOIN declarations d ON i.decl_id = d.id
            WHERE i.country_origin = ?
            GROUP BY i.hs_code, i.commercial_desc
            ORDER BY i.commercial_desc
            LIMIT ?
        """
        return self._fetchall(sql, [code, limit])

    def get_stats(self) -> Dict:
        """Vraća statistiku indeksa."""
        self._ensure_index()
        cur = self._db.cursor()
        decl_count = cur.execute("SELECT COUNT(*) FROM declarations").fetchone()[0]
        item_count = cur.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        unique_tariffs = cur.execute("SELECT COUNT(DISTINCT hs_code) FROM items").fetchone()[0]
        countries = cur.execute(
            "SELECT country_origin, COUNT(*) as cnt FROM items "
            "WHERE country_origin != '' GROUP BY country_origin "
            "ORDER BY cnt DESC LIMIT 10"
        ).fetchall()
        return {
            "declarations": decl_count,
            "items": item_count,
            "unique_tariffs": unique_tariffs,
            "top_countries": [(r[0], r[1]) for r in countries],
        }

    # ─── INDEXER ───────────────────────────────────────────────────────────────

    def _ensure_index(self):
        """Gradi ili učitava SQLite indeks."""
        if self._indexed:
            return

        INDEX_DB.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(INDEX_DB))
        self._db.row_factory = sqlite3.Row

        self._create_schema()

        # Provjeri treba li reindeksiranje
        xml_files = sorted(XML_DIR.glob("*.xml")) if XML_DIR.exists() else []
        indexed_count = self._db.execute(
            "SELECT COUNT(*) FROM declarations"
        ).fetchone()[0]

        if indexed_count < len(xml_files) * 0.9:
            logger.info(f"Indeksiranje {len(xml_files)} XML deklaracija...")
            self._index_all(xml_files)
            logger.info("Indeksiranje završeno.")

        self._indexed = True

    def _create_schema(self):
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS declarations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                filename    TEXT UNIQUE,
                decl_type   TEXT,
                exporter_name TEXT,
                consignee_name TEXT,
                consignee_jib  TEXT
            );
            CREATE TABLE IF NOT EXISTS items (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                decl_id     INTEGER REFERENCES declarations(id),
                hs_code     TEXT,
                commercial_desc TEXT,
                description TEXT,
                country_origin  TEXT,
                preference  TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_items_hs    ON items(hs_code);
            CREATE INDEX IF NOT EXISTS idx_items_co    ON items(country_origin);
            CREATE INDEX IF NOT EXISTS idx_items_desc  ON items(commercial_desc);
        """)
        self._db.commit()

    def _index_all(self, xml_files: list):
        """Parsira sve XML fajlove i upisuje u SQLite."""
        self._db.execute("DELETE FROM items")
        self._db.execute("DELETE FROM declarations")
        self._db.commit()

        batch_decls = []
        batch_items = []

        for xml_path in xml_files:
            try:
                decl, items = self._parse_xml(xml_path)
                if decl:
                    batch_decls.append(decl)
                    batch_items.append(items)
            except Exception as e:
                logger.debug(f"Skip {xml_path.name}: {e}")

            if len(batch_decls) >= 100:
                self._flush_batch(batch_decls, batch_items)
                batch_decls.clear()
                batch_items.clear()

        if batch_decls:
            self._flush_batch(batch_decls, batch_items)

    def _flush_batch(self, decls: list, items_list: list):
        cur = self._db.cursor()
        for decl, items in zip(decls, items_list):
            cur.execute(
                "INSERT OR IGNORE INTO declarations "
                "(filename, decl_type, exporter_name, consignee_name, consignee_jib) "
                "VALUES (?, ?, ?, ?, ?)",
                decl
            )
            decl_id = cur.lastrowid
            if decl_id and items:
                cur.executemany(
                    "INSERT INTO items "
                    "(decl_id, hs_code, commercial_desc, description, country_origin, preference) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    [(decl_id,) + item for item in items]
                )
        self._db.commit()

    def _parse_xml(self, xml_path: Path):
        """Parsira jedan XML fajl — vraća (decl_tuple, [item_tuples])."""
        tree = ET.parse(str(xml_path))
        root = tree.getroot()

        # Header
        decl_type = _txt(root, "Identification/Type/Type_of_declaration")
        exporter  = _txt(root, "Traders/Exporter/Exporter_name")
        consignee = _txt(root, "Traders/Consignee/Consignee_name")
        jib       = _txt(root, "Traders/Consignee/Consignee_code")

        # Normalizuj višelinijska polja
        exporter  = " ".join(exporter.split())
        consignee = " ".join(consignee.split())

        decl = (xml_path.name, decl_type, exporter, consignee, jib)

        # Stavke
        items = []
        for item_el in root.findall("Item"):
            commodity = _txt(item_el, "Tarification/HScode/Commodity_code")
            precision = _txt(item_el, "Tarification/HScode/Precision_1", "000")
            hs_code   = _build_hs_code(commodity, precision)
            preference = _txt(item_el, "Tarification/Preference_code")
            country    = _txt(item_el, "Goods_description/Country_of_origin_code")
            commercial = _txt(item_el, "Goods_description/Commercial_Description")
            description = _txt(item_el, "Goods_description/Description_of_goods")

            # Normalizuj višelinijska polja
            commercial  = " ".join(commercial.split())[:200]
            description = " ".join(description.split())[:150]

            if hs_code or commercial:
                items.append((hs_code, commercial, description, country, preference))

        return decl, items

    # ─── HELPERS ───────────────────────────────────────────────────────────────

    def _fetchall(self, sql: str, params: list) -> List[Dict]:
        try:
            cur = self._db.cursor()
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"SQL greška: {e}")
            return []
