# AGENT_CODE_DOC: tariff-doc-history
"""
Uči iz istorijskih XML deklaracija koje su priložene isprave (doc codes) bile
korištene za određeni tarifni broj. Pamti u SQLite tabeli tariff_doc_history.

Tok:
  import_from_xml_folder() → parsira SVE XML-ove iz foldera → upisuje u DB
  get_suggested_docs(tariff_code) → vraća prijedloge za novo naimenovanje
  record_usage() → poziva se pri bildovanju XML-a → auto-učenje

Kodovi koji se NIKAD ne predlažu (prisutni u svakoj deklaraciji):
  _UNIVERSAL_CODES — N380, DIS, DV1, PZT, VOZ, OST, N730
  Ti su već dodani iz XML importa / fakture / vozarine.
"""

import logging
import os
import sqlite3
import xml.etree.ElementTree as ET
from datetime import date
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Kodovi koji se pojavljuju u SVAKOJ deklaraciji bez obzira na tarifni broj —
# ne predlažemo ih jer ih drugi mehanizmi već dodaju.
# Uključuje i stari format ekvivalente (FAK=N380, CMR=N730, ZUT=PZT, OSI=osiguranje).
_UNIVERSAL_CODES = {
    "N380", "DIS", "DV1", "PZT", "VOZ", "OST", "N730", "DUIM",          # novi format — uvijek prisutni
    "FAK", "CMR", "ZUT", "OSI", "ZNP", "OST0",                           # stari format — uvijek prisutni
    "FTAP", "FTA", "FTAT", "FTAТ", "EUP", "EUPT", "TRP", "EFTA", "T1",  # dokazi o porijeklu — stari format
    # PE1/PE2/PE3 se dodaju iz Rb.44.4 — ne predlažu se iz istorije
    "PE1", "PE2", "PE3",
}

# Mapiranje starih šifra → novih (novi format ASYCUDA World)
_CODE_NORMALIZE = {
    "VET":  "N853",  # Veterinarsko uvjerenje
    "SAN":  "N852",  # Sanitarno-zdravstveno uvjerenje
    "UVK":  "N003",  # Uvjerenje o kvaliteti robe
    "FAK":  "N380",  # Faktura (→ već u universal)
    "CMR":  "N730",  # CMR/tovarni list (→ već u universal)
    "ZUT":  "PZT",   # Zavisni troškovi (→ već u universal)
    "FTAP": "FTAP",  # CEFTA/PEM dokaz (ostaje)
    "EUP":  "EUP",   # EU preferencijal (ostaje)
    "FTA":  "FTA",   # CEFTA 2006 (ostaje)
    "TRP":  "TRP",   # Turska povlastica (ostaje)
    "EFTA": "EFTA",  # EFTA sporazum (ostaje)
    "FIT":  "FIT",   # Fitosanitarno uvjerenje (ostaje)
    "AGL":  "AGL",   # Agencija za lijekove (ostaje)
    "PE1":  "PE1",
    "PE2":  "PE2",
    "PE3":  "PE3",
}

_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "database", "deklarant_sistem.db"
)


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


class TariffDocHistoryService:
    """Historija priloženih dokumenata po tarifnom broju — učenje iz XML-ova."""

    # ------------------------------------------------------------------ import

    def import_from_xml_folder(self, *folders: str) -> Dict[str, int]:
        """Skenira sve XML-ove u navedenim folderima i puni tariff_doc_history.

        Vraća rječnik sa statistikama: {'fajlova': N, 'unosa': M, 'grešaka': K}
        """
        stats = {"fajlova": 0, "unosa": 0, "greske": 0}
        for folder in folders:
            if not os.path.isdir(folder):
                logger.warning(f"Folder ne postoji: {folder}")
                continue
            for fname in os.listdir(folder):
                if not fname.lower().endswith(".xml"):
                    continue
                fpath = os.path.join(folder, fname)
                try:
                    added = self.import_from_xml_file(fpath)
                    stats["fajlova"] += 1
                    stats["unosa"] += added
                except Exception as e:
                    logger.warning(f"Greška pri parsiranju {fname}: {e}")
                    stats["greske"] += 1
        logger.info(f"Import završen: {stats}")
        return stats

    def import_from_xml_file(self, filepath: str) -> int:
        """Parsira jedan XML fajl i upisuje tarifa→doc mapiranja. Vraća broj novih/ažuriranih unosa."""
        tree = ET.parse(filepath)
        root = tree.getroot()

        # Tarifni brojevi po stavkama (Item tag — isti u starim i novim XML-ovima)
        tariff_codes: List[str] = []
        for el in root.findall(".//Commodity_code"):
            code = (el.text or "").strip()
            if code and code not in ("null", "0"):
                tariff_codes.append(code[:8])  # uvijek 8 cifara

        if not tariff_codes:
            return 0

        # Priloženi dokumenti na nivou zaglavlja
        header_docs: List[Dict[str, str]] = []
        for ad in root.findall(".//Attached_documents"):
            code_el = ad.find("Attached_document_code")
            name_el = ad.find("Attached_document_name")
            code = (code_el.text or "").strip() if code_el is not None else ""
            name = (name_el.text or "").strip() if name_el is not None else ""
            if code:
                header_docs.append({"code": code, "name": name})

        # Item-level doc kodovi (stari format: "N380 DIS DV1 DUIM" — razmacima)
        item_doc_codes: List[str] = []
        for el in root.findall(".//Attached_doc_item"):
            text = (el.text or "").strip()
            for part in text.split():
                if part and part not in item_doc_codes:
                    item_doc_codes.append(part)

        # Kombinirani set dokumenata za ovu deklaraciju
        all_docs: Dict[str, str] = {d["code"]: d["name"] for d in header_docs}
        for c in item_doc_codes:
            if c not in all_docs:
                all_docs[c] = ""

        if not all_docs:
            return 0

        today = date.today().isoformat()
        added = 0

        with _get_conn() as conn:
            for tariff_code in tariff_codes:
                for doc_code, doc_name in all_docs.items():
                    try:
                        conn.execute(
                            """
                            INSERT INTO tariff_doc_history (tariff_code, doc_code, doc_name, count, last_seen)
                            VALUES (?, ?, ?, 1, ?)
                            ON CONFLICT(tariff_code, doc_code) DO UPDATE SET
                                count = count + 1,
                                doc_name = CASE WHEN doc_name = '' THEN excluded.doc_name ELSE doc_name END,
                                last_seen = excluded.last_seen
                            """,
                            (tariff_code, doc_code, doc_name, today),
                        )
                        added += 1
                    except Exception as e:
                        logger.debug(f"Upsert greška {tariff_code}/{doc_code}: {e}")

        return added

    # ----------------------------------------------------------------- suggest

    def get_suggested_docs(
        self,
        tariff_code: str,
        min_count: int = 2,
        exclude_universal: bool = True,
    ) -> List[Dict[str, str]]:
        """Vrati prijedloge priloženih dokumenata za dati tarifni broj.

        Pretražuje:
        1. Tačan 8-cifreni kod
        2. 6-cifreni prefix (podbroj bez zadnje 2 cifre)
        3. 4-cifreni heading

        Vraća liste diktova: [{'code': 'N852', 'name': '...', 'count': 5}, ...]
        sortirane po count DESC.
        """
        if not tariff_code or len(tariff_code.strip()) < 4:
            return []

        code = tariff_code.strip()[:8]
        candidates = list({code, code[:6], code[:4]})

        query = """
            SELECT doc_code, doc_name, SUM(count) AS total
            FROM tariff_doc_history
            WHERE tariff_code IN ({placeholders})
              AND count >= ?
            GROUP BY doc_code
            ORDER BY total DESC
        """.format(placeholders=",".join("?" * len(candidates)))

        try:
            with _get_conn() as conn:
                rows = conn.execute(query, candidates + [min_count]).fetchall()
        except Exception as e:
            logger.error(f"get_suggested_docs greška: {e}")
            return []

        # Normalizuj stare kodove → nove i merguj countove
        merged: Dict[str, Dict] = {}
        for row in rows:
            raw_code = row["doc_code"]
            if exclude_universal and raw_code in _UNIVERSAL_CODES:
                continue
            normalized = _CODE_NORMALIZE.get(raw_code, raw_code)
            if exclude_universal and normalized in _UNIVERSAL_CODES:
                continue
            if normalized not in merged:
                merged[normalized] = {"code": normalized, "name": row["doc_name"] or "", "count": 0}
            merged[normalized]["count"] += row["total"]
            # Preferiši naziv na latinici (ne ćirilica)
            name = row["doc_name"] or ""
            if name and not any(c in name for c in "абвгдђежзијклљмнњопрстћуфхцчџш"):
                merged[normalized]["name"] = name

        return sorted(merged.values(), key=lambda x: x["count"], reverse=True)

    # ----------------------------------------------------------------- record

    def record_usage(self, tariff_code: str, doc_codes: List[str]) -> None:
        """Zabilježi korištenje dokumenata za tarifni broj (auto-učenje pri bildovanju XML-a)."""
        if not tariff_code or not doc_codes:
            return
        today = date.today().isoformat()
        code8 = tariff_code.strip()[:8]
        with _get_conn() as conn:
            for doc_code in doc_codes:
                if not doc_code:
                    continue
                conn.execute(
                    """
                    INSERT INTO tariff_doc_history (tariff_code, doc_code, count, last_seen)
                    VALUES (?, ?, 1, ?)
                    ON CONFLICT(tariff_code, doc_code) DO UPDATE SET
                        count = count + 1,
                        last_seen = excluded.last_seen
                    """,
                    (code8, doc_code, today),
                )


# ------------------------------------------------------------------ singleton

_service_instance: Optional[TariffDocHistoryService] = None


def get_tariff_doc_history_service() -> TariffDocHistoryService:
    global _service_instance
    if _service_instance is None:
        _service_instance = TariffDocHistoryService()
    return _service_instance
