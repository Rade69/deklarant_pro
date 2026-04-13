# importers/vendors/leburic/leburic_pekabesko_pdf_parser.py
"""
ASYCUDA Pro - Leburic/Pekabesko PDF Parser

Parsira Pekabesko AD fakture u PDF formatu (skenirani OCR dokumenti).

Kolone (x pozicije iz extract_words):
  item_code  : x ≈  40–200  (šifra artikla, 5-6 cifara)
  barcode    : x ≈ 200–260  (EAN/barcode, prefix 3102...)
  tariff     : x ≈ 260–330  (HS tarifni broj, 8-10 cifara, OCR artefakti)
  unit       : x ≈ 305–328  (JM: qr/gr/kgr, često OCR kvar)
  qty        : x ≈ 335–390  (količina/broj paketa, OCR artefakti)
  neto_kgr   : x ≈ 385–425  (neto težina stavke u kg, header "Neto (kgr)")
  gross_col  : x ≈ 438–468  (bruto iznos ili bruto kg — isti kao neto, duplikat OCR)
  discount   : x ≈ 490–515  (rabat %)
  total_eur  : x ≈ 525–565  (neto EUR iznos stavke)

Footer (pouzdaniji od stavki):
  Btol/Btoi  → ukupni bruto kg
  Nto:/Ntoi  → ukupni neto kg
  Poreklo    → zemlja porijekla (MK)
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

from core.draft.draft import InvoiceLine, Party
from importers.import_result import ImportResult

logger = logging.getLogger("asycuda_pro.import.leburic_pekabesko_pdf")

# ──────────────────────────────────────────────────────────────────
# OCR cleanup helpers
# ──────────────────────────────────────────────────────────────────

# Znakovi koji se na početku OCR teksta pojavljuju kao artefakti
_LEADING_TRASH = re.compile(r"^[^0-9]+")
# Znakovi koji se na kraju OCR teksta pojavljuju kao artefakti
_TRAILING_TRASH = re.compile(r"[^0-9.,]+$")

# Zamjene OCR grešaka u tarifnim brojevima (unutar stringa)
_TARIFF_OCR = str.maketrans({
    "r": "1", "l": "1", "I": "1", "i": "1",
    "S": "5", "s": "5", "O": "0", "o": "0",
    "G": "6", "B": "8", "A": "4",
    "/": "1", "\\": "1",
    ",": "", ".": "", "(": "", ")": "",
    "{": "", "}": "", "[": "", "]": "",
    " ": "",
})

# Zamjene za numeričke vrijednosti (cijene, mase)
_NUM_OCR = str.maketrans({
    "I": "1", "l": "1", "i": "1",
    "O": "0", "o": "0",
    "S": "5", "Z": "2",
    "t": "", "f": "", "C": "", "c": "",
    "!": "", "(": "", ")": "",
    "{": "", "}": "", "[": "", "]": "",
    ":": "", ";": "", "?": "",
})


def _clean_tariff(raw: str) -> str:
    """Očisti tarifni broj od OCR artefakata i vrati 8 ili 10-cifreni string."""
    s = raw.strip()
    # Ukloni leading non-digit prefixe (i, r, , . itd.)
    s = _LEADING_TRASH.sub("", s)
    # Primijeni OCR zamjene za preostale karaktere
    s = s.translate(_TARIFF_OCR)
    # Ostavi samo cifre
    s = re.sub(r"[^\d]", "", s)
    if not s:
        return ""
    # Pad na 8 ili 10 cifara ako su izgubljene vodeće nule
    n = len(s)
    if n == 9:
        s = s.zfill(10)
    elif n == 7:
        s = s.zfill(8)
    return s


def _clean_number(raw: str) -> Optional[float]:
    """
    Parsira broj iz OCR teksta uz uklanjanje artefakata.

    Primjeri:
      "1880("   → 1880.0
      "I504"    → 1504.0
      "337.600" → 337.600  (period = decimalni separator)
      "336,00(" → 336.0
      "33760("  → 337.60   (implicitne 2 decimale za integers)
    """
    if not raw:
        return None
    s = raw.strip()
    # Primijeni OCR zamjene
    s = s.translate(_NUM_OCR)
    # Ukloni leading/trailing smeće
    s = _LEADING_TRASH.sub("", s)
    s = _TRAILING_TRASH.sub("", s)
    if not s:
        return None

    # Ako ima i zarez i tačku: odluči koji je decimalni separator
    if "," in s and "." in s:
        # Zadnji od ta dva je decimalni separator (ex-YU standard)
        last_comma = s.rfind(",")
        last_dot = s.rfind(".")
        if last_comma > last_dot:
            # Zarez je decimalni, tačka je separator hiljada
            s = s.replace(".", "").replace(",", ".")
        else:
            # Tačka je decimalni, zarez je separator hiljada
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    # tačka ostaje kao decimalni separator

    try:
        val = float(s)
        return val
    except ValueError:
        return None


def _clean_number_implicit_decimal(raw: str, decimals: int = 2) -> Optional[float]:
    """
    Parsira broj uz implicitne decimale ako nije pronađena decimalna tačka.

    Koristi se za kolone gdje OCR briše tačku/zarez:
      "33760" → 337.60  (decimals=2)
      "179200" → 1792.00
    """
    val = _clean_number(raw)
    if val is None:
        return None
    # Ako je cijeli broj (ili nema decimala u originalnom textu),
    # primijeni implicitne decimale
    if "." not in raw and "," not in raw:
        val = val / (10 ** decimals)
    return val


# ──────────────────────────────────────────────────────────────────
# Detekcija formata
# ──────────────────────────────────────────────────────────────────

def detect_leburic_pekabesko_pdf(pdf_path: str) -> bool:
    """
    Vrać True ako PDF izgleda kao Pekabesko/Leburic faktura.

    Kriteriji:
    - Sadrži 'PEKABESKO' (ime dobavljača)
    - Sadrži 'FAKTURA' ili 'LEBURIC'
    """
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            text = ""
            for page in pdf.pages[:2]:
                text += (page.extract_text() or "")
        text_upper = text.upper()
        return "PEKABESKO" in text_upper and (
            "FAKTURA" in text_upper or "LEBURIC" in text_upper
        )
    except Exception:
        return False


# ──────────────────────────────────────────────────────────────────
# Glavni parser
# ──────────────────────────────────────────────────────────────────

# X-granice kolona (lijeva, desna)
_COL_ITEM_CODE   = (38,  205)
_COL_BARCODE     = (200, 262)
_COL_TARIFF      = (260, 330)
_COL_QTY         = (335, 390)
_COL_NETO_KGR    = (385, 430)
_COL_TOTAL_EUR   = (523, 580)

# Y-raspon za header (invoice broj, datum)
_HEADER_Y_MAX    = 230

# Regex za footer podatke
# Btol/Btoi/Bto: → ukupni bruto kg
_BRUTO_RE = re.compile(
    r"bto[il:.]?\s*:?\s*([0-9][0-9\s\.,]*)\s*k[gs]", re.IGNORECASE
)
# Nto:/Ntoi/Nto: → ukupni neto kg
_NETO_RE = re.compile(
    r"nto[il:.]?\s*:?\s*([0-9][0-9\s\.,]*)\s*k[gs]", re.IGNORECASE
)
# Poreklo + razne OCR varijante MK
_POREKLO_RE = re.compile(
    r"poreklo\s*:?\s*(MK|lrlK|I\\4K|l4K|lrK|LrlK|LRLK|lK|lYlK)", re.IGNORECASE
)
_FAKTURA_RE = re.compile(
    r"FAKTURA[:\s]+([0-9][0-9\-\./ ]{4,})", re.IGNORECASE
)
_NALOG_RE = re.compile(
    r"nalog\s+br[\s:.]*([0-9][0-9\-\./ ]{4,})", re.IGNORECASE
)
_DATUM_RE = re.compile(
    r"datum[:\s]*(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{4})", re.IGNORECASE
)


def parse_leburic_pekabesko_pdf(pdf_path: str) -> ImportResult:
    """
    Parsira Leburic/Pekabesko PDF fakturu.

    Strategija:
    1. Čita header (invoice broj, datum)
    2. Čita stavke po x-koordinatama riječi
    3. Čita footer (bruto, neto ukupno, zemlja)
    Returns:
        ImportResult sa stavkama, težinama i metapodacima
    """
    import pdfplumber

    logger.info(f"Leburic/Pekabesko PDF parsiranje: {Path(pdf_path).name}")

    invoice_number = ""
    invoice_date = ""
    bruto_kg = 0.0
    neto_kg = 0.0
    zemlja = "MK"  # default za Pekabesko (Makedonija)

    invoice_lines: list[InvoiceLine] = []
    all_words: list[dict] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words(x_tolerance=3, y_tolerance=3)
            all_words.extend(words)

    # ── 1. HEADER: invoice broj, datum ──────────────────────────────
    # Skupi text iz header zone (y < _HEADER_Y_MAX)
    header_text = " ".join(
        w["text"] for w in all_words if w["top"] < _HEADER_Y_MAX
    )

    m = _NALOG_RE.search(header_text)
    if m:
        invoice_number = m.group(1).strip().rstrip(".")
    else:
        m = _FAKTURA_RE.search(header_text)
        if m:
            invoice_number = m.group(1).strip().rstrip(".")

    m = _DATUM_RE.search(header_text)
    if m:
        invoice_date = m.group(1).strip()

    logger.info(f"  Header: faktura={invoice_number!r}, datum={invoice_date!r}")

    # ── 2. FOOTER: bruto, neto, zemlja ──────────────────────────────
    # Skupi cijeli tekst za footer regex (sve stranice)
    full_text = " ".join(w["text"] for w in all_words)

    m = _BRUTO_RE.search(full_text)
    if m:
        raw = m.group(1).replace(" ", "").replace(",", ".")
        try:
            bruto_kg = float(raw)
        except ValueError:
            pass

    m = _NETO_RE.search(full_text)
    if m:
        raw = m.group(1).replace(" ", "").replace(",", ".")
        try:
            neto_kg = float(raw)
        except ValueError:
            pass

    if _POREKLO_RE.search(full_text):
        zemlja = "MK"  # Sve Poreklo varijante u Pekabesko fakturama su MK

    logger.info(
        f"  Footer: bruto={bruto_kg:.3f}kg, neto={neto_kg:.3f}kg, zemlja={zemlja}"
    )

    # ── 3. STAVKE: grupiši po y, čitaj kolone po x ─────────────────
    # Pronađi prvu y-poziciju stavke (prva pojava 5+ cifrenog item code-a)
    # i zadnju y-poziciju (footer počinje Paritet/Btol/Nto)
    first_data_y = None
    last_data_y = None

    for w in all_words:
        # Za detekciju prve stavke: normalizuj OCR artefakte u kodu
        clean_code = re.sub(r"[^0-9]", "", w["text"])
        if re.match(r"^\d{5,6}$", clean_code) and _in_col(w, _COL_ITEM_CODE):
            if first_data_y is None:
                first_data_y = w["top"]
        if re.match(r"paritet|btol|btoi|nto[il]|poreklo", w["text"], re.IGNORECASE):
            if last_data_y is None or w["top"] < last_data_y:
                last_data_y = w["top"]

    if first_data_y is None:
        logger.warning("  ⚠️ Nije pronađena prva stavka — provjeri PDF format")
        first_data_y = 240
    if last_data_y is None:
        last_data_y = 9999

    logger.info(f"  Stavke y-raspon: {first_data_y:.0f} – {last_data_y:.0f}")

    # Filtriraj i sortiraj sve riječi u oblasti stavki
    data_words = [
        w for w in all_words
        if first_data_y - 5 <= w["top"] < last_data_y
    ]
    data_words.sort(key=lambda w: (w["top"], w["x0"]))

    # Grupiši adaptivno: nova grupa ako je y razlika od centra grupe > 10px
    row_groups: list[list[dict]] = []
    for w in data_words:
        if not row_groups:
            row_groups.append([w])
            continue
        current = row_groups[-1]
        row_center_y = sum(x["top"] for x in current) / len(current)
        if abs(w["top"] - row_center_y) <= 10:
            current.append(w)
        else:
            row_groups.append([w])

    # Obradi svaki red
    line_no = 0
    for row_words in row_groups:
        row_words = sorted(row_words, key=lambda w: w["x0"])

        # Izvuci vrijednosti po kolonama
        item_code_words  = [w for w in row_words if _in_col(w, _COL_ITEM_CODE)]
        barcode_words    = [w for w in row_words if _in_col(w, _COL_BARCODE)]
        tariff_words     = [w for w in row_words if _in_col(w, _COL_TARIFF)]
        qty_words        = [w for w in row_words if _in_col(w, _COL_QTY)]
        neto_words       = [w for w in row_words if _in_col(w, _COL_NETO_KGR)]
        total_eur_words  = [w for w in row_words if _in_col(w, _COL_TOTAL_EUR)]

        # Item code mora biti 5 cifara (Pekabesko format)
        item_code_str = " ".join(w["text"] for w in item_code_words).strip()
        # Normalizuj OCR artefakte: "603:13" → "60313", "60/85" → "60485"
        # Važno: "/" zamijeni s "4" PRIJE brisanja ostalih artefakata
        item_code_clean = item_code_str.replace("/", "4")
        item_code_clean = re.sub(r"[:\\;]", "", item_code_clean)

        if not re.search(r"\d{5}", item_code_clean):
            continue

        # Pekabesko kodovi počinju sa "6" → prednostna pretraga
        m_code = re.search(r"(6\d{4})", item_code_clean)
        if not m_code:
            m_code = re.search(r"(\d{5,6})", item_code_clean)
        if not m_code:
            continue
        item_code = m_code.group(1)

        # Barcode
        barcode_raw = " ".join(w["text"] for w in barcode_words).strip()
        barcode = _LEADING_TRASH.sub("", barcode_raw).strip()

        # Tarifni broj
        tariff_raw = " ".join(w["text"] for w in tariff_words).strip()
        # Filtriraj jedinice mjere (qr, gr, kgr...); tariff mora imati ukupno ≥4 cifre
        # Koristimo ukupan broj cifara (ne nužno uzastopnih) jer OCR unosi artefakte
        tariff_parts = [
            t for t in tariff_raw.split()
            if len(re.findall(r"\d", t)) >= 4
        ]
        tariff = _clean_tariff(" ".join(tariff_parts)) if tariff_parts else ""

        # Količina
        qty_raw = " ".join(w["text"] for w in qty_words).strip()
        qty = _clean_number(qty_raw) or 0.0

        # Neto kg (spoji sve u koloni, uzmi ukupnu vrijednost)
        neto_raw = " ".join(w["text"] for w in neto_words).strip()
        neto_item = _parse_neto_kgr(neto_raw)

        # EUR iznos
        total_raw = " ".join(w["text"] for w in total_eur_words).strip()
        # Spoj split vrijednosti (npr. "53" + "532,066")
        total_eur = _parse_joined_value(total_raw)

        line_no += 1
        logger.debug(
            f"  Stavka {line_no}: code={item_code}, tariff={tariff}, "
            f"qty={qty:.1f}, neto={neto_item:.3f}kg, EUR={total_eur:.2f}"
        )

        line = InvoiceLine(
            line_no=line_no,
            product_code=item_code,
            naziv_robe=barcode,  # koristimo barcode kao placeholder naziv
            tarifni_broj=tariff,
            zemlja_porijekla=zemlja,
            povlastica="",
            jm="kg",
            kolicina=qty,
            cijena_jed=0.0,       # teško pouzdano iz OCR-a
            iznos=total_eur,
            valuta="EUR",
            bruto_kg=0.0,         # ukupni bruto je u ImportResult
            neto_kg=neto_item,
        )
        invoice_lines.append(line)

    logger.info(
        f"  ✅ Parsed {len(invoice_lines)} stavki, "
        f"bruto={bruto_kg:.3f}kg, neto={neto_kg:.3f}kg"
    )

    return ImportResult(
        items=invoice_lines,
        bruto_kg=bruto_kg,
        neto_kg=neto_kg,
        invoice_name=invoice_number,
        currency="EUR",
        import_type="leburic_pekabesko",
        exporter=Party(name="PEKABESKO AD"),
    )


# ──────────────────────────────────────────────────────────────────
# Pomoćne funkcije za parsiranje
# ──────────────────────────────────────────────────────────────────

def _in_col(word: dict, col: tuple[int, int]) -> bool:
    """Provjeri je li word unutar x-granica kolone."""
    x = word["x0"]
    return col[0] <= x < col[1]


def _parse_neto_kgr(raw: str) -> float:
    """
    Parsira neto težinu iz OCR teksta kolone.

    Posebni slučajevi:
    - "I504 000" → "1504.000" = 1504.000 kg (split po zarezu)
    - "I81600("  → "1816.00"  = 1816.00 kg (implicitne 2 decimale)
    - "337.600"  → 337.600 kg
    - "336,00("  → 336.00 kg
    - "544 75:"  → 544.75 kg (dvije riječi = int + decimale)
    """
    s = raw.strip()
    if not s:
        return 0.0

    # Primijeni OCR zamjene
    s = s.translate(_NUM_OCR)
    s = _LEADING_TRASH.sub("", s)
    s = _TRAILING_TRASH.sub("", s)
    if not s:
        return 0.0

    # Ako ima razmak, pokušaj spojiti kao cijeli_broj + decimale
    parts = s.split()
    if len(parts) == 2:
        # Provjeri da li drugi dio izgleda kao decimale (manje od 4 cifre)
        p1, p2 = parts[0], parts[1]
        p2_clean = re.sub(r"[^\d]", "", p2)
        if p2_clean and len(p2_clean) <= 3:
            # Spoji: npr. "544" + "75" → "544.75"
            p1_clean = re.sub(r"[^\d.,]", "", p1).replace(",", ".")
            combined = f"{p1_clean}.{p2_clean}"
            try:
                return float(combined)
            except ValueError:
                pass
        else:
            # Spoji kao jedan broj: "1504" + "000" → "1504.000"
            p1_clean = re.sub(r"[^\d]", "", p1)
            p2_clean2 = re.sub(r"[^\d]", "", p2)
            if p1_clean and p2_clean2:
                combined = f"{p1_clean}.{p2_clean2}"
                try:
                    return float(combined)
                except ValueError:
                    pass

    # Jedan token
    s = s.replace(",", ".")
    # Ako nema decimale, primijeni implicitne 2 decimale
    has_decimal = "." in s
    try:
        val = float(s)
        if not has_decimal and val > 10000:
            # Verovatno je implicitne 2 decimale: 33760 → 337.60
            val = val / 100
        return val
    except ValueError:
        return 0.0


def _parse_joined_value(raw: str) -> float:
    """
    Parsira EUR iznos koji može biti razdvojen ili bez eksplicitnih decimala.

    BiH/ex-YU format: tačka = separator hiljada, zarez = decimalni.
    OCR briše separatore pa "4.744,761" postaje "4744761".

    Pravilo za čiste integere (bez decimalnog separatora):
      - 5 cifara → ÷10    (npr. "50253" → 5025.3)
      - 6 cifara → ÷100   (npr. "319200" → 3192.00, "662476" → 6624.76)
      - 7+ cifara → ÷1000 (npr. "4744761" → 4744.761)
    """
    s = raw.strip().translate(_NUM_OCR)
    s = _LEADING_TRASH.sub("", s)
    s = _TRAILING_TRASH.sub("", s)
    if not s:
        return 0.0

    # Spoji dijelove ako je vrijednost splitovana razmakom
    # npr. "53 532,066" → p1="53", p2="532,066" → "53532.066"
    parts = s.split()
    if len(parts) == 2:
        p2 = re.sub(r"[^\d.,]", "", parts[1])
        if "," in p2 or "." in p2:
            # Drugi dio ima decimale — direktno spoji
            p1_digits = re.sub(r"[^\d]", "", parts[0])
            p2_norm = p2.replace(",", ".")
            try:
                return float(p1_digits + p2_norm)
            except ValueError:
                pass
        # Bez decimale: spoji i primijeni implicitne decimale
        joined = re.sub(r"[^\d]", "", "".join(parts))
        return _apply_implicit_decimal(joined)

    # Jedan token: normalizuj zarez i tačku
    has_comma = "," in s
    has_dot = "." in s

    if has_comma and has_dot:
        # Zadnji od ta dva je decimalni separator
        last_comma = s.rfind(",")
        last_dot = s.rfind(".")
        if last_comma > last_dot:
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
        try:
            return float(s)
        except ValueError:
            return 0.0

    if has_comma:
        # Zarez je decimalni separator: "954,40" → 954.40
        try:
            return float(s.replace(",", "."))
        except ValueError:
            pass

    if has_dot:
        try:
            return float(s)
        except ValueError:
            pass

    # Čisti integer bez decimalnog separatora — primijeni implicitne decimale
    digits_only = re.sub(r"[^\d]", "", s)
    return _apply_implicit_decimal(digits_only)


def _apply_implicit_decimal(digits: str) -> float:
    """
    Za čiste integere bez decimalnog separatora, primijeni implicitne decimale.

    BiH invoices: OCR briše separatore iz "4.744,761" → "4744761"
      5 cifara → ÷10    : "50253" → 5025.3
      6 cifara → ÷100   : "319200" → 3192.00
      7+ cifara → ÷1000 : "4744761" → 4744.761
    """
    if not digits:
        return 0.0
    try:
        val = float(digits)
    except ValueError:
        return 0.0

    n = len(digits)
    if n == 5:
        return val / 10
    elif n == 6:
        return val / 100
    elif n >= 7:
        return val / 1000
    return val
