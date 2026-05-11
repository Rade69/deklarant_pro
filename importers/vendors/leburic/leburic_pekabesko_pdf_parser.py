# importers/vendors/leburic/leburic_pekabesko_pdf_parser.py
"""
Deklarant Pro - Leburic/Pekabesko PDF Parser

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
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
from types import SimpleNamespace

from core.draft.draft import InvoiceLine, Party
from importers.import_result import ImportResult

logger = logging.getLogger("deklarant_pro.import.leburic_pekabesko_pdf")

# ──────────────────────────────────────────────────────────────────
# OCR cleanup helpers
# ──────────────────────────────────────────────────────────────────

# Znakovi koji se na početku OCR teksta pojavljuju kao artefakti
_LEADING_TRASH = re.compile(r"^[^0-9]+")
# Znakovi koji se na kraju OCR teksta pojavljuju kao artefakti
_TRAILING_TRASH = re.compile(r"[^0-9.,]+$")

# Predkompajlirani OCR fix-evi za nazive proizvoda na Leburic/Pekabesko fakturama
_PRODUCT_NAME_FIXES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(?i)\bPilecaPicasunka\b"), "Pileca Picasunka"),
    (re.compile(r"(?i)\bPilecaekstra\b"), "Pileca ekstra"),
    (re.compile(r"(?i)\bPilecavirsla\b"), "Pileca virsla"),
    (re.compile(r"(?i)\bkolbaspiknik\b"), "kolbas piknik"),
    (re.compile(r"(?i)\bslajsMAP\b"), "slajs MAP"),
    (re.compile(r"(?i)\bumrezavakum\b"), "u mreza vakum"),
    (re.compile(r"(?i)\buomotacu\b"), "u omotacu"),
    (re.compile(r"(?i)\bpremiumkobasica\b"), "premium kobasica"),
    (re.compile(r"(?i)\bDimjenapecenica\b"), "Dimljena pecenica"),
    (re.compile(r"(?i)\bDimjenaplecka\b"), "Dimljena plecka"),
    (re.compile(r"(?i)\bCajnikolbasrefus\b"), "Cajni kolbas refus"),
    (re.compile(r"(?i)\bCaen\b"), "Cajni"),
    (re.compile(r"(?i)\bGoldpilecefile\b"), "Gold pilece file"),
    (re.compile(r"(?i)\bGoldsunka\b"), "Gold sunka"),
    (re.compile(r"(?i)\bslajs100g\b"), "slajs 100 g"),
    (re.compile(r"(?i)\bkolbas295grvakum\b"), "kolbas 295 gr vakum"),
]

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
    "r": "1",              # OCR česta greška: 'r' za '1' u brojevima
    "/": "7",              # OCR česta greška: '/' za '7' (npr. '5/15' → '5715')
    "O": "0", "o": "0",
    "S": "5", "s": "5", "Z": "2",
    "t": "", "f": "", "C": "", "c": "",
    "!": "", "(": "", ")": "",
    "{": "", "}": "", "[": "", "]": "",
    ":": "", ";": "", "?": "",
    "'": "", "\u2019": "", "\u2018": "",  # OCR quote artefakti
    "-": "",               # crtice kao artefakti (ne decimalni separator)
})


def _clean_tariff(raw: str) -> str:
    """Očisti tarifni broj od OCR artefakata i ZADRŽI pune cifre."""
    s = raw.strip()
    # Ukloni leading non-digit prefixe (i, r, , . itd.)
    s = _LEADING_TRASH.sub("", s)
    # Primijeni OCR zamjene za preostale karaktere
    s = s.translate(_TARIFF_OCR)
    # Ostavi samo cifre
    s = re.sub(r"[^\d]", "", s)
    if not s:
        return ""
    # Zadrži puni broj cifara — ne siječi (precision kodovi su namjerni)
    # Ali ako je OCR očigledno spojio više brojeva (>14 cifara), skrati
    if len(s) > 14:
        s = s[:10]
    # Pad na 8/10 ako su izgubljene vodeće cifre (kratki kodovi)
    n = len(s)
    if n == 9:
        if s.startswith("6"):
            # OCR ispustio vodeću '1': '601009100' → '1601009100' (meso = poglavlje 16)
            s = "1" + s
        else:
            s = s.zfill(10)
    elif n == 7:
        s = s.zfill(8)
    elif n < 8 and n >= 4:
        # Možda su izgubljene vodeće nule — ne dodaj automatski
        pass
    return s


def _normalize_tariff_length(tariff: str) -> str:
    s = re.sub(r"[^\d]", "", tariff or "")
    if not s:
        return ""
    if len(s) == 11:
        if s.startswith("1") and s[1:3] in {"02", "16"}:
            s = s[1:]
        elif s[:2] in {"02", "16"}:
            s = s[:10]
    elif len(s) > 11:
        if "160" in s:
            i = s.find("160")
            s = s[i:i + 10]
        elif "021" in s:
            i = s.find("021")
            s = s[i:i + 10]
        else:
            s = s[:10]
    return s


def _extract_tariff_from_row(row_words: list[dict], tariff_words: list[dict], barcode_words: list[dict]) -> str:
    tariff_raw = " ".join(w["text"] for w in tariff_words).strip()
    tariff_parts = [t for t in tariff_raw.split() if len(re.findall(r"\d", t)) >= 4]
    tariff = _clean_tariff(" ".join(tariff_parts)) if tariff_parts else ""
    tariff = _normalize_tariff_length(tariff)
    if tariff:
        return tariff

    # Fallback: OCR često spoji barcode + tarifu (npr. 5310...|1601009900)
    for w in barcode_words + row_words:
        text = w.get("text", "")
        for candidate in re.findall(r"(?:\d[\d\|=]{7,14}\d)", text):
            digits = re.sub(r"[^\d]", "", candidate)
            if len(digits) < 8 or len(digits) > 13:
                continue
            if digits.startswith("5310"):  # EAN barcode prefix
                continue
            if "160" in digits:
                i = digits.find("160")
                t = _normalize_tariff_length(digits[i:i + 11])
                if len(t) >= 8:
                    return t
            if "021" in digits:
                i = digits.find("021")
                t = _normalize_tariff_length(digits[i:i + 11])
                if len(t) >= 8:
                    return t
    return ""


def _extract_item_code(item_code_str: str) -> str:
    # OCR često daje "6/160917" (redni broj + stvarna šifra artikla)
    m = re.match(r"^\s*\d+\s*/\s*(\d{5,6})", item_code_str)
    if m:
        code = m.group(1)
        if len(code) == 6 and code.startswith("1"):
            return code[1:]
        return code

    # Normalizuj OCR artefakte: "603:13" → "60313", "60/85" → "60785"
    # "/" je OCR za "7" (ne "4") u Pekabesko kodovima
    item_code_clean = item_code_str.replace("/", "7")
    item_code_clean = re.sub(r"[:\\;]", "", item_code_clean)

    # Šifra mora imati bar 5 cifara i ne smije počinjati s 0
    if not re.search(r"[1-9]\d{4}", item_code_clean):
        return ""

    # Pekabesko kodovi počinju sa "6" → prednostna pretraga
    # Na stranici 2 OCR spaja redni broj + šifru: "10160835" = red 10 + šifra 60835
    m_code = re.search(r"(6\d{4,5})", item_code_clean)
    if not m_code:
        m_code = re.search(r"([1-9]\d{4,5})", item_code_clean)
    if not m_code:
        return ""
    item_code = m_code.group(1)
    if len(item_code) > 6:
        item_code = item_code[-6:]
    return item_code


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
    # Ukloni interne razmake (OCR split broja: "1 504" → "1504")
    s = s.replace(" ", "")
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

# X-granice kolona (lijeva, desna) — podešeno da radi i za jednostraničnu i višestraničnu
# varijantu fakture (koordinate se neznatno razlikuju između PDF-ova, ~5px pomak)
# Redoslijed kolona: No | Item | Description | BarCode | Tarif | JM | Packets | Neto(kgr) | Qty in Unit | Price/Unit | Total EUR
_COL_ITEM_CODE   = (22,  205)  # prošireno na x=22 za višestranične (row_no+item_code na x24)
_COL_DESC        = (54,  202)  # naziv robe (između koda i barkoda)
_COL_BARCODE     = (200, 262)
_COL_TARIFF      = (260, 330)
_COL_PACKETS     = (332, 390)  # broj paketa (Packets) — NE koristi se za kolicina
_COL_NETO_KGR    = (382, 436)  # neto težina stavke u kgr (x387-410 u različitim fakturama)
_COL_QTY_UNIT    = (436, 492)  # količina u jedinici mjere (x436-460)
_COL_PRICE       = (490, 533)  # cijena po jedinici mjere (x492-505)
_COL_TOTAL_EUR   = (533, 598)  # ukupni iznos u EUR (x534-557)

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
        for page_no, page in enumerate(pdf.pages):
            words = page.extract_words(x_tolerance=3, y_tolerance=3)
            # Dodaj y-offset da sprijecimo preklapanje koordinata izmedju stranica
            # Stranica 2 ima iste y-koordinate kao stranica 1 (npr. y=200 na obe)
            # Offset 2000px po stranici garantuje da se opsezi ne preklapaju
            offset = page_no * 2000
            for w in words:
                w["top"] += offset
                w["bottom"] += offset
            all_words.extend(words)

    ocr_full_text = ""
    if not all_words:
        all_words = _extract_words_with_ocr(pdf_path)
        if all_words:
            ocr_full_text = _extract_pdf_text_with_ocr(pdf_path)
            logger.info("  OCR fallback aktiviran (skenirani PDF bez text layer-a)")
        else:
            ocr_full_text = _extract_pdf_text_with_ocr(pdf_path)
            if ocr_full_text:
                logger.info("  OCR text fallback aktiviran (bez koordinata)")

    # ── 1. HEADER: invoice broj, datum ──────────────────────────────
    # Skupi text iz header zone (y < _HEADER_Y_MAX)
    header_text = " ".join(
        w["text"] for w in all_words if w["top"] < _HEADER_Y_MAX
    ) if all_words else ocr_full_text

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

    # ── 1b. PARTIES: izvoznik (exporter) i uvoznik (importer) ───────
    # Koristimo cijeli tekst (sve stranice, sve stranice)
    full_text = " ".join(w["text"] for w in all_words) if all_words else ocr_full_text
    exporter, importer = _extract_parties(full_text)
    logger.info(f"  Izvoznik: {exporter.name if exporter else '—'} | "
                f"Uvoznik: {importer.name if importer else '—'}")

    origin_statements = _detect_origin_statements_robust(full_text)
    has_origin_statement = bool(origin_statements)
    is_authorized_exporter = any(
        getattr(s, "tip_izjave", "") == "ovlaseni_izvoznik" for s in origin_statements
    )
    logger.info(
        f"  Izjava o porijeklu: {'DA' if has_origin_statement else 'NE'} | "
        f"ovlasteni izvoznik: {'DA' if is_authorized_exporter else 'NE'}"
    )

    # ── 2. FOOTER: bruto, neto, zemlja ──────────────────────────────

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

    # ── 2b. EXCEL PODACI (nazivi + tarife, ako postoji u istom folderu) ──
    excel_data = _load_excel_data(pdf_path, invoice_number)

    # ── 3. STAVKE: grupiši po y, čitaj kolone po x ─────────────────
    # Pronađi prvu y-poziciju stavke (prva pojava 5+ cifrenog item code-a)
    # i zadnju y-poziciju (footer počinje Paritet/Btol/Nto)
    first_data_y = None
    last_data_y = None

    for w in all_words:
        # Za detekciju prve stavke: normalizuj OCR artefakte u kodu
        clean_code = re.sub(r"[^0-9]", "", w["text"])
        if re.match(r"^\d{5,8}$", clean_code) and _in_col(w, _COL_ITEM_CODE):
            if first_data_y is None:
                first_data_y = w["top"]
        if re.match(r"paritet|btol|btoi|nto[il]|poreklo", w["text"], re.IGNORECASE):
            if last_data_y is None or w["top"] > last_data_y:  # zadnji footer (max y)
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

    # Grupiši po y-koordinati: nova grupa ako je y razlika od PRVE riječi u grupi > 8px
    # Koristimo prvu riječ (anchor) a ne pomični prosjek — adaptive centar drifta i
    # može spojiti fragmente susjednih redova (OCR baseline razlike do ±6px unutar reda)
    row_groups: list[list[dict]] = []
    for w in data_words:
        if not row_groups:
            row_groups.append([w])
            continue
        current = row_groups[-1]
        anchor_y = current[0]["top"]  # prva y kao anchor — ne drifta
        if abs(w["top"] - anchor_y) <= 10:
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
        neto_words       = [w for w in row_words if _in_col(w, _COL_NETO_KGR)]
        packets_words    = [w for w in row_words if _in_col(w, _COL_PACKETS)]
        qty_unit_words   = [w for w in row_words if _in_col(w, _COL_QTY_UNIT)]
        price_words      = [w for w in row_words if _in_col(w, _COL_PRICE)]
        total_eur_words  = [w for w in row_words if _in_col(w, _COL_TOTAL_EUR)]

        # Item code mora biti 5 cifara (Pekabesko format)
        item_code_str = " ".join(w["text"] for w in item_code_words).strip()
        item_code = _extract_item_code(item_code_str)
        if not item_code:
            continue

        # Tarifni broj (OCR — može biti neprecizan)
        tariff = _extract_tariff_from_row(row_words, tariff_words, barcode_words)

        # Naziv robe i Excel override: Excel > PDF > prazan string
        desc_words = [w for w in row_words if _in_col(w, _COL_DESC)]
        pdf_naziv = _extract_desc_from_row(item_code_words, desc_words)
        excel_entry = excel_data.get(item_code, {})
        naziv = excel_entry.get("naziv") or pdf_naziv
        naziv = _normalize_product_name(naziv)
        # Tarifa iz Excel-a pouzdanija nego OCR (npr. "1601009100" vs "0601009100")
        if excel_entry.get("tariff"):
            tariff = excel_entry["tariff"]

        # Neto kg
        neto_raw = " ".join(w["text"] for w in neto_words).strip()
        neto_item = _parse_neto_kgr(neto_raw)

        # Količina paketa (Packets kolona)
        packets_raw = " ".join(w["text"] for w in packets_words).strip()
        packets = _parse_packets(packets_raw)

        # Količina u jedinici mjere (Qty in Unit of measure)
        qty_raw = " ".join(w["text"] for w in qty_unit_words).strip()
        qty = _parse_qty(qty_raw)
        if packets > 0.0:
            # Fallback: Qty nije čitljiv
            if qty <= 0.0:
                qty = packets
            # OCR anomalija: Qty često "pobjegne" x5-x20 naspram Pakets kolone
            elif qty >= packets * 3:
                qty = packets

        # Cijena po jedinici mjere
        price_raw = " ".join(w["text"] for w in price_words).strip()
        cijena = _parse_price(price_raw)

        # EUR iznos
        total_raw = " ".join(w["text"] for w in total_eur_words).strip()
        total_eur = _parse_joined_value(total_raw)

        # Preskoči potpuno prazne redove — OCR artefakti iz footer zone
        if not tariff and qty == 0.0 and neto_item == 0.0 and total_eur == 0.0:
            logger.debug(f"  Skip prazni red: code={item_code} (sve 0, bez tarife)")
            continue

        line_no += 1
        logger.debug(
            f"  Stavka {line_no}: code={item_code}, tariff={tariff}, "
            f"qty={qty:.3f}, packets={packets:.3f}, cijena={cijena:.3f}, neto={neto_item:.3f}kg, EUR={total_eur:.3f}"
        )

        line = InvoiceLine(
            line_no=line_no,
            product_code=item_code,
            naziv_robe=naziv,
            tarifni_broj=tariff,
            zemlja_porijekla=zemlja,
            povlastica="",
            jm="kg",
            kolicina=qty,
            cijena_jed=cijena,
            iznos=total_eur,
            valuta="EUR",
            bruto_kg=0.0,         # ukupni bruto je u ImportResult
            neto_kg=neto_item,
            has_origin_statement=has_origin_statement,
            is_authorized_exporter=is_authorized_exporter,
        )
        if exporter:
            line.exporter = exporter
        if importer:
            line.importer = importer
        invoice_lines.append(line)

    logger.info(
        f"  ✅ Parsed {len(invoice_lines)} stavki, "
        f"bruto={bruto_kg:.3f}kg, neto={neto_kg:.3f}kg"
    )

    text_for_line_fallback = ocr_full_text or full_text
    if len(invoice_lines) < 8 and text_for_line_fallback:
        text_fallback_lines = _parse_items_from_ocr_text_fallback(
            full_text=text_for_line_fallback,
            zemlja=zemlja,
            has_origin_statement=has_origin_statement,
            is_authorized_exporter=is_authorized_exporter,
            exporter=exporter,
            importer=importer,
        )
        current_sum = sum(getattr(it, "iznos", 0.0) for it in invoice_lines)
        fallback_sum = sum(getattr(it, "iznos", 0.0) for it in text_fallback_lines)
        should_take_fallback = (
            len(text_fallback_lines) > len(invoice_lines)
            or (
                len(text_fallback_lines) == len(invoice_lines)
                and fallback_sum > (current_sum * 1.2)
            )
            or (
                len(text_fallback_lines) >= max(3, int(len(invoice_lines) * 0.6))
                and fallback_sum > (current_sum * 2.0)
            )
        )
        if should_take_fallback:
            logger.info(
                "  OCR text fallback: "
                f"{len(invoice_lines)} -> {len(text_fallback_lines)} stavki, "
                f"sum {current_sum:.3f} -> {fallback_sum:.3f}"
            )
            invoice_lines = text_fallback_lines

    if len(invoice_lines) < 8:
        excel_lines = _load_excel_lines_for_pdf(
            pdf_path=pdf_path,
            pdf_invoice_number=invoice_number,
            zemlja=zemlja,
            has_origin_statement=has_origin_statement,
            is_authorized_exporter=is_authorized_exporter,
            exporter=exporter,
            importer=importer,
        )
        if len(excel_lines) > len(invoice_lines):
            logger.info(
                f"  Excel fallback: {len(invoice_lines)} -> {len(excel_lines)} stavki"
            )
            invoice_lines = excel_lines

    return ImportResult(
        items=invoice_lines,
        bruto_kg=bruto_kg,
        neto_kg=neto_kg,
        invoice_name=invoice_number,
        currency="EUR",
        import_type="leburic_pekabesko",
        has_origin_statement=has_origin_statement,
        is_authorized_exporter=is_authorized_exporter,
        origin_statements=origin_statements,
        exporter=exporter,
        importer=importer,
    )


def _extract_words_with_ocr(pdf_path: str) -> list[dict]:
    images_prefix = None
    try:
        with tempfile.NamedTemporaryFile(prefix="deklarant_ocr_", suffix=".png", delete=False) as tmp:
            images_prefix = str(Path(tmp.name).with_suffix(""))
        Path(images_prefix + ".png").unlink(missing_ok=True)

        subprocess.run(
            ["pdftoppm", "-r", "300", "-f", "1", "-singlefile", "-png", pdf_path, images_prefix],
            check=True,
            capture_output=True,
            text=True,
        )
        tsv = subprocess.check_output(
            ["tesseract", images_prefix + ".png", "stdout", "-l", "eng", "--psm", "11", "tsv"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        rows = tsv.splitlines()[1:]
        page_w = 0.0
        page_h = 0.0
        for line in rows:
            parts = line.split("\t")
            if len(parts) < 12:
                continue
            if parts[0] == "1":
                try:
                    page_w = float(parts[8])
                    page_h = float(parts[9])
                except ValueError:
                    pass
                break
        scale_x = (595.0 / page_w) if page_w > 0 else 1.0
        scale_y = (842.0 / page_h) if page_h > 0 else 1.0

        words: list[dict] = []
        for line in rows:
            parts = line.split("\t")
            if len(parts) < 12:
                continue
            text = parts[11].strip()
            if not text:
                continue
            try:
                left = float(parts[6])
                top = float(parts[7])
                width = float(parts[8])
                height = float(parts[9])
                conf = float(parts[10])
            except ValueError:
                continue
            if conf < 0:
                continue
            words.append({
                "text": text,
                "x0": left * scale_x,
                "top": top * scale_y,
                "bottom": (top + height) * scale_y,
            })
        return words
    except Exception:
        logger.debug("  OCR words fallback nije uspio", exc_info=True)
        return []
    finally:
        if images_prefix:
            Path(images_prefix + ".png").unlink(missing_ok=True)


def _extract_pdf_text_with_ocr(pdf_path: str) -> str:
    images_prefix = None
    try:
        with tempfile.NamedTemporaryFile(prefix="deklarant_ocr_", suffix=".png", delete=False) as tmp:
            images_prefix = str(Path(tmp.name).with_suffix(""))
        Path(images_prefix + ".png").unlink(missing_ok=True)

        subprocess.run(
            ["pdftoppm", "-f", "1", "-singlefile", "-png", pdf_path, images_prefix],
            check=True,
            capture_output=True,
            text=True,
        )
        text = subprocess.check_output(
            ["tesseract", images_prefix + ".png", "stdout", "-l", "eng", "--psm", "11"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return text or ""
    except Exception:
        logger.debug("  OCR fallback nije uspio", exc_info=True)
        return ""
    finally:
        if images_prefix:
            Path(images_prefix + ".png").unlink(missing_ok=True)


def _parse_items_from_ocr_text_fallback(
    full_text: str,
    zemlja: str,
    has_origin_statement: bool,
    is_authorized_exporter: bool,
    exporter: Optional[Party],
    importer: Optional[Party],
) -> list[InvoiceLine]:
    lines = [ln.strip() for ln in full_text.splitlines() if ln.strip()]
    start_idxs: list[int] = []
    row_start = re.compile(r"^\s*\d{1,2}\s*[/|]?\s*\d{5,6}\b|^\s*\d{7,8}\b")
    for i, ln in enumerate(lines):
        if row_start.search(ln):
            start_idxs.append(i)

    invoice_lines: list[InvoiceLine] = []
    for pos, start in enumerate(start_idxs):
        end = start_idxs[pos + 1] if pos + 1 < len(start_idxs) else len(lines)
        chunk = " ".join(lines[start:end])
        if re.search(r"\bVkupno\b|\bParitet\b", chunk, re.IGNORECASE):
            continue

        m2 = re.match(r"^\s*(\d{7,8})\b", chunk)
        if m2:
            raw = m2.group(1)
            line_no = int(raw[0])
            product_code = raw[1:] if len(raw) >= 7 else raw
            after_code = chunk[m2.end():].strip()
        else:
            m = re.match(r"^\s*(\d{1,2})\s*[/|]\s*(\d{5,6})\b", chunk)
            if not m:
                continue
            line_no = int(m.group(1))
            product_code = m.group(2)
            after_code = chunk[m.end():].strip()

        tariff_match = re.search(r"\b(1\d{9})\b", after_code)
        tariff = tariff_match.group(1) if tariff_match else ""
        naziv = after_code
        if tariff_match:
            naziv = after_code[:tariff_match.start()].strip(" |-")
        naziv = _normalize_product_name(naziv)

        values = re.findall(r"\d[\d\s]*,\d{2,3}", chunk)
        parsed_values = [_parse_joined_value(v) for v in values]
        parsed_values = [v for v in parsed_values if v > 0]
        if not parsed_values:
            continue

        iznos = parsed_values[-1]
        kolicina = parsed_values[2] if len(parsed_values) >= 3 else parsed_values[0]
        if kolicina <= 0:
            continue
        cijena_jed = (iznos / kolicina) if kolicina else 0.0

        line = InvoiceLine(
            line_no=line_no if line_no > 0 else len(invoice_lines) + 1,
            product_code=product_code,
            naziv_robe=naziv,
            tarifni_broj=tariff,
            zemlja_porijekla=zemlja,
            povlastica="",
            jm="kg",
            kolicina=kolicina,
            cijena_jed=cijena_jed,
            iznos=iznos,
            valuta="EUR",
            bruto_kg=0.0,
            neto_kg=0.0,
            has_origin_statement=has_origin_statement,
            is_authorized_exporter=is_authorized_exporter,
        )
        if exporter:
            line.exporter = exporter
        if importer:
            line.importer = importer
        invoice_lines.append(line)

    deduped: list[InvoiceLine] = []
    seen_codes: set[str] = set()
    for line in sorted(invoice_lines, key=lambda it: it.line_no):
        if line.product_code in seen_codes:
            continue
        seen_codes.add(line.product_code)
        deduped.append(line)
    return deduped


# ──────────────────────────────────────────────────────────────────
# Ekstrakcija izvoznika i uvoznika iz OCR teksta
# ──────────────────────────────────────────────────────────────────

def _extract_parties(full_text: str) -> tuple[Optional[Party], Optional[Party]]:
    """
    Izvlači izvoznika (exporter, Rb.2) i uvoznika (importer, Rb.8) iz OCR teksta.

    Strategija:
    - Izvoznik: www.COMPANY.com.mk domain je čitljiv čak i kad je ime firme OCR šum
    - Uvoznik: 'LEBURIC KOMERC' se pojavljuje direktno kao tekst kupca
    """
    exporter = None
    importer = None

    # Izvoznik: iz www domaina (www.pekabesko.com.mk → PEKABESKO)
    m = re.search(r'www\.([a-zA-Z]{4,})\.[a-zA-Z]', full_text, re.IGNORECASE)
    if m:
        domain_name = m.group(1).upper()
        exporter = Party(name=domain_name)
        logger.debug(f"  Izvoznik iz domaina: {domain_name}")
    else:
        # Fallback: hardcoded za Pekabesko fakturu
        exporter = Party(name="PEKABESKO AD")
        logger.debug("  Izvoznik: fallback PEKABESKO AD")

    # Uvoznik: LEBURIC KOMERC d.o.o — jasno čitljiv u OCR
    m = re.search(r'(LEBURIC\s+KOMERC(?:\s+d\.o\.o)?)', full_text, re.IGNORECASE)
    if m:
        imp_name = re.sub(r'\s+', ' ', m.group(1)).strip().upper()
        importer = Party(name=imp_name)
        logger.debug(f"  Uvoznik iz teksta: {imp_name}")
    else:
        importer = Party(name="LEBURIC KOMERC D.O.O.")
        logger.debug("  Uvoznik: fallback LEBURIC KOMERC D.O.O.")

    return exporter, importer


def _detect_origin_statements_robust(full_text: str) -> list:
    try:
        from services.tariff.origin_statement_detector import OriginStatementDetector
        detector = OriginStatementDetector()

        matches = detector.detect_all_in_text(full_text)
        if matches:
            return matches

        replacements = {
            "Theexporter": "The exporter",
            "ofthe": "of the",
            "bythis": "by this",
            "customsauthorization": "customs authorization",
            "exceptwhere": "except where",
            "indicated,these": "indicated, these",
            "Macedonianpreferential": "Macedonian preferential",
            "appliedwithEU": "applied with EU",
        }
        normalized = full_text
        for src, dst in replacements.items():
            normalized = normalized.replace(src, dst)

        matches = detector.detect_all_in_text(normalized)
        if matches:
            return matches
    except Exception:
        pass

    # Fallback regex tolerantan na OCR bez razmaka: "Theexporter ... customsauthorization No. MK/153/2020 ... preferential origin"
    compact = re.sub(r"\s+", "", full_text)
    m = re.search(
        r"theexporteroftheproductscoveredbythisdocument"
        r"\(customsauthorizationno[\.,:]?(?P<broj>[A-Z0-9/\-]+)\)"
        r"declaresthat,?exceptwhereotherwiseclearlyindicated,?"
        r"theseproductsareof(?P<origin>[A-Za-z]+)preferentialorigin",
        compact,
        re.IGNORECASE,
    )
    if m:
        return [
            SimpleNamespace(
                jezik="english",
                tip_izjave="ovlaseni_izvoznik",
                origin_country=m.group("origin").upper(),
                authorization_number=m.group("broj"),
                full_text="",
                confidence=0.8,
                text_position=0,
                item_range=None,
            )
        ]
    return []


# ──────────────────────────────────────────────────────────────────
# Pomoćne funkcije za parsiranje
# ──────────────────────────────────────────────────────────────────

def _in_col(word: dict, col: tuple[int, int]) -> bool:
    """Provjeri je li word unutar x-granica kolone."""
    x = word["x0"]
    return col[0] <= x < col[1]


def _extract_desc(desc_words: list[dict]) -> str:
    """
    Pokušaj izvući naziv robe iz zone opisa (x=54-202).

    Filtrira OCR artefakte — prihvata samo riječi s bar 2 slova.
    Ako nema ništa čitljivo, vrać prazan string.
    """
    words = []
    for w in desc_words:
        tok = re.sub(r"^[^\wšđčćžŠĐČĆŽäöüÄÖÜ]+|[^\wšđčćžŠĐČĆŽäöüÄÖÜ]+$", "", w["text"])
        if len(re.sub(r"[^a-zA-ZšđčćžŠĐČĆŽäöüÄÖÜ]", "", tok)) >= 2:
            words.append(tok)
    return " ".join(words).strip()


def _extract_desc_from_row(item_code_words: list[dict], desc_words: list[dict]) -> str:
    base_desc = _extract_desc(desc_words)
    extra_desc = ""

    item_text = " ".join(w["text"] for w in item_code_words).strip()
    if item_text:
        stripped = re.sub(r"^\s*\d+\s*/\s*\d{5,6}[.\-_:|]*", "", item_text)
        stripped = re.sub(r"^\s*\d+\|\s*\d{5,6}[.\-_:|]*", "", stripped)
        stripped = re.sub(r"^\s*\d+\s+\d{5,6}[.\-_:|]*", "", stripped)
        stripped = re.sub(r"^\s*\d{6,8}[.\-_:|]*", "", stripped)
        stripped = re.sub(r"^\s*\d+[.\-_:|]+", "", stripped)
        stripped = stripped.strip()
        if stripped:
            clean = re.sub(r"[|=]+", " ", stripped)
            clean = re.sub(r"\s+", " ", clean).strip()
            if clean:
                extra_desc = clean

    # Ako već imamo solidan naziv iz desc kolone, item tail koristi samo kao dopunu
    if base_desc and extra_desc:
        base_l = base_desc.lower()
        extra_l = extra_desc.lower()
        if extra_l in base_l:
            merged_text = base_desc
        elif base_l in extra_l and len(extra_desc) >= len(base_desc):
            merged_text = extra_desc
        else:
            merged_text = f"{extra_desc} {base_desc}"
    else:
        merged_text = base_desc or extra_desc

    desc_tokens = merged_text.split()
    seen: set[str] = set()
    merged: list[str] = []
    for tok in desc_tokens:
        tok = re.sub(r"^[^\wšđčćžŠĐČĆŽäöüÄÖÜ]+|[^\wšđčćžŠĐČĆŽäöüÄÖÜ]+$", "", tok)
        if not tok:
            continue
        key = tok.lower()
        if key in seen:
            continue
        seen.add(key)
        merged.append(tok)
    return " ".join(merged).strip()


def _normalize_product_name(name: str) -> str:
    if not name:
        return ""
    s = re.sub(r"[|=]+", " ", name)
    s = re.sub(r"\s+", " ", s).strip()

    for pattern, repl in _PRODUCT_NAME_FIXES:
        s = pattern.sub(repl, s)

    # Generic cleanup: spojevi slova+brojeva+jedinica
    s = re.sub(r"(?i)([A-Za-zšđčćžŠĐČĆŽ])(\d{2,4}gr)\b", r"\1 \2", s)
    s = re.sub(r"(?i)\b(\d{2,4})(gr|kg|g)\b", r"\1 \2", s)
    s = re.sub(r"(?i)\b(vak)(\d{2,4}g)\b", r"\1.\2", s)

    # OCR dupli prefiks na pocetku (npr. PPileci -> Pileci)
    s = re.sub(r"(?i)^PPile", "Pile", s)

    # Ukloni vodece artefakte
    s = re.sub(r"^[^A-Za-z0-9šđčćžŠĐČĆŽ]+", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _load_excel_data(pdf_path: str, pdf_invoice_number: str = "") -> dict[str, dict]:
    """
    Pokušaj pronaći Excel fajl u istom folderu i učitaj nazive + tarife po product_code.

    Vraća dict {product_code: {"naziv": ..., "tariff": ...}}.
    Ključ je i 6-cifreni (originalni) i 5-cifreni (bez prefixnog "1").

    Matching logika:
    - Ako je poznat PDF invoice broj (npr. "0504-3-20-00015"), traži Excel čiji stem
      se nalazi u tom broju (npr. "20-00015" IN "0504-3-20-00015" → True)
    - Ako PDF invoice nije poznat, provjeri da li Excel invoice ćelija sadrži xlsx stem
    """
    try:
        import openpyxl
        folder = Path(pdf_path).parent
        pdf_inv_norm = pdf_invoice_number.lower().replace(" ", "")

        # Sortiraj po dužini stem-a — duži match ima prednost
        all_xlsx = sorted(folder.glob("*.xlsx"), key=lambda p: len(p.stem), reverse=True)

        for xlsx in all_xlsx:
            try:
                xlsx_stem = xlsx.stem.lower()
                wb = openpyxl.load_workbook(xlsx, data_only=True, read_only=True)
                ws = wb.worksheets[0]
                header = {
                    str(ws.cell(1, c).value or "").strip().lower(): c
                    for c in range(1, ws.max_column + 1)
                    if ws.cell(1, c).value
                }
                col_item   = header.get("item", 0)
                col_desc   = header.get("description", 0)
                col_tariff = header.get("customid", 0)
                if not col_item or not col_desc:
                    wb.close()
                    continue

                # Čitaj podatke i provjeri match
                data: dict[str, dict] = {}
                invoice_match = False
                for row in range(2, ws.max_row + 1):
                    inv_cell = str(ws.cell(row, 1).value or "").strip().lower().replace(" ", "")
                    code = str(ws.cell(row, col_item).value or "").strip()
                    desc = str(ws.cell(row, col_desc).value or "").strip()
                    desc = re.sub(r"_x000D_|\n|\r", " ", desc).strip()
                    tariff_raw = str(ws.cell(row, col_tariff).value or "").strip() if col_tariff else ""
                    tariff_clean = re.sub(r"[.\s]", "", tariff_raw)
                    # Excel float-repr: '1602411000.0' → '16024110000' (11 cifara) → skrati na 10
                    # NE uklanjati nule iz 10-cifrenih kodova (1602411000 je validan!)
                    if len(tariff_clean) == 11 and tariff_clean[-1] == "0":
                        tariff_clean = tariff_clean[:10]

                    if not invoice_match and xlsx_stem:
                        if pdf_inv_norm and xlsx_stem in pdf_inv_norm:
                            # PDF invoice broj sadrži xlsx stem (npr. "20-00015" u "0504-3-20-00015")
                            invoice_match = True
                        elif not pdf_inv_norm and inv_cell and xlsx_stem in inv_cell:
                            # Fallback SAMO kada PDF invoice broj nije poznat:
                            # Excel invoice ćelija sadrži xlsx stem
                            invoice_match = True

                    if code and desc:
                        entry = {"naziv": desc, "tariff": tariff_clean}
                        data[code] = entry
                        if len(code) == 6 and code[0] == "1":
                            data[code[1:]] = entry
                wb.close()

                # Koristi ovaj Excel ako postoji match ili ako je jedini u folderu
                if data and (invoice_match or len(all_xlsx) == 1):
                    logger.info(f"  📋 Excel podaci: {xlsx.name} ({len(data)//2} stavki, match={invoice_match})")
                    return data
            except Exception as _xe:
                logger.debug("Preskočen xlsx %s: %s", xlsx.name, _xe)
                continue
    except Exception as e:
        logger.debug(f"Greška pri učitavanju Excel-a: {e}")
    return {}


def _load_excel_lines_for_pdf(
    pdf_path: str,
    pdf_invoice_number: str,
    zemlja: str,
    has_origin_statement: bool,
    is_authorized_exporter: bool,
    exporter: Optional[Party],
    importer: Optional[Party],
) -> list[InvoiceLine]:
    try:
        import openpyxl

        folder = Path(pdf_path).parent
        pdf_inv_norm = (pdf_invoice_number or "").lower().replace(" ", "")
        all_xlsx = sorted(folder.glob("*.xlsx"), key=lambda p: len(p.stem), reverse=True)

        for xlsx in all_xlsx:
            try:
                xlsx_stem = xlsx.stem.lower()
                wb = openpyxl.load_workbook(xlsx, data_only=True, read_only=True)
                ws = wb.worksheets[0]
                header = {
                    str(ws.cell(1, c).value or "").strip().lower(): c
                    for c in range(1, ws.max_column + 1)
                    if ws.cell(1, c).value
                }

                def col(name: str, *aliases: str) -> int:
                    for n in (name, *aliases):
                        if n.lower() in header:
                            return header[n.lower()]
                    return 0

                col_invoice = col("invoice")
                col_item = col("item")
                col_desc = col("description")
                col_unit = col("unit")
                col_custom = col("customid")
                col_neto = col("neto(kgr)")
                col_qty = col("quantity in unit")
                col_price = col("price per unit")
                col_total = col("total in eur")
                if not col_item or not col_desc:
                    wb.close()
                    continue

                lines: list[InvoiceLine] = []
                invoice_match = False
                for row in range(2, ws.max_row + 1):
                    inv_cell = str(ws.cell(row, col_invoice).value or "").strip().lower().replace(" ", "") if col_invoice else ""
                    if not invoice_match and xlsx_stem:
                        if pdf_inv_norm and xlsx_stem in pdf_inv_norm:
                            invoice_match = True
                        elif not pdf_inv_norm and inv_cell and xlsx_stem in inv_cell:
                            invoice_match = True

                    item_val = ws.cell(row, col_item).value
                    if not item_val:
                        continue

                    product_code = str(item_val).strip()
                    naziv = str(ws.cell(row, col_desc).value or "").strip().replace("_x000D_", "").strip()
                    tarifni = _read_tariff_code(ws.cell(row, col_custom).value if col_custom else None)
                    jm = _normalize_jm(str(ws.cell(row, col_unit).value or "").strip()) if col_unit else "kg"
                    neto_item = _parse_number(ws.cell(row, col_neto).value) if col_neto else 0.0
                    qty = _parse_number(ws.cell(row, col_qty).value) if col_qty else 0.0
                    cijena = _parse_number(ws.cell(row, col_price).value) if col_price else 0.0
                    iznos = _parse_number(ws.cell(row, col_total).value) if col_total else 0.0

                    line = InvoiceLine(
                        line_no=len(lines) + 1,
                        product_code=product_code,
                        naziv_robe=naziv,
                        tarifni_broj=tarifni,
                        zemlja_porijekla=zemlja,
                        povlastica="",
                        jm=jm,
                        kolicina=qty,
                        cijena_jed=cijena,
                        iznos=iznos,
                        valuta="EUR",
                        bruto_kg=0.0,
                        neto_kg=neto_item,
                        has_origin_statement=has_origin_statement,
                        is_authorized_exporter=is_authorized_exporter,
                    )
                    if exporter:
                        line.exporter = exporter
                    if importer:
                        line.importer = importer
                    lines.append(line)

                wb.close()

                if lines and invoice_match:
                    logger.info(f"  📋 Excel fallback source: {xlsx.name} ({len(lines)} stavki)")
                    return lines
            except Exception as _xe:
                logger.debug("Preskočen xlsx fallback %s: %s", xlsx.name, _xe)
                continue
    except Exception:
        logger.debug("Greška pri učitavanju Excel fallback stavki", exc_info=True)
    return []


def _parse_qty(raw: str) -> float:
    """
    Parsira količinu u JM iz OCR-a.

    Pekabesko qty vrijednosti: 336.00, 1504.00, 3376.00, 544.75, itd.
    OCR problemi:
      - '33760(' → '33760' (5 cifara bez decimalnog zareza) → ÷10 = 3376.0
      - '3360C'  → '3360'  (4 cifre, OCR gubi zarez iz '336,00') → ÷10 = 336.0
      - '544 7'  → split → '544.7' (drugi dio = decimale)
      - '3s8400' → '358400' (6 cifara) → ÷100 = 3584.0
    """
    s = raw.strip()
    if not s:
        return 0.0

    s_tr = s.translate(_NUM_OCR)
    s_clean = _LEADING_TRASH.sub("", s_tr)
    s_clean = _TRAILING_TRASH.sub("", s_clean)
    if not s_clean:
        return 0.0

    # Slučaj: dva tokena razdvojena razmakom (OCR razbio broj na dva dijela)
    parts = s_clean.split()
    if len(parts) == 2:
        p1, p2 = parts[0], parts[1]
        p2_digits = re.sub(r"[^\d]", "", p2)
        if p2_digits and len(p2_digits) <= 3 and "." not in p1 and "," not in p1:
            # Kraći drugi dio = decimale: "544 75" → "544.75"
            p1_norm = re.sub(r"[^\d.,]", "", p1).replace(",", ".")
            try:
                return float(f"{p1_norm}.{p2_digits}")
            except ValueError:
                pass
        else:
            # Duži drugi dio: spoji kao jedan broj i primijeni implicitne decimale
            joined = re.sub(r"[^\d]", "", "".join(parts))
            if joined:
                return _apply_qty_decimal(joined)

    # Jedan token: ima li decimalni separator?
    s_single = s_clean.replace(",", ".")
    if "." in s_single:
        try:
            return float(s_single)
        except ValueError:
            pass

    digits = re.sub(r"[^\d]", "", s_clean)
    return _apply_qty_decimal(digits)


def _parse_packets(raw: str) -> float:
    s = raw.strip()
    if not s:
        return 0.0
    s = s.translate(_NUM_OCR)
    s = _LEADING_TRASH.sub("", s)
    s = _TRAILING_TRASH.sub("", s)
    if not s:
        return 0.0
    s = s.replace(",", ".")
    m = re.search(r"\d+(?:\.\d+)?", s)
    if not m:
        return 0.0
    try:
        return float(m.group(0))
    except ValueError:
        return 0.0


def _apply_qty_decimal(digits: str) -> float:
    """
    Implicitne decimale za qty kolonu (Pekabesko fakture uvijek imaju 2 decimale).
    OCR briše zarez pa '3376,00' → '337600' ili '33760'.
    Pravilo: uvijek ÷10 za 4-5 cifara, ÷100 za 6 cifara.
    """
    if not digits:
        return 0.0
    try:
        val = float(digits)
    except ValueError:
        return 0.0
    n = len(digits)
    if n <= 5:
        return val / 10   # '3360' → 336.0,  '33760' → 3376.0
    if n == 6:
        return val / 100  # '358400' → 3584.0
    return val / 1000


def _parse_price(raw: str) -> float:
    """
    Parsira cijenu po jedinici mjere iz OCR-a.

    Pekabesko cijene imaju uvijek 3 decimale: 3,800 / 6,453 / 0,970
    OCR problemi:
      - '2,841'  → direktno ✓
      - '3 80('  → split na zarezu → digits '380' (3 cifre) → ÷100 = 3.80
      - '6453'   → 4 cifre → ÷1000 = 6.453
      - '0,97('  → zarez → '0.97' ✓
    """
    s = raw.strip().translate(_NUM_OCR).replace(" ", "")
    s = _LEADING_TRASH.sub("", s)
    s = _TRAILING_TRASH.sub("", s)
    if not s:
        return 0.0

    # Ima li decimalni separator?
    if "," in s or "." in s:
        try:
            return float(s.replace(",", "."))
        except ValueError:
            pass

    # Integer bez separatora — OCR je izbrisao zarez
    digits = re.sub(r"[^\d]", "", s)
    if not digits:
        return 0.0
    n = len(digits)
    val = float(digits)
    if n == 2: return val / 10    # '38' → 3.8 (rijedak slučaj)
    if n == 3: return val / 100   # '380' → 3.80
    if n == 4: return val / 1000  # '6453' → 6.453
    if n == 5: return val / 1000  # '03648' → 3.648
    return val


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
    s = s.replace(" ", "")  # OCR razdvoji znakove: '7 3 8 , 2 6 0' → '738,260'
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
