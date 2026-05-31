# importers/pdf/ocr_invoice_parser.py

"""
Parser OCR teksta (stranice kao stringovi) u InvoiceLine objekte.

Dvije strategije:

STRUKTURIRANI format (Medicopharm, standardne tabele sa kodom i tarifom):
  seq  code  tariff  naziv...  JM  qty  price  iznos
  npr: 1 11878 38249993 SUSSINA 650 tbl. KOM 150.00 1.020 152.95

GENERIČKI format (StancMetal, jednostavne fakture):
  seq. naziv...  qty  jm  price/jm  iznos
  npr: 1. 0.40 x 40 mm  3.10 mt  1535EUR/mt  4758.50EUR
"""

import logging
import re
from typing import List, Tuple, Dict, Optional

from core.draft.draft import InvoiceLine
from importers.import_result import ImportResult

logger = logging.getLogger("deklarant_pro.import.ocr_parser")


# ─────────────────────────────────────────────────────────────
# POMOĆNE FUNKCIJE
# ─────────────────────────────────────────────────────────────

def _parse_num(s: str) -> float:
    """Pretvara OCR broj u float. Podržava EU (1.234,56) i US (1,234.56).

    Pravilo za jednoznačni zarez (bez tačke):
    - Ako je integer dio <= 3 cifre → zarez je decimalni separator (4,079 = 4.079)
    - Ako je integer dio > 3 cifre → zarez je separator hiljada (4079,00 = 4079.00)
    """
    if not s:
        return 0.0
    s = re.sub(r"[^\d,.\-]", "", str(s).strip())
    if not s:
        return 0.0
    if "." in s and "," in s:
        last_dot = s.rfind(".")
        last_comma = s.rfind(",")
        if last_comma > last_dot:   # EU: 1.234,56
            s = s.replace(".", "").replace(",", ".")
        else:                       # US: 1,234.56
            s = s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        if len(parts) == 2:
            int_part, dec_part = parts
            # Integer dio <= 3 cifre → zarez je decimalni separator
            if len(int_part) <= 3:
                s = int_part + "." + dec_part
            else:
                s = int_part + dec_part  # hiljadice
        else:
            s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _extract_weights(text: str) -> Tuple[float, float]:
    bruto = 0.0
    neto = 0.0
    b = re.search(r"(?:gross|bruto|G\.?W\.?|BRUTO\s+TEZINA)[^\d]{0,15}([\d,.]+)\s*kg", text, re.IGNORECASE)
    if b:
        bruto = _parse_num(b.group(1))
    n = re.search(r"(?:neto|net(?!\w)|N\.?W\.?)[^\d]{0,15}([\d,.]+)\s*kg", text, re.IGNORECASE)
    if n:
        neto = _parse_num(n.group(1))
    return bruto, neto


def _extract_invoice_number(text: str) -> str:
    patterns = [
        r"FAKTURA[\s\-]+(\d{1,6}/\d{2,4})",
        r"(?:invoice|faktura|račun|racun)[^\w]{0,5}(?:no|br|broj)?[^\w]{0,5}([A-Z0-9\-/]+)",
        r"INV[:#\s]{1,3}([A-Z0-9\-/]{3,20})",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            v = m.group(1).strip()
            if 2 <= len(v) <= 30:
                return v
    return ""


# Srpski/bosanski nazivi zemalja → ISO kod
_COUNTRY_MAP = {
    "NEMACKA": "DE", "NJEMACKA": "DE", "GERMANY": "DE", "DEUTSCHLAND": "DE",
    "FRANCUSKA": "FR", "FRANCE": "FR",
    "ITALIJA": "IT", "ITALY": "IT",
    "AUSTRIJA": "AT", "AUSTRUA": "AT", "AUSTRIA": "AT",
    "PORTUGAL": "PT",
    "POLJSKA": "PL", "POLAND": "PL",
    "SJEDINJENE": "US", "AMERIKE": "US", "USA": "US", "SAD": "US",
    "VELIKABRITANIJA": "GB", "BRITANIJA": "GB", "ENGLAND": "GB",
    "CESKA": "CZ", "CZECH": "CZ",
    "SPANIJA": "ES", "SPAIN": "ES",
    "GRCKA": "GR", "GREECE": "GR",
    "KINA": "CN", "CHINA": "CN",
    "SLOVENIJA": "SI", "SLOVENIA": "SI",
    "HRVATSKA": "HR", "CROATIA": "HR",
    "SRBIJA": "RS", "SERBIA": "RS",
    "TURSKA": "TR", "TURKEY": "TR",
    "RUMUNIJA": "RO", "ROMANIA": "RO",
    "BELGIJA": "BE", "BELGIUM": "BE",
    "HOLANDIJA": "NL", "NETHERLANDS": "NL",
    "SVEDSKA": "SE", "SWEDEN": "SE",
    "SUNCARSKA": "CH", "SWITZERLAND": "CH",
    "RUSIJA": "RU", "RUSSIA": "RU",
    "JAPAN": "JP",
    "INDIJA": "IN", "INDIA": "IN",
}


def _normalize_country(name: str) -> str:
    """Prevodi naziv zemlje (bosanski/engleski) u ISO2 kod."""
    name = name.strip().upper()
    # Direktno podudaranje
    if name in _COUNTRY_MAP:
        return _COUNTRY_MAP[name]
    # Podudaranje po prefiksu (npr. "SJEDINJENE AM." → "US")
    for key, iso in _COUNTRY_MAP.items():
        if name.startswith(key[:5]):
            return iso
    # Ako je već 2-slovna (ISO kod)
    if re.match(r"^[A-Z]{2}$", name):
        return name
    return ""


def _parse_origin_table(full_text: str) -> Dict[str, str]:
    """
    Parsira tabelu 'Tarifna oznaka → Zemlja porijekla' koja se pojavljuje
    na zadnjim stranicama Medicopharm fakture.

    Format:
      tarifna_oznaka  ZEMLJA  količina  iznos  težina
      npr: 33049900000 FRANCUSKA 584.00 3,547.35 21.68

    Returns:
        Dict {tarifni_broj: iso_country_code}
    """
    mapping: Dict[str, str] = {}

    # Nađi sekciju koja je SPECIFIČNA za tabelicu zemalja:
    # "ariff heading Country" (ne "ariff heading Item" koji je header stavki)
    # ili "arifna oznaka Zemlja"
    # Uzimamo PRVU pojavu — tabela počinje na stranici 3, podaci se protežu do str. 4
    first_match = re.search(
        r"(?:ariff heading\s+Country|arifna oznaka\s+Zemlja)",
        full_text, re.IGNORECASE
    )
    table_start = first_match.end() if first_match else -1

    if table_start < 0:
        # Fallback: traži redove koji počinju ciframa i imaju poznatu zemlju
        logger.debug("Tabela zemlja: header nije pronađen, pokušavam direktno parsiranje")
        table_text = full_text
    else:
        # Uzmi tekst od table_start do kraja ili do "Fakturisao"
        end_match = re.search(r"Fakturisao|ZA UPLATU|SLOVIMA", full_text[table_start:], re.IGNORECASE)
        end_pos = end_match.start() if end_match else len(full_text) - table_start
        table_text = full_text[table_start:table_start + end_pos]

    # Svaki red: cifre + zemlja + brojevi
    for line in table_text.split("\n"):
        line = line.strip()
        if not line or len(line) < 10:
            continue

        # Pattern: {tariff_digits} {COUNTRY_NAME} {numbers...}
        m = re.match(
            r"^(\d{6,12}(?:/\d+)?)\s+"           # tarifna oznaka (može imati /)
            r"([A-ZŠĐČĆŽ][A-ZŠĐČĆŽА-Яа-яa-z\s.]{2,30}?)\s+"  # ime zemlje
            r"([\d,. |]+)$",                      # ostatak (količine, iznosi, težine)
            line, re.IGNORECASE
        )
        if not m:
            continue

        raw_tariff = m.group(1).split("/")[0]  # uzmi dio prije / ako ima
        raw_country = m.group(2).strip()

        iso = _normalize_country(raw_country)
        if not iso:
            continue

        # Skrati na 10 cifara ako je duži
        if len(raw_tariff) > 10:
            raw_tariff = raw_tariff[:10]

        mapping[raw_tariff] = iso

    logger.debug(f"Tabela zemlja: {len(mapping)} unosa")
    return mapping


# ─────────────────────────────────────────────────────────────
# STRUKTURIRANI PARSER (Medicopharm-like: seq+code+tariff+naziv+jm+qty+price+iznos)
# ─────────────────────────────────────────────────────────────

def _clean_ocr_line(line: str) -> str:
    """
    Čisti česte OCR greške u Medicopharm fakturama prije pokušaja parsiranja.
    - 'li' ili 'lI' na početku → '11'
    - '6S', '7B' na početku (cifra + slovo) → dodaj razmak
    - '+=' ili '= ' između koda i tarife → obriši
    - Period odmah iza rednog broja → razmak
    """
    line = line.strip()

    # li/lI na početku linije (OCR čita '11' kao 'li')
    line = re.sub(r"^([lL][iIl1])\s+", "11 ", line)

    # Cifra + jedno slovo na početku (npr. '6S' → pokušaj sačuvati kao '65')
    # Samo ako iza toga dolazi razmak i broj (šifra)
    line = re.sub(r"^(\d)([A-Z])\s+(\d{4,7})\s", lambda m: m.group(1) + " " + m.group(3) + " ", line)

    # Period odmah iza rednog broja (npr. '43. 23913' → '43 23913')
    line = re.sub(r"^(\d{1,3})\.\s+", r"\1 ", line)

    # OCR šum između šifre i tarifne oznake (npr. '17419 += 33049900' → '17419 33049900')
    line = re.sub(r"(\d{4,7})\s*[+\-=]{1,3}\s*(\d{8})", r"\1 \2", line)

    return line


# Format: 1  11878  38249993  NAZIV ROBE  KOM  150.00  1.020  152.95  ...
_STRUCTURED_ROW = re.compile(
    r"^(\d{1,3})\s+"             # redni broj
    r"(\d{3,7})\s+"              # šifra (3-7 cifara — Medicopharm ima 3-5)
    r"(\d{7,12})\s+"             # tarifni broj (7-12 cifara, OCR ponekad izgubi cifru)
    r"(.+?)\s+"                  # naziv (non-greedy)
    r"([A-Za-z]{1,5})[.,]?\s+"  # JM (KOM, ML, G, L, SC...) — dozvoli tačku/zarez iza
    r"([\d,.]+)\s+"              # količina
    r"([\d,.]+)\s+"              # cijena
    r"([\d,.]+)",                # iznos
    re.IGNORECASE
)


def _try_structured(lines: List[str]) -> List[InvoiceLine]:
    """Parsira Medicopharm-style fakture (kod + tarifni + naziv + jm + qty + cijena + iznos)."""
    items: List[InvoiceLine] = []
    seen_seq = set()  # spriječi duplikate

    for raw_line in lines:
        line = _clean_ocr_line(raw_line)
        m = _STRUCTURED_ROW.match(line)
        if not m:
            continue

        naziv = m.group(4).strip()
        # Preskoci header i footer redove
        if re.search(r"(total|ukupno|naziv|description|code|tariff|amount|heading)", naziv, re.IGNORECASE):
            continue
        # Preskoci redove koji su previše kratki da budu nazivi robe
        if len(naziv) < 2:
            continue

        seq_str = m.group(1)
        try:
            seq = int(seq_str)
        except ValueError:
            continue

        # Spriječi duplikate
        if seq in seen_seq:
            continue
        seen_seq.add(seq)

        kolicina = _parse_num(m.group(6))
        cijena   = _parse_num(m.group(7))
        iznos    = _parse_num(m.group(8))
        if iznos == 0 and kolicina > 0 and cijena > 0:
            iznos = round(kolicina * cijena, 4)

        # Provjeri matematičku konzistentnost: qty × price ≈ iznos (±5%)
        if kolicina > 0 and cijena > 0 and iznos > 0:
            expected = kolicina * cijena
            ratio = abs(expected - iznos) / max(iznos, 0.001)
            if ratio > 0.05:
                for div in (1000, 100, 10):
                    if abs((kolicina * cijena / div) - iznos) / max(iznos, 0.001) < 0.05:
                        cijena /= div
                        break
                else:
                    for div in (1000, 100, 10):
                        if abs((kolicina / div * cijena) - iznos) / max(iznos, 0.001) < 0.05:
                            kolicina /= div
                            break

        tariff = m.group(3)
        # Validiraj tarifni: 8-12 cifara, skrati na 10 ako je duži
        if not re.match(r"^\d{8,12}$", tariff):
            tariff = ""
        elif len(tariff) > 10:
            tariff = tariff[:10]

        items.append(InvoiceLine(
            line_no=seq,
            product_code=m.group(2),
            tarifni_broj=tariff,
            naziv_robe=naziv,
            jm=m.group(5).upper(),
            kolicina=kolicina,
            cijena_jed=cijena,
            iznos=iznos,
            valuta="EUR",
        ))

    # Sortiraj po rednom broju
    items.sort(key=lambda x: x.line_no)
    # Renumber
    for i, item in enumerate(items):
        item.line_no = i + 1

    return items


# ─────────────────────────────────────────────────────────────
# TABELARNI PARSER (header detekcija + kolone po redu)
# ─────────────────────────────────────────────────────────────

_HEADER_SIGNALS = re.compile(
    r"(?:qty|quantity|koli[cč]|description|naziv|price|cijena|amount|iznos|tariff|oznaka)",
    re.IGNORECASE
)

_DATA_LINE = re.compile(
    r"^\d{1,3}[\.\):]?\s+"
    r".+"
    r"([\d,.]+)\s+"
    r"[\w/€$]?\s*"
    r"([\d,.]+)",
    re.IGNORECASE
)


def _try_tabular(lines: List[str]) -> List[InvoiceLine]:
    """
    Traži header red, pa parsira redove ispod koristeći pozicijski pristup
    (tokenizacija razmacima, zadnji tokeni su brojevi).
    """
    header_idx = -1
    for i, line in enumerate(lines[:50]):
        matches = _HEADER_SIGNALS.findall(line)
        if len(matches) >= 3:
            header_idx = i
            break

    if header_idx < 0:
        return []

    items: List[InvoiceLine] = []
    for line in lines[header_idx + 1:]:
        line = line.strip()
        if not line or len(line) < 8:
            continue
        if re.search(r"(ukupno|total|grand|subtotal|sum:|zbir)", line, re.IGNORECASE):
            continue

        tokens = line.split()
        if not tokens:
            continue

        num_tokens = []
        text_tokens = []
        for tok in tokens:
            clean = re.sub(r"[A-Z€$%]", "", tok.upper())
            clean = re.sub(r"[^\d,.]", "", clean)
            if clean and re.match(r"^\d", clean):
                try:
                    val = _parse_num(clean)
                    if val > 0:
                        num_tokens.append((tok, val))
                        continue
                except Exception:
                    pass
            text_tokens.append(tok)

        if len(num_tokens) < 2:
            continue

        iznos   = num_tokens[-1][1]
        cijena  = num_tokens[-2][1] if len(num_tokens) >= 2 else 0.0
        kolicina = num_tokens[-3][1] if len(num_tokens) >= 3 else 0.0

        naziv_tokens = [t for t in text_tokens if not re.match(r"^\d{1,3}\.?$", t)]
        naziv = " ".join(naziv_tokens).strip()

        if not naziv or iznos <= 0:
            continue

        items.append(InvoiceLine(
            line_no=len(items) + 1,
            naziv_robe=naziv,
            jm="",
            kolicina=kolicina,
            cijena_jed=cijena,
            iznos=iznos,
            valuta="EUR",
        ))

    return items


# ─────────────────────────────────────────────────────────────
# GENERIČKI PARSER (StancMetal-like, jednostavne fakture)
# ─────────────────────────────────────────────────────────────

_GENERIC_ROW = re.compile(
    r"^(\d{1,3})[\.\):]?\s+"
    r"(.+?)\s+"
    r"([\d,.]+)\s+"
    r"([a-zA-Z]{1,6})?\s*"
    r"([\d,.]+)\s*"
    r"(?:[A-Z€/\w]+\s+)?"
    r"([\d,.]+)",
    re.IGNORECASE
)


def _try_generic(lines: List[str]) -> List[InvoiceLine]:
    """Generički parser za jednostavne fakture bez jasne tabele."""
    items: List[InvoiceLine] = []
    for line in lines:
        m = _GENERIC_ROW.match(line.strip())
        if not m:
            continue
        naziv = m.group(2).strip()
        if re.search(r"(total|ukupno|naziv|description|invoice|faktura)", naziv, re.IGNORECASE):
            continue
        kolicina = _parse_num(m.group(3))
        cijena   = _parse_num(m.group(5))
        iznos    = _parse_num(m.group(6))
        jm       = m.group(4) or ""
        if iznos == 0 and kolicina > 0 and cijena > 0:
            iznos = round(kolicina * cijena, 4)
        if iznos <= 0:
            continue
        items.append(InvoiceLine(
            line_no=len(items) + 1,
            naziv_robe=naziv,
            jm=jm,
            kolicina=kolicina,
            cijena_jed=cijena,
            iznos=iznos,
            valuta="EUR",
        ))
    return items


# ─────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────

def parse_ocr_result(pages_text: List[str], pdf_path: str = "") -> ImportResult:
    """
    Parsira OCR tekst po stranicama u ImportResult.

    Args:
        pages_text: izlaz ocr_pdf_to_text() — lista stringova po stranicama
        pdf_path: putanja za logging
    """
    full_text = "\n".join(pages_text)
    lines = full_text.split("\n")

    bruto_kg, neto_kg = _extract_weights(full_text)
    invoice_number = _extract_invoice_number(full_text)
    has_origin = bool(re.search(
        r"preferential origin|origin declaration|izjava.*porijekl|preferencijal",
        full_text, re.IGNORECASE
    ))

    # Tabela zemlja porijekla (Medicopharm stil — zadnje stranice)
    origin_map = _parse_origin_table(full_text)

    # 1. Strukturirani parser (najspecifičniji — Medicopharm, fakture sa kodom+tarifom)
    items = _try_structured(lines)
    if items:
        logger.info(f"📋 Strukturirani OCR parser: {len(items)} stavki")

    # 2. Tabelarni (header detekcija)
    if not items:
        items = _try_tabular(lines)
        if items:
            logger.info(f"📊 Tabelarni OCR parser: {len(items)} stavki")

    # 3. Generički fallback
    if not items:
        items = _try_generic(lines)
        if items:
            logger.info(f"🔍 Generički OCR parser: {len(items)} stavki")

    if not items:
        logger.warning("⚠️ OCR: nijedan parser nije pronašao stavke")

    # Primijeni tabelu zemlja porijekla na stavke
    if origin_map:
        _apply_origin_map(items, origin_map)

    logger.info(
        f"✅ OCR završen: {len(items)} stavki | bruto={bruto_kg} kg | "
        f"neto={neto_kg} kg | faktura={invoice_number}"
    )

    return ImportResult(
        items=items,
        bruto_kg=bruto_kg,
        neto_kg=neto_kg,
        invoice_name=invoice_number,
        currency="EUR",
        has_origin_statement=has_origin,
        origin_statements=[],
    )


def _apply_origin_map(items: List[InvoiceLine], origin_map: Dict[str, str]) -> None:
    """
    Primijenjuje tabelu tarif → zemlja porijekla na stavke.
    Pokušava exact match, pa suffix match.

    OCR u tabeli zemlja često gubi 1-2 vodeće cifre (npr. "3" → "8" ili nestane),
    pa poredimo zadnjih 8-10 cifara tarife.
    """
    for item in items:
        if item.zemlja_porijekla:
            continue
        tariff = item.tarifni_broj
        if not tariff:
            continue

        # 1. Exact match
        if tariff in origin_map:
            item.zemlja_porijekla = origin_map[tariff]
            continue

        # 2. Suffix match — pokušaj zadnjih 10, 9, 8, 7 cifara
        matched = ""
        for suffix_len in (10, 9, 8, 7):
            if len(tariff) < suffix_len:
                continue
            t_suffix = tariff[-suffix_len:]
            for map_tariff, country in origin_map.items():
                m_clean = map_tariff.split("/")[0]
                if len(m_clean) >= suffix_len and m_clean[-suffix_len:] == t_suffix:
                    matched = country
                    break
            if matched:
                break

        if matched:
            item.zemlja_porijekla = matched
