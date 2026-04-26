"""
Exporter XML Indexer

Jednokratno indexira sve XML-ove iz docs/NOVA ASIKUDA i pravi bazu
PAR (exporter + consignee) â†’ xml_filepath za brzi lookup.

Workflow:
1. ÄŒita SVE XML-ove iz foldera
2. Ekstrahuje Exporter_name i Consignee_name iz svakog
3. Normalizuje imena (uppercase, uklanja DOO, D.O.O., etc.)
4. Za svaki par uzima NAJNOVIJI XML (po declaration date)
5. SaÄuva u bazu catalogs.exporter_xml_index

Usage:
    python -m services.agent.exporter_xml_indexer
    python -m services.agent.exporter_xml_indexer --reindex  # Force reindex
    python -m services.agent.exporter_xml_indexer --lookup "ENMON|IPEK"  # Test lookup
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

logger = logging.getLogger("deklarant_pro.exporter_indexer")

FUZZY_MATCH_THRESHOLD = 0.92


def get_db_connection():
    """Konekcija na bazu koristeÄ‡i centralni config."""
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
    """Vrati folder za XML uÄenje iz env override-a ili projektne strukture."""
    import os
    from config.settings import PROJECT_ROOT

    override = os.getenv("XML_LEARNING_FOLDER", "").strip()
    if override:
        return Path(override).expanduser()
    return PROJECT_ROOT / "docs" / "NOVA ASIKUDA"


XML_FOLDER = get_xml_folder()

# GodiÅ¡nji filter â€” gornja granica je tekuÄ‡a + 1 da pokrije nove deklaracije
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
    Normalizuje ime exportera za uporeÄ‘ivanje.
    
    'ENMON d.o.o.' â†’ 'ENMON'
    'Å umaprom Commerce D.O.O.' â†’ 'Å UMAPROM COMMERCE'
    'KONZUM DOO BEOGRAD' â†’ 'KONZUM'
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
        r'^TRGOVINSKA\s+DRUÅ TVA?\s*',
        r'^PREDMUZEÄ†E\s+',
        r'^DRUÅ TVO\s+SA\s+OGRANIÄŒENOM\s+ODGOVORNOÅ Ä†U\s*',
        r'^DOO\s+',
        r'^D\.\s*O\.\s*O\.?\s+',
    ]

    for pattern in suffixes_to_remove:
        name = re.sub(pattern, '', name, flags=re.IGNORECASE).strip()
    for pattern in prefixes_to_remove:
        name = re.sub(pattern, '', name, flags=re.IGNORECASE).strip()

    # Ukloni viÅ¡estruke zareze/taÄke na kraju
    name = re.sub(r'[,.\s]+$', '', name).strip()

    # Ukloni brojeve na kraju (JMBG, PIB, etc.)
    name = re.sub(r'\s+\d{6,}.*$', '', name)
    
    # Collapse whitespace
    name = re.sub(r'\s+', ' ', name).strip()
    
    return name


def parse_declaration_date(xml_path: Path) -> Optional[datetime]:
    """IzvuÄe datum deklaracije iz XML-a (ASYCUDA World format)."""
    try:
        tree = ET.parse(str(xml_path))
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
        logger.debug(f"Nije moguÄ‡e izvuÄ‡i datum iz {xml_path.name}: {e}")

    return None


def extract_parties_from_xml(xml_path: Path) -> tuple[Optional[str], Optional[str], Optional[str], Optional[datetime]]:
    """
    Ekstrahuje ime exportera, consignee-a i datum iz XML-a.
    
    Returns:
        (exporter_name, consignee_name, consignee_jib, declaration_date) ili (None, None, None, None)
    """
    try:
        tree = ET.parse(str(xml_path))
        root = tree.getroot()
        
        exporter_name = None
        consignee_name = None
        
        # Exporter - viÅ¡e XPath varijanti
        for xpath in [".//Traders/Exporter/Exporter_name", ".//Exporter/Name"]:
            elem = root.find(xpath)
            if elem is not None and elem.text and elem.text.strip():
                exporter_name = elem.text.strip().split('\n')[0].strip()
                if exporter_name:
                    break
        
        # Consignee - viÅ¡e XPath varijanti
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
        logger.debug(f"GreÅ¡ka pri parsiranju {xml_path.name}: {e}")
        return None, None, None, None


# Backward compatibility
def extract_exporter_from_xml(xml_path: Path) -> tuple[Optional[str], Optional[datetime]]:
    """Backward compatibility - samo exporter."""
    exp, _, _jib, date = extract_parties_from_xml(xml_path)
    return exp, date


def scan_xml_folder() -> Dict[Tuple[str, str], ExporterEntry]:
    """
    Skenira folder i gradi dict (exporter, consignee) â†’ najbolji XML.
    
    Za svaki par pamti samo NAJNOVIJI XML.
    
    Returns:
        Dict[(exporter_norm, consignee_norm), ExporterEntry]
    """
    if not XML_FOLDER.exists():
        logger.error(f"XML folder ne postoji: {XML_FOLDER}")
        return {}
    
    xml_files = list(XML_FOLDER.glob("*.xml"))
    logger.info(f"ðŸ“‚ PronaÄ‘eno {len(xml_files)} XML fajlova")
    
    # GrupiÅ¡i po PARU (exporter + consignee_jib) - Äuvaj najnoviji
    # KljuÄ: (exporter_norm, consignee_jib) ako JIB postoji, inaÄe (exporter_norm, consignee_norm)
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

        # GodiÅ¡nji filter
        if declaration_date:
            if declaration_date.year < YEAR_FROM or declaration_date.year > YEAR_TO:
                logger.debug(f"   PreskaÄem {xml_path.name} - datum {declaration_date.year} van opsega")
                continue

        # KljuÄ: JIB ima prednost, inaÄe normalizovano ime
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

        # Ako veÄ‡ imamo ovaj par, zadrÅ¾i najnoviji
        if key in pairs:
            existing = pairs[key]
            if declaration_date and (not existing.declaration_date or declaration_date > existing.declaration_date):
                pairs[key] = entry
        else:
            pairs[key] = entry
    
    logger.info(f"âœ… Indexiranje zavrÅ¡eno: {len(pairs)} jedinstvenih parova, {skipped} preskoÄeno")
    
    return pairs


def _ensure_table(cursor) -> None:
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
    """Kreira tabelu sa parovima bez brisanja postojeÄ‡ih podataka."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            _ensure_table(cursor)
        conn.commit()
        logger.info("âœ… Tabela catalogs.exporter_xml_index spremna")
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
    SaÄuva index parova u bazu.
    
    Koristi INSERT ... ON CONFLICT za aÅ¾uriranje postojeÄ‡ih.
    
    Returns:
        Broj saÄuvanih redova
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            _ensure_table(cursor)
            saved = _save_pairs(cursor, pairs)
            conn.commit()
        
        logger.info(f"âœ… SaÄuvano {saved} exportera u bazu")
        return saved
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def clear_index():
    """OÄisti cijeli index."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            _ensure_table(cursor)
            cursor.execute("DELETE FROM catalogs.exporter_xml_index")
            conn.commit()
        logger.info("ðŸ—‘ï¸ Index oÄiÅ¡Ä‡en")
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
    logger.info("ðŸ”„ POÄŒINJEM REINDEXIRANJE...")
    exporters = scan_xml_folder()
    if not exporters:
        logger.warning("âš ï¸ Nema validnih XML parova; postojeÄ‡i indeks nije mijenjan")
        return 0

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            _ensure_table(cursor)
            cursor.execute("DELETE FROM catalogs.exporter_xml_index")
            saved = _save_pairs(cursor, exporters)
        conn.commit()
        logger.info(f"âœ… Atomski reindex zavrÅ¡en: {saved} parova")
        return saved
    except Exception:
        conn.rollback()
        logger.exception("Reindex nije uspio; prethodni indeks je saÄuvan")
        raise
    finally:
        conn.close()


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# RUNTIME LOOKUP - Ovo se koristi u agentu
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

def find_xml_for_pair(exporter_hint: str, consignee_jib: str = "", consignee_hint: str = "") -> Optional[Dict]:
    """
    PronaÄ‘i XML filepath za dati PAR (exporter + consignee).

    Lookup prioritet:
    1. TaÄan match po exporter + consignee_jib (JIB je jedinstven!)
    2. TaÄan match po exporter + consignee_normalized (ako nema JIB)
    3. TaÄan match po exporter (bilo koji consignee)
    4. Fuzzy match po exporter

    Args:
        exporter_hint: Ime exportera (iz fakture)
        consignee_jib: JIB consignee-a (preferovano - jedinstven identifikator)
        consignee_hint: Ime consignee-a (fallback ako nema JIB)

    Returns:
        Dict sa xml_filepath, exporter_original, consignee_original, consignee_jib, etc.
        ili None ako nije pronaÄ‘en
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
            # 1. Direktan match po exporter + JIB (najtaÄniji)
            if jib:
                cursor.execute("""
                    SELECT exporter_original, consignee_original, consignee_jib,
                           xml_filepath, declaration_date, use_count
                    FROM catalogs.exporter_xml_index
                    WHERE exporter_normalized = %s AND consignee_jib = %s
                """, (exp_norm, jib))

                row = cursor.fetchone()
                if row:
                    return {
                        'xml_filepath': row[3],
                        'exporter_original': row[0],
                        'consignee_original': row[1],
                        'consignee_jib': row[2],
                        'declaration_date': row[4],
                        'match_type': 'exact_jib'
                    }

            # 2. Match po exporter + consignee_normalized (ako nema JIB)
            if cons_norm:
                cursor.execute("""
                    SELECT exporter_original, consignee_original, consignee_jib,
                           xml_filepath, declaration_date, use_count
                    FROM catalogs.exporter_xml_index
                    WHERE exporter_normalized = %s AND consignee_normalized = %s
                    ORDER BY use_count DESC, declaration_date DESC
                    LIMIT 1
                """, (exp_norm, cons_norm))

                row = cursor.fetchone()
                if row:
                    return {
                        'xml_filepath': row[3],
                        'exporter_original': row[0],
                        'consignee_original': row[1],
                        'consignee_jib': row[2],
                        'declaration_date': row[4],
                        'match_type': 'exact_name'
                    }

            # 3. Samo po exporteru (bilo koji consignee)
            cursor.execute("""
                SELECT exporter_original, consignee_original, consignee_jib,
                       xml_filepath, declaration_date, use_count
                FROM catalogs.exporter_xml_index
                WHERE exporter_normalized = %s
                ORDER BY use_count DESC, declaration_date DESC
                LIMIT 1
            """, (exp_norm,))

            row = cursor.fetchone()
            if row:
                return {
                    'xml_filepath': row[3],
                    'exporter_original': row[0],
                    'consignee_original': row[1],
                    'consignee_jib': row[2],
                    'declaration_date': row[4],
                    'match_type': 'exporter_only'
                }

            # 4. Fuzzy match po exporteru
            cursor.execute("""
                SELECT exporter_normalized, exporter_original, consignee_original, consignee_jib,
                       xml_filepath, declaration_date, use_count
                FROM catalogs.exporter_xml_index
                ORDER BY use_count DESC, declaration_date DESC
                LIMIT 300
            """)

            rows = cursor.fetchall()
            best_match = None
            best_score = 0.0

            for row in rows:
                score = _similarity_score(exp_norm, row[0])
                if score > best_score and score >= FUZZY_MATCH_THRESHOLD:
                    best_score = score
                    best_match = row

            if best_match:
                return {
                    'xml_filepath': best_match[4],
                    'exporter_original': best_match[1],
                    'consignee_original': best_match[2],
                    'consignee_jib': best_match[3],
                    'declaration_date': best_match[5],
                    'match_type': f'fuzzy ({best_score:.0%})'
                }

    except Exception as e:
        logger.error(f"GreÅ¡ka pri lookupu: {e}")
    finally:
        conn.close()

    return None


def find_xml_by_consignee(consignee_jib: str = "", consignee_hint: str = "") -> Optional[Dict]:
    """
    PronaÄ‘i XML po consignee-u (uvozniku/primaocu) â€” za uvozne deklaracije (IM).

    Lookup prioritet:
    1. TaÄan match po consignee_jib
    2. TaÄan match po consignee_normalized
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
            # 1. TaÄan match po JIB-u
            if jib:
                cursor.execute("""
                    SELECT exporter_original, consignee_original, consignee_jib,
                           xml_filepath, declaration_date, use_count
                    FROM catalogs.exporter_xml_index
                    WHERE consignee_jib = %s
                    ORDER BY use_count DESC, declaration_date DESC
                    LIMIT 1
                """, (jib,))
                row = cursor.fetchone()
                if row:
                    return {
                        'xml_filepath': row[3],
                        'exporter_original': row[0],
                        'consignee_original': row[1],
                        'consignee_jib': row[2],
                        'declaration_date': row[4],
                        'match_type': 'consignee_jib'
                    }

            # 2. TaÄan match po imenu
            if cons_norm:
                cursor.execute("""
                    SELECT exporter_original, consignee_original, consignee_jib,
                           xml_filepath, declaration_date, use_count
                    FROM catalogs.exporter_xml_index
                    WHERE consignee_normalized = %s
                    ORDER BY use_count DESC, declaration_date DESC
                    LIMIT 1
                """, (cons_norm,))
                row = cursor.fetchone()
                if row:
                    return {
                        'xml_filepath': row[3],
                        'exporter_original': row[0],
                        'consignee_original': row[1],
                        'consignee_jib': row[2],
                        'declaration_date': row[4],
                        'match_type': 'consignee_name'
                    }

            # 3. Fuzzy match po consignee imenu
            if cons_norm:
                cursor.execute("""
                    SELECT consignee_normalized, exporter_original, consignee_original,
                           consignee_jib, xml_filepath, declaration_date, use_count
                    FROM catalogs.exporter_xml_index
                    ORDER BY use_count DESC, declaration_date DESC
                    LIMIT 300
                """)
                rows = cursor.fetchall()
                best_match = None
                best_score = 0.0
                for row in rows:
                    score = _similarity_score(cons_norm, row[0])
                    if score > best_score and score >= FUZZY_MATCH_THRESHOLD:
                        best_score = score
                        best_match = row
                if best_match:
                    return {
                        'xml_filepath': best_match[4],
                        'exporter_original': best_match[1],
                        'consignee_original': best_match[2],
                        'consignee_jib': best_match[3],
                        'declaration_date': best_match[5],
                        'match_type': f'consignee_fuzzy ({best_score:.0%})'
                    }
    except Exception as e:
        logger.error(f"GreÅ¡ka pri consignee lookupu: {e}")
    finally:
        conn.close()

    return None


# Backward compatibility
def find_xml_for_exporter(exporter_hint: str) -> Optional[Dict]:
    """Backward compatibility - samo exporter."""
    return find_xml_for_pair(exporter_hint)


def increment_use_count(exporter_normalized: str, consignee_jib: str = "", consignee_normalized: str = ""):
    """Inkrementira broj koriÅ¡tenja za par (po JIB ako postoji)."""
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
        logger.warning(f"GreÅ¡ka pri inkrementiranju use_count: {e}")
    finally:
        conn.close()


def update_mapping(exporter_normalized: str, consignee_jib: str, xml_filepath: str,
                   exporter_original: str, consignee_original: str, consignee_normalized: str = ""):
    """
    AÅ¾urira mapiranje (korisnik je ruÄno izabrao drugi XML).

    Args:
        exporter_normalized: Normalizovano ime exportera
        consignee_jib: JIB consignee-a (jedinstven kljuÄ)
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

        logger.info(f"âœ… AÅ¾urirano mapiranje: {exporter_normalized}+{consignee_jib} â†’ {Path(xml_filepath).name}")
    except Exception as e:
        logger.error(f"GreÅ¡ka pri aÅ¾uriranju mapiranja: {e}")
    finally:
        conn.close()


def _similarity_score(a: str, b: str) -> float:
    """
    RaÄuna sliÄnost dva stringa.
    
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
                    'exporter_normalized': r[0],
                    'consignee_normalized': r[1],
                    'consignee_jib': r[2],
                    'exporter_original': r[3],
                    'consignee_original': r[4],
                    'xml_filepath': r[5],
                    'declaration_date': r[6],
                    'use_count': r[7],
                    'last_used': r[8]
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
                'total_pairs': row[0],
                'total_uses': row[1] or 0,
                'last_used_any': row[2],
                'unique_exporters': row[3],
                'unique_jibs': row[4],
                'unique_consignees': row[5]
            }
        conn.commit()
        return stats
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# CLI
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

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
        print(f"\nðŸ“Š INDEX STATS:")
        print(f"   Ukupno parova: {stats['total_pairs']}")
        print(f"   Jedinstvenih exportera: {stats['unique_exporters']}")
        print(f"   Consignee sa JIB-om: {stats['unique_jibs']}")
        print(f"   Jedinstvenih consignee naziva: {stats['unique_consignees']}")
        print(f"   Ukupno koriÅ¡tenja: {stats['total_uses']}")
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
            print(f"\nðŸ” LOOKUP: '{exporter}' + JIB='{jib}'")
            print(f"   âœ… Match: {result['match_type']}")
            print(f"   ðŸ“„ XML: {fname}")
            print(f"   ðŸ“¦ Exporter: {result['exporter_original']}")
            print(f"   ðŸ“¥ Consignee: {result['consignee_original']} (JIB: {result.get('consignee_jib', 'â€”')})")
        else:
            print(f"\nðŸ” LOOKUP: '{exporter}' + JIB='{jib}'")
            print(f"   âŒ Nije pronaÄ‘en")
        return
    
    if args.list:
        pairs = get_all_pairs()
        print(f"\nðŸ“‹ SVI PAROVI ({len(pairs)}):")
        for p in pairs[:50]:
            jib_str = f" [{p['consignee_jib']}]" if p.get('consignee_jib') else ""
            print(f"   {p['exporter_normalized']:<30} â†’ {p['consignee_normalized']:<25}{jib_str} ({Path(p['xml_filepath']).name})")
        if len(pairs) > 50:
            print(f"   ... i joÅ¡ {len(pairs) - 50} parova")
        return
    
    # Default: index
    create_table_if_not_exists()
    count = reindex()
    print(f"\nâœ… Indexiranje zavrÅ¡eno: {count} parova")


if __name__ == "__main__":
    main()

