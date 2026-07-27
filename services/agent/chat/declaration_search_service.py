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
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Optional
from services.security.safe_xml import safe_parse

logger = logging.getLogger("deklarant_pro.agent.declaration_search")

PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Povećati kad se mijenja shema — triggeriše rebuild postojećeg indeksa
_SCHEMA_VERSION = 2

GENERIC_SEARCH_TOKENS = {
    "artikl", "artikal", "faktura", "gel", "komad", "krem", "ml",
    "model", "naziv", "ostali", "ostalo", "proizvod", "proizvodi", "robe",
    "tbl", "tip",
}

# Putanja do XML fajlova
XML_DIR = PROJECT_ROOT / "data" / "knowledge_base" / "NOVA ASIKUDA"

# SQLite index — u istom folderu kao XML-ovi
INDEX_DB = PROJECT_ROOT / "data" / "knowledge_base" / "declaration_index.db"


def _path_from_env(name: str, default: Path) -> Path:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    path = Path(raw).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def _resolve_xml_dir() -> Path:
    path = _path_from_env("XML_ARCHIVE_DIR", XML_DIR)
    if not path.exists():
        raise FileNotFoundError(
            f"XML arhiv nije pronađen: {path}. Postavite XML_ARCHIVE_DIR u .env."
        )
    return path


def _resolve_index_db() -> Path:
    return _path_from_env("DECLARATION_INDEX_DB", INDEX_DB)


def _txt(element, path: str, default: str = "") -> str:
    """Sigurno čita text iz XML elementa po xpath-u."""
    try:
        el = element.find(path)
        if el is not None and el.text:
            return el.text.strip()
    except Exception as e:
        logger.warning("XML parse greška za xpath '%s': %s", path, e)
    return default


def _build_hs_code(commodity: str, precision: str) -> str:
    """Sastavlja 11-cifreni HS kod iz Commodity_code + Precision_1."""
    c = (commodity or "").strip()
    p = (precision or "000").strip()
    if not c:
        return ""
    return c + p if p else c + "000"


def _normalize_search_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_value = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", re.sub(r"[^a-zA-Z0-9]+", " ", ascii_value.lower())).strip()


def _search_words(query: str) -> list[str]:
    words = []
    for word in re.split(r"\s+", _normalize_search_text(query)):
        if len(word) < 3:
            continue
        if word not in words:
            words.append(word)
    return words


def _goods_match_score(row: Dict, words: list[str], phrase: str) -> float:
    text = _normalize_search_text(
        f"{row.get('commercial_desc', '')} {row.get('description', '')}"
    )
    if not text:
        return 0.0

    required = [
        word for word in words
        if len(word) >= 5 and not word.isdigit() and word not in GENERIC_SEARCH_TOKENS
    ][:3]
    if required and not any(word in text for word in required):
        return 0.0

    matched = sum(1 for word in words if word in text)
    if not matched:
        return 0.0
    if len(words) >= 3 and matched < 2:
        return 0.0

    score = matched / max(len(words), 1)
    if phrase and phrase in text:
        score += 0.5
    commercial = _normalize_search_text(row.get("commercial_desc", ""))
    if commercial.startswith(phrase[:40]):
        score += 0.2
    return score


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
        words = _search_words(query)
        if not words:
            return []

        # FTS5 MATCH — inverted index, višestruko brže od LIKE za veliku arhivu
        fts_query = " ".join(words)
        sql = """
            SELECT i.hs_code, i.commercial_desc, i.description,
                   i.country_origin, i.preference,
                   d.exporter_name, d.consignee_name, d.filename,
                   bm25(items_fts) AS _rank
            FROM items_fts f
            JOIN items i ON f.item_id = i.id
            JOIN declarations d ON i.decl_id = d.id
            WHERE items_fts MATCH ?
            ORDER BY _rank
            LIMIT ?
        """
        try:
            rows = self._fetchall(sql, [fts_query, max(limit * 20, 100)])
        except Exception:
            # Fallback na LIKE ako FTS5 indeks nije populiran (stara baza)
            rows = self._fetchall(
                "SELECT i.hs_code, i.commercial_desc, i.description,"
                " i.country_origin, i.preference,"
                " d.exporter_name, d.consignee_name, d.filename"
                " FROM items i JOIN declarations d ON i.decl_id = d.id"
                f" WHERE {' OR '.join(['i.commercial_desc LIKE ? OR i.description LIKE ?'] * len(words))}"
                " LIMIT ?",
                [p for w in words for p in (f"%{w}%", f"%{w}%")] + [max(limit * 20, 100)]
            )
        phrase = _normalize_search_text(query)
        scored = [
            (_goods_match_score(row, words, phrase), row)
            for row in rows
        ]
        scored = [(score, row) for score, row in scored if score > 0]
        scored.sort(
            key=lambda item: (
                item[0],
                bool((item[1].get("country_origin") or "").strip()),
                -len(item[1].get("commercial_desc") or ""),
            ),
            reverse=True,
        )
        return [row for _, row in scored[:limit]]

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

        xml_dir = _resolve_xml_dir()
        index_db = _resolve_index_db()
        index_db.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(index_db))
        self._db.row_factory = sqlite3.Row

        self._create_schema()

        # Provjeri schema verziju — zastarjela shema triggeriše rebuild
        stored_ver = self._db.execute(
            "SELECT value FROM schema_meta WHERE key='version'"
        ).fetchone()
        needs_rebuild = (stored_ver is None or int(stored_ver[0]) < _SCHEMA_VERSION)

        xml_files = sorted(xml_dir.glob("*.xml"))
        indexed_count = self._db.execute(
            "SELECT COUNT(*) FROM declarations"
        ).fetchone()[0]

        if needs_rebuild or indexed_count < len(xml_files) * 0.9:
            logger.info(f"Indeksiranje {len(xml_files)} XML deklaracija (schema v{_SCHEMA_VERSION})...")
            self._index_all(xml_files)
            self._db.execute(
                "INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('version', ?)",
                (str(_SCHEMA_VERSION),)
            )
            self._db.commit()
            logger.info("Indeksiranje završeno.")

        self._indexed = True

    def _create_schema(self):
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS schema_meta (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
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
            CREATE INDEX IF NOT EXISTS idx_items_hs ON items(hs_code);
            CREATE INDEX IF NOT EXISTS idx_items_co ON items(country_origin);
            CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(
                item_id     UNINDEXED,
                commercial_desc,
                description,
                tokenize    = 'unicode61 remove_diacritics 2'
            );
        """)
        self._db.commit()

    def _index_all(self, xml_files: list):
        """Parsira sve XML fajlove i upisuje u SQLite."""
        self._db.execute("DELETE FROM items_fts")
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
                # FTS5 — upiši commercial_desc + description za pretragu.
                # cur.lastrowid se NE ažurira nakon executemany (ostaje od
                # prethodnog execute() za deklaraciju), pa se pravi id-evi
                # upisanih stavki moraju dohvatiti upitom — inače se item_id
                # u items_fts pomjeri i pretraga vrati podatke pogrešne stavke.
                # Vidi agent_reports/2026-07-03_declaration-search-fts-item-id-fix.md
                item_ids = [
                    row[0] for row in cur.execute(
                        "SELECT id FROM items WHERE decl_id = ? ORDER BY id",
                        (decl_id,)
                    ).fetchall()
                ]
                cur.executemany(
                    "INSERT INTO items_fts(item_id, commercial_desc, description) "
                    "VALUES (?, ?, ?)",
                    [
                        (item_id, item[1] or "", item[2] or "")
                        for item_id, item in zip(item_ids, items)
                    ]
                )
        self._db.commit()

    def _parse_xml(self, xml_path: Path):
        """Parsira jedan XML fajl — vraća (decl_tuple, [item_tuples])."""
        tree = safe_parse(xml_path)
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
