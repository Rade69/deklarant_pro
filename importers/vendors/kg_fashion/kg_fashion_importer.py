# importers/vendors/kg_fashion/kg_fashion_importer.py
"""
"K... G... Fashion" D.O.O. Cacak - Parser za PDF fakture.

Sve fakture imaju identican format tabele bez obzira na brend:
  Rb. | Sifra artikla | Naziv | Boja | Tip | Kom-Par | Pol | Sastav | HS | Kol | Cijena | Vrednost C/O

Podrzani brendovi: Petite Jolie, Vizzano, Benetton, Sisley, Ambitious,
                   Kese (Ciklopak), Bueno, Mod 21016, Jagger i dr.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pdfplumber
import xlrd

from core.draft.draft import InvoiceLine, Party
from importers.import_result import ImportResult
from importers.invoice_line_utils import parse_eu_number, normalize_tariff_number

logger = logging.getLogger("deklarant_pro.import.kg_fashion")

_EXPORTER = Party(name='"K... G... FASHION" D.O.O.', address="Bulevar Oslobodjenja 41", city="Cacak", country="RS")
_IMPORTER = Party(name='"PRET A PORTER" D.O.O.', city="Banja Luka", country="BA")

# ---------------------------------------------------------------------------
# Regex paterni
# ---------------------------------------------------------------------------

# Zaglavlje tabele - linija koja sadrzi "Rb." i "Sifra" (ili samo "Rb.")
_TABLE_HEADER_RE = re.compile(r'\bRb\..*(?:ifra|Sifra)', re.IGNORECASE)

_INVOICE_NO_RE = re.compile(
    r'RA[CČ]UN\s+BR\.?/INVOICE\s+No\.?:\s*([A-Z0-9][A-Z0-9\-/\.]{2,})',
    re.IGNORECASE
)
_DATE_RE = re.compile(r'(\d{1,2}\.\d{1,2}\.\d{4})')
_BRAND_RE = re.compile(r'Brend:\s*(.+?)(?:\s*$)', re.IGNORECASE | re.MULTILINE)
_TOTAL_RE = re.compile(r'TOTAL\s*\(([A-Z]{3})\)\s*[:\s]+\s*([\d\.,]+)', re.IGNORECASE)

# "sB:ruto" je PDF artefakt za "Bruto" — trazimo "ruto" kao pouzdaniji anchor
_BRUTO_RE = re.compile(r'ruto[:\s]+([\d\.,]+)\s*Kg', re.IGNORECASE)
_NETO_RE = re.compile(r'[Nn]eto[:\s]+([\d\.,]+)\s*Kg', re.IGNORECASE)
_INCOTERM_RE = re.compile(r'paritetu:\s*([A-Z]{2,5})', re.IGNORECASE)

# Tail pattern: <middle> qty price CUR amount CUR
# Greedy match za middle osigurava da qty/price/CUR/amount/CUR budu POSLJEDNJI u liniji.
_TAIL_RE = re.compile(
    r'^(.*)\s+([\d]+[\d\.]*)\s+([\d\.,]+)\s+(EUR|USD|BAM)\s+([\d\.,]+)\s+(EUR|USD|BAM)\s*$',
    re.IGNORECASE
)

# HS kod: 6-12 cifara (ciste, bez slova)
_HS_RE = re.compile(r'^\d{6,12}$')

# C/O: tacno 2 velika latinicna slova
_CO_2LETTER_RE = re.compile(r'^[A-Z]{2}$')

# Stop uslovi (kraj sekcije sa stavkama)
_STOP_RE = re.compile(
    r'^(TOTAL\s*\('
    r'|MODNA GALANTERIJA'
    r'|OBUĆ[AC]'
    r'|Napomena o poreskom'
    r'|NAPOMENA:'
    r'|Ova faktura'
    r'|Robu primio'
    r'|Fakturisao'
    r'|Roba po rezervacijama)',
    re.IGNORECASE
)

# Linije koje treba preskociti unutar tabele (ponavljajuci header po stranicama)
_SKIP_IN_TABLE_RE = re.compile(
    r'^("K\.\.\.|Tel:|Ul\.|PIB:|RA[CČ]UN BR\./INV|Delivery address'
    r'|Mesto i datum|Datum prometa|Brend:|Page:|'
    r'Item\s+Style\s+no|Pcs-Pair|C/O\s*$)',
    re.IGNORECASE
)

# Poznate nazive zemalja → ISO kod (za C/O koji nije 2-slovni kod)
_COUNTRY_MAP: Dict[str, str] = {
    "srbija": "RS",
    "kina": "CN",
    "turska": "TR",
    "italija": "IT",
    "njemacka": "DE",
    "nemacka": "DE",
    "francuska": "FR",
    "spanija": "ES",
    "brasil": "BR",
    "brazil": "BR",
    "portugal": "PT",
    "vijetnam": "VN",
    "indija": "IN",
    "banglades": "BD",
    "indonezija": "ID",
    "bosna": "BA",
    "hrvatska": "HR",
    "slovenija": "SI",
    "koreja": "KR",
    "japan": "JP",
    "usa": "US",
    "sad": "US",
}


# ---------------------------------------------------------------------------
# Interni model stavke
# ---------------------------------------------------------------------------

@dataclass
class KGLine:
    rbr: int
    code: str
    naziv: str
    unit: str
    qty: float
    price: float
    amount: float
    currency: str
    tarifni_broj: str = ""
    co: str = ""


# ---------------------------------------------------------------------------
# Pomocne funkcije
# ---------------------------------------------------------------------------

def _detect_co(token: str) -> str:
    """Detekcija C/O iz jednog tokena. Vraca ISO kod ili ''."""
    if not token:
        return ""
    # Tacno 2 velika slova → vjerovatno ISO kod drzave
    if _CO_2LETTER_RE.match(token):
        return token
    # Poznata puna imena zemalja (bez dijakritika)
    normalized = (
        token.lower()
        .replace("š", "s").replace("đ", "dj").replace("č", "c")
        .replace("ć", "c").replace("ž", "z")
    )
    return _COUNTRY_MAP.get(normalized, "")


def _parse_item_line(s: str) -> Optional[KGLine]:
    """
    Parsira jednu stavku fakture iz teksta linije.

    Format (desno):  qty price CUR amount CUR
    Format (lijevo): Rb# code naziv boja tip KOM/PAR pol sastav HS C/O
    """
    m = _TAIL_RE.match(s)
    if not m:
        return None

    middle = m.group(1).strip()
    qty = parse_eu_number(m.group(2))
    price = parse_eu_number(m.group(3))
    cur = m.group(4).upper()
    amount = parse_eu_number(m.group(5))

    # Rb# na pocetku
    rb_m = re.match(r'^(\d+)\s+(.*)', middle)
    if not rb_m:
        return None
    rbr = int(rb_m.group(1))
    rest = rb_m.group(2).strip()
    tokens = rest.split()
    if not tokens:
        return None

    # --- Parsiranje od desna ---

    # 1. C/O (zadnji token)
    co = _detect_co(tokens[-1])
    if co:
        tokens = tokens[:-1]

    # 2. HS kod (zadnji token nakon uklanjanja C/O)
    hs = ""
    if tokens and _HS_RE.match(tokens[-1]):
        hs = normalize_tariff_number(tokens[-1])
        tokens = tokens[:-1]

    if not tokens:
        return None

    # 3. Pronalazak KOM ili PAR (zadnje pojavljivanje = jedinica mjere)
    unit = "KOM"
    unit_pos = -1
    for i in range(len(tokens) - 1, -1, -1):
        if tokens[i].upper() in ("KOM", "PAR"):
            unit = tokens[i].upper()
            unit_pos = i
            break

    # Sve do KOM/PAR = sifra + naziv
    cn_tokens = tokens[:unit_pos] if unit_pos >= 0 else tokens
    if not cn_tokens:
        return None

    code = cn_tokens[0]
    naziv = " ".join(cn_tokens[1:]) if len(cn_tokens) > 1 else code

    return KGLine(
        rbr=rbr,
        code=code,
        naziv=naziv,
        unit=unit,
        qty=qty,
        price=price,
        amount=amount,
        currency=cur,
        tarifni_broj=hs,
        co=co,
    )


# ---------------------------------------------------------------------------
# Glavni parser
# ---------------------------------------------------------------------------

def parse_kg_fashion_pdf(pdf_path: str) -> Tuple[Dict[str, Any], List[KGLine]]:
    """Parsira KG Fashion PDF fakturu. Vraca (header_dict, lista_stavki)."""
    with pdfplumber.open(pdf_path) as pdf:
        all_lines: List[str] = []
        for page in pdf.pages:
            txt = page.extract_text() or ""
            all_lines.extend(ln.rstrip() for ln in txt.splitlines())

    full_text = "\n".join(all_lines)
    header: Dict[str, Any] = {"source_file": Path(pdf_path).name}

    # Broj fakture
    m = _INVOICE_NO_RE.search(full_text)
    if m:
        header["invoice_no"] = m.group(1).strip().rstrip(".,;:")

    # Datum (trazi u prvim linijama koje sadrze "datum")
    for ln in all_lines[:30]:
        if "datum" in ln.lower():
            dm = _DATE_RE.search(ln)
            if dm:
                header["date"] = dm.group(1)
                break

    # Brend
    bm = _BRAND_RE.search(full_text)
    if bm:
        header["brand"] = bm.group(1).strip()

    # Valuta i ukupna vrijednost (preskoci RSD, uzmi prvu non-RSD vrijednost)
    for tm in _TOTAL_RE.finditer(full_text):
        cur = tm.group(1).upper()
        if cur != "RSD":
            header["currency"] = cur
            header["total_value"] = parse_eu_number(tm.group(2))
            break

    # Tezine
    for ln in all_lines:
        bm2 = _BRUTO_RE.search(ln)
        if bm2:
            header["gross_kg"] = parse_eu_number(bm2.group(1))
            break
    for ln in all_lines:
        nm = _NETO_RE.search(ln)
        if nm:
            header["net_kg"] = parse_eu_number(nm.group(1))
            break

    # Incoterm (paritet)
    im = _INCOTERM_RE.search(full_text)
    if im:
        header["incoterm"] = im.group(1).upper()

    # --- Parsiranje stavki ---
    items: List[KGLine] = []
    in_table = False
    current_item: Optional[KGLine] = None

    for ln in all_lines:
        s = (ln or "").strip()
        if not s:
            continue

        # Detekcija zaglavlja tabele
        if _TABLE_HEADER_RE.search(s):
            in_table = True
            current_item = None
            continue

        if not in_table:
            continue

        # Preskoci ponavljajuce header linije po stranicama
        if _SKIP_IN_TABLE_RE.search(s):
            continue
        if s == "C/O":
            continue

        # Stop uslovi
        if _STOP_RE.match(s):
            in_table = False
            continue

        # Nova stavka: pocinje brojem i ima "qty price CUR amount CUR" na kraju
        if re.match(r'^\d+\s', s):
            parsed = _parse_item_line(s)
            if parsed:
                items.append(parsed)
                current_item = parsed
            # else: red pocinje brojem ali nema tail (npr. VIZZANO "5 100%...") — ignoriši

    return header, items


# ---------------------------------------------------------------------------
# Import funkcija (API za import_service)
# ---------------------------------------------------------------------------

def import_kg_fashion(pdf_path: str) -> ImportResult:
    """
    Importuje KG Fashion PDF fakturu u Deklarant Pro format.

    Automatski trazi XLS transport manifest u istom folderu i primjenjuje:
      - has_eur1 → has_origin_statement = True (EUR1 obrazac preferencijalno porijeklo)
      - bruto/neto iz manifesta ako PDF nema podatke o tezinama
    """
    logger.info(f"KG Fashion parser: {Path(pdf_path).name}")

    header, kg_lines = parse_kg_fashion_pdf(pdf_path)
    currency = header.get("currency", "EUR")

    # --- Ucitaj XLS manifest ako postoji ---
    manifest_data: Optional[Dict[str, Any]] = None
    xls_path = _find_kg_manifest_xls(pdf_path)
    if xls_path:
        manifest = _parse_manifest_xls(xls_path)
        racun_num = _extract_racun_num(header.get("invoice_no", ""))
        if racun_num is not None and racun_num in manifest:
            manifest_data = manifest[racun_num]
            logger.info(
                f"  Manifest match RAC.{racun_num}: "
                f"EUR1={manifest_data['has_eur1']} | "
                f"C/O={manifest_data['co'] or 'X'} | "
                f"Bruto={manifest_data['bruto']} | Neto={manifest_data['neto']}"
            )

    has_eur1 = manifest_data["has_eur1"] if manifest_data else False
    manifest_co = manifest_data["co"] if manifest_data else ""

    invoice_lines: List[InvoiceLine] = []
    for item in kg_lines:
        # C/O prioritet: iz PDF stavke, zatim iz manifesta
        co = item.co or manifest_co
        line = InvoiceLine(
            line_no=item.rbr,
            product_code=item.code,
            naziv_robe=item.naziv,
            tarifni_broj=item.tarifni_broj,
            zemlja_porijekla=co,
            jm=item.unit.lower(),
            kolicina=item.qty,
            cijena_jed=item.price,
            iznos=item.amount,
            valuta=item.currency,
            bruto_kg=0.0,
            neto_kg=0.0,
            exporter=_EXPORTER,
            importer=_IMPORTER,
        )
        invoice_lines.append(line)

    # Tezine: PDF ima prednost, manifest kao fallback
    gross_kg = header.get("gross_kg", 0.0) or (manifest_data["bruto"] if manifest_data else 0.0)
    net_kg   = header.get("net_kg",   0.0) or (manifest_data["neto"]  if manifest_data else 0.0)

    if has_eur1:
        logger.info(f"  EUR1 potvrden iz manifesta — has_origin_statement=True")

    logger.info(f"  Parsirano {len(invoice_lines)} stavki, valuta={currency}, EUR1={has_eur1}")

    return ImportResult(
        items=invoice_lines,
        bruto_kg=gross_kg,
        neto_kg=net_kg,
        invoice_name=header.get("invoice_no", ""),
        currency=currency,
        import_type="kg_fashion",
        has_origin_statement=has_eur1,
        exporter=_EXPORTER,
        importer=_IMPORTER,
    )


def detect_kg_fashion(text_sample: str) -> bool:
    """Detekcija KG Fashion formata iz uzorka teksta."""
    upper = text_sample.upper()
    return "K... G... FASHION" in upper or "KGFASHION.DOO" in upper


# ---------------------------------------------------------------------------
# XLS Manifest parser (transport lista sa EUR1 i tezinama)
# ---------------------------------------------------------------------------

# Kolumne u XLS manifestu (0-indeksirane)
_XLS_COL_RACUN = 2   # "RAČUN"
_XLS_COL_BREND = 11  # "Brend"
_XLS_COL_CO    = 13  # "C/O"
_XLS_COL_EUR1  = 14  # "EUR1"
_XLS_COL_BRUTO = 15  # "Bruto"
_XLS_COL_NETO  = 16  # "Neto"


def _find_kg_manifest_xls(pdf_path: str) -> Optional[str]:
    """
    Trazi XLS transport manifest u istom folderu kao PDF.
    Prepoznaje ga po prisutnosti 'PTP' ili sifre kupca '15467' u imenu fajla.
    """
    folder = Path(pdf_path).parent
    for pattern in ("*.xls", "*.xlsx"):
        for f in sorted(folder.glob(pattern)):
            name_upper = f.name.upper()
            if "PTP" in name_upper or "15467" in name_upper:
                return str(f)
    return None


def _parse_manifest_xls(xls_path: str) -> Dict[int, Dict[str, Any]]:
    """
    Parsira XLS transport manifest.

    Grupira redove po broju fakture (kolona RACUN) i za svaku fakturu vraca:
      {
        "has_eur1": bool,          - da li je EUR1 obrazac prisutan
        "co": str,                 - zemlja porijekla iz manifesta (2-slovni ISO)
        "bruto": float,            - ukupna bruto tezina svih posiljki te fakture
        "neto": float,             - ukupna neto tezina
      }

    Kljuc mape: cijeli broj fakture (npr. 296 za RAC.296).
    """
    result: Dict[int, Dict[str, Any]] = {}
    try:
        wb = xlrd.open_workbook(xls_path)
        ws = wb.sheet_by_index(0)
    except Exception as e:
        logger.warning(f"KG Manifest: ne mogu otvoriti XLS '{xls_path}': {e}")
        return result

    # Provjeri zaglavlje (red 1, 0-indeks)
    try:
        header_row = [str(ws.cell_value(1, c)).strip() for c in range(ws.ncols)]
        if "RAČUN" not in header_row and "RACUN" not in [h.upper() for h in header_row]:
            logger.warning(f"KG Manifest: nepoznat format XLS '{Path(xls_path).name}'")
            return result
    except Exception:
        return result

    current_racun: Optional[int] = None

    for r in range(2, ws.nrows):
        try:
            racun_val = ws.cell_value(r, _XLS_COL_RACUN)
            co_val    = str(ws.cell_value(r, _XLS_COL_CO)).strip()
            eur1_val  = str(ws.cell_value(r, _XLS_COL_EUR1)).strip()
            bruto_val = ws.cell_value(r, _XLS_COL_BRUTO)
            neto_val  = ws.cell_value(r, _XLS_COL_NETO)

            # Novi blok fakture kada je RACUN kolona popunjena
            if racun_val and racun_val != "":
                try:
                    current_racun = int(float(racun_val))
                except (ValueError, TypeError):
                    current_racun = None

            if current_racun is None:
                continue

            # Inicijalizuj entry ako ne postoji
            if current_racun not in result:
                result[current_racun] = {
                    "has_eur1": False,
                    "co": co_val if co_val and co_val != "X" else "",
                    "bruto": 0.0,
                    "neto": 0.0,
                }

            entry = result[current_racun]

            # EUR1: bilo koji red fakture ima EUR1 → cijela faktura ima EUR1
            if eur1_val.upper() == "EUR1":
                entry["has_eur1"] = True

            # C/O: uzmi prvu ne-X vrijednost
            if not entry["co"] and co_val and co_val != "X":
                entry["co"] = co_val

            # Akumuliraj tezine
            try:
                entry["bruto"] += float(bruto_val) if bruto_val else 0.0
                entry["neto"]  += float(neto_val)  if neto_val  else 0.0
            except (TypeError, ValueError):
                pass

        except Exception as e:
            logger.debug(f"KG Manifest: greska na redu {r}: {e}")
            continue

    logger.info(f"KG Manifest: ucitano {len(result)} faktura iz '{Path(xls_path).name}'")
    for num, data in sorted(result.items()):
        eur1_flag = " [EUR1]" if data["has_eur1"] else ""
        logger.info(f"  RAC.{num}: C/O={data['co'] or 'X'} | Bruto={data['bruto']} | Neto={data['neto']}{eur1_flag}")

    return result


def _extract_racun_num(invoice_no: str) -> Optional[int]:
    """Iz broja fakture '25-296/2026' izvlaci cijeli broj (296)."""
    m = re.search(r'-(\d+)/', invoice_no)
    if m:
        return int(m.group(1))
    # Fallback: samo cifre na kraju
    m = re.search(r'(\d{3,})$', invoice_no.split('/')[0])
    if m:
        return int(m.group(1))
    return None
