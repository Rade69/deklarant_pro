# importers/blagic_attos_importer.py

"""
Blagić Attos Importer
Specijalizovan parser za Blagić fakture od ATTOS dobavljača (Novi Sad).

Format:
- PDF Faktura (RAČUN-OTPREMNICA): sadrži cijene, bez težina i porekla po stavci
- PDF Lista pakovanja: sadrži težine i poreklo, bez cijena

Auto-kombinacija: Automatski pronalazi i kombinuje oba PDF-a
- Faktura: "Faktura 3940 Blagić.pdf"
- Lista pakovanja: "Lista pakovanja 3940 Blagić.pdf"
"""

import os
import logging
import re
from typing import List, Optional, Tuple, Dict
from pathlib import Path

import pdfplumber

from core.draft.draft import InvoiceLine, Party
from importers.import_result import ImportResult
from importers.incoterm_utils import detect_incoterm
from importers.invoice_line_utils import KNOWN_JM, parse_eu_number, parse_invoice_tail, parse_packing_tail
from utils.country_normalizer import normalize_country_name

logger = logging.getLogger("deklarant_pro.import.blagic_attos")


def detect_blagic_attos_pdf(filepath: str) -> bool:
    """
    Detekcija Blagic-Attos formata.

    Kriteriji:
    - PDF dokument
    - Sadržaj sadrži "RAČUN-OTPREMNICA" ili "LISTA PAKOVANJA"
    - Sadržaj sadrži "ATTOS" ili "Novi Sad"
    - Sadržaj sadrži "Blagić" ili "BLAGIĆ"

    Args:
        filepath: Putanja do PDF fajla

    Returns:
        True ako je Blagic-Attos format
    """
    try:
        if not filepath.lower().endswith('.pdf'):
            return False

        # Provjeri cache (populiran od _detect_pdf_format ako je već parsiran)
        from importers.smart_pdf_importer import get_cached_pdf_text
        cached = get_cached_pdf_text(filepath)
        if cached:
            text, text_upper, text_norm = cached
        else:
            with pdfplumber.open(filepath) as pdf:
                text = pdf.pages[0].extract_text() or ""
                text_upper = text.upper()

        has_document_type = ("RAČUN-OTPREMNICA" in text_upper or
                            "RACUN-OTPREMNICA" in text_upper or
                            "LISTA PAKOVANJA" in text_upper)
        has_supplier = "ATTOS" in text_upper or "NOVI SAD" in text_upper
        has_customer = "BLAGIĆ" in text_upper or "BLAGIC" in text_upper

        if has_document_type and has_supplier and has_customer:
            logger.info(f"Blagic-Attos format detektovan: {filepath}")
            return True

        return False

    except Exception as e:
        logger.warning(f"Greška tokom detekcije Blagic-Attos formata: {e}")
        return False


def is_blagic_attos_packing_list(filepath: str) -> bool:
    """Provjerava da li je PDF packing list umjesto fakture."""
    try:
        fname = Path(filepath).name.lower()
        if "lista pakovanja" in fname:
            return True
        from importers.smart_pdf_importer import get_cached_pdf_text
        cached = get_cached_pdf_text(filepath)
        if cached:
            _, text_upper, _ = cached
            return "LISTA PAKOVANJA" in text_upper
        with pdfplumber.open(filepath) as pdf:
            text = pdf.pages[0].extract_text() or ""
            return "LISTA PAKOVANJA" in text.upper()
    except Exception as e:
        logger.debug(f"Detekcija packing liste nije uspjela: {e}")
        return False


def find_matching_packing_list(invoice_pdf_path: str) -> Optional[str]:
    """
    Pronalazi listu pakovanja koja odgovara fakturi.

    Logic:
    - Iz imena fajla izvlači prvi broj (npr. "722" iz bilo kog formata)
    - Traži drugi PDF u istom folderu sa istim brojem
    - Preferira fajl koji je suprotnog tipa (ako je ulaz faktura → traži packing list i obrnuto)

    Args:
        invoice_pdf_path: Putanja do fajla

    Returns:
        Putanja do match fajla ili None
    """
    try:
        invoice_path = Path(invoice_pdf_path)
        folder = invoice_path.parent
        filename = invoice_path.name

        # Generički: izvuči PRVI broj iz imena fajla
        match = re.search(r'(\d+)', filename)
        if not match:
            logger.warning(f"Nije moguće izvući broj iz imena: {filename}")
            return None

        invoice_number = match.group(1)
        is_input_packing = is_blagic_attos_packing_list(invoice_pdf_path)

        # Traži sve PDF-ove u folderu sa istim brojem
        for file in folder.glob("*.pdf"):
            if file == invoice_path:
                continue
            if invoice_number not in file.name:
                continue

            # Provjeri da li je suprotnog tipa
            is_candidate_packing = is_blagic_attos_packing_list(str(file))
            if is_input_packing != is_candidate_packing:
                logger.info(f"Pronađen par: {file.name} ↔ {filename}")
                return str(file)

        logger.warning(f"Nije pronađen par za broj {invoice_number} u {folder}")
        return None

    except Exception as e:
        logger.error(f"Greška tokom traženja para: {e}")
        return None


def parse_blagic_attos_invoice(filepath: str) -> Tuple[Dict, List[Dict]]:
    """
    Parse Blagic-Attos fakture (RAČUN-OTPREMNICA).

    Ekstraktuje:
    - Header informacije (broj fakture, datum, dobavljač, kupac, ukupna cijena)
    - Stavke sa cijenama (šifra, naziv, količina, cijena)
    - Detektuje izjavu o poreklu (ako postoji)

    Args:
        filepath: Putanja do PDF fakture

    Returns:
        Tuple (header_dict, items_list)
    """
    logger.info(f"Blagic-Attos invoice parsing započet: {filepath}")

    try:
        with pdfplumber.open(filepath) as pdf:
            # Extract text from all pages
            all_text = ""
            for page in pdf.pages:
                all_text += (page.extract_text() or "") + "\n"

        lines = all_text.split("\n")

        # DETEKTUJ SVE izjave o poreklu u celom PDF-u
        origin_statements = _detect_all_origin_statements(all_text)
        has_origin_statement = len(origin_statements) > 0
        logger.info(f"Detekcija izjave o poreklu: {has_origin_statement} ({len(origin_statements)} izjava)")

        # Parse header
        header = _parse_attos_invoice_header(lines)

        # Sačuvaj informaciju o izjavi u header
        header["has_origin_statement"] = has_origin_statement
        header["origin_statements"] = origin_statements
        header["incoterm"] = detect_incoterm(all_text)  # Rb.20 "Uslovi isporuke"

        # Parse items
        items = _parse_attos_invoice_items(lines)

        logger.info(f"Parsed {len(items)} items from invoice")

        return header, items

    except Exception as e:
        logger.error(f"Greška tokom parsiranja Attos fakture: {e}", exc_info=True)
        raise ValueError(f"Nije moguće parsirati Attos fakturu: {e}") from e


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
        from services.tariff.origin_statement_detector import OriginStatementDetector
        
        detector = OriginStatementDetector()
        result = detector.detect_in_text(text)
        
        if result:
            logger.info(f"  ✅ Nađena izjava o poreklu: {result.jezik} / {result.tip_izjave} / origin={result.origin_country}")
            return True
        else:
            logger.info(f"  ❌ Nije nađena izjava o poreklu")
            return False
            
    except Exception as e:
        logger.warning(f"Greška tokom detekcije izjave: {e}")
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
        logger.warning(f"Greška tokom detekcije izjava: {e}")
        return []


def _parse_attos_invoice_header(lines: List[str]) -> Dict:
    """
    Parse header informacije iz fakture.

    Returns:
        Dict sa header informacijama
    """
    header = {
        "invoice_number": "",
        "date": "",
        "supplier": "ATTOS d.o.o. Novi Sad",
        "customer": "Sreto Blagić sp",
        "currency": "EUR",
        "total_amount": 0.0,
        "bruto_kg": 0.0,
        "neto_kg": 0.0,
    }

    for line in lines:
        # Invoice number: "RAČUN-OTPREMNICA: 3940/2025"
        if "RAČUN-OTPREMNICA" in line or "RACUN-OTPREMNICA" in line:
            match = re.search(r"(\d+/\d{4})", line)
            if match:
                header["invoice_number"] = match.group(1)

        # Date: "15.09.2025"
        match = re.search(r"(\d{2}\.\d{2}\.\d{4})", line)
        if match:
            header["date"] = match.group(1)

        # Total amount: "Ukupno za uplatu: 6.848,66" (EUR može biti ili ne mora biti)
        if "Ukupno za uplatu" in line or "za uplatu" in line:
            match = re.search(r":\s*([\d\.]+,\d+)", line)
            if match:
                amount_str = match.group(1).replace(".", "").replace(",", ".")
                try:
                    header["total_amount"] = float(amount_str)
                except (ValueError, TypeError):
                    pass

        # Weights: "Neto: 591,925 kg"
        if "Neto:" in line:
            match = re.search(r"Neto:\s*([\d\.,]+)", line)
            if match:
                weight_str = match.group(1).replace(".", "").replace(",", ".")
                try:
                    header["neto_kg"] = float(weight_str)
                except (ValueError, TypeError):
                    pass

        if "Bruto:" in line:
            match = re.search(r"Bruto:\s*([\d\.,]+)", line)
            if match:
                weight_str = match.group(1).replace(".", "").replace(",", ".")
                try:
                    header["bruto_kg"] = float(weight_str)
                except (ValueError, TypeError):
                    pass

    return header


def _parse_attos_invoice_items(lines: List[str]) -> List[Dict]:
    """
    Parse items iz fakture.

    Delegira detekciju JM i ekstrakciju numeričkih kolona na
    `parse_invoice_tail()` iz `invoice_line_utils`.

    Podržava Format A (sa CC porekla) i Format B (bez CC) — auto-detekcija.

    Returns:
        Lista diktova sa stavkama
    """
    items = []

    for line in lines:
        if not line.strip():
            continue

        # Item red počinje brojem
        if not re.match(r"^\s*\d+\s+", line):
            continue

        # Mora sadržati poznatu JM
        if not any(f" {u} " in line for u in KNOWN_JM):
            continue

        # Završni markeri
        if "Ukupno za uplatu" in line or "Pakovao" in line:
            break

        parts = line.split()

        tail = parse_invoice_tail(parts)
        if tail is None:
            logger.debug(f"Nepotpuna/neprepoznatljiva linija fakture: {line[:60]}")
            continue

        try:
            jm_pos = tail["jm_pos"]
            rb_str = parts[0]
            sifra_parts = []
            naziv_parts = []
            for i in range(1, jm_pos):
                part = parts[i]
                if i <= 2 and part.isdigit():
                    sifra_parts.append(part)
                else:
                    naziv_parts.append(part)

            rb = int(rb_str)
            poreklo = tail["poreklo"]
            items.append({
                "rb": rb,
                "sifra": " ".join(sifra_parts),
                "naziv": " ".join(naziv_parts),
                "jm": tail["jm"],
                "kolicina": parse_eu_number(tail["kolicina_str"]),
                "cijena_jed": parse_eu_number(tail["cijena_str"]),
                "iznos": parse_eu_number(tail["iznos_str"]),
                "tarifni_broj": "",
                "zemlja_porijekla": normalize_country_name(poreklo) if len(poreklo) == 2 else "",
                "bruto_kg": 0.0,
                "neto_kg": 0.0,
            })

        except (ValueError, IndexError) as e:
            logger.debug(f"Preskakanje reda (parsing greška): {line[:50]}... - {e}")
            continue

    return items


def parse_blagic_attos_packing_list(filepath: str) -> List[Dict]:
    """
    Parse Blagic-Attos liste pakovanja.

    Ekstraktuje:
    - Stavke sa težinama i porekl (šifra, naziv, poreklo, neto, bruto)

    Args:
        filepath: Putanja do PDF liste pakovanja

    Returns:
        Lista diktova sa stavkama
    """
    logger.info(f"Blagic-Attos packing list parsing započet: {filepath}")

    try:
        with pdfplumber.open(filepath) as pdf:
            # Extract text from all pages
            all_text = ""
            for page in pdf.pages:
                all_text += (page.extract_text() or "") + "\n"

        lines = all_text.split("\n")

        # Parse items
        items = _parse_attos_packing_items(lines)

        logger.info(f"Parsed {len(items)} items from packing list")

        return items

    except Exception as e:
        logger.error(f"Greška tokom parsiranja Attos liste pakovanja: {e}", exc_info=True)
        raise ValueError(f"Nije moguće parsirati Attos listu pakovanja: {e}") from e


def _parse_attos_packing_items(lines: List[str]) -> List[Dict]:
    """
    Parse items iz liste pakovanja.

    Lista pakovanja ima sve kolone spojene u jednu liniju:
    RB. Šifra Naziv Poreklo JM Količina Neto Bruto

    Example: "2. 120 100 Termostat KV 441 R3 SI kom 120,00 10,080 13,200"

    Returns:
        Lista diktova sa stavkama
    """
    items = []

    # Stavke počinju odmah (nema posebnog header reda)
    for line in lines:
        # Skip empty lines
        if not line.strip():
            continue

        # Check if this looks like an item row (starts with number followed by dot)
        if not re.match(r"^\s*\d+\.\s+", line):
            continue

        # Mora sadržati poznatu JM
        if not any(f" {u} " in line for u in KNOWN_JM):
            continue

        # Završni markeri
        if "Ukupna" in line or "Pakovao" in line or "Robu izdao" in line:
            break

        parts = line.split()

        tail = parse_packing_tail(parts)
        if tail is None:
            logger.debug(f"Nepotpuna/neprepoznatljiva linija pakovanja: {line[:60]}")
            continue

        try:
            jm_pos = tail["jm_pos"]
            rb_str = parts[0].rstrip('.')
            sifra_parts = []
            naziv_parts = []
            # Sve ispred CC (jm_pos - 1) je RB + Šifra + Naziv
            cc_pos = jm_pos - 1
            for i in range(1, cc_pos):
                part = parts[i]
                if i <= 2 and part.isdigit():
                    sifra_parts.append(part)
                else:
                    naziv_parts.append(part)

            rb = int(rb_str)
            cc = tail["cc"]
            items.append({
                "rb": rb,
                "sifra": " ".join(sifra_parts),
                "naziv": " ".join(naziv_parts),
                "jm": tail["jm"],
                "kolicina": parse_eu_number(tail["kolicina_str"]),
                "zemlja_porijekla": normalize_country_name(cc) if len(cc) == 2 else "",
                "bruto_kg": parse_eu_number(tail["bruto_str"]),
                "neto_kg": parse_eu_number(tail["neto_str"]),
            })

        except (ValueError, IndexError) as e:
            logger.debug(f"Preskakanje reda (parsing greška): {line[:50]}... - {e}")
            continue

    return items


def combine_invoice_and_packing(
    invoice_items: List[Dict],
    packing_items: List[Dict],
    has_origin_statement: bool = False
) -> List[InvoiceLine]:
    """
    Kombinuje stavke iz fakture i liste pakovanja.

    Matching je na osnovu šifre artikla.

    Args:
        invoice_items: Stavke iz fakture (sa cijenama)
        packing_items: Stavke iz liste pakovanja (sa težinama i porekl)
        has_origin_statement: Da li faktura sadrži izjavu o poreklu

    Returns:
        Lista InvoiceLine objekata sa kompletnim podacima
    """
    # Create mapping: sifra -> packing item
    packing_map = {item["sifra"]: item for item in packing_items}

    combined_items = []

    for inv_item in invoice_items:
        sifra = inv_item["sifra"]

        # Try to find matching packing item
        packing_item = packing_map.get(sifra)

        # Create InvoiceLine
        item = InvoiceLine(
            line_no=inv_item["rb"],
            naziv_robe=inv_item["naziv"],
            product_code=sifra,  # IMPORTANT: Populate product code for matching
            tarifni_broj="",  # Not available in Attos format
            zemlja_porijekla=packing_item["zemlja_porijekla"] if packing_item else "",
            kolicina=inv_item["kolicina"],
            cijena_jed=inv_item["cijena_jed"],
            iznos=inv_item["iznos"],
            valuta="EUR",
            bruto_kg=packing_item["bruto_kg"] if packing_item else 0.0,
            neto_kg=packing_item["neto_kg"] if packing_item else 0.0,
            jm=inv_item["jm"],
            has_origin_statement=has_origin_statement  # SAVE FLAG
        )

        combined_items.append(item)

    return combined_items


def parse_blagic_attos_with_auto_combine(invoice_pdf_path: str) -> ImportResult:
    """
    Parse Blagic-Attos fakture sa automatskom kombinacijom liste pakovanja.
    """
    logger.info(f"Blagic-Attos parsing sa auto-kombinacijom: {invoice_pdf_path}")

    # Ako je ovo packing list, parsiraj kao packing list
    if is_blagic_attos_packing_list(invoice_pdf_path):
        logger.info(f"Detektovana LISTA PAKOVANJA — parsiram kao packing list")
        packing_items = parse_blagic_attos_packing_list(invoice_pdf_path)
        items = []
        for p_item in packing_items:
            item = InvoiceLine(
                line_no=p_item["rb"],
                naziv_robe=p_item["naziv"],
                product_code="",
                tarifni_broj="",
                zemlja_porijekla=p_item.get("zemlja", ""),
                kolicina=p_item["kolicina"],
                cijena_jed=0.0,
                iznos=0.0,
                valuta="EUR",
                bruto_kg=p_item.get("bruto_kg", 0.0),
                neto_kg=p_item.get("neto_kg", 0.0),
                jm=p_item.get("jm", ""),
            )
            items.append(item)
        _imp = Party(name="BLAGIĆ D.O.O.")
        for item in items:
            item.exporter = Party(name="ATTOS")
            item.importer = _imp
        return ImportResult(
            items=items,
            bruto_kg=sum(i.bruto_kg for i in items),
            neto_kg=sum(i.neto_kg for i in items),
            invoice_name="",
            currency="EUR",
            exporter=Party(name="ATTOS"),
            importer=_imp,
        )

    # Normalan tok: parsiraj kao fakturu
    header, invoice_items = parse_blagic_attos_invoice(invoice_pdf_path)

    # Get origin statement flag from header
    has_origin_statement = header.get("has_origin_statement", False)

    # Try to find matching packing list
    packing_list_path = find_matching_packing_list(invoice_pdf_path)

    if packing_list_path:
        # Parse packing list
        packing_items = parse_blagic_attos_packing_list(packing_list_path)

        # Combine (pass origin statement flag)
        combined_items = combine_invoice_and_packing(
            invoice_items,
            packing_items,
            has_origin_statement
        )

        # NAPOMENA: finalni "Bruto:" red u dokumentu (header) uključuje i
        # procijenjenu težinu palete (ATTOS paušalno dodaje ~20kg za EUR paletu),
        # što ne odgovara stvarnoj težini robe. Za ATTOS koristimo zbir bruto/neto
        # po stavkama iz liste pakovanja (bez palete) — poslovna odluka korisnika.
        bruto_kg = sum(p.get("bruto_kg", 0.0) for p in packing_items)
        neto_kg = sum(p.get("neto_kg", 0.0) for p in packing_items)

        logger.info(f"Kombinovano {len(combined_items)} stavki iz fakture i liste pakovanja")
    else:
        # No packing list found - use only invoice data
        logger.warning("Lista pakovanja nije pronađena - koristim samo podatke iz fakture")

        combined_items = []
        for inv_item in invoice_items:
            item = InvoiceLine(
                line_no=inv_item["rb"],
                naziv_robe=inv_item["naziv"],
                product_code=inv_item["sifra"],  # IMPORTANT: Populate product code for matching
                tarifni_broj="",
                zemlja_porijekla="",
                kolicina=inv_item["kolicina"],
                cijena_jed=inv_item["cijena_jed"],
                iznos=inv_item["iznos"],
                valuta="EUR",
                bruto_kg=0.0,
                neto_kg=0.0,
                jm=inv_item["jm"],
                has_origin_statement=has_origin_statement  # SAVE FLAG
            )
            combined_items.append(item)

        # Nema liste pakovanja — nema po-stavci težina, koristi header fakture
        bruto_kg = header.get("bruto_kg", 0.0)
        neto_kg = header.get("neto_kg", 0.0)

    _imp = Party(name="BLAGIĆ D.O.O.")
    for item in combined_items:
        item.exporter = Party(name="ATTOS")
        item.importer = _imp

    # Return ImportResult
    return ImportResult(
        items=combined_items,
        bruto_kg=bruto_kg,
        neto_kg=neto_kg,
        invoice_name=header.get("invoice_number", ""),
        currency=header.get("currency", "EUR"),
        has_origin_statement=has_origin_statement,
        origin_statements=header.get("origin_statements", []),
        exporter=Party(name="ATTOS"),
        importer=_imp,
        is_combined=bool(packing_list_path),
        consumed_paths=[packing_list_path] if packing_list_path else [],
        incoterm_code=header.get("incoterm", ""),
    )


# ============================================================
# USAGE EXAMPLE
# ============================================================

if __name__ == "__main__":
    # Test with sample file
    test_invoice = "/home/radovan/Desktop/PythonProjects/deklarant_pro/najavauvoza/blagic-attos/Faktura 3940 Blagić.pdf"

    if os.path.exists(test_invoice):
        # Test detection
        is_attos = detect_blagic_attos_pdf(test_invoice)
        logger.debug(f"Detection result: {is_attos}")

        if is_attos:
            # Test parsing with auto-combine
            result = parse_blagic_attos_with_auto_combine(test_invoice)
            logger.debug(f"\nParsed: {len(result.items)} items")
            logger.debug(f"Bruto weight: {result.bruto_kg} kg")
            logger.debug(f"Neto weight: {result.neto_kg} kg")
            logger.debug(f"Invoice name: {result.invoice_name}")
            logger.debug(f"\nFirst 3 items:")
            for item in result.items[:3]:
                logger.debug(f"  - {item.naziv_robe[:50]}")
                logger.debug(f"    Country: {item.zemlja_porijekla}, Qty: {item.kolicina}, Price: {item.cijena_jed}, Neto: {item.neto_kg} kg")
    else:
        logger.debug(f"Test file not found: {test_invoice}")
