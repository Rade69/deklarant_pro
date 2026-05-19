# importers/blagic_combined_importer.py

"""
Blagić Combined Importer - Master Frigo Style

Kombinuje Blagić Excel (mapping) + Blagić PDF (faktura) kao Master Frigo:
1. Excel → product_code : {tariff, origin, preferential, naziv, jm}
2. PDF → product_code : {cijena, količina, iznos}
3. Match po product_code → kompletan InvoiceLine
"""

import logging
from typing import Any, Dict, List, Tuple, Optional
from pathlib import Path
from difflib import SequenceMatcher

from core.draft.draft import InvoiceLine, Party
from importers.import_result import ImportResult
from importers.vendors.blagic.blagic_loren_importer import parse_blagic_loren_excel
from importers.vendors.blagic.blagic_loren_pdf_parser import parse_blagic_loren_pdf, detect_blagic_loren_pdf
from importers.vendors.blagic.blagic_attos_importer import parse_blagic_attos_with_auto_combine

logger = logging.getLogger("deklarant_pro.import.blagic_combined")


_EU_COUNTRIES = {
    "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI",
    "FR", "GR", "HR", "HU", "IE", "IT", "LT", "LU", "LV", "MT",
    "NL", "PL", "PT", "RO", "SE", "SI", "SK",
}


def _statement_origin_matches_country(statement_origin: str, country_code: str) -> bool:
    """
    Provjeri da li se porijeklo iz izjave poklapa sa ISO zemljom stavke.

    Pravila:
    - EU izjava pokriva sve EU države (npr. SI, HR, DE...)
    - U ostalim slučajevima treba tačno poklapanje koda.
    """
    stmt = (statement_origin or "").strip().upper()
    cc = (country_code or "").strip().upper()
    if not stmt or not cc:
        return False
    if stmt == "EU":
        return cc in _EU_COUNTRIES
    return stmt == cc


def _extract_product_code_from_name(naziv: str) -> tuple[Optional[str], str]:
    """
    Ekstraktuje product_code sa početka naziva ako postoji.

    Npr: "301SA010 TUNEL GUMA..." → ("301SA010", "TUNEL GUMA...")

    Returns:
        Tuple (product_code or None, cleaned_naziv)
    """
    import re
    # Pattern: alfanumerička šifra (6-10 karaktera) na početku
    match = re.match(r'^([A-Z0-9]{6,10})\s+(.+)$', naziv, re.IGNORECASE)
    if match:
        return (match.group(1), match.group(2))
    return (None, naziv)


def _fuzzy_match_by_name(
    target_name: str,
    excel_mapping: Dict[str, InvoiceLine],
    threshold: float = 0.85
) -> Optional[InvoiceLine]:
    """
    Pokušaj pronaći match u Excel mapping-u po nazivu proizvoda (fuzzy matching).

    Args:
        target_name: Naziv proizvoda koji tražimo (iz PDF-a)
        excel_mapping: Dict product_code → InvoiceLine iz Excel-a
        threshold: Minimalni prag sličnosti (default 0.85 = 85%)

    Returns:
        InvoiceLine iz Excel-a ako je pronađen match, inače None
    """
    if not target_name or not target_name.strip():
        return None

    # VAŽNO: Ukloni product_code sa početka naziva ako postoji (npr. "301SA010 TUNEL...")
    # Ovo omogućava matching čak i kada PDF parser stavi šifru u naziv
    extracted_code, cleaned_name = _extract_product_code_from_name(target_name)
    target_lower = cleaned_name.lower().strip()

    best_match = None
    best_similarity = 0.0

    for code, excel_item in excel_mapping.items():
        if not excel_item.naziv_robe:
            continue

        candidate_lower = excel_item.naziv_robe.lower().strip()

        # Izračunaj sličnost
        similarity = SequenceMatcher(None, target_lower, candidate_lower).ratio()

        if similarity > best_similarity:
            best_similarity = similarity
            best_match = excel_item

    # Vraćamo match samo ako je iznad praga
    if best_similarity >= threshold:
        if extracted_code:
            logger.info(f"   🎯 Fuzzy match po nazivu ({best_similarity*100:.1f}%): '{cleaned_name[:30]}' (izvučen kod: {extracted_code}) → '{best_match.naziv_robe[:40]}'")
        else:
            logger.info(f"   🎯 Fuzzy match po nazivu ({best_similarity*100:.1f}%): '{target_name[:40]}' → '{best_match.naziv_robe[:40]}'")
        return best_match

    return None


def _validate_weights(
    items: List[InvoiceLine],
    total_bruto_kg: float,
    total_neto_kg: float
) -> None:
    """
    Poredi sumu Excel stavki sa ukupnim PDF težinama (informativno).

    NAPOMENA: Excel ima precizne decimalne težine po stavkama.
    PDF ima zaokružene ukupne težine. Razlika je očekivana i NORMALNA.
    ImportResult uvijek koristi Excel sume (preciznije za carinjenje).
    WARNING se emituje samo za sumnjive razlike > 25%.
    """
    if not items:
        return
    if total_bruto_kg <= 0 and total_neto_kg <= 0:
        return

    if total_neto_kg > total_bruto_kg and total_bruto_kg > 0:
        logger.error(f"❌ PDF GREŠKA: Neto ({total_neto_kg} kg) > Bruto ({total_bruto_kg} kg) — provjerite PDF!")
        return

    excel_bruto_sum = sum(item.bruto_kg for item in items)
    excel_neto_sum  = sum(item.neto_kg  for item in items)

    logger.info(
        f"⚖️  Težine — Excel suma: {excel_bruto_sum:.3f} kg bruto / {excel_neto_sum:.3f} kg neto  |  "
        f"PDF zaokruženo: {total_bruto_kg:.2f} kg bruto / {total_neto_kg:.2f} kg neto"
    )
    logger.info("   ✅ Koriste se Excel vrijednosti (precizne decimale po stavkama)")

    # Upozori samo na sumnjivo veliku razliku (> 25%) koja može ukazivati na grešku
    if total_bruto_kg > 0 and excel_bruto_sum > 0:
        diff_pct = abs(excel_bruto_sum - total_bruto_kg) / total_bruto_kg * 100
        if diff_pct > 25.0:
            logger.warning(
                f"⚠️  Velika razlika bruto: Excel {excel_bruto_sum:.3f} kg vs PDF {total_bruto_kg:.2f} kg "
                f"({diff_pct:.1f}%) — provjerite da li su spareni pravi fajlovi!"
            )

    if total_neto_kg > 0 and excel_neto_sum > 0:
        diff_pct = abs(excel_neto_sum - total_neto_kg) / total_neto_kg * 100
        if diff_pct > 25.0:
            logger.warning(
                f"⚠️  Velika razlika neto: Excel {excel_neto_sum:.3f} kg vs PDF {total_neto_kg:.2f} kg "
                f"({diff_pct:.1f}%) — provjerite da li su spareni pravi fajlovi!"
            )


def combine_blagic_excel_and_pdf(
    excel_path: str,
    pdf_path: str
) -> Tuple[List[InvoiceLine], Dict[str, Any]]:
    """
    Kombinuje Blagić Excel (mapping) i PDF (faktura) kao Master Frigo.

    Args:
        excel_path: Putanja do Blagić Excel fajla (Loren format)
        pdf_path: Putanja do Blagić PDF fakture (Attos format)

    Returns:
        Tuple of (combined_items, stats)
    """
    logger.info(f"Kombinovanje Blagić Excel i PDF:")
    logger.info(f"  Excel (mapping): {Path(excel_path).name}")
    logger.info(f"  PDF (faktura): {Path(pdf_path).name}")

    # ========================================
    # STEP 1: Učitaj Excel kao MAPPING
    # ========================================
    # _skip_pdf_lookup=True jer PDF obrađujemo posebno u STEP 2 — izbjegavamo duplo otvaranje
    excel_result = parse_blagic_loren_excel(excel_path, _skip_pdf_lookup=True)

    # Kreiraj mapping: product_code → InvoiceLine (sa tarifom, zemljom, itd.)
    excel_mapping: Dict[str, InvoiceLine] = {}

    for item in excel_result.items:
        if item.product_code and item.product_code.strip():
            code = item.product_code.strip()
            excel_mapping[code] = item
        else:
            logger.warning(f"Excel stavka nema product_code: {item.naziv_robe[:50]}")

    logger.info(f"✅ Excel mapping: {len(excel_mapping)} stavki sa product_code")

    # ========================================
    # STEP 2: Parsuj PDF fakturu (auto-detect Loren vs Attos)
    # ========================================

    # Detektuj tip PDF-a
    is_loren_pdf = detect_blagic_loren_pdf(pdf_path)

    if is_loren_pdf:
        logger.info("📄 PDF format: Blagić Loren (Beograd)")
        pdf_result = parse_blagic_loren_pdf(pdf_path)
    else:
        logger.info("📄 PDF format: Blagić Attos")
        pdf_result = parse_blagic_attos_with_auto_combine(pdf_path)

    logger.info(f"✅ PDF faktura: {len(pdf_result.items)} stavki")
    if pdf_result.bruto_kg > 0 or pdf_result.neto_kg > 0:
        logger.info(f"   Bruto: {pdf_result.bruto_kg} kg, Neto: {pdf_result.neto_kg} kg")

    # ========================================
    # STEP 3: Matchuj po product_code
    # ========================================
    combined_items: List[InvoiceLine] = []
    matched_count = 0
    unmatched_count = 0
    unmatched_codes = []

    for pdf_item in pdf_result.items:
        # MATCHING STRATEGIJA:
        # 0. EXTRACTION: Ako product_code nije u polju, pokušaj izvući iz naziva
        # 1. PRIMARY: Direct lookup po product_code (ako postoji)
        # 2. SECONDARY: Fuzzy match po nazivu (>85% sličnosti)

        excel_item = None
        code = None

        # KORAK 0: Provjeri da li product_code postoji; ako ne, izvuci ga iz naziva
        if pdf_item.product_code and pdf_item.product_code.strip():
            code = pdf_item.product_code.strip()
        else:
            # Pokušaj izvući product_code iz naziva (npr. "301SA010 TUNEL GUMA...")
            extracted_code, cleaned_name = _extract_product_code_from_name(pdf_item.naziv_robe or "")
            if extracted_code:
                code = extracted_code
                logger.debug(f"📌 Izvučen product_code '{code}' iz naziva: {pdf_item.naziv_robe[:50]}")
                # VAŽNO: Postavi product_code u PDF item za dalju upotrebu
                pdf_item.product_code = code
            else:
                logger.debug(f"PDF stavka bez product_code: {pdf_item.naziv_robe[:50]}")

        # KORAK 1: PRIMARY match po product_code (ako ga ima)
        if code:
            excel_item = excel_mapping.get(code)  # Primary match
            if excel_item:
                logger.debug(f"✓ Primary match po code '{code}': {excel_item.naziv_robe[:40]}")

        # KORAK 2: SECONDARY fuzzy match (ako PRIMARY nije uspio)
        if not excel_item:
            if code:
                logger.debug(f"✗ Product code '{code}' nije pronađen - pokušavam fuzzy match po nazivu...")
            else:
                logger.debug(f"Pokušavam fuzzy match po nazivu...")

            excel_item = _fuzzy_match_by_name(pdf_item.naziv_robe, excel_mapping, threshold=0.85)

        if excel_item:
            # ✅ MATCHED! (bilo po code-u bilo po nazivu)
            combined_item = InvoiceLine(
                line_no=pdf_item.line_no,

                # Iz Excel-a (mapping)
                naziv_robe=excel_item.naziv_robe or pdf_item.naziv_robe,
                tarifni_broj=excel_item.tarifni_broj,
                zemlja_porijekla=excel_item.zemlja_porijekla,
                povlastica=excel_item.povlastica,
                jm=excel_item.jm or pdf_item.jm,

                # VAŽNO: ZADRŽAVAMO product_code iz PDF-a za eventualnu upotrebu
                # GUI će ga obrisati pri prikazu u tabeli
                product_code=pdf_item.product_code,

                # Iz PDF-a (faktura - cijene)
                kolicina=pdf_item.kolicina,
                cijena_jed=pdf_item.cijena_jed,
                iznos=pdf_item.iznos,
                valuta=pdf_item.valuta,

                # Iz Excel-a (težine - PDF ih nema po stavkama!)
                bruto_kg=excel_item.bruto_kg if excel_item.bruto_kg > 0 else excel_item.neto_kg,
                neto_kg=excel_item.neto_kg,

                # Zadrži per-item izjavu o poreklu iz PDF-a
                has_origin_statement=pdf_item.has_origin_statement,
                raw=dict(pdf_item.raw) if getattr(pdf_item, "raw", None) else {},
            )

            # Validacija: izjava na fakturi mora biti konzistentna sa zemljom porijekla.
            stmt_origin = (combined_item.raw or {}).get("origin_from_statement")
            if combined_item.has_origin_statement and stmt_origin:
                if _statement_origin_matches_country(stmt_origin, combined_item.zemlja_porijekla):
                    combined_item.country_confidence = "HIGH"
                    combined_item.country_source = "PDF_IZJAVA_MATCH"
                else:
                    combined_item.country_confidence = "CONFLICT"
                    combined_item.country_source = "CONFLICT"
                    combined_item.country_conflict_details = (
                        f"Izjava na fakturi: {stmt_origin}, Excel zemlja: "
                        f"{combined_item.zemlja_porijekla or '(prazno)'}"
                    )
                    combined_item.raw["origin_conflict"] = True
                    combined_item.raw["origin_conflict_details"] = combined_item.country_conflict_details
                    logger.warning(
                        "⚠️ Konflikt porijekla za line_no=%s code=%s: %s",
                        combined_item.line_no,
                        combined_item.product_code,
                        combined_item.country_conflict_details,
                    )

            combined_items.append(combined_item)
            matched_count += 1

            logger.debug(f"✓ Matched '{code}': {excel_item.naziv_robe[:40]}")

        else:
            # ❌ UNMATCHED! Nije pronađen ni po code-u ni po nazivu
            if code:
                logger.warning(f"✗ Unmatched '{code}': {pdf_item.naziv_robe[:50]}")
                unmatched_codes.append(code)
            else:
                logger.warning(f"✗ Unmatched (bez code-a): {pdf_item.naziv_robe[:50]}")

            logger.warning(f"   Nije pronađen ni po product_code ni po fuzzy match nazivu")

            # Dodaj PDF stavku kao unmatched (nedostaju tariff/origin)
            # VAŽNO: Obriši product_code jer se koristi samo za matching!
            logger.debug(f"🗑️  Brišem product_code '{pdf_item.product_code}' za unmatched item")
            pdf_item.product_code = ""
            logger.debug(f"   Nakon brisanja: product_code='{pdf_item.product_code}', naziv='{pdf_item.naziv_robe[:50]}'")
            combined_items.append(pdf_item)
            unmatched_count += 1

    # ========================================
    # STEP 3.5: Validacija težina (Excel vs PDF)
    # ========================================
    # Excel ima težine po stavkama, PDF ima ukupne bruto/neto
    # Uporedi i prikaži upozorenja ako se ne poklapaju
    _validate_weights(combined_items, pdf_result.bruto_kg, pdf_result.neto_kg)

    # ========================================
    # STEP 4: Stats
    # ========================================
    # Koristimo sumu Excel stavki jer je preciznija od zaokruženih PDF vrijednosti.
    # PDF ima cijele kg (npr. 451 kg), Excel ima decimale po stavkama (npr. 463.52 kg).
    excel_bruto_sum = sum(item.bruto_kg for item in combined_items)
    excel_neto_sum  = sum(item.neto_kg  for item in combined_items)

    # Ako Excel nema neto po stavkama, padni na PDF vrijednost
    final_bruto = excel_bruto_sum if excel_bruto_sum > 0 else pdf_result.bruto_kg
    final_neto  = excel_neto_sum  if excel_neto_sum  > 0 else pdf_result.neto_kg

    if pdf_result.bruto_kg > 0 and abs(excel_bruto_sum - pdf_result.bruto_kg) > 0.5:
        logger.info(
            f"ℹ️  Težine: Excel suma ({excel_bruto_sum:.3f} kg bruto) korišćena umjesto "
            f"zaokružene PDF vrijednosti ({pdf_result.bruto_kg:.2f} kg)"
        )

    stats = {
        "excel_items": len(excel_result.items),
        "pdf_items": len(pdf_result.items),
        "matched": matched_count,
        "unmatched": unmatched_count,
        "unmatched_codes": unmatched_codes,
        "total_combined": len(combined_items),
        "invoice_name": pdf_result.invoice_name,
        "bruto_kg": final_bruto,
        "neto_kg": final_neto,
        "bruto_kg_pdf": pdf_result.bruto_kg,   # za referencu
        "neto_kg_pdf": pdf_result.neto_kg,      # za referencu
        "currency": pdf_result.currency,
        "has_origin_statement": pdf_result.has_origin_statement,
        "origin_statements": pdf_result.origin_statements,
        "exporter_name": pdf_result.exporter.name if pdf_result.exporter else "LOREN",
    }

    logger.info(f"\n📊 MATCHING REZULTAT:")
    logger.info(f"   Excel mapping: {stats['excel_items']} stavki")
    logger.info(f"   PDF faktura: {stats['pdf_items']} stavki")
    logger.info(f"   ✅ Matched: {matched_count} ({matched_count / stats['pdf_items'] * 100:.1f}%)")
    logger.info(f"   ❌ Unmatched: {unmatched_count}")

    if unmatched_count > 0:
        logger.warning(f"\n⚠️ Unmatched product kodovi:")
        for code in unmatched_codes[:10]:
            logger.warning(f"   - {code}")
        if len(unmatched_codes) > 10:
            logger.warning(f"   ... i još {len(unmatched_codes) - 10}")

    return combined_items, stats


def import_blagic_combined(
    excel_path: str,
    pdf_path: str
) -> ImportResult:
    """
    Wrapper funkcija koja vraća ImportResult.

    Args:
        excel_path: Putanja do Blagić Excel fajla
        pdf_path: Putanja do Blagić PDF fakture

    Returns:
        ImportResult sa kombinovanim stavkama
    """
    combined_items, stats = combine_blagic_excel_and_pdf(excel_path, pdf_path)

    return ImportResult(
        items=combined_items,
        bruto_kg=stats.get("bruto_kg", 0.0),
        neto_kg=stats.get("neto_kg", 0.0),
        invoice_name=Path(pdf_path).stem,
        currency=stats.get("currency", "EUR"),
        has_origin_statement=stats.get("has_origin_statement", False),
        exporter=Party(name=stats.get("exporter_name", "LOREN")),
        consumed_paths=[excel_path],
    )


# ============================================================
# USAGE EXAMPLE
# ============================================================

if __name__ == "__main__":
    import sys
    from pathlib import Path

    # Add project root to path (vendors/blagic → vendors → importers → project_root)
    project_root = Path(__file__).parent.parent.parent.parent
    sys.path.insert(0, str(project_root))

    # Test sa pravim fajlovima
    excel_file = "najavauvoza/blagic-loren/702VP-2025 BLAGIC.xlsx"
    pdf_file = "najavauvoza/blagic-attos/Faktura 3940 Blagić.pdf"

    logger.debug("\n" + "=" * 70)
    logger.debug("BLAGIĆ COMBINED IMPORTER - Test")
    logger.debug("=" * 70 + "\n")

    try:
        combined_items, stats = combine_blagic_excel_and_pdf(excel_file, pdf_file)

        logger.info(f"\n✅ Kombinovanje uspješno!")
        logger.debug(f"\n📊 Statistike:")
        logger.debug(f"   Excel stavki: {stats['excel_items']}")
        logger.debug(f"   PDF stavki: {stats['pdf_items']}")
        logger.debug(f"   Matched: {stats['matched']} ({stats['matched'] / stats['pdf_items'] * 100:.1f}%)")
        logger.debug(f"   Unmatched: {stats['unmatched']}")
        logger.debug(f"   Ukupno: {stats['total_combined']} stavki")
        logger.debug(f"   Težine: Bruto {stats['bruto_kg']} kg, Neto {stats['neto_kg']} kg")

        logger.debug(f"\n📦 Prvih 5 kombinovanih stavki:")
        for i, item in enumerate(combined_items[:5], 1):
            logger.debug(f"\n{i}. {item.naziv_robe[:60]}")
            logger.debug(f"   Code: {item.product_code}")
            logger.debug(f"   Tariff: {item.tarifni_broj}, Origin: {item.zemlja_porijekla}")
            logger.debug(f"   Qty: {item.kolicina} {item.jm}, Price: {item.cijena_jed} {item.valuta}")

        if stats['unmatched'] > 0:
            logger.warning(f"\n⚠️ {stats['unmatched']} stavki nije matchovano!")
            logger.debug(f"   Razlog: Product kodovi nisu pronađeni u Excel-u")
            logger.debug(f"   Unmatched kodovi: {', '.join(stats['unmatched_codes'][:5])}")

    except Exception as e:
        logger.error(f"\n❌ Greška: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
