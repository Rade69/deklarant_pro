# importers/sumaprom_combined_importer.py

"""
ŠUMAPROM Combined Importer
Kombinuje ŠUMAPROM Excel + PDF fakture.

Workflow:
1. Excel ima: stavke, količine, cene, iznose, zemlje porekla
2. PDF ima: bruto/neto težine, broj paketa, dodatne informacije
3. Kombinuje: uzima stavke iz Excela, težine iz PDFa

TODO: Implementirati kada bude potreban.
"""

import logging
from typing import List, Tuple, Dict, Any

from core.draft.draft import InvoiceLine
from importers.import_result import ImportResult

logger = logging.getLogger("asycuda_pro.import.sumaprom_combined")


def combine_sumaprom_excel_and_pdf(
    excel_path: str,
    pdf_path: str
) -> Tuple[List[InvoiceLine], Dict[str, Any]]:
    """
    Kombinuj ŠUMAPROM Excel i PDF fakture.

    Workflow:
    1. Excel ima: stavke, količine, cene, iznose, zemlje porekla
    2. PDF ima: bruto/neto težine, broj paketa, dodatne informacije
    3. Kombinuje: uzima stavke iz Excela, težine iz PDFa i distribuira proporcionalno

    Args:
        excel_path: Putanja do Excel fajla
        pdf_path: Putanja do PDF fajla

    Returns:
        Tuple of (combined_items, stats)
        - combined_items: Lista InvoiceLine sa kombinovanim podacima
        - stats: Dict sa metapodacima (bruto_kg, neto_kg, currency, itd.)
    """
    logger.info(f"ŠUMAPROM kombinovanje: Excel={excel_path}, PDF={pdf_path}")
    
    # STEP 1: Parsuj Excel
    from importers.sumaprom_excel_parser import parse_sumaprom_excel
    excel_result = parse_sumaprom_excel(excel_path)
    
    logger.info(f"  Excel: {len(excel_result.items)} stavki, bruto={excel_result.bruto_kg} kg")
    
    # STEP 2: Parsuj PDF
    from importers.sumaprom_pdf_parser import parse_sumaprom_pdf
    result = parse_sumaprom_pdf(pdf_path)
    
    logger.info(f"  PDF: {len(result.items)} stavki, bruto={result.bruto_kg} kg, neto={result.neto_kg} kg")
    
    # STEP 3: Kombinuj podatke
    # Koristi Excel stavke kao primarne
    combined_items = list(excel_result.items)
    
    # Uzmi težine iz PDFa (ako su bolje)
    bruto_kg = result.bruto_kg if result.bruto_kg > 0 else excel_result.bruto_kg
    neto_kg = result.neto_kg if result.neto_kg > 0 else excel_result.neto_kg
    
    # STEP 4: Distribuiraj težine proporcionalno po iznosima
    if combined_items and (bruto_kg > 0 or neto_kg > 0):
        total_amount = sum(item.iznos for item in combined_items)
        
        if total_amount > 0:
            for item in combined_items:
                proportion = item.iznos / total_amount
                item.bruto_kg = proportion * bruto_kg
                item.neto_kg = proportion * neto_kg
                
                # Normalize Brazil country code (BRA → BR)
                if item.zemlja_porijekla == "BRA":
                    item.zemlja_porijekla = "BR"
            
            logger.info(f"  📊 Težine distribuirane proporcionalno (ukupno: {total_amount:.2f} EUR)")
    
    warnings = []
    if bruto_kg > 0 and neto_kg == 0:
        warnings.append(
            f"⚠️ Neto težina nije pronađena u ŠUMAPROM fakturi (bruto={bruto_kg:.2f} kg). "
            f"Unesite neto težinu ručno u toolbar Faktura taba."
        )

    stats = {
        "bruto_kg": bruto_kg,
        "neto_kg": neto_kg,
        "currency": excel_result.currency,
        "invoice_name": excel_result.invoice_name,
        "excel_items": len(excel_result.items),
        "pdf_items": len(result.items),
        "combined": True,
        "warnings": warnings,
    }

    logger.info(f"  ✅ Kombinovano: {len(combined_items)} stavki, bruto={bruto_kg} kg, neto={neto_kg} kg")
    if warnings:
        for w in warnings:
            logger.warning(w)

    return combined_items, stats


if __name__ == "__main__":
    # Test
    import sys
    
    if len(sys.argv) > 2:
        excel_file = sys.argv[1]
        pdf_file = sys.argv[2]
        
        logger.info(f"Testing ŠUMAPROM combined importer")
        logger.info(f"  Excel: {excel_file}")
        logger.info(f"  PDF: {pdf_file}")
        
        items, stats = combine_sumaprom_excel_and_pdf(excel_file, pdf_file)
        
        logger.info(f"\n✅ Combined: {len(items)} items")
        logger.info(f"  Bruto: {stats['bruto_kg']} kg")
        logger.info(f"  Neto: {stats['neto_kg']} kg")
        logger.info(f"  Currency: {stats['currency']}")
    else:
        logger.info("Usage: python sumaprom_combined_importer.py <excel_file> <pdf_file>")
