"""
PIP Food Group PDF Parser

Parsira PDF fakture PIP Food Group doo Novi Sad.
Format: tabela sa kolonama: R.br., Naziv, Tarifni broj, JM, Izlaz, Cena bruto, Rabat %, Cena neto, Iznos EUR
"""

import logging
import re
from typing import List, Dict, Any, Optional
import pdfplumber

from core.draft.draft import InvoiceLine, Party
from importers.import_result import ImportResult

logger = logging.getLogger("deklarant_pro.import.pip_food")


def _extract_invoice_number(full_text: str) -> str:
    """
    Ekstraktuje broj prve fakture iz teksta (za ImportResult invoice_name).
    
    Format: Faktura: IF0520/26-02
    
    Ako ima više faktura, vraća prvu koju pronađe.
    """
    patterns = [
        r'Faktura[:#]?\s*([A-Z0-9][A-Z0-9./\-_]*)',
        r'Invoice[:#]?\s*([A-Z0-9][A-Z0-9./\-_]*)',
        r'Invoice[:#]?\s*No\.?\s*[:#]?\s*([A-Z0-9][A-Z0-9./\-_]*)',
        r'Br\.?\s*fakture[:#]?\s*([A-Z0-9][A-Z0-9./\-_]*)',
    ]
    for pattern in patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            val = match.group(1).strip().rstrip(':.,')
            if val:
                return val
    return ""


def _extract_date(full_text: str) -> str:
    """
    Ekstraktuje datum iz fakture.
    
    Format: Datum: 20.05.2026
    """
    patterns = [
        r'Datum[:#]?\s*([0-9]{1,2}\.[0-9]{1,2}\.[0-9]{4})',
        r'Date[:#]?\s*([0-9]{1,2}\.[0-9]{1,2}\.[0-9]{4})',
    ]
    for pattern in patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""


def parse_pip_food_pdf(pdf_path: str) -> ImportResult:
    """
    Parsira PIP Food Group PDF fakturu.
    
    Format tabele:
    R.br. | Naziv | Tarifni broj | JM | Izlaz | Cena bruto | Rabat % | Cena neto | Iznos EUR
    
    Primer:
    1 FROSTY GOLD 10/1 2106909890 KG 600,00 3,2500 0,00 3,2500 1.950,00
    
    Args:
        pdf_path: Putanja do PDF fajla
        
    Returns:
        ImportResult sa parsiranim stavkama
    """
    logger.info(f"Parsing PIP Food Group PDF: {pdf_path}")
    
    items: List[InvoiceLine] = []
    invoice_number = ""
    current_invoice_number = ""
    invoice_date = ""
    
    with pdfplumber.open(pdf_path) as pdf:
        full_text = ""
        
        # Extract text from all pages
        for page in pdf.pages:
            text = page.extract_text() or ""
            full_text += text + "\n"
        
        invoice_number = _extract_invoice_number(full_text)
        if invoice_number:
            logger.debug(f"Invoice number: {invoice_number}")
        
        invoice_date = _extract_date(full_text)
        if invoice_date:
            logger.debug(f"Invoice date: {invoice_date}")
        
        # Parse items from text
        lines = full_text.split('\n')
        
        # Pattern za redove sa stavkama:
        # R.br. Naziv Tarifni broj JM Izlaz Cena bruto Rabat % Cena neto Iznos EUR
        # 1 FROSTY GOLD 10/1 2106909890 KG 600,00 3,2500 0,00 3,2500 1.950,00
        # 1 SVEŽI PEKARSKI KVASAC KG 2.800,00 0,6900 0,00 0,6900 1.932,00 (nema tarifni broj)
        #
        # Napomena: "Tarifni broj" može biti 8-10 cifara ili odsutan
        # "Rabat %" je uvek 0,00 za PIP fakture (trenutno)
        #
        # Regex objašnjenje:
        # - (\d+) : redni broj
        # - (.+?) : naziv (lazy match)
        # - (?:\s+(\d{8,10}))? : opcionalni tarifni broj (8-10 cifara)
        # - (\s+[A-Z]{2,4}) : jedinica mere
        # - ([\d,\.]+) : izlaz/količina
        # - ([\d,\.]+) : cena bruto
        # - ([\d,\.]+) : rabat %
        # - ([\d,\.]+) : cena neto
        # - ([\d\.\,]+) : iznos EUR
        
        item_pattern = re.compile(
            r'^(\d+)\s+(.+?)\s+(?:\s*(\d{8,10})\s+)?([A-Z]{2,4})\s+([\d,\.]+)\s+([\d,\.]+)\s+([\d,\.]+)\s+([\d,\.]+)\s+([\d,\.]+)$',
            re.IGNORECASE
        )
        
        current_item = None
        
        for line in lines:
            line = line.strip()
            
            # Detektuj novu fakturu i ažuriraj current_invoice_number
            invoice_match = re.search(r'Faktura[:#]?\s*([A-Z0-9][A-Z0-9./\-_]*)', line, re.IGNORECASE)
            if invoice_match:
                current_invoice_number = invoice_match.group(1).strip().rstrip(':.,')
                logger.debug(f"Novi broj fakture: {current_invoice_number}")
                continue  # Skip header red sa fakturom
            
            # Skip header i prazne linije
            if not line:
                continue
            if any(x in line for x in ['R.br.', 'Naziv', 'Tarifni', 'JM', 'Izlaz', 'Cena bruto', 'Rabat', 'Cena neto', 'Iznos', 'EUR']):
                if 'R.br.' in line and any(x in line for x in ['Tarifni', 'JM', 'Cena']):
                    continue  # Ovo je header
            
            # Check if this is a new item line
            match = item_pattern.match(line)
            
            if match:
                # Save previous item if exists
                if current_item:
                    items.append(current_item)
                
                # Parse new item
                line_no = int(match.group(1))
                naziv = match.group(2).strip()
                tarifni_broj = match.group(3).strip() if match.group(3) else ""
                jedinica_mere = match.group(4).upper()
                kolicina_str = match.group(5)
                cena_bruto_str = match.group(6)
                rabat_str = match.group(7)
                cena_neto_str = match.group(8)
                iznos_str = match.group(9)
                
                kolicina = _parse_number(kolicina_str)
                cena_bruto = _parse_number(cena_bruto_str)
                rabat = _parse_number(rabat_str)
                cena_neto = _parse_number(cena_neto_str)
                iznos = _parse_number(iznos_str)
                
                current_item = InvoiceLine(
                    line_no=line_no,
                    invoice_number=current_invoice_number,
                    product_code="",  # PIP ne šalje šifre, koristimo naziv kao identifikator
                    naziv_robe=naziv,
                    jm=jedinica_mere,
                    kolicina=kolicina,
                    cijena_jed=cena_neto,
                    iznos=iznos,
                    valuta="EUR",
                    tarifni_broj=tarifni_broj,
                    zemlja_porijekla="",  # Izjave o poreklu se nalaze u posebnom tekstu
                    bruto_kg=0.0,
                    neto_kg=0.0,
                )
                
                logger.debug(f"Parsed item {line_no}: {naziv[:50]} - {kolicina} x {cena_neto} = {iznos}")
                
                # Cistimo "Ser. br." i "Najbolje upotrebiti" iz naziva (to su meta podaci o pakovanju)
                # Ovi podaci su već u nazivu jer se nalaze u istom redu u PDF-u
                naziv_ciscen = _clean_pip_naziv(naziv)
                if naziv_ciscen != naziv:
                    logger.debug(f"   Cleaned naziv: {naziv_ciscen[:50]}")
                current_item.naziv_robe = naziv_ciscen
                
            elif current_item and line:
                # Multi-line description continuation
                # Provjeravamo da li je ovo nastavak opisa ili footer ili novi header
                line_upper = line.upper()
                
                # Skip footer redove
                _skip_keywords = [
                    'UKUPNO', 'RABAT', 'STRANA', 'STRANA', 'O.O.',
                    'TEL:', 'FAX:', 'EMAIL:', 'PIB:', 'MATIČNI', 'MATICNI',
                    'TEKUCI', 'TEKUCI', 'RAČUN', 'RAČUN', 'ADRESA',
                    'NAPOMENA', 'INSTRUKCIJE', 'HIGIJENA', 'NETO TEŽINA',
                    'BRUTO TEŽINA', 'BRUTO SA', 'BROJ PALETA',
                    'FAKTURISAO', 'OTP BANKA', 'IBAN', 'PARITET', 'VOZILO',
                    'BL 4', 'Astrum', 'DALIBOR', 'BOMEŠTAR', 'DEKOR', 'AURORA',
                    'SER. BR.', 'SERIJSKI', 'SERIJSKI', 'SERBR',
                    'NAJBO LJ UPOTREBITI', 'NAJBO LJ', 'NAJBOLJE',
                    'Najbolje upotrebiti', 'NAJBO LJ DO',
                    'PIP FOOD', 'PIP 92', 'LAKTAŠI', 'OSLOBO', 'PDV',
                    'ZAKONA', 'SL. GLASNIK'
                ]
                
                # Proveri da li je ovo novi header (novi faktura)
                if 'FAKTURA' in line_upper or 'INVOICE' in line_upper or 'PIP FOOD' in line_upper:
                    # Resetuj current_item jer počinje nova faktura
                    if current_item:
                        items.append(current_item)
                        current_item = None
                    continue
                
                if not any(kw in line_upper for kw in _skip_keywords):
                    # Ovo je nastavak opisa (npr. serijski brojevi)
                    current_item.naziv_robe += " " + line.strip()
        
        # Add last item
        if current_item:
            items.append(current_item)
        
        # Extract totals
        ukupno_match = re.search(r'Ukupno\s+bez\s+rabata[:#]?\s*([\d\.\,]+)', full_text, re.IGNORECASE)
        ukupno_eur_match = re.search(r'Ukupno\s+EUR[:#]?\s*([\d\.\,]+)', full_text, re.IGNORECASE)
        
        bruto_kg = 0.0
        neto_kg = 0.0
        
        # Extract weights
        bruto_patterns = [
            r'[Bb]ruto\s+[Tt]ežina[:#]?\s*([\d\.\,]+)\s*[Kk][Gg]',
            r'[Bb]ruto[:#]?\s*([\d\.\,]+)\s*[Kk][Gg]',
            r'[Tt]otal\s+[Bb]ruto[:#]?\s*([\d\.\,]+)\s*[Kk][Gg]',
            r'[Bb]ruto\s+[Ww]eight[:#]?\s*([\d\.\,]+)\s*[Kk][Gg]',
        ]
        
        for pattern in bruto_patterns:
            match = re.search(pattern, full_text)
            if match:
                bruto_kg = _parse_number(match.group(1))
                break
        
        neto_patterns = [
            r'[Nn]eto\s+[Tt]ežina[:#]?\s*([\d\.\,]+)\s*[Kk][Gg]',
            r'[Nn]eto[:#]?\s*([\d\.\,]+)\s*[Kk][Gg]',
            r'[Tt]otal\s+[Nn]eto[:#]?\s*([\d\.\,]+)\s*[Kk][Gg]',
            r'[Nn]et\s+[Ww]eight[:#]?\s*([\d\.\,]+)\s*[Kk][Gg]',
        ]
        
        for pattern in neto_patterns:
            match = re.search(pattern, full_text)
            if match:
                neto_kg = _parse_number(match.group(1))
                break
        
        # Extract palettes count
        palettes_match = re.search(r'[Bb]roj\s+[Pp]aleta[:#]?\s*(\d+)', full_text, re.IGNORECASE)
        palettes_count = int(palettes_match.group(1)) if palettes_match else 0
        
        logger.debug(f"Weights: Bruto={bruto_kg} kg, Neto={neto_kg} kg, Palettes={palettes_count}")
        
        # DETEKTUJ SVE izjave o poreklu
        origin_statements = _detect_all_origin_statements(full_text)
        has_origin_statement = len(origin_statements) > 0
        logger.info(f"  ✅ Detekcija izjave o poreklu: {has_origin_statement} ({len(origin_statements)} izjava)")
        
        # PIP fakture nemaju inline izjave o poreklu u tekstu (samo generalna napomena)
        # Zato ne mapiramo po stavkama - svi artikli su istog porekla ili nema izjave
        
        if has_origin_statement:
            for item in items:
                item.has_origin_statement = True
                item.raw["has_origin_statement"] = True
        else:
            for item in items:
                item.raw["has_origin_statement"] = False
        
        # Distribuiraj težine proporcionalno po iznosima
        if items and (bruto_kg > 0 or neto_kg > 0):
            total_amount = sum(item.iznos for item in items)
            if total_amount > 0:
                for item in items:
                    proportion = item.iznos / total_amount
                    item.bruto_kg = round(proportion * bruto_kg, 4)
                    item.neto_kg = round(proportion * neto_kg, 4)
                logger.debug(f"Distributed weights proportionally across {len(items)} items")
        
        logger.info(f"Parsed {len(items)} items from PIP Food PDF")
        
    # Create exporter/importer parties
    # PIP Food Group doo Novi Sad je dobavljač (exporter)
    # ''PIP 92'' D.O.O. LAKTAŠI je kupac (importer)
    
    _exp = Party(
        name="PIP Food Group doo Novi Sad",
        address="Salaš 280, 21233 Čenej, Srbija",
    )
    
    _imp = Party(
        name="'PIP 92' D.O.O. LAKTAŠI",
        address="Prnjavorski put 7, Čardačani, 78250 Laktaši",
    )
    
    for item in items:
        item.exporter = _exp
        item.importer = _imp
    
    return ImportResult(
        items=items,
        bruto_kg=bruto_kg,
        neto_kg=neto_kg,
        invoice_name=invoice_number,
        currency="EUR",
        import_type='pip_food_pdf',
        has_origin_statement=has_origin_statement,
        origin_statements=origin_statements,
        exporter=_exp,
        importer=_imp,
    )


def _clean_pip_naziv(naziv: str) -> str:
    """
    Čisti PIP naziv robe od meta podataka o pakovanju.
    
    U PIP fakturama, serijski brojevi i datumi često idu u isti red
    kao naziv robe. Ova funkcija uklanja te podatke iz naziva.
    
    Primeri:
    - "FROSTY GOLD 10/1 Ser. br.: 260519-17003" → "FROSTY GOLD 10/1"
    - "HAMBI MIX VEGE 10/1 Ser. br.: 260519-19002 Najbolje upotrebiti do: 13.02.2027" → "HAMBI MIX VEGE 10/1"
    """
    # Ukloni "Ser. br." i sve nakon njega
    naziv = re.split(r'\s*Ser\.\s*br\.[:\s]', naziv, flags=re.IGNORECASE)[0]
    
    # Ukloni "Najbolje upotrebiti do:" i sve nakon njega
    naziv = re.split(r'\s*Najbolje\s+upotrebiti\s+do[:\s]', naziv, flags=re.IGNORECASE)[0]
    
    # Ukloni dodatne razmake na početku i kraju
    naziv = naziv.strip()
    
    return naziv


def _parse_number(s: str) -> float:
    """
    Parsira broj iz stringa (podržava evropski i US format).
    
    Formati:
    - Evropski: "1.920,00" (tačka=hiljade, zarez=decimale)
    - US: "1,920.00" (zarez=hiljade, tačka=decimale)
    - Jednostavan: "1920,00" ili "1920.00"
    """
    if not s:
        return 0.0
    
    s = str(s).strip()
    
    # Ukloni valutne simbole i razmake
    s = re.sub(r'[€$£\s]', '', s)
    
    if not s or s in ('.', ',', '-'):
        return 0.0
    
    has_comma = ',' in s
    has_dot = '.' in s
    
    if has_comma and has_dot:
        # Koji je zadnji separator? To je decimalni.
        last_comma = s.rfind(',')
        last_dot = s.rfind('.')
        
        if last_dot > last_comma:
            # "1,920.00" — US format (tačka je decimalni)
            s = s.replace(',', '')
        else:
            # "1.920,00" — evropski format (zarez je decimalni)
            s = s.replace('.', '').replace(',', '.')
    elif has_comma and not has_dot:
        # Samo zarez — ako je 3 cifre posle, onda je separator hiljada
        parts = s.split(',')
        if len(parts) == 2 and len(parts[1]) == 3 and parts[0].isdigit():
            s = s.replace(',', '')
        else:
            s = s.replace(',', '.')
    elif has_dot and not has_comma:
        # Samo tačka
        parts = s.split('.')
        if len(parts) == 2 and len(parts[1]) == 3 and parts[0].isdigit():
            # "1.234" — separator hiljada
            s = s.replace('.', '')
        elif s.count('.') > 1:
            # "1.234.567" — sve tačke su separatori hiljada
            s = s.replace('.', '')
    
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def detect_pip_food_pdf(filepath: str) -> bool:
    """
    Detektuje da li je PDF PIP Food Group format.
    
    Kriteriji:
    - Sadrži "PIP Food Group"
    - Sadrži "Faktura:" ili "Invoice:"
    - Sadrži kolone kao što su "R.br.", "Tarifni broj", "Iznos EUR"
    
    Args:
        filepath: Putanja do PDF fajla
        
    Returns:
        True ako je PIP Food Group PDF
    """
    try:
        with pdfplumber.open(filepath) as pdf:
            if not pdf.pages:
                return False
            
            # Check first page
            text = pdf.pages[0].extract_text() or ""
            
            # Check for PIP Food signature
            has_pip_food = ("PIP Food Group" in text or 
                          "PIP Food" in text and "Group" in text)
            
            # Check for invoice format
            has_invoice = ("Faktura:" in text or "Invoice:" in text or 
                          "FAKTURA" in text or "INVOICE" in text)
            
            # Check for table headers
            has_table_headers = any(x in text for x in 
                ['R.br.', 'Tarifni broj', 'Iznos EUR', 'Cena bruto'])
            
            # Check for common PIP identifiers
            has_pip_identifier = ("PIP 92" in text or 
                                 "PIP CORN" in text or 
                                 "FROSTY GOLD" in text or
                                 "EXTRA FRESH" in text)
            
            # Check for PIB pattern (112655385 je PIP Food Group PIB)
            has_pip_pib = "112655385" in text
            
            # DETECTION: PIP Food Group + (invoice ILI faktura) + (table ILI PIB)
            if has_pip_food and (has_invoice or has_pip_identifier) and (has_table_headers or has_pip_pib):
                logger.debug(f"✅ PIP Food PDF detected")
                return True
        
        logger.debug(f"❌ Not PIP Food PDF")
        return False
        
    except Exception as e:
        logger.warning(f"Error detecting PIP Food PDF: {e}")
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


# ============================================================
# USAGE EXAMPLE
# ============================================================

if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    # Add project root to path
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))
    
    # Test
    test_file = "najavauvoza/PIP92.pdf"
    
    logger.debug("\n" + "=" * 70)
    logger.debug("PIP FOOD GROUP PDF PARSER - Test")
    logger.debug("=" * 70 + "\n")
    
    try:
        # Test detection
        is_pip = detect_pip_food_pdf(test_file)
        logger.debug(f"Detection: {is_pip}")
        
        if is_pip:
            # Test parsing
            result = parse_pip_food_pdf(test_file)
            
            logger.info(f"\n✅ Parsed: {len(result.items)} items")
            logger.debug(f"Invoice: {result.invoice_name}")
            logger.debug(f"Currency: {result.currency}")
            logger.debug(f"Bruto: {result.bruto_kg} kg, Neto: {result.neto_kg} kg")
            
            logger.debug(f"\nPrvih 5 stavki:")
            for i, item in enumerate(result.items[:5], 1):
                logger.debug(f"\n{i}. Naziv: {item.naziv_robe[:60]}")
                logger.debug(f"   Tarifni: {item.tarifni_broj}")
                logger.debug(f"   Qty: {item.kolicina} {item.jm}, Price: {item.cijena_jed} EUR, Amount: {item.iznos} EUR")
                
    except Exception as e:
        logger.error(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
