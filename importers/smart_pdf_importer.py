"""
Smart PDF Importer - Unified univerzalni parser sa automatskom detekcijom

Jedan parser koji:
1. Automatski detektuje format (Blagić, IMAMOGLU, Master Frigo...)
2. Koristi specijalizovane funkcije za poznate formate
3. Fallback na generičku tabular extraction za nepoznate formate
"""

import logging
import pdfplumber
from typing import Optional
from pathlib import Path

from importers.import_result import ImportResult
from importers.generic_pdf_importer import parse_generic_pdf

logger = logging.getLogger("deklarant_pro.import.smart_pdf")

# Cache teksta prvih stranica po putanji — punjen u _detect_pdf_format,
# dostupan specijalizovanim parserima koji inače čitaju iste stranice ponovo.
# Format: {filepath: (text_raw, text_upper, text_norm)}
_pdf_text_cache: dict = {}


def get_cached_pdf_text(pdf_path: str):
    """Vrati (text, text_upper, text_norm) iz cache-a ili None."""
    return _pdf_text_cache.get(str(pdf_path))


# SECTION: pdf_parse_pipeline
# PURPOSE: 5-koračni pipeline sa fallback lancem: specijalizirani → generic → OCR
# DOC: docs/sections/pdf_parse_pipeline.md
def parse_smart_pdf(pdf_path: str) -> ImportResult:
    """
    Pametno parsira bilo koji PDF - automatski detektuje format i koristi
    odgovarajuću parsing funkciju.

    Args:
        pdf_path: Putanja do PDF fajla

    Returns:
        ImportResult sa parsiranim stavkama
    """
    logger.info(f"🤖 Smart PDF Parser: {Path(pdf_path).name}")

    # 1. DETEKCIJA FORMATA
    pdf_format = _detect_pdf_format(pdf_path)
    logger.info(f"   Detektovan format: {pdf_format}")

    result = None

    # 2. PARSIRANJE PREMA FORMATU
    try:
        if pdf_format == "leburic_pekabesko":
            logger.info("   📋 Koristim Leburic/Pekabesko specijalizovanu funkciju")
            result = _parse_leburic_pekabesko(pdf_path)

        elif pdf_format == "pip_food":
            logger.info("   📋 Koristim PIP Food Group specijalizovanu funkciju")
            result = _parse_pip_food(pdf_path)

        elif pdf_format == "invoice_improved":
            logger.info("   📋 Koristim Invoice-Improved specijalizovanu funkciju")
            result = _parse_invoice_improved(pdf_path)

        elif pdf_format == "blagic_loren":
            logger.info("   📋 Koristim Blagić-Loren specijalizovanu funkciju")
            result = _parse_blagic_loren(pdf_path)

        elif pdf_format == "blagic_attos":
            logger.info("   📋 Koristim Blagić-Attos specijalizovanu funkciju")
            result = _parse_blagic_attos(pdf_path)

        elif pdf_format == "imamoglu":
            logger.info("   📋 Koristim IMAMOGLU specijalizovanu funkciju")
            result = _parse_imamoglu(pdf_path)

        elif pdf_format == "master_frigo":
            logger.info("   📋 Koristim Master Frigo specijalizovanu funkciju")
            result = _parse_master_frigo(pdf_path)

        elif pdf_format == "medicopharm":
            logger.info("   📋 Koristim Medico Pharm specijalizovanu funkciju")
            result = _parse_medicopharm(pdf_path)

        elif pdf_format == "proton_system":
            logger.info("   📋 Koristim Proton System (MGM) specijalizovanu funkciju")
            result = _parse_proton_system(pdf_path)

        elif pdf_format == "sumaprom":
            logger.info("   📋 Koristim ŠUMAPROM specijalizovanu funkciju")
            result = _parse_sumaprom(pdf_path)

        elif pdf_format == "kg_fashion":
            logger.info("   📋 Koristim KG Fashion specijalizovanu funkciju")
            result = _parse_kg_fashion(pdf_path)

        elif pdf_format == "cmana":
            logger.info("   📋 Koristim CMANA specijalizovanu funkciju")
            result = _parse_cmana(pdf_path)

        else:
            logger.info("   🔍 Nepoznat format - koristim generičku tabular extraction")
            result = parse_generic_pdf(pdf_path)

    except Exception as e:
        logger.exception(f"   ⚠️  Specijalizovani parser nije uspio: {e}")
        logger.info("   🔄 Fallback na generičku extraction...")
        result = parse_generic_pdf(pdf_path)

    # 3. FALLBACK AKO JE REZULTAT PRAZAN
    # VAŽNO: koristiti "result is not None" jer ImportResult.__len__ vraća 0 za prazan result
    # što bi ga učinilo falsy pri bool evaluaciji
    if result is not None and hasattr(result, 'items') and len(result.items) == 0:
        logger.warning("   ⚠️  Parser vratio 0 stavki")

        # Ako smo već koristili generic, ne pokušavaj ponovo
        if pdf_format != "generic":
            logger.info("   🔄 Pokušavam sa generičkom extraction kao fallback...")
            try:
                result = parse_generic_pdf(pdf_path)
                if result is not None and len(result.items) > 0:
                    logger.info(f"   ✅ Generic fallback našao {len(result.items)} stavki!")
            except Exception as e:
                logger.error(f"   ❌ Generic fallback također nije uspio: {e}")

    # 4. OCR FALLBACK — ako i dalje nema stavki, provjeri da li je PDF skeniran
    if result is not None and hasattr(result, 'items') and len(result.items) == 0:
        try:
            from importers.pdf.ocr_utils import is_scanned_pdf, ocr_pdf_to_text
            from importers.pdf.ocr_invoice_parser import parse_ocr_result
            if is_scanned_pdf(pdf_path):
                logger.info("   📷 PDF je skeniran — pokušavam OCR (Tesseract)...")
                pages_text = ocr_pdf_to_text(pdf_path, dpi=300)
                ocr_result = parse_ocr_result(pages_text, pdf_path=pdf_path)
                if ocr_result is not None and len(ocr_result.items) > 0:
                    logger.info(f"   ✅ OCR našao {len(ocr_result.items)} stavki!")
                    result = ocr_result
                else:
                    logger.warning("   ⚠️  OCR nije pronašao stavke")
        except ImportError:
            logger.debug("   OCR nije dostupan (pytesseract/pdf2image nisu instalirani)")
        except Exception as e:
            logger.error(f"   ❌ OCR fallback nije uspio: {e}")

    # 5. FINALNI REZULTAT
    if result is not None:
        item_count = len(result.items) if hasattr(result, 'items') else len(result)
        logger.info(f"✅ Parsiranje završeno: {item_count} stavki")

        # VAŽNO: Dodaj metadata o detektovanom formatu
        # Ovo će pomoći import_service da postavi pravilan last_import_type
        if hasattr(result, '__dict__'):
            result._detected_format = pdf_format  # Hidden attribute za internal use
    else:
        logger.warning("❌ Parsiranje nije uspjelo - nema rezultata")
        result = ImportResult(items=[], bruto_kg=0.0, neto_kg=0.0, invoice_name="", currency="EUR")

    # Oslobodi cache — fajl je parsiran, tekst više nije potreban
    _pdf_text_cache.pop(str(pdf_path), None)

    return result


# SECTION: pdf_format_detection
# PURPOSE: Analizira tekst PDF-a i vraća string-key formata; redoslijed provjera je bitan
# DOC: docs/sections/pdf_format_detection.md
def _detect_pdf_format(pdf_path: str) -> str:
    """
    Detektuje format PDF-a analizirajući tekst.

    Returns:
        "invoice_improved", "blagic_loren", "blagic_attos", "imamoglu", "master_frigo", "medicopharm", "sumaprom", ili "generic"
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Ekstraktuj tekst iz prvih 3 stranice
            text = ""
            for page in pdf.pages[:3]:
                page_text = page.extract_text() or ""
                text += page_text[:2000]  # Ograniči na 2000 karaktera po stranici

            text_upper = text.upper()

            # Normalizovana verzija bez dijakritika (npr. BLAGIĆ → BLAGIC)
            import unicodedata
            text_norm = "".join(
                c for c in unicodedata.normalize("NFD", text_upper)
                if unicodedata.category(c) != "Mn"
            )

            # Sačuvaj u cache — specijalizovani parseri mogu preskočiti re-čitanje
            _pdf_text_cache[str(pdf_path)] = (text, text_upper, text_norm)

            # BLAGIĆ ATTOS - specifičan format (provjeri prije generičkog Blagić)
            # Koristimo text_norm jer PDF može imati BLAGIĆ (dijakritik) umjesto BLAGIC
            if "BLAGIC" in text_norm and "ATTOS" in text_upper:
                return "blagic_attos"

            # INVOICE IMPROVED - moderni format sa specifičnim header-om
            # VAŽNO: Provjeri PRIJE generičkog Blagić Loren!
            # Karakteristični header: No. Code Title Measure Quantity Price Value
            if ("NO." in text_upper and "CODE" in text_upper and
                "TITLE" in text_upper and "MEASURE" in text_upper and
                "QUANTITY" in text_upper and "PRICE" in text_upper):
                return "invoice_improved"

            # IMAMOGLU - provjeri PRIJE blagic_loren jer fakture mogu imati
            # BLAGIC kao ime kupca (uvoznika), što bi lažno aktiviralo blagic_loren
            if "IMAMOGLU" in text_upper or "İMAMOĞLU" in text:
                return "imamoglu"

            # BLAGIĆ LOREN - stariji generički Blagić format
            # Koristimo text_norm za detekciju BLAGIĆ/BLAGIC
            if "BLAGIC" in text_norm or "LOREN" in text_upper:
                # Dodatna provjera - ima li karakteristike Loren fakture
                if "INVOICE" in text_upper and "CODE" in text_upper:
                    return "blagic_loren"

            # MASTER FRIGO
            if "MASTER" in text_upper and "FRIGO" in text_upper:
                return "master_frigo"
            if "MASTERFRIGO" in text_upper:
                return "master_frigo"

            # MEDICO PHARM SERVIS
            if "MEDICO PHARM SERVIS" in text_upper:
                return "medicopharm"

            # PROTON SYSTEM DOO (MGM fakture)
            # Detektuj po nazivu firme ILI po specifičnom zaglavlje tabele
            if "PROTON SYSTEM" in text_upper:
                return "proton_system"
            if ("ŠIFRA ARTIKLA" in text_upper or "SIFRA ARTIKLA" in text_upper) and "NETO CENA" in text_upper:
                return "proton_system"

            # ŠUMAPROM
            if "ŠUMAPROM" in text or "SUMAPROM" in text_upper:
                if "FAKTURA" in text_upper or "INVOICE" in text_upper:
                    return "sumaprom"

            # Skenirani PDF (bez teksta) — probaj OCR za Šumaprom detekciju
            if len(text.strip()) < 50:
                try:
                    from importers.sumaprom_pdf_parser import detect_sumaprom_pdf
                    if detect_sumaprom_pdf(pdf_path):
                        return "sumaprom"
                except Exception:
                    pass

            # LEBURIC / PEKABESKO — PDF je supplement (uz Excel), ne importuje se direktno
            if "PEKABESKO" in text_upper:
                return "leburic_pekabesko"

            # PIP FOOD GROUP
            if "PIP FOOD GROUP" in text_upper or "PIP FOOD" in text_upper:
                if "FAKTURA" in text_upper or "INVOICE" in text_upper:
                    return "pip_food"

            # KG FASHION - fakture od "K... G... FASHION" D.O.O. Cacak
            # Brendovi: Petite Jolie, Vizzano, Benetton, Sisley, Ambitious, Bueno, Jagger itd.
            if "K... G... FASHION" in text_upper or "KGFASHION" in text_upper:
                return "kg_fashion"

            # CMANA - Račun ino kupcu
            if "CMANA" in text_upper and ("RAČUN" in text_upper or "RACUN" in text_upper):
                return "cmana"

            # Nepoznat format - generička extraction
            return "generic"

    except Exception as e:
        logger.warning(f"Greška tokom detekcije formata: {e}")
        return "generic"


def _parse_invoice_improved(pdf_path: str) -> ImportResult:
    """Parsira Invoice-Improved format (moderni format sa NO. CODE TITLE...)."""
    from importers.invoice_improved_parser import parse_invoice_improved
    return parse_invoice_improved(pdf_path)


def _parse_blagic_loren(pdf_path: str) -> ImportResult:
    """Parsira Blagić-Loren format."""
    from importers.blagic_loren_pdf_parser import parse_blagic_loren_pdf
    return parse_blagic_loren_pdf(pdf_path)


def _parse_blagic_attos(pdf_path: str) -> ImportResult:
    """Parsira Blagić-Attos format."""
    from importers.blagic_attos_importer import parse_blagic_attos_with_auto_combine
    return parse_blagic_attos_with_auto_combine(pdf_path)


def _parse_sumaprom(pdf_path: str) -> ImportResult:
    """Parsira ŠUMAPROM format (PDF) — tekstualni ili skenirani (OCR)."""
    from importers.sumaprom_pdf_parser import parse_sumaprom_pdf
    return parse_sumaprom_pdf(pdf_path)


def _parse_imamoglu(pdf_path: str) -> ImportResult:
    """Parsira IMAMOGLU format."""
    from importers.imamoglu_pdf_parser import parse_imamoglu_pdf
    return parse_imamoglu_pdf(pdf_path)


# SECTION: master_frigo_mapping
# PURPOSE: Pronalazi Excel fajl sa tarifama/zemljama koji vrijedi za sve Master Frigo fakture
# DOC: docs/sections/master_frigo_mapping.md
# DOC: scripts/master_frigo_agent_import_2026-04-26.md
def _find_master_frigo_mapping_xlsx(pdf_path: str) -> str | None:
    """
    Traži Excel fajl sa tarifama/zemljama u istom folderu kao PDF.

    Master Frigo šalje jedan Excel ('tarife i zemlje porekla' ili 'podela po poreklu')
    za sve fakture. Tražimo po prepoznatljivim riječima iz tih naziva.
    """
    from pathlib import Path
    folder = Path(pdf_path).parent
    for xlsx in folder.glob("*.xlsx"):
        name_lower = xlsx.name.lower()
        if (
            "tarife" in name_lower
            or "podela" in name_lower
            or "porekla" in name_lower
            or "poreklu" in name_lower
            or "poreklo" in name_lower
            or "porijekla" in name_lower
            or "porijeklu" in name_lower
        ):
            logger.info(f"  📋 Master Frigo: nađen mapping Excel: {xlsx.name}")
            return str(xlsx)
    return None


# DOC: docs/sections/master_frigo_mapping.md — consumed_paths + importer fix
def _parse_master_frigo(pdf_path: str) -> ImportResult:
    """Parsira Master Frigo format koristeći specijalizovani parser."""
    from importers.master_frigo_importer import (
        parse_master_frigo_pdf, convert_to_invoice_lines, _read_mapping_xlsx
    )
    from core.draft.draft import Party

    # Auto-detektuj Excel mapping u istom folderu
    mapping = {}
    xlsx_path = _find_master_frigo_mapping_xlsx(pdf_path)
    consumed: list[str] = []
    if xlsx_path:
        try:
            mapping = _read_mapping_xlsx(xlsx_path)
            logger.info(f"  ✅ Master Frigo mapping učitan: {len(mapping)} šifara")
            # Označiti mapping xlsx kao potrošen — agent ne smije da ga uvozi zasebno
            consumed = [xlsx_path]
        except Exception as e:
            logger.warning(f"  ⚠️ Greška pri učitavanju Master Frigo mapping-a: {e}")

    header, imported_items = parse_master_frigo_pdf(pdf_path, mapping=mapping)
    currency = header.get("currency", "EUR")
    invoice_lines = convert_to_invoice_lines(imported_items, currency=currency)
    bruto_kg = header.get("gross_kg", 0.0)
    neto_kg = header.get("net_kg", 0.0)
    invoice_name = header.get("invoice_no", "")

    # Postavi exporter i importer na svaku stavku (convert_to_invoice_lines samo exporter)
    _exp = Party(name="MASTER FRIGO")
    _imp = Party(name="MASTER FRIGO D.O.O. BANJA LUKA")
    for line in invoice_lines:
        line.exporter = _exp
        line.importer = _imp

    return ImportResult(
        items=invoice_lines,
        bruto_kg=bruto_kg,
        neto_kg=neto_kg,
        invoice_name=invoice_name,
        currency=currency,
        has_origin_statement=header.get("has_origin_statement", False),
        origin_statements=header.get("origin_statements", []),
        exporter=_exp,
        importer=_imp,
        consumed_paths=consumed,
    )


def _parse_medicopharm(pdf_path: str) -> ImportResult:
    """Parsira Medico Pharm Servis format."""
    from importers.medicopharm_importer import parse_medicopharm_pdf
    return parse_medicopharm_pdf(pdf_path)


def _parse_proton_system(pdf_path: str) -> ImportResult:
    """Parsira Proton System DOO format (MGM fakture)."""
    from importers.proton_system_importer import parse_proton_system_pdf
    return parse_proton_system_pdf(pdf_path)


def _parse_leburic_pekabesko(pdf_path: str) -> ImportResult:
    """Parsira Leburic/Pekabesko PDF format (skenirani OCR dokumenti)."""
    from importers.leburic_pekabesko_importer import parse_leburic_pekabesko_pdf
    return parse_leburic_pekabesko_pdf(pdf_path)


def _parse_pip_food(pdf_path: str) -> ImportResult:
    """Parsira PIP Food Group PDF format."""
    from importers.vendors.pip_food.pip_food_parser import parse_pip_food_pdf
    return parse_pip_food_pdf(pdf_path)


def _parse_kg_fashion(pdf_path: str) -> ImportResult:
    """Parsira KG Fashion D.O.O. format (Petite Jolie, Vizzano, Benetton, Sisley, Ambitious, Bueno, Jagger itd.)."""
    from importers.vendors.kg_fashion.kg_fashion_importer import import_kg_fashion
    return import_kg_fashion(pdf_path)


def _parse_cmana(pdf_path: str) -> ImportResult:
    """Parsira CMANA DOO Krnjevo format."""
    from importers.vendors.cmana.cmana_pdf_parser import parse_cmana_pdf
    return parse_cmana_pdf(pdf_path)


# Alias za kompatibilnost
smart_parse_pdf = parse_smart_pdf
