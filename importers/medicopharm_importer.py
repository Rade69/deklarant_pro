# importers/medicopharm_importer.py
"""
ASYCUDA Pro - Medico Pharm Servis Parser

Parser za fakture dobavljača MEDICO PHARM SERVIS DOO (Beograd/Leštane).

Format fakture (digitalni PDF):
  Header kolone: Rb.No. | Šifra | Tar.oznaka | Naziv artikla | JM | Količina | Cena | Iznos | Rab% | Rabat | Izn.Rabat
  Valuta: EUR
  Bruto težina: footer "BRUTO TEZINA:300 kg"
  Neto težina: iz sumarnog tabela (Total red, zadnja kolona = Težina)
  Sumarni tabela (str. 3-4): Tarifna oznaka | Zemlja | Količina | Iznos | Težina
    → koristimo za automatsko punjenje zemlja porijekla po tarifnom broju

Struktura repa stavke (7 tokena od desna):
  JM[-7]  KOL[-6]  CENA[-5]  IZNOS[-4]  RAB%[-3]  RABAT[-2]  IZN_RABAT[-1]

  Napomene:
  - JM može imati završnu tačku: SC. → sc, FL. → fl (strip se primjenjuje pri lookup-u)
  - Broj format: US (tačka=decimal, zarez=hiljadar): 1,000.00 / 4.295
  - Iznos koji koristimo: Izn.Rabat (tail[-1]) = stvarni iznos poslije rabata
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pdfplumber

from core.draft.draft import InvoiceLine
from importers.import_result import ImportResult
from importers.invoice_line_utils import KNOWN_JM, parse_eu_number
from utils.country_normalizer import normalize_country_name

logger = logging.getLogger("asycuda_pro.import.medicopharm")

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_INVOICE_NO_RE = re.compile(r"Faktura\s*[-–]\s*(\d+/\d+)", re.IGNORECASE)
_DATE_RE = re.compile(r"Datum\s+fakture[^:]*:\s*(\d{1,2}\.\d{1,2}\.\d{4})", re.IGNORECASE)
_BRUTO_RE = re.compile(r"BRUTO\s+TE[ZŽ]INA\s*:?\s*([\d\.,]+)\s*kg", re.IGNORECASE)

# Header tabla stavki: prepoznaje "Rb." i "JM" na istoj liniji
_ITEM_HEADER_RE = re.compile(r"\bRb\.\s*No\b|\bRb\b.*\bJM\b", re.IGNORECASE)

# Header sumarnog tabela po tarifama/zemljama
_SUMMARY_HEADER_RE = re.compile(r"Tarifna\s+oznaka|Tariff\s+heading", re.IGNORECASE)

# Total red u sumarnom tabelu
_TOTAL_LINE_RE = re.compile(r"^Total\b", re.IGNORECASE)

# Linije koje su sigurno "šum" (footer, zaglavlje stranice, ponavljanje headera)
_NOISE_PATTERNS = [
    re.compile(r"^\s*Strana\s+\d+", re.IGNORECASE),
    re.compile(r"^\s*Page\s+\d+", re.IGNORECASE),
    re.compile(r"MEDICO\s+PHARM\s+SERVIS", re.IGNORECASE),
    re.compile(r"KRUŽNI\s+PUT|KRU[ZŽ]NI\s+PUT", re.IGNORECASE),
    re.compile(r"^\s*TEL\s*:", re.IGNORECASE),
    re.compile(r"^\s*www\.", re.IGNORECASE),
    re.compile(r"^\s*IB\s*:", re.IGNORECASE),
    re.compile(r"Datum\s+fakture|Invoice\s+date", re.IGNORECASE),
    re.compile(r"Datum\s+isporuke|Delivery\s+date", re.IGNORECASE),
    re.compile(r"Komitent\s*/\s*Client", re.IGNORECASE),
    re.compile(r"SKLADI[ŠS]TE\s*:", re.IGNORECASE),
    re.compile(r"KRALJA\s+DRAGUTINA", re.IGNORECASE),
    re.compile(r"Rok\s+pla[ćc]anja|Date\s+to\s+pay", re.IGNORECASE),
    re.compile(r"Mesto\s+izdav\.", re.IGNORECASE),
    re.compile(r"Faktura\s*[-–]\s*\d+", re.IGNORECASE),     # Ponavljanje "Faktura - 213/26"
    re.compile(r"\bNaziv\s+artikla\b|\bItem\s+name\b", re.IGNORECASE),  # Ponavljanje header-a tabele
    re.compile(r"\bRab%\b|\bRebate\b|\bIzn\.Rabat\b", re.IGNORECASE),  # Kolone u headeru
    re.compile(r"^590\s*-\s*", re.IGNORECASE),              # Komitent info
    re.compile(r"CAR\.BR\.D-", re.IGNORECASE),               # CAR.BR.D-4099
    re.compile(r"^\s*JIB\s*:", re.IGNORECASE),
    re.compile(r"^\s*PDV\s*:", re.IGNORECASE),
    re.compile(r"^\d{5}-\d{2}-\d{2}", re.IGNORECASE),        # Telefon format
    re.compile(r"SLOVIMA\s*:", re.IGNORECASE),               # Iznos slovima
    re.compile(r"ZA UPLATU/For payment", re.IGNORECASE),
    re.compile(r"Ukupno\s*/\s*Total|Ukupno\s+rabata", re.IGNORECASE),
    re.compile(r"Ukupan\s+iznos/For\s+payment", re.IGNORECASE),
]

# Stop pri parsiranju stavki — počela je sumarni dio ili kraj
_STOP_PREFIXES = [
    "ukupno",
    "tarifna oznaka",
    "tariff heading",
    "za uplatu",
    "for payment",
    "slovima",
    "total",
    "fakturisao",
    "paritet",
    "bruto tezina",
    "bruto težina",
    "napomena",
    "ova izjava",
    "izvoznik",
    "mesto",
]


# ---------------------------------------------------------------------------
# Javna funkcija
# ---------------------------------------------------------------------------

def parse_medicopharm_pdf(pdf_path: str) -> ImportResult:
    """
    Parsira Medico Pharm Servis PDF fakturu (digitalni format).

    Vraća ImportResult sa stavkama, bruto/neto težinom i nazivom fakture.
    """
    logger.info(f"🏥 Medico Pharm parser: {Path(pdf_path).name}")

    lines = _extract_lines(pdf_path)
    
    # Ekstraktuj full tekst za detekciju izjave
    full_text = "\n".join(lines)

    # --- Zaglavlje ---
    invoice_name = ""
    bruto_kg = 0.0
    
    # --- DETEKTUJ izjavu o poreklu ---
    origin_statements = _detect_all_origin_statements(full_text)
    has_origin_statement = len(origin_statements) > 0
    logger.info(f"  ✅ Detekcija izjave o poreklu: {has_origin_statement} ({len(origin_statements)} izjava)")

    for ln in lines:
        if not invoice_name:
            m = _INVOICE_NO_RE.search(ln)
            if m:
                # "213/26" → "213_26" (za sigurne putanje)
                invoice_name = m.group(1).replace("/", "_")

        if not bruto_kg:
            m = _BRUTO_RE.search(ln)
            if m:
                bruto_kg = parse_eu_number(m.group(1))

    # --- Pronađi granice tabela ---
    item_start = None
    summary_start = None

    for i, ln in enumerate(lines):
        if item_start is None and _ITEM_HEADER_RE.search(ln):
            item_start = i + 1
        if item_start is not None and _SUMMARY_HEADER_RE.search(ln):
            summary_start = i + 1
            break

    if item_start is None:
        logger.warning("❌ Nije pronađen header tabele stavki — možda skenirani PDF?")
        return ImportResult(
            items=[], bruto_kg=0.0, neto_kg=0.0,
            invoice_name=invoice_name, currency="EUR"
        )

    # --- Stavke ---
    end_idx = summary_start if summary_start else len(lines)
    raw_items = _parse_items(lines[item_start:end_idx])
    logger.info(f"   📋 Parsed {len(raw_items)} stavki")

    # --- Sumarni tabela ---
    neto_kg = 0.0
    if summary_start:
        neto_kg, tariff_country_map = _parse_summary(lines[summary_start:])
        _apply_countries(raw_items, tariff_country_map)
        logger.info(f"   🌍 Zemlja porekla dodijeljena za {sum(1 for i in raw_items if i['zemlja'])} stavki")

    logger.info(f"✅ Medico Pharm: {len(raw_items)} stavki | bruto={bruto_kg}kg | neto={neto_kg}kg")

    return ImportResult(
        items=_to_invoice_lines(raw_items),
        bruto_kg=bruto_kg,
        neto_kg=neto_kg,
        invoice_name=invoice_name,
        currency="EUR",
        has_origin_statement=has_origin_statement,
        origin_statements=origin_statements,
    )


# ---------------------------------------------------------------------------
# Interni parseri
# ---------------------------------------------------------------------------

def _extract_lines(pdf_path: str) -> List[str]:
    """Ekstrahuje sve tekstualne linije iz PDF-a."""
    with pdfplumber.open(pdf_path) as pdf:
        result = []
        for page in pdf.pages:
            txt = page.extract_text() or ""
            result.extend(ln.rstrip() for ln in txt.splitlines())
    return result


def _is_noise(s: str) -> bool:
    """Provjeri da li je linija šum (header stranice, footer, ponavljanje zaglavlja)."""
    for pat in _NOISE_PATTERNS:
        if pat.search(s):
            return True
    return False


def _should_stop(s_lower: str) -> bool:
    """Provjeri da li treba prekinuti parsiranje stavki."""
    return any(s_lower.startswith(w) for w in _STOP_PREFIXES)


def _parse_items(lines: List[str]) -> List[Dict]:
    """
    Parsira listu linija tabele stavki.

    Svaki red koji počinje RBR-om i ima JM na poziciji -7 je nova stavka.
    Ostali redovi su nastavak naziva prethodne stavke.
    """
    items: List[Dict] = []
    current: Optional[Dict] = None

    for ln in lines:
        s = ln.strip()
        if not s:
            continue

        # Preskoči ponavljanje table headera na novim stranicama
        if _ITEM_HEADER_RE.search(s):
            continue

        # Preskoči šum (zaglavlja stranica, footer-i...)
        if _is_noise(s):
            continue

        # Stop kad stignemo do sumarnog dijela ili kraja fakture
        if _should_stop(s.lower()):
            break

        # Pokušaj parsirati kao novu stavku
        parsed = _try_parse_item_line(s)
        if parsed:
            if current:
                items.append(current)
            current = parsed
        elif current:
            # Nastavak naziva prethodne stavke (multi-line opis)
            current["name"] = (current["name"] + " " + s).strip()

    if current:
        items.append(current)

    return items


def _try_parse_item_line(line: str) -> Optional[Dict]:
    """
    Pokušava parsirati liniju kao stavku fakture.

    Očekivani format:
      RBR  SIFRA  TARIFF  ...NAZIV...  JM  KOL  CENA  IZNOS  RAB%  RABAT  IZN_RABAT
    Tail = 7 tokena od desna: JM + 6 numeričkih vrijednosti.

    Returns:
        Dict sa podacima stavke ili None ako linija nije stavka.
    """
    parts = line.split()
    if not parts:
        return None

    # RBR mora biti mali pozitivni cijeli broj (1-9999)
    try:
        rbr = int(parts[0])
        if rbr <= 0 or rbr > 9999:
            return None
    except ValueError:
        return None

    # Minimum: rbr + code + tariff + 1-znak-naziv + jm + 6-numerika = 10
    if len(parts) < 10:
        return None

    # Traži JM od desna na poziciji -7 (ili -8 kao fallback za dugačak naziv)
    for offset in (7, 8):
        if len(parts) <= offset:
            continue

        jm_raw = parts[-offset]
        jm = jm_raw.rstrip(".")  # Skini završnu tačku: SC. → sc, FL. → fl

        if jm.lower() not in KNOWN_JM:
            continue

        tail = parts[-offset + 1:]
        if len(tail) != 6:
            continue

        # Provjeri da su svih 6 tail tokena numerički (digits, tačke, zarezi)
        if not all(_is_numeric_token(t) for t in tail):
            continue

        # Prefix: rbr code tariff *name_tokens
        prefix = parts[:-offset]
        if len(prefix) < 3:
            continue

        code = prefix[1]
        tariff = prefix[2]
        name = " ".join(prefix[3:])

        # Iznos = Izn.Rabat (tail[5]) = konačni iznos poslije rabata
        iznos = parse_eu_number(tail[5])
        if iznos == 0.0:
            iznos = parse_eu_number(tail[2])  # Fallback na Iznos

        return {
            "rbr": rbr,
            "code": code,
            "tariff": tariff,
            "name": name,
            "jm": jm.lower(),
            "kolicina": parse_eu_number(tail[0]),
            "cijena": parse_eu_number(tail[1]),
            "iznos": iznos,
            "zemlja": "",
        }

    return None


def _is_numeric_token(s: str) -> bool:
    """Provjeri da li je token numeričke vrijednosti (može imati tačku/zarez)."""
    clean = s.replace(",", "").replace(".", "")
    if not clean:
        return False
    if clean.startswith("-"):
        clean = clean[1:]
    return clean.isdigit()


def _parse_summary(lines: List[str]) -> Tuple[float, Dict[str, List[str]]]:
    """
    Parsira sumarnu tabelu po tarifnim oznakama i zemljama (stranice 3-4).

    Format redova:
      TARIFF  ZEMLJA_TOKEN(S)  KOLICINA  IZNOS  TEZINA

    Returns:
        (neto_kg, {tariff: [iso_country, ...]})
        neto_kg = ukupna neto težina iz Total reda sumarnog tabela
    """
    tariff_country_map: Dict[str, List[str]] = {}
    neto_kg = 0.0

    # Skip dvojni header (Tarifna oznaka / Tariff heading)
    skip_headers = 2

    for ln in lines:
        s = ln.strip()
        if not s:
            continue

        # Preskoči header linije sumarnog tabela
        if _SUMMARY_HEADER_RE.search(s):
            skip_headers -= 1
            continue

        if skip_headers > 0:
            skip_headers -= 1
            continue

        s_lower = s.lower()

        # Total red: ukupna neto težina (zadnji token)
        if _TOTAL_LINE_RE.match(s):
            parts = s.split()
            if len(parts) >= 4:
                try:
                    neto_kg = parse_eu_number(parts[-1])
                except Exception:
                    pass
            continue

        # Stop pri kraju sumarnog dijela
        if any(s_lower.startswith(w) for w in ("fakturisao", "paritet", "za uplatu", "slovima", "napomena")):
            break

        parts = s.split()
        # Red sumarnog tabela: tarifa (samo cifre) + zemlja + kolicina + iznos + tezina
        if len(parts) < 5:
            continue
        if not re.match(r"^\d+$", parts[0]):
            continue

        tariff = parts[0]
        # Zadnja 3 tokena su numerički (kolicina, iznos, tezina)
        # Između tarife i ta 3 tokena je naziv zemlje (može biti više tokena)
        if not all(_is_numeric_token(t) for t in parts[-3:]):
            continue

        country_tokens = parts[1:-3]
        if not country_tokens:
            continue

        country_raw = " ".join(country_tokens)
        country_iso = normalize_country_name(country_raw)

        if tariff not in tariff_country_map:
            tariff_country_map[tariff] = []
        if country_iso and country_iso not in tariff_country_map[tariff]:
            tariff_country_map[tariff].append(country_iso)

    return neto_kg, tariff_country_map


def _apply_countries(items: List[Dict], tariff_country_map: Dict[str, List[str]]) -> None:
    """
    Dodijeli zemlja porijekla stavkama čija tarifna oznaka ima
    tačno jednu zemlju u sumarnom tabelu.

    Ako tarifa ima više zemalja, zemlja ostaje prazna (korisnik popunjava ručno).
    """
    for item in items:
        tariff = item.get("tariff", "")
        if not tariff:
            continue
        countries = tariff_country_map.get(tariff, [])
        if len(countries) == 1:
            item["zemlja"] = countries[0]


def _to_invoice_lines(items: List[Dict]) -> List[InvoiceLine]:
    """Konvertuje interni dict lista u InvoiceLine objekte."""
    result = []
    for item in items:
        line = InvoiceLine(
            line_no=item["rbr"],
            product_code=item["code"],
            naziv_robe=item["name"],
            tarifni_broj=item["tariff"],
            zemlja_porijekla=item.get("zemlja", ""),
            povlastica="",
            jm=item["jm"],
            kolicina=item["kolicina"],
            cijena_jed=item["cijena"],
            iznos=item["iznos"],
            valuta="EUR",
            bruto_kg=0.0,
            neto_kg=0.0,
        )
        result.append(line)
    return result


def _detect_origin_statement(text: str) -> bool:
    """
    Detektuj da li PDF sadrži izjavu o preferencijalnom poreklu.

    Koristi OriginStatementDetector servis.

    Args:
        text: Tekst PDF fakture

    Returns:
        True ako je nađena izjava, False inače
    """
    try:
        from services.origin_statement_detector import OriginStatementDetector

        detector = OriginStatementDetector()
        result = detector.detect_in_text(text)

        if result:
            logger.info(f"  ✅ Nađena izjava o poreklu: {result.jezik} / {result.tip_izjave} / origin={result.origin_country}")
            return True
        else:
            logger.debug("  ℹ️  Nije nađena izjava o poreklu")
            return False

    except Exception as e:
        logger.warning(f"  ⚠️  Greška tokom detekcije izjave: {e}")
        return False


def _detect_all_origin_statements(text: str) -> List:
    """
    Detektuj SVE izjave o preferencijalnom poreklu u tekstu.

    Args:
        text: Tekst PDF fakture

    Returns:
        Lista OriginStatementMatch objekata
    """
    try:
        from services.origin_statement_detector import OriginStatementDetector

        detector = OriginStatementDetector()
        statements = detector.detect_all_in_text(text)

        return statements

    except Exception as e:
        logger.warning(f"  ⚠️  Greška tokom detekcije izjava: {e}")
        return []
