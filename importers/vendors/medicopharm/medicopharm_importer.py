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

from core.draft.draft import InvoiceLine, Party
from importers.import_result import ImportResult
from importers.invoice_line_utils import KNOWN_JM, parse_eu_number, normalize_tariff_number
from utils.country_normalizer import normalize_country_name

logger = logging.getLogger("asycuda_pro.import.medicopharm")

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_INVOICE_NO_RE = re.compile(r"Faktura\s*[-–]\s*(\d+/\d+)", re.IGNORECASE)
_DATE_RE = re.compile(r"Datum\s+fakture[^:]*:\s*(\d{1,2}\.\d{1,2}\.\d{4})", re.IGNORECASE)
_BRUTO_RE = re.compile(r"BRUTO\s+TE[ZŽ]INA\s*:?\s*([\d\.,]+)\s*kg", re.IGNORECASE)

# Header tabla stavki: prepoznaje "Rb." + "JM" ili "Rbr" + "J.M." ili "Rb. Šifra" (novi format)
_ITEM_HEADER_RE = re.compile(
    r"\bRb\.\s*No\b|\bRb[r.]?\b.*\bJ\.?M\.?\b|\bRb\.\s+[ŠS]ifra\b",
    re.IGNORECASE
)

# Header sumarnog tabela — SAMO srpska verzija, ne "Tariff heading" (pojavljuje se i u headeru stavki)
_SUMMARY_HEADER_RE = re.compile(r"Tarifna\s+oznaka", re.IGNORECASE)

# Total red u sumarnom tabelu
_TOTAL_LINE_RE = re.compile(r"^Total\b", re.IGNORECASE)

# Linije koje su sigurno "šum" (footer, zaglavlje stranice, ponavljanje headera)
_NOISE_PATTERNS = [
    re.compile(r"^\s*Strana\s+\d+", re.IGNORECASE),
    re.compile(r"^\s*Page\s+\d+", re.IGNORECASE),
    re.compile(r"^\s*JM\s*$", re.IGNORECASE),              # Standalone "JM" red između tabela headera
    re.compile(r"^No\.\s+Code\b", re.IGNORECASE),           # "No. Code Tariff heading Item name..." (drugi red headera)
    re.compile(r"^Tariff\s+heading\b.*Country\b", re.IGNORECASE),  # Summary sub-header
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

# Linija sa šifrom serije + (opcioni token) + datumom roka + količinom (šum)
# Format 3 tokena: "301575 30.06.2028 400"
# Format 4 tokena: "300401 3 31.05.2027 80"  (srednji token je dodatan broj)
_LOT_DATE_QTY_RE = re.compile(r"^\d{4,8}\s+(?:\S+\s+)?\d{2}\.\d{2}\.\d{4}\s+\d+\s*$")

# "Zemlja porekla X" — prosta izjava o porijeklu robe
_ZEMLJA_POREKLA_RE = re.compile(
    r"Zemlja\s+porekla\s+([\wčćšžđČĆŠŽĐ]+(?:\s+[\wčćšžđČĆŠŽĐ]+){0,2})",
    re.IGNORECASE,
)

# Raspon stavki: "stavke broj 43-46"
_ITEM_RANGE_RE = re.compile(
    r"stavk[ei]\s+broj[a]?\s+(\d+)\s*[-–]\s*(\d+)",
    re.IGNORECASE,
)

# Pojedinačna stavka: "stavke broj 47" (bez iza nje -)
_ITEM_SINGLE_RE = re.compile(
    r"stavk[ei]?\s+broj[a]?\s+(\d+)(?!\s*[-–]\s*\d)",
    re.IGNORECASE,
)

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
            invoice_name=invoice_name, currency="EUR",
            exporter=Party(name="MEDICO PHARM SERVIS"),
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

    # --- Fallback: "Zemlja porekla X" izjava ---
    # Pretraži sve linije (fakture bez sumarnog tabela imaju samo tekst izjave)
    default_zemlja, item_zemlja_map = _parse_zemlja_porekla(lines)
    if default_zemlja:
        _apply_zemlja_porekla(raw_items, default_zemlja, item_zemlja_map)
        logger.info(f"   🌍 Zemlja porekla (izjava) dodijeljena za {sum(1 for i in raw_items if i['zemlja'])} stavki")

    logger.info(f"✅ Medico Pharm: {len(raw_items)} stavki | bruto={bruto_kg}kg | neto={neto_kg}kg")

    return ImportResult(
        items=_to_invoice_lines(raw_items),
        bruto_kg=bruto_kg,
        neto_kg=neto_kg,
        invoice_name=invoice_name,
        currency="EUR",
        has_origin_statement=has_origin_statement,
        origin_statements=origin_statements,
        exporter=Party(name="MEDICO PHARM SERVIS"),
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

    Podržava dva formata:
    1. Regularni (jednolinijski): RBR CODE TARIFF NAME JM KOL CENA IZNOS RAB% RABAT IZN_RABAT
    2. Split (višelinijski, Medicopharm format sa internim šiframa):
       - Linija 1: RBR CODE NAME... (bez JM i numeričkog repa)
       - Linija 2+: nastavak naziva / interna šifra kataloga
       - Zadnja linija segmenta: TARIFF JM KOL CENA IZNOS RAB% IZN_RABAT
    """
    items: List[Dict] = []
    current: Optional[Dict] = None

    # Buffer za "floating" linije koje dolaze ISPRED RBR linije (Proton System format)
    pending_name_parts: List[str] = []

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
            # Proton System: naziv dolazi iz pending buffera (ispred RBR linije)
            if pending_name_parts:
                prefix = " ".join(pending_name_parts)
                current["name"] = (prefix + " " + current["name"]).strip()
            pending_name_parts = []
        elif current and current.get("_partial"):
            # Split stavka — čekamo liniju s tarifom + JM + numeričkim repom
            completion = _try_complete_split_item(s)
            if completion:
                current.update(completion)
                del current["_partial"]
            else:
                # Nastavak naziva (interna šifra, drugi dio teksta)
                if not _LOT_DATE_QTY_RE.match(s):
                    current["name"] = (current["name"] + " " + s).strip()
        elif current:
            # Preskoči liniju šifra_serije + datum_roka + količina
            if _LOT_DATE_QTY_RE.match(s):
                continue
            if current.get("_proton"):
                # Proton System: naziv je kompletan — naredne linije su pending za sljedeću stavku
                pending_name_parts.append(s)
            else:
                # Medico Pharm: nastavak naziva iste stavke (multi-line opis)
                current["name"] = (current["name"] + " " + s).strip()
        else:
            # Pokušaj detektovati početak split stavke (RBR + CODE + NAME, bez JM u repu)
            partial = _try_parse_partial_item_start(s)
            if partial:
                if current:
                    items.append(current)
                current = partial
                pending_name_parts = []
            elif not _LOT_DATE_QTY_RE.match(s):
                # Nema tekuće stavke → buferiraj kao potencijalni naziv za sljedeću stavku
                pending_name_parts.append(s)

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

    # Minimum: rbr + code + jm + 5 numerika = 8 (Proton System)
    # ili: rbr + code + tariff + naziv + jm + 6 numerika = 10 (Medico Pharm)
    if len(parts) < 8:
        return None

    # ──────────────────────────────────────────────────────────────────
    # Pokušaj JM na pozicijama od desna: 6 → Proton System (5 num tail)
    #                                    7, 8 → Medico Pharm (6 num tail)
    # ──────────────────────────────────────────────────────────────────
    for offset in (7, 8, 6):
        if len(parts) <= offset:
            continue

        jm_raw = parts[-offset]
        jm = jm_raw.rstrip(".")  # SC. → sc, FL. → fl

        if jm.lower() not in KNOWN_JM:
            continue

        if offset == 6:
            # ── Proton System: RBR CODE [tekst...] KOL JM CENA POPUST NETO PDV IZNOS ──
            # JM na -6, tail = 5 numericka, kolicina na -7
            tail = parts[-5:]
            if not all(_is_numeric_token(t) for t in tail):
                continue
            kolicina_raw = parts[-7]
            if not _is_numeric_token(kolicina_raw):
                continue
            # Tekst između code i kolicine (name overflow iz naziva)
            extra_name = " ".join(parts[2:-7]) if len(parts) > 8 else ""
            return {
                "rbr": rbr,
                "code": parts[1],
                "tariff": "",
                "name": extra_name,   # Pending buffer se dodaje u _parse_items
                "jm": jm.lower(),
                "kolicina": parse_eu_number(kolicina_raw),
                "cijena": parse_eu_number(tail[0]),
                "iznos": parse_eu_number(tail[4]),
                "zemlja": "",
                "_proton": True,      # Flag: naziv dolazi iz pending buffera
            }
        else:
            # ── Medico Pharm: RBR CODE TARIFF [naziv] JM KOL CENA IZNOS RAB% RABAT IZN_RABAT ──
            tail = parts[-offset + 1:]
            if len(tail) != 6:
                continue
            if not all(_is_numeric_token(t) for t in tail):
                continue
            prefix = parts[:-offset]
            if len(prefix) < 3:
                continue
            code = prefix[1]
            tariff = prefix[2]
            name = " ".join(prefix[3:])
            iznos = parse_eu_number(tail[5])
            if iznos == 0.0:
                iznos = parse_eu_number(tail[2])
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


def _try_parse_partial_item_start(line: str) -> Optional[Dict]:
    """
    Detektuje PRVI red split-stavke (Medicopharm format sa internim šiframa).

    Format: RBR CODE NAME... (bez JM u repu, tipično završava jednim brojem 0.00)
    Primjer: "6 1611 GW REZERVNI DEO -DRŽAČ ZA SPREJ 0.00"

    Razlikuje se od regularnog reda: nema prepoznatog JM na pozicijama od desna.
    """
    parts = line.split()
    if len(parts) < 3:
        return None

    try:
        rbr = int(parts[0])
        if rbr <= 0 or rbr > 9999:
            return None
    except ValueError:
        return None

    # Ako ima JM na standardnim pozicijama → to je regularni red, ne split
    for offset in (7, 8, 6):
        if len(parts) <= offset:
            continue
        if parts[-offset].rstrip(".").lower() in KNOWN_JM:
            return None

    # Mora završavati numeričkim tokenom (tipično 0.00) ali ne smije biti samo broj
    if not _is_numeric_token(parts[-1]):
        return None
    if len(parts) < 4:
        return None

    code = parts[1]
    name = " ".join(parts[2:-1])  # Naziv između code i završnog broja

    return {
        "rbr": rbr,
        "code": code,
        "tariff": "",
        "name": name,
        "jm": "",
        "kolicina": 0.0,
        "cijena": 0.0,
        "iznos": 0.0,
        "zemlja": "",
        "_partial": True,
    }


def _try_complete_split_item(line: str) -> Optional[Dict]:
    """
    Pokušava kompletirati split-stavku pronalazeći liniju oblika:
    TARIFF JM KOL CENA IZNOS [RAB%] [RABAT] IZN_RABAT

    Primjer: "90330090 KOM 1.00 76.481 76.48 0.00 76.48"
    Tarifa je čisto numerička (>= 4 cifre), JM mora biti u KNOWN_JM.
    """
    parts = line.split()
    if len(parts) < 4:
        return None

    # Tarifa mora biti samo cifre (4+ cifre, >1000)
    if not re.match(r"^\d{4,}$", parts[0]):
        return None

    # Drugi token mora biti JM
    jm = parts[1].rstrip(".")
    if jm.lower() not in KNOWN_JM:
        return None

    # Ostatak moraju biti numerički tokeni (3-6 vrijednosti)
    tail = parts[2:]
    if len(tail) < 3 or not all(_is_numeric_token(t) for t in tail):
        return None

    tariff = parts[0]
    kolicina = parse_eu_number(tail[0])
    cijena = parse_eu_number(tail[1]) if len(tail) > 1 else 0.0
    iznos = parse_eu_number(tail[-1])  # IZN_RABAT = zadnji token

    return {
        "tariff": tariff,
        "jm": jm.lower(),
        "kolicina": kolicina,
        "cijena": cijena,
        "iznos": iznos,
    }


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

    # Skip samo jednu sub-header liniju ("Tariff heading Country Amount Sum Weight")
    # Napomena: "Tarifna oznaka" linija je već preskočena u detekcijskom loopu (summary_start = i+1)
    skip_headers = 1

    for ln in lines:
        s = ln.strip()
        if not s:
            continue

        # Preskoči header/sub-header linije sumarnog tabela (ako se ponavljaju)
        if _SUMMARY_HEADER_RE.search(s):
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
        # Red sumarnog tabela: tarifa (cifre, opciono sa "/") + zemlja + kolicina + iznos + tezina
        if len(parts) < 5:
            continue
        if not re.match(r"^\d[\d/]*$", parts[0]):
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


def _parse_zemlja_porekla(lines: List[str]) -> Tuple[str, Dict[int, str]]:
    """
    Pretražuje sve linije dokumenta za "Zemlja porekla X" izjave.

    Podržava:
    - Prosto: "Zemlja porekla Nemačka"
    - Složeno: "Zemlja porekla Srbija, osim stavke broj 43-46 Zemlja porekla Srbija
      bez pref. porekla i stavke broj 47 - Zemlja porekla Francuska bez pref. porekla"

    Returns:
        (default_country_iso, {rbr: country_iso})
        default_country_iso — zemlja za sve stavke koje nemaju override
        dict — per-stavka override (po rbr)
    """
    full_text = " ".join(lines)
    matches = list(_ZEMLJA_POREKLA_RE.finditer(full_text))

    if not matches:
        return "", {}

    def _resolve_country(candidate: str) -> str:
        """Pokušava normalizovati kandidat, smanjujući broj riječi dok ne dobije ISO kod."""
        words = candidate.strip().split()
        for n in range(len(words), 0, -1):
            phrase = " ".join(words[:n])
            iso = normalize_country_name(phrase)
            # normalize_country_name vraća original ako nije pronašlo — znači nije ISO
            if iso != phrase and len(iso) == 2:
                return iso
        return ""

    found = [
        (m.start(), _resolve_country(m.group(1)))
        for m in matches
    ]
    # Preskočimo matcheve gdje zemlja nije prepoznata
    found = [(pos, iso) for pos, iso in found if iso]

    default_country = found[0][1]
    item_overrides: Dict[int, str] = {}

    # Za svaki naredni match, u segmentu između prethodnog i trenutnog
    # tražimo na koje stavke se primjenjuje
    for i in range(1, len(found)):
        pos, country = found[i]
        prev_pos = found[i - 1][0]
        segment = full_text[prev_pos:pos]

        for m in _ITEM_RANGE_RE.finditer(segment):
            for rbr in range(int(m.group(1)), int(m.group(2)) + 1):
                item_overrides[rbr] = country

        for m in _ITEM_SINGLE_RE.finditer(segment):
            item_overrides[int(m.group(1))] = country

    if default_country:
        logger.info(
            f"   🌍 Zemlja porekla iz izjave: default={default_country}"
            + (f", overrides={item_overrides}" if item_overrides else "")
        )

    return default_country, item_overrides


def _apply_zemlja_porekla(
    items: List[Dict],
    default_country: str,
    item_overrides: Dict[int, str],
) -> None:
    """
    Dopuni zemlja porijekla stavkama koje je još nemaju.
    Koristi per-stavka override ako postoji, inače default.
    """
    for item in items:
        if item.get("zemlja"):
            continue  # Već popunjeno iz sumarnog tabela
        rbr = item.get("rbr", 0)
        item["zemlja"] = item_overrides.get(rbr, default_country)


def _to_invoice_lines(items: List[Dict]) -> List[InvoiceLine]:
    """Konvertuje interni dict lista u InvoiceLine objekte."""
    result = []
    for item in items:
        line = InvoiceLine(
            line_no=item["rbr"],
            product_code=item["code"],
            naziv_robe=item["name"],
            tarifni_broj=normalize_tariff_number(item["tariff"]),
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
        from services.tariff.origin_statement_detector import OriginStatementDetector

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
        from services.tariff.origin_statement_detector import OriginStatementDetector

        detector = OriginStatementDetector()
        statements = detector.detect_all_in_text(text)

        return statements

    except Exception as e:
        logger.warning(f"  ⚠️  Greška tokom detekcije izjava: {e}")
        return []
