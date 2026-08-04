"""
Packing List Parser - Univerzalni parser za packing liste

Parsira packing liste sa različitim formatima i ekstraktuje:
- Product code / Šifra
- Naziv proizvoda
- Količina
- Jedinica mjere (kom, par, bunt, koleto, svežanj, kutija, rolna, pakovanje, itd.)
- Bruto težina (kg) po stavci
- Neto težina (kg) po stavci
- Broj paketa / Package count
"""

import logging
import re
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from core.draft.draft import InvoiceLine
from importers.invoice_line_utils import parse_number_permissive as _parse_number

logger = logging.getLogger("deklarant_pro.import.packing_list")


# Poznate jedinice pakovanja (za normalizaciju)
PACKING_UNITS = {
    # Osnovne
    "kom": "kom",
    "pcs": "kom",
    "piece": "kom",
    "pieces": "kom",

    # Parovi
    "par": "par",
    "pair": "par",
    "pairs": "par",

    # Bunti/rolne
    "bunt": "bunt",
    "bundle": "bunt",
    "bundles": "bunt",
    "rolna": "rolna",
    "roll": "rolna",
    "rolls": "rolna",

    # Pakovanja
    "koleto": "koleto",
    "collo": "koleto",
    "colli": "koleto",
    "pakovanje": "pakovanje",
    "package": "pakovanje",
    "packages": "pakovanje",
    "pkg": "pakovanje",

    # Kutije/kartoni
    "kutija": "kutija",
    "box": "kutija",
    "boxes": "kutija",
    "karton": "karton",
    "carton": "karton",
    "cartons": "karton",
    "ctn": "karton",

    # Svežnjevi
    "svežanj": "svežanj",
    "svezanj": "svežanj",
    "snop": "svežanj",

    # Ostalo
    "set": "set",
    "sets": "set",
    "palet": "palet",
    "paleta": "palet",
    "pallet": "palet",
    "pallets": "palet",
}


@dataclass
class PackingItem:
    """Stavka iz packing liste."""
    line_no: int
    product_code: str
    naziv_robe: str
    kolicina: float
    jm: str  # Jedinica mjere
    bruto_kg: float
    neto_kg: float
    broj_paketa: int = 0
    tip_pakovanja: str = ""  # npr. "karton", "koleto"

    def to_invoice_line(self) -> InvoiceLine:
        """Konvertuje u InvoiceLine (bez cijena - to dolazi iz fakture)."""
        return InvoiceLine(
            line_no=self.line_no,
            product_code=self.product_code,
            naziv_robe=self.naziv_robe,
            kolicina=self.kolicina,
            jm=self.jm,
            bruto_kg=self.bruto_kg,
            neto_kg=self.neto_kg,
        )


def parse_packing_list(pdf_path: str) -> List[PackingItem]:
    """
    Parsira packing list PDF i ekstraktuje stavke sa težinama.

    Args:
        pdf_path: Putanja do packing list PDF-a

    Returns:
        Lista PackingItem objekata sa bruto/neto težinama
    """
    logger.info(f"📦 Parsing packing list: {pdf_path}")

    import pdfplumber

    items: List[PackingItem] = []

    with pdfplumber.open(pdf_path) as pdf:
        # Ekstraktuj tekst iz svih stranica
        full_text = ""
        for page in pdf.pages:
            text = page.extract_text() or ""
            full_text += text + "\n"

        # Pokušaj tabularnu extraction (primarni način)
        table_items = _extract_from_tables(pdf)
        if table_items:
            items.extend(table_items)
            logger.info(f"   ✅ Izvučeno {len(table_items)} stavki iz tabela")
        else:
            # Fallback na text-based parsing
            logger.info("   🔍 Tabele nisu pronađene, koristim text-based parsing")
            text_items = _extract_from_text(full_text)
            items.extend(text_items)
            logger.info(f"   ✅ Izvučeno {len(text_items)} stavki iz teksta")

    logger.info(f"✅ Parsed {len(items)} items from packing list")

    return items


def _extract_from_tables(pdf) -> List[PackingItem]:
    """Ekstraktuje stavke iz PDF tabela (primarni način)."""
    items: List[PackingItem] = []

    for page_num, page in enumerate(pdf.pages, 1):
        tables = page.extract_tables()
        if not tables:
            continue

        for table in tables:
            if not table or len(table) < 2:
                continue

            # Detektuj kolone u header redu
            header = table[0]
            col_map = _detect_packing_columns(header)

            if not col_map:
                continue  # Nije packing list tabela

            # Parsiraj data redove
            for row_idx, row in enumerate(table[1:], 1):
                if not row or len(row) < 3:
                    continue

                # Skip footer redovi (Total, Subtotal, itd.)
                first_cell = str(row[0] or "").strip().upper()
                if first_cell in ["TOTAL", "SUBTOTAL", "SUM", "UKUPNO", ""]:
                    continue

                item = _parse_packing_row(row, col_map, row_idx)
                if item:
                    items.append(item)

    return items


def _detect_packing_columns(header: List[str]) -> Optional[Dict[str, int]]:
    """
    Detektuje kolone u packing list tabeli.

    Returns:
        Dict sa mapiranjem: {'code': idx, 'description': idx, ...} ili None ako nije packing lista
    """
    if not header:
        return None

    header_upper = [str(cell or "").strip().upper() for cell in header]

    # Mora imati minimalno: Code/Šifra, Description/Naziv
    has_code = any("CODE" in h or "ŠIFRA" in h or "ART" in h or "ITEM" in h or "TM" in h for h in header_upper)
    has_description = any("DESCRIPTION" in h or "NAZIV" in h or "TITLE" in h or "ARTICLE" in h or "OPIS" in h for h in header_upper)

    # Težine - može biti GROSS+NET ili samo NET ili TOTAL KG
    has_gross = any("GROSS" in h or "BRUTO" in h or "G.W" in h or "GW" in h for h in header_upper)
    has_net = any("NET" in h or "NETO" in h or "N.W" in h or "NW" in h for h in header_upper)
    has_total_kg = any("TOTAL" in h and "KG" in h for h in header_upper)

    # Ako nema barem NET ili TOTAL KG, nije packing lista
    # (dozvoli packing liste BEZ gross weight-a)
    if not (has_net or has_total_kg or has_gross):
        return None

    col_map = {}

    for idx, h in enumerate(header_upper):
        # Product Code / Šifra (TM code, Code, Šifra)
        if not col_map.get("code"):
            if re.search(r'\b(TM|CODE|ŠIFRA|SIFRA|ART\.?|ITEM\s*NO|SKU)\b', h):
                col_map["code"] = idx

        # Description / Naziv
        if not col_map.get("description"):
            if re.search(r'\b(DESCRIPTION|NAZIV|OPIS|TITLE|ARTICLE|PRODUCT|COMMODITY)\b', h):
                col_map["description"] = idx

        # Quantity
        if not col_map.get("quantity"):
            if re.search(r'\b(QTY|QUANTITY|KOLIČINA|KOLICINA|KOL\.?)\b', h):
                col_map["quantity"] = idx

        # VAŽNO: PRVO detektuj težinske kolone, PA TEK ONDA jedinicu mjere!

        # Gross Weight (opciono)
        if not col_map.get("gross"):
            if re.search(r'\b(GROSS|BRUTO|G\.?W\.?|GW)\b', h) and "UNIT" not in h:
                col_map["gross"] = idx

        # Net Weight (Unit NET KG ili NET KG)
        if not col_map.get("net"):
            if re.search(r'\b(UNIT\s*NET|NET\s*KG|NET|NETO|N\.?W\.?|NW)\b', h):
                # Ali samo ako NIJE "Total KG" (to je total_kg)
                if "TOTAL" not in h:
                    col_map["net"] = idx

        # Total KG (ukupna neto težina)
        if not col_map.get("total_kg"):
            if re.search(r'\b(TOTAL\s*KG|TOTAL.*WEIGHT)\b', h):
                col_map["total_kg"] = idx

        # Unit of Measure (J.M., JM)
        # SAMO ako kolona NE sadrži težinske keywords (NET, GROSS, BRUTO, KG)
        if not col_map.get("unit"):
            if "NET" in h or "GROSS" in h or "BRUTO" in h or "NETO" in h or ("KG" in h and "TOTAL" not in h):
                continue  # Skip ovu kolonu
            if re.search(r'\b(JM|J\.?M\.?|U\.?M\.?|UOM|MEASURE|UNIT)\b', h):
                col_map["unit"] = idx

        # Package Count
        if not col_map.get("packages"):
            if re.search(r'\b(PACKAGES?|PKG|COLLI|KOLETO|PAKETA|NO\.?\s*OF\s*PKG)\b', h):
                col_map["packages"] = idx

        # Package Type
        if not col_map.get("package_type"):
            if re.search(r'\b(PACKAGE\s*TYPE|PACKING|TYPE|VRSTA\s*PAK)\b', h):
                col_map["package_type"] = idx

    return col_map if col_map else None


def _parse_packing_row(row: List[str], col_map: Dict[str, int], line_no: int) -> Optional[PackingItem]:
    """Parsira jedan red iz packing list tabele."""
    try:
        # Extract values
        code = _get_cell(row, col_map.get("code", -1))
        description = _get_cell(row, col_map.get("description", -1))
        quantity = _parse_number(_get_cell(row, col_map.get("quantity", -1)))
        unit = _normalize_unit(_get_cell(row, col_map.get("unit", -1)))

        # Težine - podrška za različite formate
        gross = _parse_number(_get_cell(row, col_map.get("gross", -1)))
        net_per_unit = _parse_number(_get_cell(row, col_map.get("net", -1)))
        total_kg = _parse_number(_get_cell(row, col_map.get("total_kg", -1)))

        # PRIORITET: Ako imamo Total KG, koristi to kao NETO (ukupna težina)
        # Ako nema Total KG, onda koristi Net (može biti ukupna ili po komadu)
        if total_kg > 0:
            net = total_kg
        else:
            net = net_per_unit

        # Ako imamo Net ali ne Gross, procijeni Bruto kao Net + 5% (standardno pakovanje)
        if net > 0 and gross == 0:
            gross = net * 1.05  # +5% za pakovanje

        packages = int(_parse_number(_get_cell(row, col_map.get("packages", -1))))
        package_type = _get_cell(row, col_map.get("package_type", -1))

        # Validacija - mora imati barem naziv i težine
        if not description or (gross == 0 and net == 0):
            return None

        return PackingItem(
            line_no=line_no,
            product_code=code,
            naziv_robe=description,
            kolicina=quantity,
            jm=unit,
            bruto_kg=gross,
            neto_kg=net,
            broj_paketa=packages,
            tip_pakovanja=package_type,
        )

    except Exception as e:
        logger.debug(f"Ne mogu parsirati red {line_no}: {e}")
        return None


def _extract_from_text(text: str) -> List[PackingItem]:
    """
    Ekstraktuje stavke iz teksta (fallback metoda).

    Traži text-based format sličan invoice_improved:
    No. Code Description Qty Unit Gross(kg) Net(kg)
    1.  1071 NAZIV       100 kom  50.00     45.00
    """
    items: List[PackingItem] = []
    lines = text.split('\n')

    # Pattern za početak stavke
    # Broj., Kod, Ostatak...
    item_pattern = re.compile(
        r'^(\d+)\.\s+([A-Z0-9]+)\s+(.+)',
        re.IGNORECASE
    )

    current_item_data = None

    for line in lines:
        line = line.strip()

        # Skip empty i header
        if not line or "PACKING" in line.upper() or line.startswith("No."):
            continue

        match = item_pattern.match(line)

        if match:
            # Sačuvaj prethodnu stavku
            if current_item_data:
                item = _parse_text_item(current_item_data)
                if item:
                    items.append(item)

            # Nova stavka
            num = int(match.group(1))
            code = match.group(2).strip()
            rest = match.group(3).strip()

            current_item_data = {
                'num': num,
                'code': code,
                'line': rest,
                'continuation_lines': []
            }

        elif current_item_data:
            # Multi-line nastavak
            if not re.match(r'^\d+\.', line):
                current_item_data['continuation_lines'].append(line)

    # Dodaj posljednju stavku
    if current_item_data:
        item = _parse_text_item(current_item_data)
        if item:
            items.append(item)

    return items


def _parse_text_item(item_data: Dict[str, Any]) -> Optional[PackingItem]:
    """
    Parsira stavku iz text-based formata.

    Format: NAZIV jm količina bruto_kg neto_kg
    Npr: "GREJAC kom 100,00 50,00 45,00"
    """
    num = item_data['num']
    code = item_data['code']
    line = item_data['line']

    # Pattern za kraj linije: JM QTY GROSS NET
    # kom 100,00 50,00 45,00
    end_pattern = re.compile(
        r'([a-zA-Zčćžšđ]{2,15})\s+([\d,\.]+)\s+([\d,\.]+)\s+([\d,\.]+)$',
        re.IGNORECASE
    )

    match = end_pattern.search(line)
    if not match:
        logger.debug(f"Stavka #{num}: Ne mogu parsirati brojeve: {line}")
        return None

    unit = _normalize_unit(match.group(1))
    quantity = _parse_number(match.group(2))
    gross = _parse_number(match.group(3))
    net = _parse_number(match.group(4))

    # Naziv je sve prije jedinice
    naziv_end = match.start()
    naziv = line[:naziv_end].strip()

    # Dodaj continuation lines
    if item_data.get('continuation_lines'):
        naziv += " " + " ".join(item_data['continuation_lines'])

    naziv = naziv.strip()

    return PackingItem(
        line_no=num,
        product_code=code,
        naziv_robe=naziv,
        kolicina=quantity,
        jm=unit,
        bruto_kg=gross,
        neto_kg=net,
    )


def _get_cell(row: List[str], idx: int) -> str:
    """Safely get cell value from row."""
    if idx < 0 or idx >= len(row):
        return ""
    return str(row[idx] or "").strip()

def _normalize_unit(unit: str) -> str:
    """Normalizuje jedinicu mjere koristeći poznate jedinice pakovanja."""
    if not unit:
        return "kom"

    unit_lower = unit.lower().strip()

    # Provjeri poznate jedinice
    normalized = PACKING_UNITS.get(unit_lower)
    if normalized:
        return normalized

    # Ako nije poznata, vrati originalnu (lowercase)
    return unit_lower


def detect_packing_list(pdf_path: str) -> bool:
    """
    Detektuje da li je PDF packing lista.

    Returns:
        True ako je detektovana packing lista
    """
    import pdfplumber

    try:
        with pdfplumber.open(pdf_path) as pdf:
            if not pdf.pages:
                return False

            # Provjeri prvu stranicu
            text = pdf.pages[0].extract_text() or ""
            text_upper = text.upper()

            # Karakteristični keywords za packing list
            has_packing_keyword = any(kw in text_upper for kw in [
                "PACKING LIST",
                "PAKOVANJE",
                "PACKING SLIP",
                "DELIVERY NOTE",
                "OTPREMNICA",
            ])

            # VAŽNO: Ako ima "INVOICE" ili "FAKTURA", to NIJE packing list!
            # Ovo sprječava false positives na fakturama sa weight poljima
            has_invoice_marker = any(kw in text_upper for kw in [
                "INVOICE",
                "FAKTURA",
                "COMMERCIAL INVOICE",
            ])

            # Mora imati Gross i Net weight kolone
            has_weights = ("GROSS" in text_upper or "BRUTO" in text_upper) and \
                         ("NET" in text_upper or "NETO" in text_upper)

            # STRIKTNO: Mora eksplicitno imati packing keyword.
            # has_weights alone nije dovoljan - fakture takođe imaju weight kolone.
            if has_invoice_marker:
                # Ako ima "INVOICE", mora eksplicitno imati "PACKING LIST" keyword
                return has_packing_keyword
            else:
                # Čak i bez "INVOICE", zahtijevamo eksplicitni packing keyword
                # kako bismo izbjegli false positives na fakturama bez "INVOICE" u naslovu
                return has_packing_keyword

    except Exception as e:
        logger.debug(f"Greška tokom detekcije packing liste: {e}")
        return False


def combine_invoice_and_packing(
    invoice_items: List[InvoiceLine],
    packing_items: List[PackingItem]
) -> List[InvoiceLine]:
    """
    Kombinuje stavke iz fakture sa podacima iz packing liste.

    Matching logika:
    1. Tačan match po product_code (ako postoji)
    2. Fuzzy match po nazivu (ako nema product_code)

    Args:
        invoice_items: Stavke iz fakture (sa cijenama)
        packing_items: Stavke iz packing liste (sa težinama)

    Returns:
        Lista InvoiceLine sa popunjenim bruto_kg i neto_kg
    """
    logger.info(f"🔗 Kombinujem fakturu ({len(invoice_items)} stavki) + packing list ({len(packing_items)} stavki)")

    matched = 0
    unmatched_invoice = []
    unmatched_packing = []
    used_packing: set = set()

    # ── O(m) predpriprema — jednom, ne po svakoj stavci ──────────────────────
    # Dict za exact match: product_code → [idx, ...] (jedna stavka može imati duplikat)
    code_index: dict = {}
    for idx, p in enumerate(packing_items):
        if p.product_code:
            code_index.setdefault(p.product_code, []).append(idx)

    # Normalizovani nazivi za fuzzy — računamo jednom umjesto n puta
    packing_norm: list = [
        (p.naziv_robe or "").lower().strip() for p in packing_items
    ]
    # ─────────────────────────────────────────────────────────────────────────

    for inv_item in invoice_items:
        match_found = False

        # PRIORITET 1: O(1) exact match po product_code
        if inv_item.product_code:
            for pack_idx in code_index.get(inv_item.product_code, []):
                if pack_idx not in used_packing:
                    inv_item.bruto_kg = packing_items[pack_idx].bruto_kg
                    inv_item.neto_kg  = packing_items[pack_idx].neto_kg
                    used_packing.add(pack_idx)
                    matched += 1
                    match_found = True
                    logger.debug(f"   ✅ Match po kodu: {inv_item.product_code}")
                    break

        # PRIORITET 2: Fuzzy match — samo za neuparene, sa predkompajliranim nazivima
        if not match_found:
            inv_norm = (inv_item.naziv_robe or "").lower().strip()
            best_idx = None
            best_sim = 0.0

            for pack_idx, pack_norm in enumerate(packing_norm):
                if pack_idx in used_packing:
                    continue

                sim = _fuzzy_match_normalized(inv_norm, pack_norm)
                if sim > best_sim and sim > 0.85:
                    best_sim = sim
                    best_idx = pack_idx

            if best_idx is not None:
                inv_item.bruto_kg = packing_items[best_idx].bruto_kg
                inv_item.neto_kg  = packing_items[best_idx].neto_kg
                used_packing.add(best_idx)
                matched += 1
                match_found = True

                logger.debug(f"   ✅ Fuzzy match ({best_sim:.1%}): {inv_item.naziv_robe[:30]}...")

        if not match_found:
            unmatched_invoice.append(inv_item.naziv_robe[:50])

    # Log unmatched packing items
    for pack_idx, pack_item in enumerate(packing_items):
        if pack_idx not in used_packing:
            unmatched_packing.append(pack_item.naziv_robe[:50])

    logger.info(f"✅ Matching završen:")
    logger.info(f"   Matched: {matched}/{len(invoice_items)} stavki")

    if unmatched_invoice:
        logger.warning(f"   ⚠️  Unmatched invoice items: {len(unmatched_invoice)}")
        for name in unmatched_invoice[:3]:
            logger.debug(f"      - {name}")

    if unmatched_packing:
        logger.warning(f"   ⚠️  Unmatched packing items: {len(unmatched_packing)}")
        for name in unmatched_packing[:3]:
            logger.debug(f"      - {name}")

    return invoice_items


def _fuzzy_match(text1: str, text2: str) -> float:
    """
    Fuzzy matching između dva stringa.

    Returns:
        Similarity score 0.0-1.0
    """
    if not text1 or not text2:
        return 0.0

    t1 = text1.lower().strip()
    t2 = text2.lower().strip()

    return _fuzzy_match_normalized(t1, t2)


def _fuzzy_match_normalized(t1: str, t2: str) -> float:
    """Fuzzy match nad već normalizovanim (lower+strip) stringovima."""
    if not t1 or not t2:
        return 0.0
    if t1 == t2:
        return 1.0
    if t1 in t2 or t2 in t1:
        return 0.90
    tokens1 = set(t1.split())
    tokens2 = set(t2.split())
    if not tokens1 or not tokens2:
        return 0.0
    intersection = tokens1.intersection(tokens2)
    union = tokens1.union(tokens2)
    return len(intersection) / len(union)
