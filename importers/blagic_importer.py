# importers/blagic_importer.py
"""
ASYCUDA Pro - Blagić/Loren Specialized Importer
Specijalizovani parser za Blagić/Loren fakture (PDF + XLSX)
Ova verzija je "MASTER" i služi za opšte formate Blagić faktura.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import openpyxl
import pdfplumber

from core.draft.draft import InvoiceLine, Party
from utils.country_normalizer import normalize_country_name

logger = logging.getLogger("asycuda_pro.import.blagic")


_INVOICE_ID_RE = re.compile(r"(\d+VP-\d{4})", re.IGNORECASE)


@dataclass
class ImportedLine:
    num: int
    code: str
    description: str
    unit: str
    qty: float
    price: float
    amount: float
    tariff: str = ""
    origin: str = ""
    weight_total: float = 0.0
    weight_piece: float = 0.0
    packing_matched: bool = False


def extract_invoice_id_from_filename(path: str) -> Optional[str]:
    m = _INVOICE_ID_RE.search(Path(path).name)
    return m.group(1).upper() if m else None


def _safe_float(val: Any) -> float:
    """
    Sigurna konverzija u float.
    Ako naiđe na tekst (poput 'QUANTITY'), vraća 0.0 umjesto pucanja.
    """
    if val is None or val == "":
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)

    s = str(val).strip().replace(" ", "").replace("€", "")

    # Ako string sadrži slova koja nisu naučna notacija, nije broj
    if any(c.isalpha() for c in s if c.lower() not in ["e", ".", ","]):
        return 0.0

    try:
        if "." in s and "," in s:
            s = s.replace(".", "").replace(",", ".")
        elif "," in s:
            s = s.replace(",", ".")
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def _detect_all_origin_statements(text: str) -> list:
    """Detektuj SVE izjave o preferencijalnom poreklu u tekstu."""
    try:
        from services.origin_statement_detector import OriginStatementDetector
        detector = OriginStatementDetector()
        return detector.detect_all_in_text(text)
    except Exception as e:
        logger.warning(f"  ⚠️  Greška tokom detekcije izjava: {e}")
        return []


def parse_blagic_invoice_pdf(path: str) -> Tuple[Dict[str, Any], List[ImportedLine]]:
    """Parsira PDF uz detekciju rednog broja stavke."""
    items = []
    header = {"currency": "EUR"}
    full_text = ""

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            full_text += (page.extract_text() or "") + "\n"
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if not row or len(row) < 5:
                        continue

                    row_s = [str(c).strip() if c else "" for c in row]

                    if "RAČUN BR" in " ".join(row_s).upper():
                        m = _INVOICE_ID_RE.search(" ".join(row_s))
                        if m:
                            header["invoice_id"] = m.group(1)

                    # Red mora početi brojem stavke
                    if not row_s[0].isdigit():
                        continue

                    try:
                        q = _safe_float(row_s[3])
                        if q == 0:
                            continue

                        items.append(
                            ImportedLine(
                                num=int(row_s[0]),
                                code=row_s[1],
                                description=row_s[2].replace("\n", " "),
                                unit=row_s[5] if len(row_s) > 5 else "PCS",
                                qty=q,
                                price=_safe_float(row_s[6]) if len(row_s) > 6 else 0.0,
                                amount=_safe_float(row_s[7]) if len(row_s) > 7 else 0.0,
                            )
                        )
                    except:
                        continue

    # DETEKTUJ SVE izjave o poreklu
    origin_statements = _detect_all_origin_statements(full_text)
    header["has_origin_statement"] = len(origin_statements) > 0
    header["origin_statements"] = origin_statements
    logger.info(f"  Detekcija izjave o poreklu: {header['has_origin_statement']} ({len(origin_statements)} izjava)")

    # Pokušaj detektovati naziv exportera iz teksta
    exporter_name = _detect_exporter(full_text)
    header["exporter_name"] = exporter_name

    return header, items


def parse_blagic_packing_xlsx(path: str) -> Dict[str, Dict[str, Any]]:
    """
    Parsira XLSX (Packing List).
    Automatski preskače zaglavlje tražeći kolonu CODE.
    Vraća mapu: code -> {weight: float, origin: str, tariff: str}
    """
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active
    packing_data = {}
    header_passed = False
    
    # Mapiranje kolona (fleksibilno)
    code_col = None
    weight_col = None
    origin_col = None
    tariff_col = None

    for row_idx, row in enumerate(ws.iter_rows(values_only=True)):
        if not any(row):
            continue

        # Pretvaramo cijeli red u string radi provjere zaglavlja
        row_values = [str(c).strip() if c else "" for c in row]
        row_str = " ".join(row_values).upper()

        # Detekcija zaglavlja - tražimo ključne kolone
        if not header_passed:
            for col_idx, cell_value in enumerate(row_values):
                cell_upper = cell_value.upper()
                if "CODE" in cell_upper or "ŠIFRA" in cell_upper:
                    code_col = col_idx
                elif "WEIGHT" in cell_upper or "MASA" in cell_upper or "GROSS" in cell_upper:
                    weight_col = col_idx
                elif "ORIGIN" in cell_upper or "POREKLO" in cell_upper or "COUNTRY" in cell_upper:
                    origin_col = col_idx
                elif "TARIFF" in cell_upper or "TARIFA" in cell_upper or "CN" in cell_upper:
                    tariff_col = col_idx
            
            # Ako smo pronašli CODE kolonu, pretpostavljamo da je ovo zaglavlje
            if code_col is not None:
                header_passed = True
                logger.info(f"Pronađeno zaglavlje u redu {row_idx + 1}")
                logger.info(f"Kolone: CODE={code_col}, WEIGHT={weight_col}, ORIGIN={origin_col}, TARIFF={tariff_col}")
                continue

        if not header_passed:
            # Ako nema jasnog zaglavlja, ali red počinje brojem, možda su podaci
            if row_values and not row_values[0].isdigit():
                continue

        # Čitanje podataka
        try:
            # Default vrijednosti
            code = ""
            weight = 0.0
            origin = ""
            tariff = ""
            
            # Ekstraktujemo podatke na osnovu pronađenih kolona
            if code_col is not None and len(row_values) > code_col:
                code = str(row_values[code_col]).strip()
                
            if weight_col is not None and len(row_values) > weight_col:
                weight = _safe_float(row_values[weight_col])
                
            if origin_col is not None and len(row_values) > origin_col:
                origin = str(row_values[origin_col]).strip()
                
            if tariff_col is not None and len(row_values) > tariff_col:
                tariff = str(row_values[tariff_col]).strip()

            # Validacija
            if not code or code.upper() in ["CODE", "NO", "ŠIFRA"]:
                continue

            if weight > 0:
                packing_data[code] = {
                    "weight": weight,
                    "origin": origin,
                    "tariff": tariff
                }
                
        except Exception as e:
            logger.warning(f"Greška pri parsiranju reda {row_idx + 1}: {e}")
            continue

    logger.info(f"Parsirano {len(packing_data)} stavki iz packing liste")
    return packing_data


def merge_invoice_with_packing(
    items: List[ImportedLine], packing: Dict[str, Dict[str, Any]]
) -> List[ImportedLine]:
    """Spajanje podataka iz fakture i packing liste."""
    matched_count = 0
    for item in items:
        if item.code in packing:
            pack_data = packing[item.code]
            item.weight_total = pack_data["weight"]
            item.origin = pack_data["origin"]
            item.tariff = pack_data["tariff"]
            item.packing_matched = True
            matched_count += 1
        else:
            logger.debug(f"Nema podataka u packing listi za kod: {item.code}")
    
    logger.info(f"Matched {matched_count}/{len(items)} stavki sa packing listom")
    return items


def _detect_exporter(full_text: str, fallback: str = "") -> str:
    """Try to detect company name from invoice header."""
    lines = [l.strip() for l in full_text.split('\n')[:10] if l.strip()]
    for line in lines:
        for prefix in ['Seller:', 'Vendor:', 'From:', 'FROM:', 'Prodavac:', 'Dobavljač:']:
            if line.startswith(prefix):
                name = line[len(prefix):].strip()
                if name:
                    return name
    return fallback


def convert_to_invoice_lines(
    items: List[ImportedLine], currency: str = "EUR", exporter_name: str = ""
) -> List[InvoiceLine]:
    """Konverzija u InvoiceLine objekte sa kompletnim mapiranjem."""
    lines = []
    exporter = Party(name=exporter_name) if exporter_name else Party()
    for item in items:
        # Normalizacija zemlje porijekla
        origin_normalized = normalize_country_name(item.origin) if item.origin else ""

        line = InvoiceLine(
            line_no=item.num,
            naziv_robe=item.description,
            tarifni_broj=item.tariff,
            zemlja_porijekla=origin_normalized,
            jm=item.unit,
            kolicina=item.qty,
            cijena_jed=item.price,
            iznos=item.amount,
            valuta=currency,
            bruto_kg=item.weight_total,
            neto_kg=item.weight_total,  # Za sada isto kao bruto
            exporter=exporter,
        )
        lines.append(line)
    return lines


def import_blagic_pair(
    invoice_pdf_path: str, packing_xlsx_path: str
) -> List[InvoiceLine]:
    """Glavni proces uvoza sa poboljšanom obradom grešaka."""
    try:
        logger.info(f"Počinje uvoz Blagić para: {invoice_pdf_path} + {packing_xlsx_path}")
        
        # Parsiranje fakture
        header, invoice_items = parse_blagic_invoice_pdf(invoice_pdf_path)
        logger.info(f"Parsirano {len(invoice_items)} stavki iz fakture")
        
        # Parsiranje packing liste
        packing = parse_blagic_packing_xlsx(packing_xlsx_path)
        logger.info(f"Parsirano {len(packing)} stavki iz packing liste")
        
        # Spajanje podataka
        merged = merge_invoice_with_packing(invoice_items, packing)
        
        # Konverzija u finalni format
        result = convert_to_invoice_lines(merged, currency=header.get("currency", "EUR"), exporter_name=header.get("exporter_name", ""))
        
        # Statistika
        matched_items = sum(1 for item in merged if item.packing_matched)
        logger.info(f"Uvoz završen: {len(result)} stavki, {matched_items} sa težinama")
        
        return result
        
    except Exception as e:
        logger.error(f"Greška tokom Blagić uvoza: {e}", exc_info=True)
        raise


# --- POMOĆNE FUNKCIJE ZA VALIDACIJU I ANALIZU ---

def validate_import_result(lines: List[InvoiceLine]) -> Dict[str, Any]:
    """Validacija rezultata uvoza i vraćanje statistike."""
    if not lines:
        return {"valid": False, "error": "Nema uvezenih stavki"}
    
    stats = {
        "valid": True,
        "total_items": len(lines),
        "items_with_weight": sum(1 for l in lines if l.bruto_kg > 0),
        "items_with_tariff": sum(1 for l in lines if l.tariff_code),
        "items_with_origin": sum(1 for l in lines if l.origin_country),
        "total_value": sum(l.iznos for l in lines),
        "total_weight": sum(l.bruto_kg for l in lines),
        "unique_units": list({l.unit for l in lines}),
        "errors": []
    }
    
    # Provjera kritičnih grešaka
    for i, line in enumerate(lines):
        if line.quantity <= 0:
            stats["errors"].append(f"Stavka {line.position_number}: količina <= 0")
        if line.cijena_jed <= 0:
            stats["errors"].append(f"Stavka {line.position_number}: cijena <= 0")
        if line.iznos <= 0:
            stats["errors"].append(f"Stavka {line.position_number}: iznos <= 0")
    
    stats["valid"] = len(stats["errors"]) == 0
    return stats


def get_import_summary(lines: List[InvoiceLine]) -> str:
    """Generiše sažetak uvoza za korisnika."""
    stats = validate_import_result(lines)
    
    if not stats["valid"]:
        return "❌ Uvoz nije validan:\n" + "\n".join(stats["errors"])
    
    summary = f"""✅ Uvoz uspješan!
    
📊 Statistika:
• Stavki: {stats['total_items']}
• Sa težinama: {stats['items_with_weight']}/{stats['total_items']}
• Sa tarifama: {stats['items_with_tariff']}/{stats['total_items']}
• Sa zemljom porijekla: {stats['items_with_origin']}/{stats['total_items']}
• Ukupna vrijednost: {stats['total_value']:.2f} EUR
• Ukupna težina: {stats['total_weight']:.2f} kg
• Jedinice mjere: {', '.join(stats['unique_units'])}
"""
    return summary

# Kraj fajla blagic_importer.py
