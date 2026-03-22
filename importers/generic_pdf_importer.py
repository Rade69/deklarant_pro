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
            logger.warning("⚠️  Nisu pronađene tabele u PDF-u")
            return ImportResult(
                items=[],
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
        elif re.search(r'\bDESCRIPT|\bNAZIV\b|\bARTICLE\b|\bPROIZVOD\b|\bNAME\b|\bROBA\b', cell):
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

        # Unit Price
        elif re.search(r'\bUNIT.*PRICE\b|\bPRICE\b|\bCIJENA\b|\bCENA\b', cell) and 'TOTAL' not in cell and 'AMOUNT' not in cell:
            mapping.unit_price = idx
            logger.debug(f"      Col {idx}: UNIT_PRICE")

        # Total Price/Amount
        elif re.search(r'\bAMOUNT\b|\bTOTAL\b|\bIZNOS\b|\bSUM\b', cell):
            mapping.total_price = idx
            logger.debug(f"      Col {idx}: TOTAL_PRICE")

    # Ako nemamo description ali imamo samo jednu kolonu sa tekstom, to je verovatno opis
    if mapping.description is None:
        for idx, cell in enumerate(header_normalized):
            if idx not in [mapping.product_code, mapping.quantity, mapping.unit,
                          mapping.unit_price, mapping.total_price]:
                # Ova kolona nije prepoznata, vjerovatno je opis
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
                description=description.strip(),
                quantity=quantity,
                unit_of_measure=unit.strip(),
                unit_price=unit_price,
                total_price=total_price
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
        r'Bruto[:\s]+([\d,\.]+)\s*[Kk]g',
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


def detect_generic_pdf(_pdf_path: str) -> bool:
    """
    Detektuje da li je ovo generički PDF koji može ovaj importer da parsetuje.

    Uvijek vraća True jer je ovo fallback parser za bilo koji PDF.
    """
    return True
