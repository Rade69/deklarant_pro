"""
Generic PDF Invoice Importer

Automatski detektuje i parsira proizvode iz bilo koje PDF fakture.
Koristi automatsku detekciju tabela i heuristike za identifikaciju kolona.
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import pdfplumber

from core.draft.draft import InvoiceLine
from importers.import_result import ImportResult

logger = logging.getLogger("asycuda_pro.import.generic_pdf")

# Redovi koji su jasno footer/summary — ne stavke
_SKIP_ROW_PREFIXES = re.compile(
    r'^(total|ukupno|sum|subtotal|grand\s*total|strana|page|footer|'
    r'vat|pdv|tax|porez|discount|rabat|popust|freight|špedicija|'
    r'shipping|transport|packaging|ambalaža)',
    re.IGNORECASE
)

# Valute koje tražimo u tekstu fakture
_CURRENCY_PATTERNS = [
    (r'\bEUR\b', 'EUR'),
    (r'\bUSD\b|\bUS\$\b', 'USD'),
    (r'\bCHF\b', 'CHF'),
    (r'\bGBP\b|\b£\b', 'GBP'),
    (r'\bBAM\b|\bKM\b', 'BAM'),
    (r'\bRSD\b', 'RSD'),
]


@dataclass
class ColumnMapping:
    """Mapiranje detektovanih kolona u fakturu."""
    product_code: Optional[int] = None    # Index kolone sa šifrom proizvoda
    description: Optional[int] = None    # Index kolone sa nazivom/opisom
    quantity: Optional[int] = None       # Index kolone sa količinom
    unit: Optional[int] = None           # Index kolone sa jedinicom mjere
    unit_price: Optional[int] = None     # Index kolone sa cijenom
    total_price: Optional[int] = None    # Index kolone sa ukupnim iznosom
    origin_country: Optional[int] = None # Index kolone sa zemljom porijekla
    discount: Optional[int] = None       # Index kolone sa popustom/rabatom

    def is_valid(self) -> bool:
        """Provjeri da li imamo minimalne podatke za import."""
        has_price = self.unit_price is not None or self.total_price is not None
        return self.description is not None and has_price


def parse_generic_pdf(pdf_path: str) -> ImportResult:
    """
    Parsira bilo koju PDF fakturu automatski.

    Proces:
    1. Ekstraktuje tekst za metadata (broj, težine, valuta, izvoznik)
    2. Ekstraktuje tabele ili koristi word-based fallback
    3. Detektuje kolone i parsira stavke

    Args:
        pdf_path: Putanja do PDF fajla

    Returns:
        ImportResult sa parsiranim stavkama
    """
    logger.info(f"🔍 Generic PDF import: {pdf_path}")

    items: List[InvoiceLine] = []
    invoice_number = ""
    bruto_kg = 0.0
    neto_kg = 0.0
    has_origin_statement = False
    origin_statements = []

    with pdfplumber.open(pdf_path) as pdf:
        # 1. Ekstraktuj tekst za metadata
        full_text = ""
        for page in pdf.pages:
            text = page.extract_text() or ""
            full_text += text + "\n"

        invoice_number = _extract_invoice_number(full_text)
        bruto_kg, neto_kg = _extract_weights(full_text)
        currency = _extract_currency(full_text)
        exporter_name = _detect_exporter(full_text)

        origin_statements = _detect_all_origin_statements(full_text)
        has_origin_statement = len(origin_statements) > 0

        if has_origin_statement:
            logger.info(f"  ✅ Detektovano {len(origin_statements)} izjava o poreklu:")
            for i, stmt in enumerate(origin_statements, 1):
                logger.info(f"     #{i}: {stmt.origin_country} (stavke {stmt.item_range})")
        else:
            logger.info(f"  ℹ️  Nije nađena izjava o poreklu")

        if exporter_name:
            logger.info(f"  🏢 Izvoznik: {exporter_name}")

        # 2. Ekstraktuj tabele iz svih stranica
        all_tables = []
        for page_num, page in enumerate(pdf.pages, 1):
            tables = page.extract_tables()
            if tables:
                logger.debug(f"   Stranica {page_num}: pronađeno {len(tables)} tabela")
                for table in tables:
                    if table and len(table) > 1:
                        all_tables.append(table)

        if not all_tables:
            logger.warning("⚠️  Nisu pronađene tabele — pokušavam text-based extraction")
            items = _parse_words_based(pdf_path)
            _set_line_numbers(items)
            _set_currency(items, currency)
            logger.info(f"   Text-based extraction: {len(items)} stavki")
            return ImportResult(
                items=items,
                bruto_kg=bruto_kg,
                neto_kg=neto_kg,
                invoice_name=invoice_number,
                currency=currency,
                has_origin_statement=has_origin_statement,
                origin_statements=origin_statements,
            )

        # 3. Za svaku tabelu, pokušaj detektovati kolone i parsirati stavke
        for table_idx, table in enumerate(all_tables):
            column_mapping = _detect_columns(table)

            if not column_mapping.is_valid():
                logger.debug(f"   ⏭️  Preskaćem tabelu #{table_idx + 1} - nema dovoljno kolona")
                continue

            logger.debug(f"   ✅ Mapiranje kolona: {column_mapping}")

            table_items = _parse_table_items(table, column_mapping, currency)
            items.extend(table_items)
            logger.info(f"   ✅ Izvučeno {len(table_items)} stavki iz tabele #{table_idx + 1}")

    _set_line_numbers(items)
    logger.info(f"✅ Ukupno izvučeno {len(items)} stavki")

    return ImportResult(
        items=items,
        bruto_kg=bruto_kg,
        neto_kg=neto_kg,
        invoice_name=invoice_number,
        currency=currency,
        has_origin_statement=has_origin_statement,
        origin_statements=origin_statements,
    )


# ─────────────────────────────────────────────────────────────────────────────
# DETEKCIJA KOLONA
# ─────────────────────────────────────────────────────────────────────────────

def _detect_columns(table: List[List[str]]) -> ColumnMapping:
    """
    Automatski detektuje koje kolone predstavljaju šta.

    Provjerava prvih 3 reda (multi-row header), koristi sve
    ključne riječi uključujući zemlja porijekla i popust.
    """
    if not table or len(table) == 0:
        return ColumnMapping()

    # Kombiniraj prvih 3 reda kao potencijalni header (multi-row header support)
    header_rows = table[:min(3, len(table))]
    num_cols = max(len(r) for r in header_rows)

    # Za svaku kolonu spoji tekst iz svih header redova
    combined_header: List[str] = []
    for col_idx in range(num_cols):
        parts = []
        for row in header_rows:
            if col_idx < len(row) and row[col_idx]:
                parts.append(str(row[col_idx]).strip())
        combined_header.append(" ".join(parts).upper())

    logger.debug(f"   Header (kombinovani): {combined_header}")

    mapping = ColumnMapping()

    for idx, cell in enumerate(combined_header):
        # Zemlja porijekla — provjeri PRVO jer "ORIGIN" može biti dio drugih naziva
        if re.search(r'\bORIGIN\b|\bCOUNTRY\b|\bZEMLJA\b|\bPOREKLO\b|\bPODRIJETLO\b', cell):
            if mapping.origin_country is None:
                mapping.origin_country = idx
                logger.debug(f"      Col {idx}: ORIGIN_COUNTRY")
            continue

        # Popust/rabat
        if re.search(r'\bDISCOUNT\b|\bRABAT\b|\bPOPUST\b|\bDISC\b', cell):
            if mapping.discount is None:
                mapping.discount = idx
                logger.debug(f"      Col {idx}: DISCOUNT")
            continue

        # Product code
        if re.search(r'\bCODE\b|\bŠIFRA\b|\bSIFRA\b|\bART\.?\b|\bSKU\b|\bREF\.?\b|\bPOS\.?\b', cell):
            if mapping.product_code is None:
                mapping.product_code = idx
                logger.debug(f"      Col {idx}: PRODUCT_CODE")
            continue

        # Description/Naziv — ne smije biti samo "No." ili "Br."
        if re.search(
            r'\bDESCRIPT\w*\b|\bNAZIV\b|\bARTICLE\b|\bPROIZVOD\b|\bNAME\b|\bROBA\b|\bOPIS\b|\bITEM\b|\bGOODS\b|\bTITLE\b',
            cell
        ) and not re.match(r'^(NO\.?|BR\.?|RBR\.?)$', cell.strip()):
            if mapping.description is None:
                mapping.description = idx
                logger.debug(f"      Col {idx}: DESCRIPTION")
            continue

        # Quantity
        if re.search(r'\bQTY\b|\bQ-TY\b|\bKOLIČINA\b|\bKOLICINA\b|\bQUANTITY\b|\bKOM\b|\bMENGE\b|\bPCS\b', cell):
            if mapping.quantity is None:
                mapping.quantity = idx
                logger.debug(f"      Col {idx}: QUANTITY")
            continue

        # Unit
        if re.search(r'\bUNIT\b|\bU\.?M\.?\b|\bJ\.?M\.?\b|\bMJERA\b|\bU\.?N\.?\b|\bU/M\b', cell) \
                and 'PRICE' not in cell and 'CIJENA' not in cell:
            if mapping.unit is None:
                mapping.unit = idx
                logger.debug(f"      Col {idx}: UNIT")
            continue

        # Unit Price — NE ako sadrži TOTAL/AMOUNT/IZNOS
        if re.search(r'\bUNIT.*PRICE\b|\bPRICE\b|\bCIJENA\b|\bCENA\b|\bPREIS\b|\bRATE\b', cell) \
                and not re.search(r'\bTOTAL\b|\bAMOUNT\b|\bIZNOS\b|\bSUMMA\b', cell):
            if mapping.unit_price is None:
                mapping.unit_price = idx
                logger.debug(f"      Col {idx}: UNIT_PRICE")
            continue

        # Total price
        if re.search(r'\bAMOUNT\b|\bTOTAL\b|\bIZNOS\b|\bSUM\b|\bWERT\b|\bVALUE\b|\bSUMMA\b', cell):
            if mapping.total_price is None:
                mapping.total_price = idx
                logger.debug(f"      Col {idx}: TOTAL_PRICE")
            continue

    # Fallback: ako description nije detektovana, uzmi prvu neprepoznatu kolonu
    # koja nije redni broj
    if mapping.description is None:
        used = {
            mapping.product_code, mapping.quantity, mapping.unit,
            mapping.unit_price, mapping.total_price,
            mapping.origin_country, mapping.discount,
        }
        for idx, cell in enumerate(combined_header):
            if idx not in used and not re.match(r'^(RBR\.?|R\.BR\.?|NO\.?|BR\.?|#|\d+)$', cell.strip()):
                mapping.description = idx
                logger.debug(f"      Col {idx}: DESCRIPTION (fallback)")
                break

    # Ako imamo samo unit_price (bez total), prihvati kao validno
    # Ako imamo samo total_price (bez unit_price), prihvati kao validno
    return mapping


# ─────────────────────────────────────────────────────────────────────────────
# PARSIRANJE STAVKI IZ TABELE
# ─────────────────────────────────────────────────────────────────────────────

def _parse_table_items(
    table: List[List[str]],
    mapping: ColumnMapping,
    currency: str = "EUR",
) -> List[InvoiceLine]:
    """
    Parsira stavke iz tabele koristeći detektovano mapiranje kolona.

    Preskoči header redove (prvih N redova koji su bili dio detekcije),
    filtriraj footer/VAT/discount redove, primijeni popust ako postoji kolona.
    """
    items = []

    # Odredi koliko redova preskočiti (header može biti 1-3 reda)
    # Pronađi prvi red koji ima numeričke vrijednosti (to je prva stavka)
    skip_rows = _find_data_start(table)

    for row_idx, row in enumerate(table[skip_rows:], start=skip_rows + 1):
        # Skip praznih redova
        if not row or all(not cell or str(cell).strip() == "" for cell in row):
            continue

        # Skip footer/VAT/summary redova
        row_text = " ".join(str(c).strip() for c in row if c).strip()
        if _SKIP_ROW_PREFIXES.match(row_text):
            continue

        # Skip ako je prvi sadržajni tekst ključna footer riječ
        first_cell = str(row[0]).strip().upper() if row else ""
        if _SKIP_ROW_PREFIXES.match(first_cell):
            continue

        try:
            product_code = _safe_get_cell(row, mapping.product_code, "")
            description = _safe_get_cell(row, mapping.description, "")
            qty_str = _safe_get_cell(row, mapping.quantity, "0")
            unit = _safe_get_cell(row, mapping.unit, "kom").lower()
            unit_price_str = _safe_get_cell(row, mapping.unit_price, "0")
            total_str = _safe_get_cell(row, mapping.total_price, "0")
            origin_str = _safe_get_cell(row, mapping.origin_country, "").strip().upper()
            discount_str = _safe_get_cell(row, mapping.discount, "0")

            if not description.strip():
                continue

            quantity = _parse_number(qty_str)
            unit_price = _parse_number(unit_price_str)
            total_price = _parse_number(total_str)
            discount_pct = _parse_number(discount_str)

            # Izračunaj total ako nije direktno dat u tabeli
            if total_price == 0 and quantity > 0 and unit_price > 0:
                # Primijeni popust pri računanju (total u tabeli ga već sadrži)
                if discount_pct > 0:
                    total_price = round(quantity * unit_price * (1 - discount_pct / 100), 4)
                else:
                    total_price = round(quantity * unit_price, 4)

            # Validacija
            if quantity <= 0 and unit_price <= 0 and total_price <= 0:
                continue

            # Zemlja porijekla — prihvati samo 2-slovna ISO koda ili poznate nazive
            zemlja = _normalize_country(origin_str) if origin_str else ""

            item = InvoiceLine(
                product_code=product_code.strip(),
                naziv_robe=description.strip(),
                kolicina=quantity,
                jm=unit.strip(),
                cijena_jed=unit_price,
                iznos=total_price,
                valuta=currency,
                zemlja_porijekla=zemlja,
            )
            items.append(item)
            logger.debug(
                f"   ✓ Red {row_idx}: {product_code[:15]!r} | "
                f"{description[:35]!r} | {quantity} × {unit_price} = {total_price}"
            )

        except Exception as e:
            logger.warning(f"   ⚠️  Red {row_idx}: Greška pri parsiranju - {e}")
            continue

    return items


def _find_data_start(table: List[List[str]]) -> int:
    """
    Pronađi indeks prvog reda sa stvarnim podacima (ne header).

    Strategija: header redovi nemaju numeričke vrijednosti u koloni iznosa.
    Provjeri prvih 5 redova — prvi koji ima bar jednu numeričku ćeliju je data.
    """
    for i, row in enumerate(table[:5]):
        for cell in row:
            if cell and re.search(r'\d+[.,]\d+|\d{2,}', str(cell)):
                # Provjeri da ovaj red nije header (ne smije biti pun ključnih riječi)
                row_text = " ".join(str(c or "") for c in row).upper()
                header_kw_count = sum(
                    1 for kw in ['QTY', 'PRICE', 'AMOUNT', 'TOTAL', 'QUANTITY',
                                 'DESCRIPTION', 'NAZIV', 'CODE', 'IZNOS']
                    if kw in row_text
                )
                if header_kw_count < 2:
                    return i
    return 1  # Default: preskoči prvi red


# ─────────────────────────────────────────────────────────────────────────────
# POMOĆNE FUNKCIJE
# ─────────────────────────────────────────────────────────────────────────────

def _set_line_numbers(items: List[InvoiceLine]) -> None:
    """Postavi line_no za sve stavke (in-place)."""
    for i, item in enumerate(items, 1):
        if not item.line_no:
            item.line_no = i


def _set_currency(items: List[InvoiceLine], currency: str) -> None:
    """Postavi valutu za sve stavke koje je nemaju (in-place)."""
    for item in items:
        if not item.valuta:
            item.valuta = currency


def _safe_get_cell(row: List[Any], col_idx: Optional[int], default: str = "") -> str:
    """Sigurno dohvati ćeliju iz reda."""
    if col_idx is None or col_idx >= len(row):
        return default
    cell = row[col_idx]
    if cell is None:
        return default
    return str(cell).strip()


def _parse_number(text: str) -> float:
    """
    Parsira broj iz teksta.

    Heuristika za format separatora:
    - "1.234,56" → evropski (tačka=hiljade, zarez=decimale) → 1234.56
    - "1,234.56" → američki (zarez=hiljade, tačka=decimale) → 1234.56
    - "1,234"    → ambiguozno: ako 3 decimale → hiljade (1234), inače decimale (1.234)
    - "1.234"    → ambiguozno: ako 3 decimale → hiljade (1234), inače decimale (1.234)
    """
    if not text:
        return 0.0

    text = str(text).strip()

    # Ukloni valutne simbole i razmake
    text = re.sub(r'[€$£\s]', '', text)
    # Ukloni sve osim cifara, tačke, zareza i minusa
    text = re.sub(r'[^\d,.\-]', '', text)

    if not text or text in ('.', ',', '-'):
        return 0.0

    has_comma = ',' in text
    has_dot = '.' in text

    if has_comma and has_dot:
        # Koji je zadnji separator? To je decimalni.
        last_comma = text.rfind(',')
        last_dot = text.rfind('.')
        if last_dot > last_comma:
            # "1,234.56" — američki format
            text = text.replace(',', '')
        else:
            # "1.234,56" — evropski format
            text = text.replace('.', '').replace(',', '.')
    elif has_comma and not has_dot:
        # Samo zarez — da li je decimalni ili separator hiljada?
        parts = text.split(',')
        if len(parts) == 2 and len(parts[1]) == 3 and parts[0].isdigit():
            # "1,234" — zarez je separator hiljada
            text = text.replace(',', '')
        else:
            # "1,5" ili "1,50" — zarez je decimalni
            text = text.replace(',', '.')
    elif has_dot and not has_comma:
        # Samo tačka — da li je decimalni ili separator hiljada?
        parts = text.split('.')
        if len(parts) == 2 and len(parts[1]) == 3 and parts[0].isdigit():
            # "1.234" — tačka je separator hiljada
            text = text.replace('.', '')
        elif text.count('.') > 1:
            # "1.234.567" — sve tačke su separatori hiljada
            text = text.replace('.', '')
        # inače tačka je decimalni separator (ostavljamo)

    try:
        return float(text)
    except ValueError:
        return 0.0


def _extract_invoice_number(text: str) -> str:
    """Ekstraktuje broj fakture iz teksta. Vraća "" ako nije nađen."""
    patterns = [
        r'Invoice\s*No\.?\s*[:#]?\s*([A-Z0-9][\w\-/]{2,})',
        r'Invoice\s*[:#]\s*([A-Z0-9][\w\-/]{2,})',
        r'Faktura\s*[Bb]r\.?\s*[:#]?\s*([A-Z0-9][\w\-/]{2,})',
        r'Faktura\s*[:#]\s*([A-Z0-9][\w\-/]{2,})',
        r'\bINV[:#\-]\s*([A-Z0-9][\w\-/]+)',   # zahtijeva separator iza INV
        r'\bINVOICE\s+([A-Z0-9][\w\-/]*\d[\w\-/]*)',  # mora sadržati cifru
        r'No\.\s*([A-Z0-9][\w\-/]{3,})',
    ]
    _BLACKLIST = {'DATE', 'FROM', 'TO', 'NUMBER', 'NUMBERS', 'DATED', 'REFERENCE'}
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            val = match.group(1).strip().rstrip('.:,')
            if val and val.upper() not in _BLACKLIST and len(val) >= 2:
                return val
    return ""


def _extract_currency(text: str) -> str:
    """Detektuje valutu iz teksta fakture. Vraća 'EUR' ako nije nađeno."""
    for pattern, code in _CURRENCY_PATTERNS:
        if re.search(pattern, text):
            logger.debug(f"   💱 Detektovana valuta: {code}")
            return code
    return "EUR"


def _extract_weights(text: str) -> Tuple[float, float]:
    """
    Ekstraktuje bruto i neto težinu iz teksta.

    Podržava razne formate: "Gross Weight: 45 kg", "G.W. 45,000",
    "Bruto: 45.000 KG", "Total Gross: 45 kg" itd.
    """
    bruto_kg = 0.0
    neto_kg = 0.0

    bruto_patterns = [
        r'[Gg]ross\s*[Ww]eight\s*[:\-]?\s*([\d\s,\.]+)\s*[Kk][Gg]',
        r'[Gg]ross\s*[Ww]eight\s*[:\-]?\s*([\d\s,\.]+)',
        r'[Bb]ruto\s*[Tt]ežina\s*[:\-]?\s*([\d\s,\.]+)\s*[Kk][Gg]',
        r'[Bb]ruto\s*[:\-]?\s*([\d\s,\.]+)\s*[Kk][Gg]',
        r'[Tt]otal\s+[Gg]ross\s*[:\-]?\s*([\d\s,\.]+)\s*[Kk][Gg]',
        r'G\.?\s*W\.?\s*[:\-]?\s*([\d\s,\.]+)\s*[Kk][Gg]',
        r'G\.?\s*W\.?\s*[:\-]?\s*([\d\s,\.]+)',
    ]
    for pattern in bruto_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            val = _parse_number(match.group(1).replace(' ', ''))
            if val > 0:
                bruto_kg = val
                break

    neto_patterns = [
        r'[Nn]et\s*[Ww]eight\s*[:\-]?\s*([\d\s,\.]+)\s*[Kk][Gg]',
        r'[Nn]et\s*[Ww]eight\s*[:\-]?\s*([\d\s,\.]+)',
        r'[Nn]eto\s*[Tt]ežina\s*[:\-]?\s*([\d\s,\.]+)\s*[Kk][Gg]',
        r'[Nn]eto\s*[:\-]?\s*([\d\s,\.]+)\s*[Kk][Gg]',
        r'[Tt]otal\s+[Nn]et\s*[:\-]?\s*([\d\s,\.]+)\s*[Kk][Gg]',
        r'N\.?\s*W\.?\s*[:\-]?\s*([\d\s,\.]+)\s*[Kk][Gg]',
        r'N\.?\s*W\.?\s*[:\-]?\s*([\d\s,\.]+)',
    ]
    for pattern in neto_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            val = _parse_number(match.group(1).replace(' ', ''))
            if val > 0:
                neto_kg = val
                break

    return bruto_kg, neto_kg


def _detect_exporter(full_text: str) -> str:
    """
    Pokušaj detektovati ime izvoznika iz zaglavlja fakture (prvih 15 redova).
    """
    lines = [l.strip() for l in full_text.split('\n')[:15] if l.strip()]
    for line in lines:
        for prefix in [
            'Seller:', 'Vendor:', 'From:', 'FROM:', 'Exporter:',
            'Prodavac:', 'Dobavljač:', 'Dobavljac:', 'Izvoznik:',
            'Shipper:', 'Supplier:',
        ]:
            if line.upper().startswith(prefix.upper()):
                name = line[len(prefix):].strip()
                if name:
                    return name
    return ""


def _normalize_country(raw: str) -> str:
    """
    Normalizuje naziv/kod zemlje na 2-slovni ISO kod.
    Prihvata 2-slovne kodove direktno, ili mapira poznate nazive.
    """
    raw = raw.strip().upper()
    if not raw:
        return ""

    # Već 2-slovni ISO kod
    if re.match(r'^[A-Z]{2}$', raw):
        return raw

    # Mapiranje najčešćih naziva
    _NAME_MAP = {
        'GERMANY': 'DE', 'DEUTSCHLAND': 'DE',
        'ITALY': 'IT', 'ITALIA': 'IT',
        'FRANCE': 'FR',
        'CHINA': 'CN', 'CHINA (PRC)': 'CN', 'P.R. CHINA': 'CN',
        'TURKEY': 'TR', 'TÜRKIYE': 'TR',
        'AUSTRIA': 'AT', 'ÖSTERREICH': 'AT',
        'SLOVENIA': 'SI',
        'CROATIA': 'HR', 'HRVATSKA': 'HR',
        'SERBIA': 'RS', 'SRBIJA': 'RS',
        'POLAND': 'PL', 'POLSKA': 'PL',
        'CZECH': 'CZ', 'CZECHIA': 'CZ',
        'HUNGARY': 'HU',
        'NETHERLANDS': 'NL', 'HOLLAND': 'NL',
        'BELGIUM': 'BE',
        'SPAIN': 'ES', 'ESPAÑA': 'ES',
        'PORTUGAL': 'PT',
        'SWEDEN': 'SE',
        'DENMARK': 'DK',
        'FINLAND': 'FI',
        'NORWAY': 'NO',
        'SWITZERLAND': 'CH',
        'UNITED STATES': 'US', 'USA': 'US', 'U.S.A.': 'US',
        'UNITED KINGDOM': 'GB', 'UK': 'GB',
        'INDIA': 'IN',
        'JAPAN': 'JP',
        'SOUTH KOREA': 'KR', 'KOREA': 'KR',
        'TAIWAN': 'TW',
        'VIETNAM': 'VN',
        'THAILAND': 'TH',
        'MALAYSIA': 'MY',
        'INDONESIA': 'ID',
        'BOSNA': 'BA', 'BIH': 'BA', 'BOSNIA': 'BA',
        'ALBANIA': 'AL',
        'NORTH MACEDONIA': 'MK', 'MACEDONIA': 'MK',
        'MONTENEGRO': 'ME', 'CRNA GORA': 'ME',
        'KOSOVO': 'XK',
        'ROMANIA': 'RO', 'RUMUNIJA': 'RO',
        'BULGARIA': 'BG', 'BUGARSKA': 'BG',
        'GREECE': 'GR', 'GRČKA': 'GR',
        'UKRAINE': 'UA', 'UKRAINA': 'UA',
        'RUSSIA': 'RU', 'RUSIJA': 'RU',
    }
    return _NAME_MAP.get(raw, "")


# ─────────────────────────────────────────────────────────────────────────────
# ORIGIN STATEMENT DETEKCIJA
# ─────────────────────────────────────────────────────────────────────────────

def _detect_origin_statement(text: str) -> bool:
    """Detektuj da li PDF sadrži izjavu o preferencijalnom poreklu."""
    try:
        from services.tariff.origin_statement_detector import OriginStatementDetector
        detector = OriginStatementDetector()
        result = detector.detect_in_text(text)
        if result:
            logger.info(f"  ✅ Nađena izjava o poreklu: {result.jezik} / {result.tip_izjave}")
            return True
        return False
    except Exception as e:
        logger.warning(f"  ⚠️  Greška tokom detekcije izjave: {e}")
        return False


def _detect_all_origin_statements(text: str) -> List:
    """Detektuj SVE izjave o preferencijalnom poreklu u tekstu."""
    try:
        from services.tariff.origin_statement_detector import OriginStatementDetector
        detector = OriginStatementDetector()
        return detector.detect_all_in_text(text)
    except Exception as e:
        logger.warning(f"  ⚠️  Greška tokom detekcije izjava: {e}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# WORD-BASED FALLBACK (za PDF-ove bez tabela)
# ─────────────────────────────────────────────────────────────────────────────

def _group_words_by_row(words: List[Dict], tolerance: float = 3.0) -> List[List[Dict]]:
    """
    Grupiše pdfplumber words po redovima na osnovu Y koordinate.
    Riječi čiji se 'top' razlikuje za manje od tolerance px idu u isti red.
    """
    if not words:
        return []

    sorted_words = sorted(words, key=lambda w: (round(w['top'] / tolerance), w['x0']))
    rows: List[List[Dict]] = []
    current_row: List[Dict] = [sorted_words[0]]
    current_top = sorted_words[0]['top']

    for word in sorted_words[1:]:
        if abs(word['top'] - current_top) <= tolerance:
            current_row.append(word)
        else:
            rows.append(current_row)
            current_row = [word]
            current_top = word['top']

    if current_row:
        rows.append(current_row)

    return rows


def _find_header_row(rows: List[List[Dict]]) -> Tuple[int, Dict[str, float]]:
    """
    Pronađi red koji izgleda kao header fakture.
    Vraća (index reda, {naziv_kolone: x_pozicija}).
    """
    _HEADER_KW = {
        'qty':   ['qty', 'quantity', 'kolicina', 'količina', 'q-ty', 'menge', 'pcs'],
        'price': ['price', 'cijena', 'unit price', 'preis', 'rate'],
        'total': ['total', 'amount', 'iznos', 'value', 'sum', 'betrag'],
        'desc':  ['description', 'naziv', 'article', 'name', 'roba', 'proizvod',
                  'opis', 'title', 'item', 'goods'],
        'code':  ['code', 'šifra', 'sifra', 'art', 'ref', 'sku', 'no.', 'pos'],
        'origin': ['origin', 'country', 'zemlja', 'poreklo'],
    }

    for row_idx, row in enumerate(rows[:30]):
        text_words = [w['text'].lower().strip('.:') for w in row]
        row_text = ' '.join(text_words)

        matches = 0
        col_positions: Dict[str, float] = {}

        for col_name, keywords in _HEADER_KW.items():
            for kw in keywords:
                if kw in row_text:
                    for w in row:
                        if kw in w['text'].lower():
                            col_positions[col_name] = w['x0']
                            break
                    matches += 1
                    break

        if matches >= 3:
            return row_idx, col_positions

    return -1, {}


def _assign_to_column(word_x: float, col_positions: Dict[str, float]) -> Optional[str]:
    """Dodijeli riječ koloni na osnovu X pozicije (najbliža kolona)."""
    if not col_positions:
        return None
    closest = min(col_positions.items(), key=lambda kv: abs(kv[1] - word_x))
    if abs(closest[1] - word_x) < 80:
        return closest[0]
    return None


def _parse_words_based(pdf_path: str) -> List[InvoiceLine]:
    """
    Text-based extraction koristeći koordinate rijeci (extract_words).
    Funkcioniše na PDF-ovima bez tabelarnih struktura.
    """
    items: List[InvoiceLine] = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                words = page.extract_words(
                    x_tolerance=3, y_tolerance=3, keep_blank_chars=False
                )
                if not words:
                    continue

                rows = _group_words_by_row(words, tolerance=4.0)
                header_idx, col_positions = _find_header_row(rows)

                if header_idx < 0:
                    logger.debug(f"   Stranica {page_num}: header nije pronađen")
                    continue

                logger.debug(
                    f"   Stranica {page_num}: header na redu {header_idx}, "
                    f"kolone: {list(col_positions.keys())}"
                )

                for row in rows[header_idx + 1:]:
                    row_text = ' '.join(w['text'] for w in row).strip()

                    if not row_text:
                        continue
                    if _SKIP_ROW_PREFIXES.match(row_text):
                        continue
                    # Preskoči ponavljajuće headere
                    if header_idx > 0 and _find_header_row([row])[0] >= 0:
                        continue

                    col_texts: Dict[str, List[str]] = {c: [] for c in col_positions}
                    unassigned: List[str] = []

                    for word in row:
                        col = _assign_to_column(word['x0'], col_positions)
                        if col:
                            col_texts[col].append(word['text'])
                        else:
                            unassigned.append(word['text'])

                    desc_parts = col_texts.get('desc', []) + unassigned
                    naziv = ' '.join(desc_parts).strip()
                    code = ' '.join(col_texts.get('code', [])).strip()
                    qty_str = ' '.join(col_texts.get('qty', [])).strip()
                    price_str = ' '.join(col_texts.get('price', [])).strip()
                    total_str = ' '.join(col_texts.get('total', [])).strip()
                    origin_raw = ' '.join(col_texts.get('origin', [])).strip().upper()

                    if not naziv:
                        continue

                    kolicina = _parse_number(qty_str)
                    cijena = _parse_number(price_str)
                    iznos = _parse_number(total_str)

                    if iznos == 0 and kolicina > 0 and cijena > 0:
                        iznos = round(kolicina * cijena, 4)

                    if kolicina <= 0 and cijena <= 0 and iznos <= 0:
                        continue

                    zemlja = _normalize_country(origin_raw) if origin_raw else ""

                    items.append(InvoiceLine(
                        product_code=code,
                        naziv_robe=naziv,
                        kolicina=kolicina,
                        jm="",
                        cijena_jed=cijena,
                        iznos=iznos,
                        zemlja_porijekla=zemlja,
                    ))

    except Exception as e:
        logger.error(f"❌ Text-based extraction greška: {e}")

    return items


def detect_generic_pdf(_pdf_path: str) -> bool:
    """
    Uvijek vraća True — ovo je fallback parser za bilo koji PDF.
    """
    return True
