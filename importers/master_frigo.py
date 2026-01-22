# services/invoice_importers/master_frigo.py
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import openpyxl
import pdfplumber


@dataclass
class ImportedLine:
    rbr: int
    code: str
    description: str
    unit: str
    qty: float
    price: float
    amount: float
    tariff: str = ""
    origin: str = ""
    preferential: str = ""  # rub.36: povlastica / preferencijal
    serials: List[str] | None = None


_TABLE_HEADER_RE = re.compile(
    r"\bRbr\b.*\bSifra\b.*\bNaziv\b.*\bIznos\b", re.IGNORECASE
)
_INVOICE_NO_RE = re.compile(r"\bbroj:\s*([0-9]+)\b", re.IGNORECASE)
_DATE_RE = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{4})\b")
_TOTAL_VALUE_RE = re.compile(
    r"\bVrednost\s*\((?P<cur>[A-Z]{3})\)\s*:\s*(?P<val>[\d\.,]+)", re.IGNORECASE
)
_GROSS_RE = re.compile(r"\bBruto težina:\s*(?P<val>[\d\.,]+)\s*KG\b", re.IGNORECASE)
_NET_RE = re.compile(r"\bNeto težina:\s*(?P<val>[\d\.,]+)\s*KG\b", re.IGNORECASE)
_INCOTERM_RE = re.compile(r"\bParitet isporuke:\s*(?P<term>[A-Z]{3})\b", re.IGNORECASE)

# unit + qty + price + amount
_TAIL_NUMS_RE = re.compile(
    r"\s(?P<unit>[A-Za-z]{1,5}(?:\s+[A-Za-z]{1,5})?)\s+"
    r"(?P<qty>[\d\.,]+)\s+(?P<price>[\d\.,]+)\s+(?P<amount>[\d\.,]+)\b"
)


def _parse_number_any(s: str) -> float:
    s = (s or "").strip().replace(" ", "")
    if not s:
        return 0.0

    if "," in s and "." in s:
        if s.rfind(".") > s.rfind(","):
            s = s.replace(",", "")
        else:
            s = s.replace(".", "").replace(",", ".")
    else:
        if "," in s and "." not in s:
            s = s.replace(",", ".")
        else:
            s = s.replace(",", "")

    try:
        return float(s)
    except ValueError:
        return 0.0


def _parse_decimal_any(s: str) -> Decimal:
    s = (s or "").strip().replace(" ", "")
    if not s:
        return Decimal("0")

    if "," in s and "." in s:
        if s.rfind(".") > s.rfind(","):
            s = s.replace(",", "")
        else:
            s = s.replace(".", "").replace(",", ".")
    else:
        if "," in s and "." not in s:
            s = s.replace(",", ".")
        else:
            s = s.replace(",", "")

    try:
        return Decimal(s)
    except InvalidOperation:
        return Decimal("0")


def _extract_text_lines(pdf_path: str) -> List[str]:
    with pdfplumber.open(pdf_path) as pdf:
        lines: List[str] = []
        for page in pdf.pages:
            txt = page.extract_text() or ""
            lines.extend([ln.rstrip() for ln in txt.splitlines()])
    return lines


def _normalize_header_name(name: str) -> str:
    name = (name or "").strip().lower()
    # minimalna normalizacija (bez eksternih libova)
    name = (
        name.replace("š", "s")
        .replace("đ", "dj")
        .replace("č", "c")
        .replace("ć", "c")
        .replace("ž", "z")
    )
    name = re.sub(r"\s+", " ", name)
    return name


def _normalize_preferential(raw: str) -> str:
    """
    Povlastica/Preferencijal:
      - DA/YES/1/TRUE -> "P" (da se grupisanje stabilizuje)
      - NE/NO/0/FALSE/"" -> ""
      - bilo koji drugi kod (npr. "300") -> vrati original (ne gubimo informaciju)
    """
    s = (raw or "").strip()
    if not s:
        return ""
    u = s.upper()
    if u in {"DA", "YES", "Y", "1", "TRUE", "T"}:
        return "P"
    if u in {"NE", "NO", "N", "0", "FALSE", "F"}:
        return ""
    return s  # npr. šifra povlastice ako postoji


def _read_mapping_xlsx(xlsx_path: str) -> Dict[str, Dict[str, str]]:
    """
    Očekivano (varijacije imena kolona su ok):
      Šifra / Sifra
      Tarifni br / Tarifni broj
      Zemlja porekla / Zemlja porijekla
      Preferencijal / Povlastica

    Vraća: code -> {"tariff": "...", "origin": "...", "preferential": "..."}
    """
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    ws = wb[wb.sheetnames[0]]

    header_row = [str(ws.cell(1, c).value or "").strip() for c in range(1, 40)]
    idx_norm = {
        _normalize_header_name(name): i + 1 for i, name in enumerate(header_row) if name
    }

    def find_col(*candidates: str) -> Optional[int]:
        for cand in candidates:
            c = idx_norm.get(_normalize_header_name(cand))
            if c:
                return c
        return None

    code_col = find_col("Šifra", "Sifra") or 2
    tariff_col = find_col("Tarifni br", "Tarifni broj") or 6
    origin_col = find_col("Zemlja porekla", "Zemlja porijekla", "Zemlja por") or 7
    pref_col = find_col("Preferencijal", "Povlastica", "Povlašćica") or 8

    out: Dict[str, Dict[str, str]] = {}
    for r in range(2, ws.max_row + 1):
        code = ws.cell(r, code_col).value
        if not code:
            continue

        code_s = str(code).strip()
        out[code_s] = {
            "tariff": str(ws.cell(r, tariff_col).value or "").strip(),
            "origin": str(ws.cell(r, origin_col).value or "").strip(),
            "preferential": _normalize_preferential(
                str(ws.cell(r, pref_col).value or "")
            ),
        }

    return out


def _try_read_incoterm_from_xlsx(xlsx_path: str) -> str:
    """
    Ako negdje u fajlu postoji tekst "Paritet isporuke: FCA", izvuci FCA.
    (čisto kao fallback ako PDF nema)
    """
    try:
        wb = openpyxl.load_workbook(xlsx_path, data_only=True)
        ws = wb[wb.sheetnames[0]]
        for r in range(1, min(ws.max_row, 60) + 1):
            for c in range(1, min(ws.max_column, 12) + 1):
                v = ws.cell(r, c).value
                if not isinstance(v, str):
                    continue
                m = _INCOTERM_RE.search(v)
                if m:
                    return (m.group("term") or "").upper()
    except Exception:
        logging.exception("Failed to read incoterm from xlsx: %s", xlsx_path)
    return ""


def _find_code_and_desc(
    prefix_after_rbr: str, known_codes_sorted: List[str]
) -> Tuple[str, str]:
    """
    Šifra može sadržati razmake.
    Najsigurnije: NAJDUŽA šifra iz mapping-a koja je prefix linije.
    """
    s = prefix_after_rbr.strip()
    for code in known_codes_sorted:
        if s.startswith(code + " "):
            return code, s[len(code) :].strip()
        if s == code:
            return code, ""

    parts = s.split(None, 1)
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def parse_master_frigo_pdf(
    pdf_path: str, mapping: Optional[Dict[str, Dict[str, str]]] = None
) -> Tuple[Dict[str, Any], List[ImportedLine]]:
    lines = _extract_text_lines(pdf_path)

    header: Dict[str, Any] = {"source_file": Path(pdf_path).name}

    for ln in lines[:80]:
        m = _INVOICE_NO_RE.search(ln)
        if m:
            header["invoice_no"] = m.group(1)
            break

    for ln in lines[:160]:
        if "Mesto i datum izdavanja" in ln:
            m = _DATE_RE.search(ln)
            if m:
                header["date"] = m.group(1)
                break
    if "date" not in header:
        for ln in lines[:160]:
            m = _DATE_RE.search(ln)
            if m:
                header["date"] = m.group(1)
                break

    for ln in lines:
        m = _TOTAL_VALUE_RE.search(ln)
        if m:
            header["currency"] = m.group("cur").upper()
            header["total_value"] = _parse_number_any(m.group("val"))
            break

    for ln in lines:
        m = _GROSS_RE.search(ln)
        if m:
            header["gross_kg"] = _parse_number_any(m.group("val"))
            break

    for ln in lines:
        m = _NET_RE.search(ln)
        if m:
            header["net_kg"] = _parse_number_any(m.group("val"))
            break

    for ln in lines:
        m = _INCOTERM_RE.search(ln)
        if m:
            header["incoterm"] = (m.group("term") or "").upper()
            break

    # Items
    start_idx: Optional[int] = None
    for i, ln in enumerate(lines):
        if _TABLE_HEADER_RE.search(ln):
            start_idx = i + 1
            break
    if start_idx is None:
        return header, []

    mapping = mapping or {}
    known_codes_sorted = sorted(mapping.keys(), key=len, reverse=True)

    items: List[ImportedLine] = []
    current: Optional[ImportedLine] = None
    collecting_serials = False

    for ln in lines[start_idx:]:
        s = (ln or "").strip()
        if not s:
            continue

        if (
            s.upper().startswith("VREDNOST")
            or s.upper().startswith("UKUPNO")
            or "INSTRUCTION FOR" in s.upper()
        ):
            break

        if s.lower().startswith("serijski broj") or s.lower().startswith(
            "serijski brojevi"
        ):
            collecting_serials = True
            continue

        if collecting_serials and re.fullmatch(r"[0-9A-Z\-]{6,}", s.replace(" ", "")):
            if current:
                if current.serials is None:
                    current.serials = []
                current.serials.append(s.replace(" ", ""))
            continue

        if collecting_serials and re.match(r"^\d+\s", s):
            collecting_serials = False

        if re.match(r"^\d+\s", s):
            matches = list(_TAIL_NUMS_RE.finditer(s))
            if not matches:
                if current:
                    current.description = (current.description + " " + s).strip()
                continue

            m = matches[-1]
            unit = (m.group("unit") or "").replace(" ", "").lower()
            qty = _parse_number_any(m.group("qty"))
            price = _parse_number_any(m.group("price"))
            amount = _parse_number_any(m.group("amount"))
            tail = (s[m.end() :] or "").strip()

            prefix = (s[: m.start()] or "").strip()
            rbr_m = re.match(r"^(?P<rbr>\d+)\s+(?P<rest>.*)$", prefix)
            if not rbr_m:
                continue

            rbr = int(rbr_m.group("rbr"))
            rest = rbr_m.group("rest").strip()

            code, desc = _find_code_and_desc(rest, known_codes_sorted)
            if tail:
                desc = (desc + " " + tail).strip()

            map_row = mapping.get(code, {})
            current = ImportedLine(
                rbr=rbr,
                code=code,
                description=desc.strip(),
                unit=unit,
                qty=qty,
                price=price,
                amount=amount,
                tariff=map_row.get("tariff", "") or "",
                origin=map_row.get("origin", "") or "",
                preferential=_normalize_preferential(
                    map_row.get("preferential", "") or ""
                ),
                serials=[],
            )
            items.append(current)
        else:
            if current and not s.startswith(("56:", "57:", "59:")):
                current.description = (current.description + " " + s).strip()

    return header, items


def build_faktura_tab_data(
    header: Dict[str, Any], lines: List[ImportedLine]
) -> Dict[str, Any]:
    total = sum(_parse_decimal_any(str(x.amount)) for x in lines)
    incoterm = header.get("incoterm", "") or ""
    currency = header.get("currency", "EUR") or "EUR"

    # VAŽNO: Paritet ako postoji -> upiši, ako ne -> prazno (ručno)
    return {
        "Broj fakture": header.get("invoice_no", "") or "",
        "Datum fakture": header.get("date", "") or "",
        "Valuta fakture": currency,
        "Ukupan iznos": f"{total:.2f}",
        "Paritet isporuke": incoterm,  # <-- traženo
        "Uslovi isporuke": incoterm,  # <-- ostavljeno radi kompatibilnosti ako tab ima ovo ime
        "Ukupna bruto težina (kg)": f"{float(header.get('gross_kg', 0.0) or 0.0):.3f}",
        "Ukupna neto težina (kg)": f"{float(header.get('net_kg', 0.0) or 0.0):.3f}",
        "Broj stavki": str(len(lines)),
        "Napomene": f"Izvor: {header.get('source_file','')}",
    }


def _join_full_descriptions(desc_list: List[str]) -> str:
    seen = set()
    out: List[str] = []
    for d in desc_list:
        d = (d or "").strip()
        if not d or d in seen:
            continue
        seen.add(d)
        out.append(d)
    return "\n".join(out)


def build_naimenovanja_rows(
    lines: List[ImportedLine],
    total_gross_kg: float = 0.0,
    total_net_kg: float = 0.0,
) -> List[List[Any]]:
    """
    Grupisanje mora biti po ključu:
      (Tarifni broj, Zemlja porijekla, Povlastica)

    Red:
      [rb, tarifni, opis31 FULL, kolicina, vrijednost, bruto, neto, porijeklo, povlastica]
    """
    from collections import defaultdict

    def key_of(x: ImportedLine) -> Tuple[str, str, str]:
        return (
            x.tariff or "",
            x.origin or "",
            _normalize_preferential(x.preferential or ""),
        )

    groups = defaultdict(lambda: {"qty": 0.0, "value": 0.0, "desc": []})
    for it in lines:
        k = key_of(it)
        groups[k]["qty"] += float(it.qty or 0.0)
        groups[k]["value"] += float(it.amount or 0.0)
        groups[k]["desc"].append(f"{it.code} - {it.description}".strip(" -"))

    total_value = sum(g["value"] for g in groups.values()) or 0.0

    rows: List[List[Any]] = []
    for idx, ((tariff, origin, pref), g) in enumerate(
        sorted(groups.items(), key=lambda x: (x[0][0], x[0][1], x[0][2])), start=1
    ):
        value = g["value"]
        ratio = (value / total_value) if total_value > 0 else 0.0

        # Ako nema podjeljenih težina po stavkama -> raspodjela po vrijednosti
        gross = (total_gross_kg * ratio) if total_gross_kg else 0.0
        net = (total_net_kg * ratio) if total_net_kg else 0.0

        rows.append(
            [
                idx,
                tariff,
                _join_full_descriptions(g["desc"]),  # FULL rub.31 (bez truncation)
                round(g["qty"], 3),
                round(value, 2),
                round(gross, 3),
                round(net, 3),
                origin,
                pref,  # rub.36 Povlastica (ključ grupisanja)
            ]
        )
    return rows


def import_master_frigo(
    pdf_paths: List[str],
    mapping_xlsx_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Ulaz:
      - 1+ PDF računa
      - mapping excel (podela po poreklu) sa tarifom/porijeklom/povlasticom

    Izlaz:
      {
        "faktura": {...},
        "naimenovanja": {"items":[...], "editor": {}},
        "raw_lines": [...],
        "warnings": [...]
      }
    """
    mapping = _read_mapping_xlsx(mapping_xlsx_path) if mapping_xlsx_path else {}

    all_headers: List[Dict[str, Any]] = []
    all_lines: List[ImportedLine] = []
    warnings: List[str] = []

    gross_total = 0.0
    net_total = 0.0
    incoterm_final = ""

    # Fallback incoterm iz XLSX (ako PDF nema)
    if mapping_xlsx_path:
        inc_x = _try_read_incoterm_from_xlsx(mapping_xlsx_path)
        if inc_x:
            incoterm_final = inc_x

    for p in pdf_paths:
        header, lines = parse_master_frigo_pdf(p, mapping=mapping)
        all_headers.append(header)
        all_lines.extend(lines)

        gross_total += float(header.get("gross_kg", 0.0) or 0.0)
        net_total += float(header.get("net_kg", 0.0) or 0.0)

        if not incoterm_final:
            inc = (header.get("incoterm") or "").strip()
            if inc:
                incoterm_final = inc

    missing_map = sorted(
        {it.code for it in all_lines if mapping and (not it.tariff or not it.origin)}
    )
    if mapping and missing_map:
        warnings.append(
            "Nema mappinga (tarifa/porijeklo) za šifre: "
            + ", ".join(missing_map[:25])
            + (" ..." if len(missing_map) > 25 else "")
        )

    faktura_header = {
        "invoice_no": ", ".join(
            [h.get("invoice_no", "") for h in all_headers if h.get("invoice_no")]
        ),
        "date": all_headers[0].get("date", "") if all_headers else "",
        "currency": all_headers[0].get("currency", "EUR") if all_headers else "EUR",
        "gross_kg": gross_total,
        "net_kg": net_total,
        "incoterm": incoterm_final,  # <-- ovdje sad garantujemo: ili nađen ili ""
        "source_file": "; ".join(
            [h.get("source_file", "") for h in all_headers if h.get("source_file")]
        ),
    }

    faktura = build_faktura_tab_data(faktura_header, all_lines)

    naimenovanja_items = build_naimenovanja_rows(
        all_lines,
        total_gross_kg=gross_total,
        total_net_kg=net_total,
    )

    raw_lines = [it.__dict__ for it in all_lines]

    return {
        "faktura": faktura,
        "naimenovanja": {"items": naimenovanja_items, "editor": {}},
        "raw_lines": raw_lines,
        "warnings": warnings,
        "meta": {
            "gross_total": gross_total,
            "net_total": net_total,
            "pdf_count": len(pdf_paths),
            "incoterm": incoterm_final,
        },
    }
