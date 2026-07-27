"""
database/migrate_inspection_document_history.py

Skenira arhivu stvarnih ASYCUDA XML deklaracija i gradi
catalogs.inspection_document_history — istorijski (INFORMATIVNI) trag koje
vrste inspekcijskih dokumenata su stvarno bile priložene za koji tarifni broj.

VAŽNO — ovo NIKAD ne zamjenjuje niti suprimira catalogs.inspection_rules
(zvanično pravno pravilo). Vidi project_rooms/2026-07-22_istorijska-napomena-inspekcije.md
za puno obrazloženje: statični izvor pravila je iz 2015. godine i nikad nije bio
zvanično objedinjen za entitetske inspekcije (samo veterinarska je na nivou BiH),
a noviji zvaničan spisak ne postoji. Ovaj sloj pokazuje "šta se u praksi dešavalo",
korisnik sam odlučuje na osnovu oba izvora.

Pokretanje (default arhiva data/knowledge_base/NOVA ASIKUDA):
    python database/migrate_inspection_document_history.py

Sa drugom arhivom:
    python database/migrate_inspection_document_history.py --xml-dir "H:\\New folder\\NOVA ASIKUDA"

Ponovljeno pokretanje: briše i ponovo gradi sve redove (idempotentno) — arhiva
raste (korisnik dodaje nove fajlove), pa se uvijek računa iz trenutnog punog stanja
umjesto inkrementalnog dodavanja (izbjegava rizik duplog brojanja istih fajlova).
"""

# ============================================================
# SECTION: inspection-document-history-migration
# PURPOSE: Istorijski (informativni) trag priloženih inspekcijskih dokumenata
#          po tarifnom broju, iz stvarnih ASYCUDA XML deklaracija
# DOC: project_rooms/2026-07-22_istorijska-napomena-inspekcije.md
# ============================================================

import argparse
import logging
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db import get_db_connection

logger = logging.getLogger("deklarant_pro.inspection_document_history")

_DEFAULT_XML_DIR = Path(__file__).parent.parent / "data" / "knowledge_base" / "NOVA ASIKUDA"

# Mapiranje kodova priloženih dokumenata (Rubrika 44) na inspection_type ključeve
# iz services/inspection_service.py — stari (troslovni) i noviji (N-prefiksirani)
# kod za ISTI dokument tretiraju se kao ista kategorija.
# Potvrđeno korisnikom 2026-07-22: UVK/N003 = tržna (NE quality_control).
DOCUMENT_CODE_TO_INSPECTION_TYPE: dict[str, str] = {
    "SAN": "sanitary",
    "N852": "sanitary",
    "VET": "veterinary",
    "N853": "veterinary",
    "FIT": "phytosanitary",
    "N851": "phytosanitary",
    "UVK": "market_inspection",
    "N003": "market_inspection",
    "AGL": "medicines_agency",
}


def _create_table(conn) -> None:
    """Kreira tabelu catalogs.inspection_document_history u PostgreSQL."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS catalogs.inspection_document_history (
                id               SERIAL PRIMARY KEY,
                tariff_code_norm VARCHAR(20) NOT NULL,
                inspection_type  VARCHAR(50) NOT NULL,
                document_code    VARCHAR(20),
                document_name    VARCHAR(200),
                usage_count      INTEGER     DEFAULT 1,
                first_seen       TIMESTAMP   DEFAULT NOW(),
                last_seen        TIMESTAMP   DEFAULT NOW(),
                UNIQUE (tariff_code_norm, inspection_type)
            );
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_insp_doc_hist_tariff
                ON catalogs.inspection_document_history (tariff_code_norm);
        """)
    conn.commit()
    logger.info("Tabela catalogs.inspection_document_history kreirana/potvrđena")


def _clear_existing(conn) -> None:
    """Briše sve redove — reimport je idempotentan (arhiva se skenira iznova u cjelini)."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM catalogs.inspection_document_history")
    conn.commit()
    logger.info("Stari redovi obrisani")


def scan_xml_archive(xml_dir: Path) -> dict[tuple[str, str], dict]:
    """
    Skenira ASYCUDA XML fajlove u xml_dir i vrati agregirane brojače.

    Vraća dict {(tariff_code_norm, inspection_type): {"document_code": str,
    "document_name": str, "usage_count": int}} — document_code/name čuvaju
    NAJČEŠĆU varijantu viđenu za taj par (ne posljednju), radi stabilnosti
    prikaza kad postoje ćirilične/latinične varijante istog naziva.
    """
    xml_files = sorted(xml_dir.glob("*.xml"))
    logger.info("Skeniram %d XML fajlova u %s", len(xml_files), xml_dir)

    # (tariff, insp_type) -> {"count": int, "names": Counter(document_code, document_name)}
    from collections import Counter
    aggregated: dict[tuple[str, str], dict] = {}

    parse_errors = 0
    for xml_path in xml_files:
        try:
            tree = ET.parse(xml_path)
        except ET.ParseError as e:
            parse_errors += 1
            logger.debug("Preskačem %s (parse greška: %s)", xml_path.name, e)
            continue

        root = tree.getroot()
        for item in root.findall(".//Item"):
            tarif_elem = item.find(".//Tarification/HScode/Commodity_code")
            tarif = tarif_elem.text.strip() if tarif_elem is not None and tarif_elem.text else ""
            if not re.match(r'^\d{8}$', tarif):
                continue

            for doc in item.findall(".//Attached_documents"):
                code_elem = doc.find("Attached_document_code")
                name_elem = doc.find("Attached_document_name")
                code = code_elem.text.strip() if code_elem is not None and code_elem.text else ""
                name = name_elem.text.strip() if name_elem is not None and name_elem.text else ""

                insp_type = DOCUMENT_CODE_TO_INSPECTION_TYPE.get(code)
                if not insp_type:
                    continue

                key = (tarif, insp_type)
                if key not in aggregated:
                    aggregated[key] = {"count": 0, "names": Counter()}
                aggregated[key]["count"] += 1
                aggregated[key]["names"][(code, name)] += 1

    if parse_errors:
        logger.warning("Preskočeno %d fajlova zbog XML parse grešaka", parse_errors)

    result: dict[tuple[str, str], dict] = {}
    for key, data in aggregated.items():
        (best_code, best_name), _ = data["names"].most_common(1)[0]
        result[key] = {
            "document_code": best_code,
            "document_name": best_name,
            "usage_count": data["count"],
        }
    return result


def _insert_rows(conn, rows: dict[tuple[str, str], dict]) -> int:
    """Umetne agregirane redove u catalogs.inspection_document_history."""
    if not rows:
        return 0
    with conn.cursor() as cur:
        for (tariff, insp_type), data in rows.items():
            cur.execute("""
                INSERT INTO catalogs.inspection_document_history
                    (tariff_code_norm, inspection_type, document_code,
                     document_name, usage_count)
                VALUES (%s, %s, %s, %s, %s)
            """, (tariff, insp_type, data["document_code"], data["document_name"],
                  data["usage_count"]))
    conn.commit()
    return len(rows)


def migrate(xml_dir: Path) -> None:
    """Glavna funkcija migracije."""
    logger.info("Migracija istorije inspekcijskih dokumenata → PostgreSQL")

    if not xml_dir.exists():
        raise FileNotFoundError(f"XML arhiva ne postoji: {xml_dir}")

    aggregated = scan_xml_archive(xml_dir)

    with get_db_connection() as conn:
        _create_table(conn)
        _clear_existing(conn)
        n = _insert_rows(conn, aggregated)
        logger.info("UKUPNO: %d (tarifni_broj, inspection_type) parova umetnuto", n)

        with conn.cursor() as cur:
            cur.execute("""
                SELECT inspection_type, COUNT(*) as cnt, SUM(usage_count) as total_usage
                FROM catalogs.inspection_document_history
                GROUP BY inspection_type ORDER BY inspection_type
            """)
            logger.info("=== STATISTIKA ===")
            for row in cur.fetchall():
                logger.info(
                    "  %-20s: %4d tarifnih brojeva (%d ukupno pojavljivanja u arhivi)",
                    row["inspection_type"], row["cnt"], row["total_usage"],
                )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--xml-dir",
        type=str,
        default=str(_DEFAULT_XML_DIR),
        help="Putanja do arhive ASYCUDA XML deklaracija (default: data/knowledge_base/NOVA ASIKUDA)",
    )
    args = parser.parse_args()
    migrate(Path(args.xml_dir))
