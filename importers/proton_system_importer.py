# importers/proton_system_importer.py
"""
Parser za Proton System DOO format (MGM fakture).

Format stavke (3 linije):
  BA ACTIFOLIC 60 TBL BH
  1 4000298 80 kom 16,30 8 15,00 0 1.199,68
  300401 3 31.05.2027 80

Kolone na data liniji: Rbr Sifra [desc_cont] Kolicina JM Cena Popust NetoCena PDV Iznos
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional, Tuple, Dict

import pdfplumber

from core.draft.draft import InvoiceLine, Party
from importers.import_result import ImportResult
from importers.invoice_line_utils import parse_eu_number
from utils.country_normalizer import normalize_country_name

logger = logging.getLogger("asycuda_pro.import.proton_system")

# Linija sa Rbr + 7-cifrenom šifrom: "1 4000298 ..." ili "13 4000874 RS/ME/BH SF 400 kom ..."
_DATA_LINE_RE = re.compile(r"^(\d{1,3})\s+(\d{6,8})\s+(.+)$")

# Batch/serijski red: počinje sa 6+ cifara (broj serije/LOT)
_BATCH_LINE_RE = re.compile(r"^\d{6,}")
_BRUTO_RE = re.compile(r"Bruto\s+masa:\s*([\d.,]+)\s*kg", re.IGNORECASE)
_NETO_RE = re.compile(r"Neto\s+masa:\s*([\d.,]+)\s*kg", re.IGNORECASE)
_INVOICE_NO_RE = re.compile(r"Faktura:\s*(\d+)", re.IGNORECASE)

# Zaglavlje tabele
_TABLE_HEADER_RE = re.compile(r"\bRbr\b.*\bIznos\b", re.IGNORECASE)

# Ukupno — označava kraj tabele
_STOP_RE = re.compile(r"^Ukupno\b", re.IGNORECASE)

# Zemlja porekla
_ZEMLJA_RE = re.compile(
    r"Zemlja[ \t]+porekla[ \t]+([A-Za-zÀ-žčćšđžČĆŠĐŽ]+)",
    re.IGNORECASE,
)
_ITEM_RANGE_RE = re.compile(r"stavk[ei]\s+broj[a]?\s+(\d+)\s*[-–]\s*(\d+)", re.IGNORECASE)
_ITEM_SINGLE_RE = re.compile(r"stavk[ei]?\s+broj[a]?\s+(\d+)(?!\s*[-–]\s*\d)", re.IGNORECASE)

_COUNTRY_MAP = {
    "srbija": "RS", "bosna": "BA", "hrvatska": "HR", "slovenija": "SI",
    "makedonija": "MK", "crna gora": "ME", "albanija": "AL",
    "nemacka": "DE", "njemačka": "DE", "nemačka": "DE",
    "francuska": "FR", "italija": "IT", "austrija": "AT",
    "turska": "TR", "kina": "CN",
}


def _resolve_country(name: str) -> str:
    key = name.lower().strip()
    if key in _COUNTRY_MAP:
        return _COUNTRY_MAP[key]
    iso = normalize_country_name(name)
    return iso if iso != name and len(iso) == 2 else ""


def _parse_zemlja_porekla(full_text: str) -> Tuple[str, Dict[int, str]]:
    matches = [(m.start(), _resolve_country(m.group(1))) for m in _ZEMLJA_RE.finditer(full_text)]
    matches = [(pos, iso) for pos, iso in matches if iso]
    if not matches:
        return "", {}

    default = matches[0][1]
    overrides: Dict[int, str] = {}

    for i in range(1, len(matches)):
        pos, country = matches[i]
        segment = full_text[matches[i - 1][0]:pos]
        for m in _ITEM_RANGE_RE.finditer(segment):
            for rbr in range(int(m.group(1)), int(m.group(2)) + 1):
                overrides[rbr] = country
        for m in _ITEM_SINGLE_RE.finditer(segment):
            overrides[int(m.group(1))] = country

    logger.info(f"   🌍 Zemlja porekla: default={default}" + (f", overrides={overrides}" if overrides else ""))
    return default, overrides


def _parse_tail(tail: str):
    """Parsira kraj data linije: [desc_cont] kolicina jm cena popust neto pdv iznos."""
    # Tražimo: broj jm broj broj broj broj broj na kraju
    m = re.search(
        r"([\d.,]+)\s+([A-Za-z]{2,4})\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s*$",
        tail
    )
    if not m:
        return None
    desc_cont = tail[:m.start()].strip()
    return {
        "desc_cont": desc_cont,
        "kolicina": parse_eu_number(m.group(1)),
        "jm": m.group(2).lower(),
        "cena": parse_eu_number(m.group(3)),
        "iznos": parse_eu_number(m.group(7)),
    }


def parse_proton_system_pdf(pdf_path: str) -> ImportResult:
    """Parsira Proton System DOO format (MGM fakture)."""

    with pdfplumber.open(pdf_path) as pdf:
        all_lines: List[str] = []
        for page in pdf.pages:
            txt = page.extract_text() or ""
            all_lines.extend(txt.splitlines())

    full_text = " ".join(all_lines)

    # Zemlja porijekla
    default_zemlja, zemlja_overrides = _parse_zemlja_porekla(full_text)

    # Težine
    bruto_kg = 0.0
    neto_kg = 0.0
    m_bruto = _BRUTO_RE.search(full_text)
    m_neto = _NETO_RE.search(full_text)
    if m_bruto:
        bruto_kg = parse_eu_number(m_bruto.group(1))
    if m_neto:
        neto_kg = parse_eu_number(m_neto.group(1))

    # Broj fakture — samo broj, bez prefiksa "Faktura:"
    invoice_name = ""
    m_inv = _INVOICE_NO_RE.search(full_text)
    if m_inv:
        invoice_name = m_inv.group(1)

    # Parsiranje stavki
    in_table = False
    pending_desc: Optional[str] = None
    items: List[InvoiceLine] = []
    mgm_party = Party(name="MGM / PROTON SYSTEM")

    for line in all_lines:
        line = line.strip()

        if not in_table:
            if _TABLE_HEADER_RE.search(line):
                in_table = True
            continue

        if _STOP_RE.match(line):
            break

        if _BATCH_LINE_RE.match(line):
            continue

        m = _DATA_LINE_RE.match(line)
        if m:
            rbr = int(m.group(1))
            sifra = m.group(2)
            tail_str = m.group(3)

            # Ako prethodna linija ima nastavak opisa (split)
            full_desc = (pending_desc or "") + (" " + tail_str.split()[0] if pending_desc else "")

            parsed = _parse_tail(tail_str)
            if not parsed:
                pending_desc = (pending_desc or "") + " " + line
                continue

            desc = ((pending_desc or "") + " " + parsed["desc_cont"]).strip()
            pending_desc = None

            zemlja = zemlja_overrides.get(rbr, default_zemlja)

            items.append(InvoiceLine(
                line_no=rbr,
                product_code=sifra,
                naziv_robe=desc,
                tarifni_broj="",
                zemlja_porijekla=zemlja,
                povlastica="",
                jm=parsed["jm"],
                kolicina=parsed["kolicina"],
                cijena_jed=parsed["cena"],
                iznos=parsed["iznos"],
                valuta="EUR",
                bruto_kg=0.0,
                neto_kg=0.0,
                exporter=mgm_party,
            ))
        else:
            # Opis artikla — može se prostirati na više redova
            if pending_desc:
                pending_desc = pending_desc + " " + line
            else:
                pending_desc = line

    logger.info(f"✅ Proton System: {len(items)} stavki, zemlja={default_zemlja}")

    return ImportResult(
        items=items,
        bruto_kg=bruto_kg,
        neto_kg=neto_kg,
        invoice_name=invoice_name,
        has_origin_statement=bool(default_zemlja),
    )
