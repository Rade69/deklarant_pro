"""
QuotaService — preuzimanje i čuvanje tarifnih kvota sa UINO sajta.

Tok: download PDF → hash check → parse → insert PostgreSQL

Dokumentacija: docs/archive/2026-04-26/quota_module_2026-04-26.md
"""

import hashlib
import logging
import re
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("deklarant_pro.quota")

UINO_PDF_URL = "https://www.uino.gov.ba/portal/wp-content/uploads/GenerisaniPDF/Qba-Stanje.pdf"


@dataclass
class QuotaItem:
    tariff_code: str
    description: str
    unit: str
    approved_qty: Optional[float]
    used_qty: Optional[float]
    remaining_qty: Optional[float]


@dataclass
class QuotaSnapshot:
    source_url: str
    report_datetime: Optional[datetime]
    downloaded_at: datetime
    pdf_hash: str
    items: list[QuotaItem] = field(default_factory=list)


# =========================================================
# PDF PARSER
# =========================================================

def _parse_qty(text: str) -> Optional[float]:
    """Konvertuje '30.000,00' ili '197,45' u float."""
    if not text:
        return None
    cleaned = text.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_report_datetime(words: list) -> Optional[datetime]:
    """Izvlači 'Datum kreiranja izvještaja: 26.4.2026 7:00:18' iz words liste."""
    texts = [w["text"] for w in words]
    for i, t in enumerate(texts):
        if "kreiranja" in t.lower() or "izvještaja:" in t.lower():
            # Uzmi sljedeće 2 tokene (datum i vrijeme)
            date_tok = texts[i + 1] if i + 1 < len(texts) else ""
            time_tok = texts[i + 2] if i + 2 < len(texts) else ""
            try:
                return datetime.strptime(f"{date_tok} {time_tok}", "%d.%m.%Y %H:%M:%S")
            except ValueError:
                try:
                    # format 26.4.2026
                    parts = date_tok.split(".")
                    if len(parts) == 3:
                        d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
                        t_parts = time_tok.split(":")
                        h = int(t_parts[0]) if t_parts else 0
                        mi = int(t_parts[1]) if len(t_parts) > 1 else 0
                        s = int(t_parts[2]) if len(t_parts) > 2 else 0
                        return datetime(y, m, d, h, mi, s)
                except Exception:
                    pass
    return None


def parse_uino_quota_pdf(pdf_path: str) -> QuotaSnapshot:
    """
    Parsira UINO PDF izvještaj o tarifnim kvotama.

    Koordinatni pragovi (x0):
      - tarifni kod: 4 grupe cifara na x0 ≈ 44, 64, 75, 86
      - opis: x0 < 545
      - JM: 545 < x0 < 600
      - Odobreno: 600 < x0 < 670
      - Iskorišteno: 670 < x0 < 745
      - Preostalo: x0 > 745
    """
    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        all_words = []
        for page in pdf.pages:
            all_words.extend(page.extract_words())

    report_dt = _parse_report_datetime(all_words)

    # Grupiši riječi po redu (round top na 1px — PDF ima sub-pixel razliku između
    # lijevih i desnih kolona iste vizuelne linije, npr. 163.013 vs 162.981)
    rows: dict[int, list] = defaultdict(list)
    for w in all_words:
        key = round(w["top"])
        rows[key].append(w)

    DIGIT_PATTERN = re.compile(r"^\d{2,4}$")
    FIRST_GROUP_PATTERN = re.compile(r"^\d{4}$")

    items: list[QuotaItem] = []

    for top in sorted(rows.keys()):
        ws = sorted(rows[top], key=lambda w: w["x0"])

        # Provjeri da li red počinje tarifnim kodom:
        # prvi token = 4 cifre, a zatim još 3 grupe cifara (2-4 cifre) na x0 < 110
        leading = [w for w in ws if w["x0"] < 110 and DIGIT_PATTERN.match(w["text"])]
        if len(leading) < 4:
            continue
        if not FIRST_GROUP_PATTERN.match(leading[0]["text"]):
            continue

        # Tarifni kod: "XXXX XX XX XX"
        code_parts = [w["text"] for w in leading[:4]]
        tariff_code = " ".join(code_parts)

        # JM, količine
        jm_words   = [w for w in ws if 545 < w["x0"] < 600]
        odo_words  = [w for w in ws if 600 < w["x0"] < 670]
        isko_words = [w for w in ws if 670 < w["x0"] < 745]
        pre_words  = [w for w in ws if w["x0"] > 745]

        unit = jm_words[0]["text"] if jm_words else ""
        approved  = _parse_qty(odo_words[0]["text"])  if odo_words  else None
        used      = _parse_qty(isko_words[0]["text"]) if isko_words else None
        remaining = _parse_qty(pre_words[0]["text"])  if pre_words  else None

        # Opis: sve riječi između koda i JM kolone (x0 između 100 i 545)
        desc_words = [w["text"] for w in ws if 100 <= w["x0"] < 545]
        # Ukloni soft-hyphen separator
        desc_words = [t for t in desc_words if t not in ("\xad", "-", "­")]
        description = " ".join(desc_words)

        items.append(QuotaItem(
            tariff_code=tariff_code,
            description=description,
            unit=unit,
            approved_qty=approved,
            used_qty=used,
            remaining_qty=remaining,
        ))

    pdf_hash = _hash_file(pdf_path)

    return QuotaSnapshot(
        source_url=UINO_PDF_URL,
        report_datetime=report_dt,
        downloaded_at=datetime.now(),
        pdf_hash=pdf_hash,
        items=items,
    )


def _hash_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# =========================================================
# DB OPERACIJE
# =========================================================

def ensure_tables():
    """Kreira tabele ako ne postoje (idempotentno)."""
    from database.db import get_db_connection
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS catalogs.quota_snapshots (
                    id SERIAL PRIMARY KEY,
                    source_url TEXT NOT NULL,
                    report_datetime TIMESTAMP,
                    downloaded_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    pdf_hash TEXT UNIQUE,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS catalogs.quota_snapshot_items (
                    id SERIAL PRIMARY KEY,
                    snapshot_id INTEGER NOT NULL
                        REFERENCES catalogs.quota_snapshots(id) ON DELETE CASCADE,
                    tariff_code TEXT NOT NULL,
                    description TEXT,
                    approved_qty NUMERIC,
                    used_qty NUMERIC,
                    remaining_qty NUMERIC,
                    unit TEXT,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_quota_items_tariff
                    ON catalogs.quota_snapshot_items (tariff_code)
            """)


def snapshot_exists(pdf_hash: str) -> Optional[int]:
    """Vraća snapshot_id ako PDF sa tim hashom već postoji, inače None."""
    from database.db import get_db_connection
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM catalogs.quota_snapshots WHERE pdf_hash = %s LIMIT 1",
                (pdf_hash,)
            )
            row = cur.fetchone()
            return row["id"] if row else None


def insert_snapshot(snapshot: QuotaSnapshot) -> int:
    """Upisuje snapshot i stavke, vraća snapshot_id."""
    from database.db import get_db_connection
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO catalogs.quota_snapshots
                    (source_url, report_datetime, downloaded_at, pdf_hash)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (snapshot.source_url, snapshot.report_datetime,
                 snapshot.downloaded_at, snapshot.pdf_hash)
            )
            snapshot_id = cur.fetchone()["id"]

            for item in snapshot.items:
                cur.execute(
                    """
                    INSERT INTO catalogs.quota_snapshot_items
                        (snapshot_id, tariff_code, description,
                         approved_qty, used_qty, remaining_qty, unit)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (snapshot_id, item.tariff_code, item.description,
                     item.approved_qty, item.used_qty, item.remaining_qty, item.unit)
                )
    return snapshot_id


def get_latest_snapshot_meta() -> Optional[dict]:
    """Vraća metapodatke posljednjeg snapshota."""
    from database.db import get_db_connection
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, source_url, report_datetime, downloaded_at
                FROM catalogs.quota_snapshots
                ORDER BY downloaded_at DESC
                LIMIT 1
            """)
            return cur.fetchone()


def get_snapshot_items(snapshot_id: int) -> list[dict]:
    """Vraća sve stavke za dati snapshot."""
    from database.db import get_db_connection
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT tariff_code, description, approved_qty,
                       used_qty, remaining_qty, unit
                FROM catalogs.quota_snapshot_items
                WHERE snapshot_id = %s
                ORDER BY tariff_code
            """, (snapshot_id,))
            return cur.fetchall()


# =========================================================
# GLAVNI ENTRY POINT
# =========================================================

def refresh_quota_data() -> tuple[int, str]:
    """
    Preuzima PDF, parsira i upisuje u bazu.

    Returns:
        (snapshot_id, status_msg)  gdje status_msg opisuje šta se desilo.
    Raises:
        Exception na mrežnu ili parse grešku.
    """
    import urllib.request

    ensure_tables()

    # Preuzmi PDF
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        req = urllib.request.Request(
            UINO_PDF_URL,
            headers={"User-Agent": "Mozilla/5.0 (Deklarant Pro; quota fetch)"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        Path(tmp_path).write_bytes(data)
        logger.info(f"PDF preuzet: {len(data)} bajtova")
    except Exception as e:
        Path(tmp_path).unlink(missing_ok=True)
        raise ConnectionError(f"Nije moguće preuzeti UINO PDF: {e}") from e

    try:
        snapshot = parse_uino_quota_pdf(tmp_path)
    except Exception as e:
        Path(tmp_path).unlink(missing_ok=True)
        raise ValueError(
            "PDF je preuzet, ali parser nije mogao pročitati podatke. "
            "Moguće je da je UINO promijenio format izvještaja."
        ) from e
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    existing_id = snapshot_exists(snapshot.pdf_hash)
    if existing_id:
        return existing_id, "duplicate"

    snapshot_id = insert_snapshot(snapshot)
    logger.info(f"Snapshot {snapshot_id} upisan, {len(snapshot.items)} stavki")
    return snapshot_id, "new"
