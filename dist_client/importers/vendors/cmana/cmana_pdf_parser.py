"""
Deklarant Pro - CMANA PDF Parser

Parsira CMANA DOO Krnjevo fakture (račun ino kupcu).
Ovo je osnovni parser bez logike za pretragu tarifa - samo ekstrakcija podataka iz PDF-a.

Struktura fakture:
- Header: dobavljač (CMANA), kupac, broj fakture, datum
- Tabela stavki: RBr, Šifra, Naziv artikla, Mera, Količina, Komerc. pak., Koleta, Cena, Iznos, Neto Kg, Bruto Kg
- Footer: ukupno, način plaćanja, način isporuke, bankovni podaci
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

import pdfplumber

from core.draft.draft import InvoiceLine, Party
from importers.import_result import ImportResult
from importers.incoterm_utils import detect_incoterm
from importers.invoice_line_utils import parse_number_thousands_heuristic as _parse_number

logger = logging.getLogger("deklarant_pro.import.cmana_pdf")

# ──────────────────────────────────────────────────────────────────
# RegEx patterni za ekstrakciju metapodataka
# ──────────────────────────────────────────────────────────────────

_INVOICE_NUMBER_RE = re.compile(
    r"RAČUN\s+INO\s+KUPCU\s+br\.\s*([A-Z0-9][\w\-/]{4,})",
    re.IGNORECASE
)

_INVOICE_DATE_RE = re.compile(
    r"od\s+(\d{1,2}\.\d{1,2}\.\d{4})",
    re.IGNORECASE
)

_BRUTO_RE = re.compile(
    r"Bruto\s+masa.*?\([Kk]g\).*?([\d\s\.,]+)",
    re.IGNORECASE
)

_NETO_RE = re.compile(
    r"Neto\s+masa.*?\([Kk]g\).*?([\d\s\.,]+)",
    re.IGNORECASE
)

# Fallback regex za "Bruto Kg" i "Neto Kg" u footeru (npr. "8.694,88 9.842,88")
_BRUTO_FOOTER_RE = re.compile(
    r"([\d.]+,[\d]{2})\s+([\d.]+,[\d]{2})\s*$",
    re.MULTILINE
)

_TOTAL_EUR_RE = re.compile(
    r"Ukupno\s+za\s+plaćanje\s*\(EUR\)\s*[:=]?\s*([\d\s\.,]+)",
    re.IGNORECASE
)

_CMANA_PRODUCT_TARIFFS = {
    "120002": "02071450",
    "120009": "02071360",
    "120028": "02071391",
    "120031": "02071340",
    "120036": "02071110",
    "120052": "02071360",
    "120056": "02071330",
}

# Isti projektni standard kao ostali dobavljači (npr. kg_fashion_importer.py) —
# vidi AGENTS.md "Fuzzy matching threshold: min_similarity = 0.92 (ne spuštati
# bez eksplicitnog razloga)".
_TARIFF_MIN_SIMILARITY = 0.92

# ──────────────────────────────────────────────────────────────────
# Detekcija formata
# ──────────────────────────────────────────────────────────────────

def detect_cmana_pdf(pdf_path: str) -> bool:
    """
    Vraća True ako PDF izgleda kao CMANA faktura.

    Kriteriji:
    - Sadrži 'CMANA DOO KRNJEVO' u headeru
    - Sadrži 'RAČUN INO KUPCU' ili 'Račun ino kupcu'
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Provjeri samo prvu stranicu
            text = pdf.pages[0].extract_text() or ""
        text_upper = text.upper()
        return "CMANA" in text_upper and ("RAČUN" in text_upper or "RACUN" in text_upper)
    except Exception:
        return False


# ──────────────────────────────────────────────────────────────────
# Glavni parser
# ──────────────────────────────────────────────────────────────────

def parse_cmana_pdf(pdf_path: str) -> ImportResult:
    """
    Parsira CMANA PDF fakturu.

    Strategija:
    1. Ekstraktuje tekst iz svih stranica
    2. Ekstraktuje header podatke (broj, datum)
    3. Ekstraktuje tabelu stavki (text-based jer pdfplumber spoji redove)
    4. Ekstraktuje footer podatke (težine, ukupno)

    Returns:
        ImportResult sa stavkama, težinama i metapodacima
    """
    logger.info(f"CMANA PDF parsiranje: {Path(pdf_path).name}")

    invoice_number = ""
    invoice_date = ""
    bruto_kg = 0.0
    neto_kg = 0.0
    total_amount = 0.0

    items: list[InvoiceLine] = []
    all_text = ""

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            all_text += text + "\n"

    logger.debug(f"Extracted text length: {len(all_text)}")

    # Ekstraktuj header podatke
    m = _INVOICE_NUMBER_RE.search(all_text)
    if m:
        invoice_number = m.group(1).strip().rstrip(".")
    xml_tariff_map = _CMANA_PRODUCT_TARIFFS.copy()

    m = _INVOICE_DATE_RE.search(all_text)
    if m:
        invoice_date = m.group(1).strip()

    # Ekstraktuj težine iz footer-a
    m = _NETO_RE.search(all_text)
    if m:
        neto_kg = _parse_number_cmana(m.group(1).replace(" ", ""))
    else:
        # Fallback: traži brojeve u footeru kao "8.694,88 9.842,88"
        # U poslednjem redu sa "EUR" iznosi
        lines = all_text.split("\n")
        for line in reversed(lines):
            if "EUR" in line.upper() and "UKUPNO" in line.upper():
                # U skupu: "UKUPNO 574,0 574 EUR 21.005,09 8.694,88 9.842,88"
                # Neto i bruto su poslednja 2 broja
                m = _BRUTO_FOOTER_RE.search(line)
                if m:
                    # Prvi broj je neto, drugi je bruto (poredani obrnuto u outputu)
                    neto_raw = m.group(1)
                    bruto_raw = m.group(2)
                    neto_kg = _parse_number_cmana(neto_raw)
                    bruto_kg = _parse_number_cmana(bruto_raw)
                    logger.debug(f"  Footer fallback: neto={neto_kg}, bruto={bruto_kg}")
                    break

    m = _BRUTO_RE.search(all_text)
    if m:
        bruto_kg = _parse_number_cmana(m.group(1).replace(" ", ""))

    m = _TOTAL_EUR_RE.search(all_text)
    if m:
        total_amount = _parse_number(m.group(1).replace(" ", ""))

    incoterm_code = detect_incoterm(all_text)  # Rb.20 "Uslovi isporuke"

    # Parsiraj stavke iz teksta (table extraction je prelomljena)
    # Tražimo redove koji počinju brojem stavke (1-99)
    lines = all_text.split("\n")
    item_lines = []

    for i, line in enumerate(lines):
        # Red mora početi brojem stavke (1-99)
        # Preskoči header (RBr Šifra Naziv...)
        if re.match(r'^\s*(\d{1,2})\s+(\d{5,6})\s+', line):
            item_lines.append(line.strip())

    logger.debug(f"Pronađeno {len(item_lines)} potencijalnih stavki")

    # Parsiraj svaku stavku direktno iz reda
    line_no = 0
    for item_text in item_lines:
        try:
            # Format: "1 120002 Pileći File KG 3.110,480 204,0 204 3,9800 12.379,71 3.110,48 3.518,47"
            # RBr CodeNazivJM Qty Packets Koleta Price Total Neto Bruto

            # Ekstraktuj RBr i Code
            m = re.match(r'^(\d{1,2})\s+(\d{5,6})\s+(.+?)\s+KG\s+(.+)$', item_text, re.IGNORECASE)
            if not m:
                logger.debug(f"  Preskačem red koji ne odgovara formatu: {item_text[:50]}")
                continue

            line_no = int(m.group(1))
            code = m.group(2)
            # Naziv je između Code i KG
            desc_before_kg = m.group(3)
            # Ostatci su posle KG
            numbers_part = m.group(4)

            # Ekstraktuj opis (može imati BH u sebi)
            description = desc_before_kg.strip()

            # Ekstraktuj brojeve iz numbers_part
            # Format: "3.110,480 204,0 204 3,9800 12.379,71 3.110,48 3.518,47"
            # Qty Packets Koleta Price Total Neto Bruto
            # CMANA koristi evropski format sa tačkom kao separatorom hiljada
            num_matches = re.findall(r'\d[\d.,]*', numbers_part)
            numbers = []
            for n in num_matches:
                clean = n.strip()
                num_val = _parse_number_cmana(clean)
                # Prihvati sve brojeve (npr. 23 paketa, 204 koleta, 392.32 bruto)
                if num_val >= 0:  # Prihvati sve pozitivne brojeve
                    numbers.append(num_val)

            logger.debug(f"  Red {line_no} brojevi: {numbers}")

            if len(numbers) < 5:
                logger.debug(f"  Preskačem red bez dovoljno brojeva: {item_text[:50]}")
                continue

            # Očekivano: Qty, Packets, Koleta, Price, Total, Neto, Bruto (7 brojeva)
            if len(numbers) >= 7:
                qty = numbers[0]
                unit_price = numbers[3]
                total = numbers[4]
                neto = numbers[5]
                bruto = numbers[6]
            elif len(numbers) >= 5:
                # Možda pack/koleta nisu jasni
                qty = numbers[0]
                unit_price = numbers[2] if len(numbers) > 2 else 0
                total = numbers[3] if len(numbers) > 3 else 0
                neto = numbers[4] if len(numbers) > 4 else 0
                bruto = 0
            else:
                continue

            # Validacija
            if not code or not description:
                continue

            # Provjera u XML mapiranjima ako postoji tarifni broj za ovu šifru
            tariff_from_xml = _CMANA_PRODUCT_TARIFFS.get(code) or xml_tariff_map.get(code, "")
            logger.debug(f"  Lookup XML tariff za šifru {code}: {tariff_from_xml!r}")

            # Ako nije pronađen tariff na osnovu šifre, probaj pronaći na osnovu naziva proizvoda
            if not tariff_from_xml and description:
                tariff_by_name, similarity = get_tariff_codes_for_product_name(description)
                if tariff_by_name and similarity >= _TARIFF_MIN_SIMILARITY:
                    logger.debug(f"  Lookup XML tariff po nazivu: {tariff_by_name!r}, similarity={similarity:.2f} za '{description[:50]}...')")
                    tariff_from_xml = tariff_by_name

            item = InvoiceLine(
                line_no=line_no,
                product_code=code,
                naziv_robe=description,
                kolicina=qty,
                jm="kg",  # CMANA fakture su u kg
                cijena_jed=unit_price,
                iznos=total,
                valuta="EUR",
                neto_kg=neto,
                bruto_kg=bruto,
                tarifni_broj=tariff_from_xml if tariff_from_xml else "",  # Dodaj tarifni broj iz XML-a ako postoji
                zemlja_porijekla="RS",
                country_confidence="HIGH",
                country_source="PDF",
                raw={
                    "eur1_suggested": True,
                    "has_origin_statement": False,
                },
            )
            items.append(item)

        except (IndexError, ValueError) as e:
            logger.debug(f"  Greška pri parsiranju reda: {e}")
            continue

    logger.info(
        f"  Header: faktura={invoice_number!r}, datum={invoice_date!r}, "
        f"bruto={bruto_kg:.3f}kg, neto={neto_kg:.3f}kg"
    )
    logger.info(f"  ✅ Parsed {len(items)} stavki, ukupno={total_amount:.2f} EUR")

    # Eksporter je uvijek CMANA
    exporter = Party(name="CMANA DOO KRNJEVO")

    return ImportResult(
        items=items,
        bruto_kg=bruto_kg,
        neto_kg=neto_kg,
        invoice_name=invoice_number,
        currency="EUR",
        import_type="cmana",
        exporter=exporter,
        incoterm_code=incoterm_code,
    )


# ──────────────────────────────────────────────────────────────────
# Pomoćne funkcije
# ──────────────────────────────────────────────────────────────────

def _parse_number_cmana(text: str) -> float:
    """
    Parsira broj iz teksta za CMANA format (evropski sa tačkom kao separatorom hiljada).

    CMANA koristi format:
    - "12.379,71" → 12379.71 (tačka=hiljade, zarez=decimale)
    - "346,316" → 346.316 (zarez=decimale)
    - "3.518,47" → 3518.47 (tačka=hiljade, zarez=decimale)
    """
    if not text:
        return 0.0

    text = str(text).strip()
    text = re.sub(r'[€$£\s]', '', text)
    text = re.sub(r'[^\d,.\-]', '', text)

    if not text or text in ('.', ',', '-', ''):
        return 0.0

    has_comma = ',' in text
    has_dot = '.' in text

    if has_comma and has_dot:
        # "12.379,71" - evropski format (tačka=hiljade, zarez=decimale)
        text = text.replace('.', '').replace(',', '.')
    elif has_comma and not has_dot:
        # "346,316" - zarez je decimalni separator (346.316)
        text = text.replace(',', '.')
    elif has_dot and not has_comma:
        # "638.500" - tačka je separator hiljada (638500)
        if text.count('.') > 1:
            text = text.replace('.', '')
        elif text.count('.') == 1:
            parts = text.split('.')
            if len(parts) == 2 and len(parts[1]) == 3 and parts[0].isdigit():
                text = text.replace('.', '')
            # inače tačka je decimalni separator (ostavljamo)

    try:
        return float(text)
    except ValueError:
        return 0.0



def get_tariff_codes_for_invoice(invoice_number: str) -> dict[str, str]:
    """
    Vraća mapping između šifri proizvoda iz XML-a i tarifnih brojeva za dati broj računa.

    Ova funkcionalnost omogućava iskorišćavanje historijskih XML
    deklaracija za automatsko popunjavanje tarifnih brojeva iz PDF-a.
    """
    import psycopg2
    from config.settings import get_db_settings

    settings = get_db_settings()
    try:
        conn = psycopg2.connect(
            host=settings.host,
            port=settings.port,
            dbname=settings.database,
            user=settings.user,
            password=settings.password
        )
        cur = conn.cursor()

        # Tražimo tarifne mape za dati broj računa - koristimo product_code da nađemo tariff
        cur.execute("""
            SELECT product_code, commodity_code
            FROM catalogs.product_tariff_mapping
            WHERE product_code = %s
            AND supplier LIKE '%%CMANA%%'
        """, (invoice_number,))

        results = cur.fetchall()
        return {row[0]: row[1] for row in results}  # {invoice_number: tariff_code}

    except Exception:
        return {}  # Ako nije pronađeno ili greška, vraćamo prazno
    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass


def get_tariff_codes_for_product_name(product_name: str) -> tuple[str, float]:
    """
    Vraća najbolji tariff code za dani naziv proizvoda sa CMANA kataloga koristeći fuzzy matching.

    Returns:
        Tuple (tariff_code, similarity_score) najbolje poklapanje
    """
    import psycopg2
    from config.settings import get_db_settings
    import difflib

    settings = get_db_settings()
    try:
        conn = psycopg2.connect(
            host=settings.host,
            port=settings.port,
            dbname=settings.database,
            user=settings.user,
            password=settings.password
        )
        cur = conn.cursor()

        # Dohvati sve nazive proizvoda iz CMANA kataloga
        cur.execute("""
            SELECT naziv_robe, commodity_code
            FROM catalogs.product_tariff_mapping
            WHERE supplier LIKE '%%CMANA%%'
        """)

        all_products = cur.fetchall()

        # Izdvoji nazive za matching
        names = [prod[0] for prod in all_products]

        if not names:
            return "", 0.0

        # Nađi najbolje poklapanje koristeći difflib SequenceMatcher
        matcher = difflib.SequenceMatcher()
        matcher.set_seq2(product_name.lower())

        best_match = ""
        best_score = 0.0

        for name in names:
            matcher.set_seq1(name.lower())
            score = matcher.ratio()
            if score > best_score:
                best_score = score
                best_match = name

        if best_match and best_score >= _TARIFF_MIN_SIMILARITY:
            # Pronađi odgovarajući tariff code za najbolji match
            for stored_name, tariff_code in all_products:
                if stored_name == best_match:
                    return tariff_code, best_score

        return "", 0.0  # nije pronađeno

    except Exception as e:
        print(f"Error u get_tariff_codes_for_product_name: {e}")
        return "", 0.0
    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass
