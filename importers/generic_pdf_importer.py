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


@dataclass
class ColumnMapping:
    """Mapiranje detektovanih kolona u fakturu."""
    product_code: Optional[int] = None  # Index kolone sa šifrom proizvoda
    description: Optional[int] = None   # Index kolone sa nazivom/opisom
    quantity: Optional[int] = None      # Index kolone sa količinom
    unit: Optional[int] = None          # Index kolone sa jedinicom mjere
    unit_price: Optional[int] = None    # Index kolone sa cijenom
    total_price: Optional[int] = None   # Index kolone sa ukupnim iznosom

    def is_valid(self) -> bool:
        """Provjeri da li imamo minimalne podatke za import."""
        return (self.description is not None and
                self.quantity is not None and
                self.unit_price is not None)


def parse_generic_pdf(pdf_path: str) -> ImportResult:
    """
    Parsira bilo koju PDF fakturu automatski.

    Proces:
    1. Ekstraktuje tabele iz PDF-a
    2. Detektuje koju kolonu predstavlja šta (code, naziv, količina, cijena...)
    3. Parsira stavke i kreira ImportResult

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
        # 1. Ekstraktuj tekst za metadata (broj fakture, težine...)
        full_text = ""
        for page in pdf.pages:
            text = page.extract_text() or ""
            full_text += text + "\n"

        # Ekstraktuj broj fakture
        invoice_number = _extract_invoice_number(full_text)

        # Ekstraktuj težine
        bruto_kg, neto_kg = _extract_weights(full_text)

        # DETEKTUJ SVE izjave o poreklu u celom PDF-u
        origin_statements = _detect_all_origin_statements(full_text)
        has_origin_statement = len(origin_statements) > 0
        
        if has_origin_statement:
            logger.info(f"  ✅ Detektovano {len(origin_statements)} izjava o poreklu:")
            for i, stmt in enumerate(origin_statements, 1):
                logger.info(f"     #{i}: {stmt.origin_country} (stavke {stmt.item_range})")
        else:
            logger.info(f"  ℹ️  Nije nađena izjava o poreklu")

        # 2. Ekstraktuj tabele iz svih stranica
        all_tables = []
        for page_num, page in enumerate(pdf.pages, 1):
            tables = page.extract_tables()
            if tables:
                logger.debug(f"   Stranica {page_num}: pronađeno {len(tables)} tabela")
                for table in tables:
                    if table and len(table) > 1:  # Mora imati header + bar jedan red
                        all_tables.append(table)

        if not all_tables:
            logger.warning("⚠️  Nisu pronađene tabele — pokušavam text-based extraction")
            items = _parse_words_based(pdf_path)
            logger.info(f"   Text-based extraction: {len(items)} stavki")
            return ImportResult(
                items=items,
                bruto_kg=bruto_kg,
                neto_kg=neto_kg,
                invoice_name=invoice_number,
                currency="EUR",
                has_origin_statement=has_origin_statement,
                origin_statements=origin_statements
            )

        # 3. Za svaku tabelu, pokušaj detektovati kolone i parsirati stavke
        for table_idx, table in enumerate(all_tables):
            # Detektuj mapiranje kolona
            column_mapping = _detect_columns(table)

            if not column_mapping.is_valid():
                logger.debug(f"   ⏭️  Preskaćem tabelu #{table_idx + 1} - nema dovoljno kolona")
                continue

            logger.debug(f"   ✅ Mapiranje kolona: {column_mapping}")

            # Parsiraj stavke iz tabele
            table_items = _parse_table_items(table, column_mapping)
            items.extend(table_items)
            logger.info(f"   ✅ Izvučeno {len(table_items)} stavki iz tabele #{table_idx + 1}")

    logger.info(f"✅ Ukupno izvučeno {len(items)} stavki")

    return ImportResult(
        items=items,
        bruto_kg=bruto_kg,
        neto_kg=neto_kg,
        invoice_name=invoice_number,
        currency="EUR",
        has_origin_statement=has_origin_statement,
        origin_statements=origin_statements
    )


def _detect_columns(table: List[List[str]]) -> ColumnMapping:
    """
    Automatski detektuje koje kolone predstavljaju šta na osnovu header reda.

    Traži ključne riječi u header redu:
    - Code/Šifra/Art. → product_code
    - Description/Naziv/Article/Proizvod → description
    - Quantity/Količina/Qty/Q-ty → quantity
    - Unit/J.M./U.M. → unit
    - Price/Cijena/Unit Price → unit_price
    - Amount/Iznos/Total → total_price
    """
    if not table or len(table) == 0:
        return ColumnMapping()

    # Prvi red je obično header
    header_row = table[0]

    # Normalize header text
    header_normalized = [
        str(cell).strip().upper() if cell else ""
        for cell in header_row
    ]

    logger.debug(f"   Header: {header_normalized}")

    mapping = ColumnMapping()

    for idx, cell in enumerate(header_normalized):
        # Product code
        if re.search(r'\bCODE\b|\bŠIFRA\b|\bART\b|\bSK[UO]\b', cell):
            mapping.product_code = idx
            logger.debug(f"      Col {idx}: PRODUCT_CODE")

        # Description/Naziv
        elif re.search(r'\bDESCRIPT\w*\b|\bNAZIV\b|\bARTICLE\b|\bPROIZVOD\b|\bNAME\b|\bROBA\b|\bOPIS\b', cell):
            mapping.description = idx
            logger.debug(f"      Col {idx}: DESCRIPTION")

        # Quantity
        elif re.search(r'\bQTY\b|\bQ-TY\b|\bKOLIČINA\b|\bQUANTITY\b|\bKOM\b', cell):
            mapping.quantity = idx
            logger.debug(f"      Col {idx}: QUANTITY")

        # Unit (jedinica mjere)
        elif re.search(r'\bUNIT\b|\bU\.M\b|\bJ\.M\b|\bMJERA\b|\bU\.N\b', cell):
            mapping.unit = idx
            logger.debug(f"      Col {idx}: UNIT")

        # Unit Price — preskačemo kolone koje su zbir/iznos, ali dozvoljavamo "Net Unit Price"
        # NET uz AMOUNT/TOTAL = neto iznos (nije cijena); NET uz PRICE = neto cijena (jeste)
        elif re.search(r'\bUNIT.*PRICE\b|\bPRICE\b|\bCIJENA\b|\bCENA\b', cell) \
                and 'TOTAL' not in cell and 'AMOUNT' not in cell \
                and 'NETO' not in cell \
                and not (('NET' in cell or 'NETO' in cell) and re.search(r'\bAMOUNT\b|\bTOTAL\b|\bIZNOS\b', cell)) \
                and mapping.unit_price is None:
            mapping.unit_price = idx
            logger.debug(f"      Col {idx}: UNIT_PRICE")

        # Total Price/Amount
        elif re.search(r'\bAMOUNT\b|\bTOTAL\b|\bIZNOS\b|\bSUM\b', cell):
            mapping.total_price = idx
            logger.debug(f"      Col {idx}: TOTAL_PRICE")

    # Fallback: ako description nije detektovana, uzmi prvu neprepoznatu kolonu
    # koja nije numerički indeks (Rbr, No, #) jer ti su redni brojevi, ne opisi
    if mapping.description is None:
        used = {mapping.product_code, mapping.quantity, mapping.unit,
                mapping.unit_price, mapping.total_price}
        for idx, cell in enumerate(header_normalized):
            if idx not in used and not re.match(r'^(RBR|R\.BR|NO|BR|#|\d+)$', cell):
                mapping.description = idx
                logger.debug(f"      Col {idx}: DESCRIPTION (fallback)")
                break

    return mapping


def _parse_table_items(table: List[List[str]], mapping: ColumnMapping) -> List[InvoiceLine]:
    """
    Parsira stavke iz tabele koristeći detektovano mapiranje kolona.
    """
    items = []

    # Preskoči header red (prvi red)
    for row_idx, row in enumerate(table[1:], start=2):
        # Skip prazne redove
        if not row or all(not cell or str(cell).strip() == "" for cell in row):
            continue

        # Skip footer redove (TOTAL, UKUPNO, itd.)
        first_cell = str(row[0]).strip().upper() if row else ""
        if any(keyword in first_cell for keyword in ['TOTAL', 'UKUPNO', 'SUM', 'SUBTOTAL']):
            continue

        try:
            # Ekstraktuj podatke prema mapiranju
            product_code = _safe_get_cell(row, mapping.product_code, "")
            description = _safe_get_cell(row, mapping.description, "")
            quantity = _parse_number(_safe_get_cell(row, mapping.quantity, "0"))
            unit = _safe_get_cell(row, mapping.unit, "kom").lower()
            unit_price = _parse_number(_safe_get_cell(row, mapping.unit_price, "0"))
            total_price = _parse_number(_safe_get_cell(row, mapping.total_price, "0"))

            # Validacija: mora imati naziv i količinu/cijenu
            if not description or description.strip() == "":
                continue

            if quantity <= 0 and unit_price <= 0:
                continue

            # Kalkuliši total_price ako nije dat
            if total_price == 0 and quantity > 0 and unit_price > 0:
                total_price = quantity * unit_price

            # Kreiraj InvoiceLine
            item = InvoiceLine(
                product_code=product_code.strip(),
                naziv_robe=description.strip(),
                kolicina=quantity,
                jm=unit.strip(),
                cijena_jed=unit_price,
                iznos=total_price
            )

            items.append(item)
            logger.debug(f"   ✓ Red {row_idx}: {product_code[:20]} | {description[:40]} | {quantity} {unit} × {unit_price}")

        except Exception as e:
            logger.warning(f"   ⚠️  Red {row_idx}: Greška pri parsiranju - {e}")
            continue

    return items


def _safe_get_cell(row: List[Any], col_idx: Optional[int], default: str = "") -> str:
    """Sigurno dohvati ćeliju iz reda."""
    if col_idx is None or col_idx >= len(row):
        return default

    cell = row[col_idx]
    if cell is None:
        return default

    return str(cell).strip()


def _parse_number(text: str) -> float:
    """Parsira broj iz teksta (podržava zareze, tačke, razmake...)."""
    if not text:
        return 0.0

    # Ukloni sve osim cifara, tačke i zareza
    text = re.sub(r'[^\d,.\-]', '', str(text))

    # Zamijeni zarez sa tačkom
    text = text.replace(',', '.')

    # Ako ima više tačaka, prva je separator hiljada
    if text.count('.') > 1:
        parts = text.split('.')
        text = ''.join(parts[:-1]) + '.' + parts[-1]

    try:
        return float(text)
    except ValueError:
        return 0.0


def _extract_invoice_number(text: str) -> str:
    """Ekstraktuje broj fakture iz teksta."""
    patterns = [
        r'Invoice\s*[:#]?\s*([A-Z0-9\-/]+)',
        r'Faktura\s*[:#]?\s*([A-Z0-9\-/]+)',
        r'Invoice\s*No\.?\s*[:#]?\s*([A-Z0-9\-/]+)',
        r'INV[:#]?\s*([A-Z0-9\-/]+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    return "N/A"


def _extract_weights(text: str) -> Tuple[float, float]:
    """
    Ekstraktuje bruto i neto težinu iz teksta.

    Returns:
        Tuple[bruto_kg, neto_kg]
    """
    bruto_kg = 0.0
    neto_kg = 0.0

    # Bruto weight patterns
    bruto_patterns = [
        r'Gross\s*[Ww]eight[:\s]+([\d,\.]+)\s*[Kk]g',
        r'Bruto[^:\n]*[:\s]+([\d,\.]+)\s*[Kk]g',
        r'G\.?W\.?[:\s]+([\d,\.]+)',
    ]

    for pattern in bruto_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            bruto_kg = _parse_number(match.group(1))
            break

    # Neto weight patterns
    neto_patterns = [
        r'Net\s*[Ww]eight[:\s]+([\d,\.]+)\s*[Kk]g',
        r'Neto[:\s]+([\d,\.]+)\s*[Kk]g',
        r'N\.?W\.?[:\s]+([\d,\.]+)',
    ]

    for pattern in neto_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            neto_kg = _parse_number(match.group(1))
            break

    return bruto_kg, neto_kg


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

    Koristi OriginStatementDetector servis za detekciju više izjava.

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


def _group_words_by_row(words: List[Dict], tolerance: float = 3.0) -> List[List[Dict]]:
    """
    Grupiše pdfplumber words po redovima na osnovu Y koordinate.
    Riječi čiji se 'top' razlikuje za manje od tolerance px idu u isti red.
    """
    if not words:
        return []

    # Sortiraj po Y (top), pa X (x0)
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
    Ako header nije nađen, vraća (-1, {}).
    """
    # Ključne riječi koje označavaju header kolona
    _HEADER_KW = {
        'qty': ['qty', 'quantity', 'kolicina', 'količina', 'q-ty', 'menge', 'amount'],
        'price': ['price', 'cijena', 'unit price', 'preis', 'unit', 'rate'],
        'total': ['total', 'amount', 'iznos', 'value', 'sum', 'betrag'],
        'desc': ['description', 'naziv', 'article', 'name', 'roba', 'proizvod', 'opis',
                 'title', 'item', 'goods'],
        'code': ['code', 'šifra', 'sifra', 'art', 'ref', 'sku', 'no.', 'pos'],
    }

    for row_idx, row in enumerate(rows[:30]):  # Pretraži prvih 30 redova
        text_words = [w['text'].lower().strip('.:') for w in row]
        row_text = ' '.join(text_words)

        matches = 0
        col_positions: Dict[str, float] = {}

        for col_name, keywords in _HEADER_KW.items():
            for kw in keywords:
                if kw in row_text:
                    # Pronađi X poziciju te kolone
                    for w in row:
                        if kw in w['text'].lower():
                            col_positions[col_name] = w['x0']
                            break
                    matches += 1
                    break

        if matches >= 3:  # Barem 3 kolone prepoznate
            return row_idx, col_positions

    return -1, {}


def _assign_to_column(word_x: float, col_positions: Dict[str, float]) -> Optional[str]:
    """Dodijeli riječ koloni na osnovu X pozicije (najbliža kolona)."""
    if not col_positions:
        return None
    closest = min(col_positions.items(), key=lambda kv: abs(kv[1] - word_x))
    # Prihvati samo ako je unutar 80px od centra kolone
    if abs(closest[1] - word_x) < 80:
        return closest[0]
    return None


def _parse_words_based(pdf_path: str) -> List[InvoiceLine]:
    """
    Text-based extraction koristeći koordinate rijeci (extract_words).
    Funkcioniše na PDF-ovima bez tabelarnih struktura.

    Pristup:
    1. Dobije sve rijeci sa X/Y koordinatama po stranici
    2. Grupiše u redove (slična Y koordinata)
    3. Traži header red (sa kolonama kao qty/price/total)
    4. Parsiraj stavke ispod headera dodjeljujući rijeci kolonama po X poziciji
    """
    items: List[InvoiceLine] = []

    try:
        import pdfplumber
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

                # Parsiraj redove ispod headera
                for row in rows[header_idx + 1:]:
                    row_text = ' '.join(w['text'] for w in row).strip()

                    # Preskoči prazne i footer redove
                    if not row_text:
                        continue
                    if re.match(
                        r'^(total|ukupno|sum|subtotal|grand|strana|page|footer|vat|pdv)',
                        row_text.lower()
                    ):
                        continue

                    # Preskoči redove koji izgledaju kao ponavljajući header
                    if header_idx > 0 and _find_header_row([row])[0] >= 0:
                        continue

                    # Grupiraj tekst po kolonama
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

                    # Preskoci redove bez opisa
                    if not naziv:
                        continue

                    kolicina = _parse_number(qty_str)
                    cijena = _parse_number(price_str)
                    iznos = _parse_number(total_str)

                    # Kalkuliši iznos ako nedostaje
                    if iznos == 0 and kolicina > 0 and cijena > 0:
                        iznos = round(kolicina * cijena, 4)

                    # Validacija: mora imati barem nešto numerično
                    if kolicina <= 0 and cijena <= 0 and iznos <= 0:
                        continue

                    items.append(InvoiceLine(
                        line_no=len(items) + 1,
                        product_code=code,
                        naziv_robe=naziv,
                        kolicina=kolicina,
                        jm="",
                        cijena_jed=cijena,
                        iznos=iznos,
                        valuta="EUR",
                    ))

    except Exception as e:
        logger.error(f"❌ Text-based extraction greška: {e}")

    return items


def detect_generic_pdf(_pdf_path: str) -> bool:
    """
    Detektuje da li je ovo generički PDF koji može ovaj importer da parsetuje.

    Uvijek vraća True jer je ovo fallback parser za bilo koji PDF.
    """
    return True
