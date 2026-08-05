"""
Exporter XML Indexer

Jednokratno indexira sve XML-ove iz docs/NOVA ASIKUDA i pravi bazu
PAR (exporter + consignee) → xml_filepath za brzi lookup.

Workflow:
1. Čita SVE XML-ove iz foldera
2. Ekstrahuje Exporter_name i Consignee_name iz svakog
3. Normalizuje imena (uppercase, uklanja DOO, D.O.O., etc.)
4. Za svaki par uzima NAJNOVIJI XML (po declaration date)
5. Sačuva u bazu catalogs.exporter_xml_index

Usage:
    python -m services.agent.learning.exporter_xml_indexer
    python -m services.agent.learning.exporter_xml_indexer --reindex  # Force reindex
    python -m services.agent.learning.exporter_xml_indexer --lookup "ENMON|IPEK"  # Test lookup
"""

import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from difflib import SequenceMatcher

import psycopg2
from services.security.safe_xml import safe_parse

logger = logging.getLogger("deklarant_pro.exporter_indexer")

FUZZY_MATCH_THRESHOLD = 0.92


def get_db_connection():
    """Konekcija na bazu koristeći centralni config."""
    from config.settings import get_db_settings
    from psycopg2.extras import RealDictCursor

    settings = get_db_settings()
    return psycopg2.connect(
        host=settings.host,
        port=settings.port,
        database=settings.database,
        user=settings.user,
        password=settings.password,
        sslmode=settings.sslmode,
        cursor_factory=RealDictCursor,
    )


def get_xml_folder() -> Path:
    """Vrati folder za XML učenje iz env override-a ili projektne strukture."""
    import os
    from config.settings import PROJECT_ROOT

    override = os.getenv("XML_LEARNING_FOLDER", "").strip()
    if override:
        return Path(override).expanduser()
    return PROJECT_ROOT / "docs" / "NOVA ASIKUDA"


XML_FOLDER = get_xml_folder()

# Godišnji filter — gornja granica je tekuća + 1 da pokrije nove deklaracije
YEAR_FROM = 2020
YEAR_TO = datetime.now().year + 1


@dataclass
class ExporterEntry:
    """Jedan unos u indeksu."""
    exporter_normalized: str
    consignee_normalized: str
    consignee_jib: str
    exporter_original: str
    consignee_original: str
    xml_filepath: str
    declaration_date: Optional[datetime] = None


def normalize_exporter_name(name: str) -> str:
    """
    Normalizuje ime exportera za upoređivanje.
    
    'ENMON d.o.o.' → 'ENMON'
    'Šumaprom Commerce D.O.O.' → 'ŠUMAPROM COMMERCE'
    'KONZUM DOO BEOGRAD' → 'KONZUM'
    """
    if not name:
        return ""
    
    # Uppercase i strip
    name = name.upper().strip()
    
    # Ukloni sufikse i prefikse pravnih oblika (sa ili bez zareza)
    suffixes_to_remove = [
        r',?\s*D\.\s*O\.\s*O\.?\s*$',   # , D.O.O. ili D.O.O
        r',?\s*D\s*O\s*O\.?\s*$',        # , DOO ili DOO.
        r',?\s*DOO\.?\s*$',
        r',?\s*LTD\.?\s*$',
        r',?\s*LLC\.?\s*$',
        r',?\s*A\.?\s*D\.?\s*$',
        r',?\s*J\.?\s*S\.?\s*C\.?\s*$',
        r',?\s*GMBH\.?\s*$',
        r',?\s*S\.?\s*R\.?\s*O\.?\s*$',
    ]
    prefixes_to_remove = [
        r'^TRGOVINSKA\s+DRUŠTVA?\s*',
        r'^PREDMUZEĆE\s+',
        r'^DRUŠTVO\s+SA\s+OGRANIČENOM\s+ODGOVORNOŠĆU\s*',
        r'^DOO\s+',
        r'^D\.\s*O\.\s*O\.?\s+',
    ]

    for pattern in suffixes_to_remove:
        name = re.sub(pattern, '', name, flags=re.IGNORECASE).strip()
    for pattern in prefixes_to_remove:
        name = re.sub(pattern, '', name, flags=re.IGNORECASE).strip()

    # Ukloni višestruke zareze/tačke na kraju
    name = re.sub(r'[,.\s]+$', '', name).strip()

    # Ukloni brojeve na kraju (JMBG, PIB, etc.)
    name = re.sub(r'\s+\d{6,}.*$', '', name)
    
    # Collapse whitespace
    name = re.sub(r'\s+', ' ', name).strip()
    
    return name


def parse_declaration_date(xml_path: Path) -> Optional[datetime]:
    """Izvuče datum deklaracije iz XML-a (ASYCUDA World format)."""
    try:
        tree = safe_parse(xml_path)
        root = tree.getroot()

        # ASYCUDA XML: Identification/Assessment/Date ili Registration/Date
        # Format: "4/16/26" (M/D/YY) ili "4/16/2026" (M/D/YYYY)
        xpaths = [
            ".//Identification/Assessment/Date",
            ".//Identification/Registration/Date",
        ]
        formats = ["%m/%d/%y", "%m/%d/%Y", "%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y%m%d"]

        for xpath in xpaths:
            date_elem = root.find(xpath)
            if date_elem is None or not (date_elem.text or "").strip():
                continue
            raw = date_elem.text.strip()
            for fmt in formats:
                try:
                    return datetime.strptime(raw, fmt)
                except ValueError:
                    continue

    except Exception as e:
        logger.debug(f"Nije moguće izvući datum iz {xml_path.name}: {e}")

    return None


def extract_parties_from_xml(xml_path: Path) -> tuple[Optional[str], Optional[str], Optional[str], Optional[datetime]]:
    """
    Ekstrahuje ime exportera, consignee-a i datum iz XML-a.
    
    Returns:
        (exporter_name, consignee_name, consignee_jib, declaration_date) ili (None, None, None, None)
    """
    try:
        tree = safe_parse(xml_path)
        root = tree.getroot()
        
        exporter_name = None
        consignee_name = None
        
        # Exporter - više XPath varijanti
        for xpath in [".//Traders/Exporter/Exporter_name", ".//Exporter/Name"]:
            elem = root.find(xpath)
            if elem is not None and elem.text and elem.text.strip():
                exporter_name = elem.text.strip().split('\n')[0].strip()
                if exporter_name:
                    break
        
        # Consignee - više XPath varijanti
        consignee_jib = None
        for xpath in [".//Traders/Consignee/Consignee_name", ".//Consignee/Name"]:
            elem = root.find(xpath)
            if elem is not None and elem.text and elem.text.strip():
                consignee_name = elem.text.strip().split('\n')[0].strip()
                if consignee_name:
                    break

        # JIB consignee-a (Consignee_code)
        for xpath in [".//Traders/Consignee/Consignee_code", ".//Consignee/Code"]:
            elem = root.find(xpath)
            if elem is not None and elem.text and elem.text.strip():
                consignee_jib = elem.text.strip()
                break

        # Datum deklaracije
        declaration_date = parse_declaration_date(xml_path)

        return exporter_name, consignee_name, consignee_jib, declaration_date

    except ET.ParseError as e:
        logger.debug(f"XML parse error {xml_path.name}: {e}")
        return None, None, None, None
    except Exception as e:
        logger.debug(f"Greška pri parsiranju {xml_path.name}: {e}")
        return None, None, None, None


# Backward compatibility
def extract_exporter_from_xml(xml_path: Path) -> tuple[Optional[str], Optional[datetime]]:
    """Backward compatibility - samo exporter."""
    exp, _, _jib, date = extract_parties_from_xml(xml_path)
    return exp, date


def scan_xml_folder() -> Dict[Tuple[str, str], ExporterEntry]:
    """
    Skenira folder i gradi dict (exporter, consignee) → najbolji XML.
    
    Za svaki par pamti samo NAJNOVIJI XML.
    
    Returns:
        Dict[(exporter_norm, consignee_norm), ExporterEntry]
    """
    if not XML_FOLDER.exists():
        logger.error(f"XML folder ne postoji: {XML_FOLDER}")
        return {}
    
    xml_files = list(XML_FOLDER.glob("*.xml"))
    logger.info(f"📂 Pronađeno {len(xml_files)} XML fajlova")
    
    # Grupiši po PARU (exporter + consignee_jib) - čuvaj najnoviji
    # Ključ: (exporter_norm, consignee_jib) ako JIB postoji, inače (exporter_norm, consignee_norm)
    pairs: Dict[Tuple[str, str], ExporterEntry] = {}
    skipped = 0

    for i, xml_path in enumerate(xml_files):
        if (i + 1) % 500 == 0:
            logger.info(f"   Progres: {i + 1}/{len(xml_files)}")

        # Ekstrahuj exporter, consignee, JIB i datum
        exporter_raw, consignee_raw, consignee_jib, declaration_date = extract_parties_from_xml(xml_path)

        if not exporter_raw:
            skipped += 1
            continue

        # Normalizuj
        exporter_norm = normalize_exporter_name(exporter_raw)
        consignee_norm = normalize_exporter_name(consignee_raw) if consignee_raw else ""
        jib = (consignee_jib or "").strip()

        if not exporter_norm:
            skipped += 1
            continue

        # Godišnji filter
        if declaration_date:
            if declaration_date.year < YEAR_FROM or declaration_date.year > YEAR_TO:
                logger.debug(f"   Preskačem {xml_path.name} - datum {declaration_date.year} van opsega")
                continue

        # Ključ: JIB ima prednost, inače normalizovano ime
        key = (exporter_norm, jib if jib else consignee_norm)

        entry = ExporterEntry(
            exporter_normalized=exporter_norm,
            consignee_normalized=consignee_norm,
            consignee_jib=jib,
            exporter_original=exporter_raw[:100],
            consignee_original=consignee_raw[:100] if consignee_raw else "",
            xml_filepath=str(xml_path),
            declaration_date=declaration_date
        )

        # Ako već imamo ovaj par, zadrži najnoviji
        if key in pairs:
            existing = pairs[key]
            if declaration_date and (not existing.declaration_date or declaration_date > existing.declaration_date):
                pairs[key] = entry
        else:
            pairs[key] = entry
    
    logger.info(f"✅ Indexiranje završeno: {len(pairs)} jedinstvenih parova, {skipped} preskočeno")
    
    return pairs


def _ensure_table(cursor) -> None:
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'catalogs'
            AND table_name = 'exporter_xml_index'
        )
    """)
    if cursor.fetchone()['exists']:
        return

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS catalogs.exporter_xml_index (
            id SERIAL PRIMARY KEY,
            exporter_normalized TEXT NOT NULL,
            consignee_normalized TEXT NOT NULL DEFAULT '',
            consignee_jib TEXT NOT NULL DEFAULT '',
            exporter_original TEXT NOT NULL,
            consignee_original TEXT NOT NULL DEFAULT '',
            xml_filepath TEXT NOT NULL,
            declaration_date DATE,
            last_used TIMESTAMP DEFAULT NOW(),
            use_count INT DEFAULT 1,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(exporter_normalized, consignee_jib, consignee_normalized)
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_exporter_xml_exp
        ON catalogs.exporter_xml_index (exporter_normalized)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_exporter_xml_jib
        ON catalogs.exporter_xml_index (consignee_jib)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_exporter_xml_pair_jib
        ON catalogs.exporter_xml_index (exporter_normalized, consignee_jib)
    """)


def create_table_if_not_exists():
    """Kreira tabelu sa parovima bez brisanja postojećih podataka."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            _ensure_table(cursor)
        conn.commit()
        logger.info("✅ Tabela catalogs.exporter_xml_index spremna")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _save_pairs(cursor, pairs: Dict[Tuple[str, str], ExporterEntry]) -> int:
    saved = 0
    for _key, entry in pairs.items():
        cursor.execute("""
            INSERT INTO catalogs.exporter_xml_index
            (exporter_normalized, consignee_normalized, consignee_jib,
             exporter_original, consignee_original, xml_filepath, declaration_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (exporter_normalized, consignee_jib, consignee_normalized) DO UPDATE SET
                exporter_original = EXCLUDED.exporter_original,
                consignee_original = EXCLUDED.consignee_original,
                xml_filepath = EXCLUDED.xml_filepath,
                declaration_date = EXCLUDED.declaration_date
        """, (
            entry.exporter_normalized,
            entry.consignee_normalized,
            entry.consignee_jib,
            entry.exporter_original,
            entry.consignee_original,
            entry.xml_filepath,
            entry.declaration_date
        ))
        saved += 1
    return saved


def save_to_database(pairs: Dict[Tuple[str, str], ExporterEntry]) -> int:
    """
    Sačuva index parova u bazu.
    
    Koristi INSERT ... ON CONFLICT za ažuriranje postojećih.
    
    Returns:
        Broj sačuvanih redova
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            _ensure_table(cursor)
            saved = _save_pairs(cursor, pairs)
            conn.commit()
        
        logger.info(f"✅ Sačuvano {saved} exportera u bazu")
        return saved
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def clear_index():
    """Očisti cijeli index."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            _ensure_table(cursor)
            cursor.execute("DELETE FROM catalogs.exporter_xml_index")
            conn.commit()
        logger.info("🗑️ Index očišćen")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def reindex() -> int:
    """
    Potpuno ponovno indexiranje.
    
    Returns:
        Broj indexiranih exportera
    """
    logger.info("🔄 POČINJEM REINDEXIRANJE...")
    exporters = scan_xml_folder()
    if not exporters:
        logger.warning("⚠️ Nema validnih XML parova; postojeći indeks nije mijenjan")
        return 0

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            _ensure_table(cursor)
            cursor.execute("DELETE FROM catalogs.exporter_xml_index")
            saved = _save_pairs(cursor, exporters)
        conn.commit()
        logger.info(f"✅ Atomski reindex završen: {saved} parova")
        sync_tariff_knowledge_base()
        return saved
    except Exception:
        conn.rollback()
        logger.exception("Reindex nije uspio; prethodni indeks je sačuvan")
        raise
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════
# TARIFF KNOWLEDGE BASE SYNC — iz XML-ova u product_tariff_mapping
# ══════════════════════════════════════════════════════════════════════

def sync_tariff_knowledge_base() -> int:
    """Ekstraktuje tarifne brojeve iz svih indeksiranih XML-ova i upisuje ih u product_tariff_mapping."""
    from psycopg2 import sql as pg_sql

    conn = get_db_connection()
    saved = 0
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT xml_filepath, exporter_normalized FROM catalogs.exporter_xml_index")
            rows = cursor.fetchall()
            logger.info(f"📦 Ekstrakcija tarifa iz {len(rows)} XML-ova...")

            for row in rows:
                xml_path = row['xml_filepath']
                exporter = row['exporter_normalized']
                if not Path(xml_path).exists():
                    continue

                try:
                    tree = ET.parse(xml_path)
                    root = tree.getroot()
                    ns = {'ns': 'urn:carinarnica:deklaracija'}
                    for stavka in root.findall('.//ns:Stavka', ns):
                        tarifa = stavka.findtext('ns:TarifniBroj', '', ns).strip()
                        naziv = stavka.findtext('ns:NazivRobe', '', ns).strip()
                        if tarifa and naziv:
                            cursor.execute(
                                """
                                INSERT INTO catalogs.product_tariff_mapping
                                    (product_code, naziv_robe, commodity_code, precision_1, usage_count)
                                VALUES (%s, %s, %s, '000', 1)
                                ON CONFLICT (product_code, naziv_robe, commodity_code)
                                DO UPDATE SET usage_count = catalogs.product_tariff_mapping.usage_count + 1
                                """,
                                ('', naziv, tarifa)
                            )
                            saved += 1
                except Exception as e:
                    logger.warning(f"Ne mogu parsirati {xml_path}: {e}")
                    continue

            conn.commit()
        logger.info(f"✅ {saved} tarifnih brojeva dodato u bazu znanja")
        return saved
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════
# RUNTIME LOOKUP - Ovo se koristi u agentu
# ══════════════════════════════════════════════════════════════════════

def _mark_hit(cursor, conn, row_id: int) -> None:
    """
    Označi pogodak u indeksu (use_count++, last_used=NOW) po id-u konkretnog
    reda. Pozivano iz find_xml_for_pair/find_xml_by_consignee — bez ovoga
    statistika ostaje zamrznuta jer nijedan pozivalac lookupa ne javlja nazad
    da je pronađeni XML stvarno iskorišten.
    """
    try:
        cursor.execute("""
            UPDATE catalogs.exporter_xml_index
            SET use_count = use_count + 1, last_used = NOW()
            WHERE id = %s
        """, (row_id,))
        conn.commit()
    except Exception as e:
        logger.warning(f"Greška pri označavanju pogotka (id={row_id}): {e}")


def find_xml_for_pair(exporter_hint: str, consignee_jib: str = "", consignee_hint: str = "") -> Optional[Dict]:
    """
    Pronađi XML filepath za dati PAR (exporter + consignee).

    Lookup prioritet:
    1. Tačan match po exporter + consignee_jib (JIB je jedinstven!)
    2. Tačan match po exporter + consignee_normalized (ako nema JIB)
    3. Tačan match po exporter (bilo koji consignee)
    4. Fuzzy match po exporter

    Args:
        exporter_hint: Ime exportera (iz fakture)
        consignee_jib: JIB consignee-a (preferovano - jedinstven identifikator)
        consignee_hint: Ime consignee-a (fallback ako nema JIB)

    Returns:
        Dict sa xml_filepath, exporter_original, consignee_original, consignee_jib, etc.
        ili None ako nije pronađen
    """
    if not exporter_hint:
        return None

    exp_norm = normalize_exporter_name(exporter_hint)
    jib = (consignee_jib or "").strip()
    cons_norm = normalize_exporter_name(consignee_hint) if consignee_hint else ""

    if not exp_norm:
        return None

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 1. Direktan match po exporter + JIB (najtačniji)
            if jib:
                cursor.execute("""
                    SELECT id, exporter_original, consignee_original, consignee_jib,
                           xml_filepath, declaration_date, use_count
                    FROM catalogs.exporter_xml_index
                    WHERE exporter_normalized = %s AND consignee_jib = %s
                """, (exp_norm, jib))

                row = cursor.fetchone()
                if row:
                    _mark_hit(cursor, conn, row['id'])
                    return {
                        'xml_filepath': row['xml_filepath'],
                        'exporter_original': row['exporter_original'],
                        'consignee_original': row['consignee_original'],
                        'consignee_jib': row['consignee_jib'],
                        'declaration_date': row['declaration_date'],
                        'match_type': 'exact_jib'
                    }

            # 2. Match po exporter + consignee_normalized (ako nema JIB)
            if cons_norm:
                cursor.execute("""
                    SELECT id, exporter_original, consignee_original, consignee_jib,
                           xml_filepath, declaration_date, use_count
                    FROM catalogs.exporter_xml_index
                    WHERE exporter_normalized = %s AND consignee_normalized = %s
                    ORDER BY use_count DESC, declaration_date DESC
                    LIMIT 1
                """, (exp_norm, cons_norm))

                row = cursor.fetchone()
                if row:
                    _mark_hit(cursor, conn, row['id'])
                    return {
                        'xml_filepath': row['xml_filepath'],
                        'exporter_original': row['exporter_original'],
                        'consignee_original': row['consignee_original'],
                        'consignee_jib': row['consignee_jib'],
                        'declaration_date': row['declaration_date'],
                        'match_type': 'exact_name'
                    }

            # 3. Samo po exporteru (bilo koji consignee)
            cursor.execute("""
                SELECT id, exporter_original, consignee_original, consignee_jib,
                       xml_filepath, declaration_date, use_count
                FROM catalogs.exporter_xml_index
                WHERE exporter_normalized = %s
                ORDER BY use_count DESC, declaration_date DESC
                LIMIT 1
            """, (exp_norm,))

            row = cursor.fetchone()
            if row:
                _mark_hit(cursor, conn, row['id'])
                return {
                    'xml_filepath': row['xml_filepath'],
                    'exporter_original': row['exporter_original'],
                    'consignee_original': row['consignee_original'],
                    'consignee_jib': row['consignee_jib'],
                    'declaration_date': row['declaration_date'],
                    'match_type': 'exporter_only'
                }

            # 4. Fuzzy match po exporteru
            cursor.execute("""
                SELECT id, exporter_normalized, exporter_original, consignee_original, consignee_jib,
                       xml_filepath, declaration_date, use_count
                FROM catalogs.exporter_xml_index
                ORDER BY use_count DESC, declaration_date DESC
                LIMIT 300
            """)

            rows = cursor.fetchall()
            best_match = None
            best_score = 0.0

            for row in rows:
                score = _similarity_score(exp_norm, row['exporter_normalized'])
                if score > best_score and score >= FUZZY_MATCH_THRESHOLD:
                    best_score = score
                    best_match = row

            if best_match:
                _mark_hit(cursor, conn, best_match['id'])
                return {
                    'xml_filepath': best_match['xml_filepath'],
                    'exporter_original': best_match['exporter_original'],
                    'consignee_original': best_match['consignee_original'],
                    'consignee_jib': best_match['consignee_jib'],
                    'declaration_date': best_match['declaration_date'],
                    'match_type': f'fuzzy ({best_score:.0%})'
                }

    except Exception as e:
        logger.error(f"Greška pri lookupu: {e}")
    finally:
        conn.close()

    return None


def find_xml_by_consignee(consignee_jib: str = "", consignee_hint: str = "") -> Optional[Dict]:
    """
    Pronađi XML po consignee-u (uvozniku/primaocu) — za uvozne deklaracije (IM).

    Lookup prioritet:
    1. Tačan match po consignee_jib
    2. Tačan match po consignee_normalized
    3. Fuzzy match po consignee_normalized

    Returns:
        Dict sa xml_filepath i meta-podacima, ili None
    """
    jib = (consignee_jib or "").strip()
    cons_norm = normalize_exporter_name(consignee_hint) if consignee_hint else ""

    if not jib and not cons_norm:
        return None

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 1. Tačan match po JIB-u
            if jib:
                cursor.execute("""
                    SELECT id, exporter_original, consignee_original, consignee_jib,
                           xml_filepath, declaration_date, use_count
                    FROM catalogs.exporter_xml_index
                    WHERE consignee_jib = %s
                    ORDER BY use_count DESC, declaration_date DESC
                    LIMIT 1
                """, (jib,))
                row = cursor.fetchone()
                if row:
                    _mark_hit(cursor, conn, row['id'])
                    return {
                        'xml_filepath': row['xml_filepath'],
                        'exporter_original': row['exporter_original'],
                        'consignee_original': row['consignee_original'],
                        'consignee_jib': row['consignee_jib'],
                        'declaration_date': row['declaration_date'],
                        'match_type': 'consignee_jib'
                    }

            # 2. Tačan match po imenu
            if cons_norm:
                cursor.execute("""
                    SELECT id, exporter_original, consignee_original, consignee_jib,
                           xml_filepath, declaration_date, use_count
                    FROM catalogs.exporter_xml_index
                    WHERE consignee_normalized = %s
                    ORDER BY use_count DESC, declaration_date DESC
                    LIMIT 1
                """, (cons_norm,))
                row = cursor.fetchone()
                if row:
                    _mark_hit(cursor, conn, row['id'])
                    return {
                        'xml_filepath': row['xml_filepath'],
                        'exporter_original': row['exporter_original'],
                        'consignee_original': row['consignee_original'],
                        'consignee_jib': row['consignee_jib'],
                        'declaration_date': row['declaration_date'],
                        'match_type': 'consignee_name'
                    }

            # 3. Fuzzy match po consignee imenu
            if cons_norm:
                cursor.execute("""
                    SELECT id, consignee_normalized, exporter_original, consignee_original,
                           consignee_jib, xml_filepath, declaration_date, use_count
                    FROM catalogs.exporter_xml_index
                    ORDER BY use_count DESC, declaration_date DESC
                    LIMIT 300
                """)
                rows = cursor.fetchall()
                best_match = None
                best_score = 0.0
                for row in rows:
                    score = _similarity_score(cons_norm, row['consignee_normalized'])
                    if score > best_score and score >= FUZZY_MATCH_THRESHOLD:
                        best_score = score
                        best_match = row
                if best_match:
                    _mark_hit(cursor, conn, best_match['id'])
                    return {
                        'xml_filepath': best_match['xml_filepath'],
                        'exporter_original': best_match['exporter_original'],
                        'consignee_original': best_match['consignee_original'],
                        'consignee_jib': best_match['consignee_jib'],
                        'declaration_date': best_match['declaration_date'],
                        'match_type': f'consignee_fuzzy ({best_score:.0%})'
                    }
    except Exception as e:
        logger.error(f"Greška pri consignee lookupu: {e}")
    finally:
        conn.close()

    return None


# Backward compatibility
def find_xml_for_exporter(exporter_hint: str) -> Optional[Dict]:
    """Backward compatibility - samo exporter."""
    return find_xml_for_pair(exporter_hint)


def increment_use_count(exporter_normalized: str, consignee_jib: str = "", consignee_normalized: str = ""):
    """Inkrementira broj korištenja za par (po JIB ako postoji)."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            if consignee_jib:
                cursor.execute("""
                    UPDATE catalogs.exporter_xml_index
                    SET use_count = use_count + 1, last_used = NOW()
                    WHERE exporter_normalized = %s AND consignee_jib = %s
                """, (exporter_normalized, consignee_jib))
            elif consignee_normalized:
                cursor.execute("""
                    UPDATE catalogs.exporter_xml_index
                    SET use_count = use_count + 1, last_used = NOW()
                    WHERE exporter_normalized = %s AND consignee_normalized = %s
                """, (exporter_normalized, consignee_normalized))
            else:
                cursor.execute("""
                    UPDATE catalogs.exporter_xml_index
                    SET use_count = use_count + 1, last_used = NOW()
                    WHERE exporter_normalized = %s
                """, (exporter_normalized,))
            conn.commit()
    except Exception as e:
        logger.warning(f"Greška pri inkrementiranju use_count: {e}")
    finally:
        conn.close()


def update_mapping(exporter_normalized: str, consignee_jib: str, xml_filepath: str,
                   exporter_original: str, consignee_original: str, consignee_normalized: str = ""):
    """
    Ažurira mapiranje (korisnik je ručno izabrao drugi XML).

    Args:
        exporter_normalized: Normalizovano ime exportera
        consignee_jib: JIB consignee-a (jedinstven ključ)
        xml_filepath: Putanja do novog XML-a
        exporter_original: Originalno ime exportera (iz XML-a)
        consignee_original: Originalno ime consignee-a (iz XML-a)
        consignee_normalized: Normalizovano ime (opciono, za display)
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            new_date = parse_declaration_date(Path(xml_filepath))

            cursor.execute("""
                INSERT INTO catalogs.exporter_xml_index
                (exporter_normalized, consignee_normalized, consignee_jib,
                 exporter_original, consignee_original, xml_filepath, declaration_date, use_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 1)
                ON CONFLICT (exporter_normalized, consignee_jib, consignee_normalized) DO UPDATE SET
                    exporter_original = EXCLUDED.exporter_original,
                    consignee_original = EXCLUDED.consignee_original,
                    xml_filepath = EXCLUDED.xml_filepath,
                    declaration_date = EXCLUDED.declaration_date,
                    use_count = catalogs.exporter_xml_index.use_count + 1,
                    last_used = NOW()
            """, (exporter_normalized, consignee_normalized, consignee_jib,
                  exporter_original, consignee_original, xml_filepath, new_date))
            conn.commit()

        logger.info(f"✅ Ažurirano mapiranje: {exporter_normalized}+{consignee_jib} → {Path(xml_filepath).name}")
    except Exception as e:
        logger.error(f"Greška pri ažuriranju mapiranja: {e}")
    finally:
        conn.close()


def _similarity_score(a: str, b: str) -> float:
    """
    Računa sličnost dva stringa.
    
    Kombinuje:
    - SequenceMatcher ratio
    - Token overlap
    """
    if not a or not b:
        return 0.0
    
    # SequenceMatcher
    seq_score = SequenceMatcher(None, a, b).ratio()
    
    # Token overlap
    a_tokens = set(a.split())
    b_tokens = set(b.split())
    
    if a_tokens and b_tokens:
        overlap = len(a_tokens & b_tokens) / max(len(a_tokens), len(b_tokens))
        return max(seq_score, overlap)
    
    return seq_score


def get_all_pairs() -> List[Dict]:
    """Vrati sve parove iz indeksa (za debug/admin)."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT exporter_normalized, consignee_normalized, consignee_jib,
                       exporter_original, consignee_original,
                       xml_filepath, declaration_date, use_count, last_used
                FROM catalogs.exporter_xml_index
                ORDER BY use_count DESC
            """)
            rows = cursor.fetchall()
            return [
                {
                    'exporter_normalized': r['exporter_normalized'],
                    'consignee_normalized': r['consignee_normalized'],
                    'consignee_jib': r['consignee_jib'],
                    'exporter_original': r['exporter_original'],
                    'consignee_original': r['consignee_original'],
                    'xml_filepath': r['xml_filepath'],
                    'declaration_date': r['declaration_date'],
                    'use_count': r['use_count'],
                    'last_used': r['last_used']
                }
                for r in rows
            ]
    finally:
        conn.close()


# Backward compatibility
def get_all_exporters() -> List[Dict]:
    """Backward compatibility."""
    return get_all_pairs()


def get_stats() -> Dict:
    """Vrati statistiku indeksa."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            _ensure_table(cursor)
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(use_count) as total_uses,
                    MAX(last_used) as last_used_any,
                    COUNT(DISTINCT exporter_normalized) as unique_exporters,
                    COUNT(DISTINCT consignee_jib) FILTER (WHERE consignee_jib != '') as unique_jibs,
                    COUNT(DISTINCT consignee_normalized) as unique_consignees
                FROM catalogs.exporter_xml_index
            """)
            row = cursor.fetchone()
            stats = {
                'total_pairs': row['total'],
                'total_uses': row['total_uses'] or 0,
                'last_used_any': row['last_used_any'],
                'unique_exporters': row['unique_exporters'],
                'unique_jibs': row['unique_jibs'],
                'unique_consignees': row['unique_consignees']
            }
        conn.commit()
        return stats
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════

def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Exporter XML Indexer")
    parser.add_argument('--reindex', action='store_true', help='Force reindex')
    parser.add_argument('--clear', action='store_true', help='Clear index')
    parser.add_argument('--stats', action='store_true', help='Show stats')
    parser.add_argument('--list', action='store_true', help='List all pairs')
    parser.add_argument('--lookup', type=str, metavar='EXP|CONS', 
                       help='Test lookup: EXP|CONS (npr. "ENMON|IPEK" ili samo "ENMON")')
    
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    if args.clear:
        clear_index()
        return
    
    if args.stats:
        stats = get_stats()
        print(f"\n📊 INDEX STATS:")
        print(f"   Ukupno parova: {stats['total_pairs']}")
        print(f"   Jedinstvenih exportera: {stats['unique_exporters']}")
        print(f"   Consignee sa JIB-om: {stats['unique_jibs']}")
        print(f"   Jedinstvenih consignee naziva: {stats['unique_consignees']}")
        print(f"   Ukupno korištenja: {stats['total_uses']}")
        return
    
    if args.lookup:
        # Format: "EXPORTER|JIB" ili "EXPORTER|JIB|NAZIV" ili samo "EXPORTER"
        parts = args.lookup.split('|')
        exporter = parts[0].strip() if len(parts) > 0 else ""
        jib = parts[1].strip() if len(parts) > 1 else ""
        naziv = parts[2].strip() if len(parts) > 2 else ""

        result = find_xml_for_pair(exporter, consignee_jib=jib, consignee_hint=naziv)
        if result:
            fname = Path(result['xml_filepath']).name
            print(f"\n🔍 LOOKUP: '{exporter}' + JIB='{jib}'")
            print(f"   ✅ Match: {result['match_type']}")
            print(f"   📄 XML: {fname}")
            print(f"   📦 Exporter: {result['exporter_original']}")
            print(f"   📥 Consignee: {result['consignee_original']} (JIB: {result.get('consignee_jib', '—')})")
        else:
            print(f"\n🔍 LOOKUP: '{exporter}' + JIB='{jib}'")
            print(f"   ❌ Nije pronađen")
        return
    
    if args.list:
        pairs = get_all_pairs()
        print(f"\n📋 SVI PAROVI ({len(pairs)}):")
        for p in pairs[:50]:
            jib_str = f" [{p['consignee_jib']}]" if p.get('consignee_jib') else ""
            print(f"   {p['exporter_normalized']:<30} → {p['consignee_normalized']:<25}{jib_str} ({Path(p['xml_filepath']).name})")
        if len(pairs) > 50:
            print(f"   ... i još {len(pairs) - 50} parova")
        return
    
    # Default: index
    create_table_if_not_exists()
    count = reindex()
    print(f"\n✅ Indexiranje završeno: {count} parova")


if __name__ == "__main__":
    main()
