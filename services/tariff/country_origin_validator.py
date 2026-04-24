# services/country_origin_validator.py

"""
Country Origin Validator

Validacija zemlje porijekla na osnovu podataka iz PDF fakture i baze znanja.

Hijerarhija validacije:
1. Ako PDF ima poreklo → koristi se PDF (visok prioritet)
2. Ako PDF nema, a baza ima → koristi se baza (srednji prioritet)
3. Ako oba imaju → poredi se i flaguje konflikt
4. Ako nijedan nema → ostaje prazno (nizak prioritet)
"""

import logging
from enum import Enum
from typing import Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger("asycuda_pro.country_origin_validator")


class ConfidenceLevel(Enum):
    """Nivo pouzdanosti za zemlju porijekla."""
    HIGH = "HIGH"           # PDF ima ili oba poklapaju
    MEDIUM = "MEDIUM"       # Samo baza ima
    LOW = "LOW"             # Nijedan nema
    CONFLICT = "CONFLICT"   # PDF i baza imaju različite vrednosti


@dataclass
class CountryValidationResult:
    """Rezultat validacije zemlje porijekla."""
    final_country: str          # Finalna zemlja porijekla
    final_preference: str       # Izvedena povlastica
    confidence: ConfidenceLevel # Nivo pouzdanosti
    source: str                 # Izvor: "PDF", "BAZA", "CONFLICT", "NONE", "PDF_IZJAVA", "PDF_OZNAKA"
    has_origin_statement: bool = False  # Da li PDF sadrži izjavu o poreklu
    conflict_details: Optional[str] = None  # Detalji konflikta


# ISO 3166-1 alpha-2 kodovi EU članica
_EU_MEMBER_STATES: frozenset[str] = frozenset({
    "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI",
    "FR", "GR", "HR", "HU", "IE", "IT", "LT", "LU", "LV", "MT",
    "NL", "PL", "PT", "RO", "SE", "SI", "SK",
})

# Povlastica kodovi koji su isključivo za robu EU porijekla
_EU_ONLY_PREFERENCES: frozenset[str] = frozenset({"EUP"})

# CEFTA potpisnice (osim BA — to je uvoznik)
_CEFTA_MEMBER_STATES: frozenset[str] = frozenset({
    "RS", "MK", "AL", "ME", "MD", "XK",
})


def derive_preference(zemlja: str) -> str:
    """
    Izvedi povlasticu na osnovu zemlje porijekla.

    Pravila:
    - EU članica → EUP
    - CEFTA potpisnica → CEFTAP
    - Ostalo → ""

    Args:
        zemlja: ISO 3166-1 alpha-2 kod zemlje

    Returns:
        Kod povlastice ("EUP", "CEFTAP") ili prazan string
    """
    if not zemlja:
        return ""

    zemlja_upper = zemlja.strip().upper()

    if zemlja_upper in _EU_MEMBER_STATES:
        return "EUP"

    if zemlja_upper in _CEFTA_MEMBER_STATES:
        return "CEFTAP"

    if zemlja_upper in {"CH", "NO", "IS", "LI"}:
        return "EFTA2"  # Izjava o porijeklu na fakturi (PEM konvencija)

    return ""


def validate_preference(zemlja: str, povlastica: str) -> str:
    """
    Validiraj kombinaciju zemlja+povlastica.

    Roba iz ne-EU zemalja ne može imati EU povlasticu (EUP).

    Args:
        zemlja: ISO kod zemlje
        povlastica: Kod povlastice

    Returns:
        Validna povlastica ili prazan string ako nije validno
    """
    if not povlastica:
        return povlastica
    
    zemlja_upper = (zemlja or "").strip().upper()
    povlastica_upper = povlastica.strip().upper()
    
    if povlastica_upper in _EU_ONLY_PREFERENCES and zemlja_upper not in _EU_MEMBER_STATES:
        logger.debug(
            f"⚠️ Nevalidna kombinacija: zemlja={zemlja!r}, povlastica={povlastica!r} → povlastica odbijena"
        )
        return ""
    
    return povlastica


def merge_country_origin(
    zemlja_pdf: str,
    zemlja_baza: str,
    povlastica_baza: str = "",
    has_origin_statement: bool = False,  # Da li PDF ima izjavu o poreklu
) -> CountryValidationResult:
    """
    Glavna funkcija za spajanje i validaciju zemlje porijekla.

    HIJERARHIJA:
    1. PDF ima IZJAVU o poreklu → koristi se PDF + povlastica (HIGH)
    2. PDF ima samo OZNAKU zemlje (bez izjave) → koristi se zemlja, BEZ povlastice (MEDIUM)
    3. PDF nema ništa, baza ima → NE KORISTI SE (ostaje prazno)
    4. Oba imaju i poklapaju se → koristi se (HIGH)
    5. Oba imaju i različita → koristi se PDF, flaguj konflikt (CONFLICT)
    6. Oba prazna → ostaje prazno (LOW)

    VAŽNO: Povlastica se NIKADA ne uzima automatski iz baze!
    Povlastica se dodeljuje samo ako:
    - PDF ima izjavu o poreklu, ILI
    - Zemlja je iz EU (EUP se automatski izvede)

    Args:
        zemlja_pdf: Zemlja porijekla iz PDF fakture
        zemlja_baza: Zemlja porijekla iz baze znanja
        povlastica_baza: Povlastica iz baze znanja (koristi se samo za validaciju)
        has_origin_statement: Da li PDF sadrži izjavu o poreklu

    Returns:
        CountryValidationResult sa finalnim podacima i nivoom pouzdanosti
    """
    # Normalizuj inpute
    pdf_clean = (zemlja_pdf or "").strip().upper()
    baza_clean = (zemlja_baza or "").strip().upper()
    pref_baza = (povlastica_baza or "").strip().upper()

    logger.debug(
        f"🔍 merge_country_origin: PDF='{pdf_clean}', BAZA='{baza_clean}', "
        f"has_statement={has_origin_statement}, PREF='{pref_baza}'"
    )

    # SLUČAJ 1: PDF ima IZJAVU o poreklu → najviši prioritet
    if has_origin_statement and pdf_clean:
        pref = derive_preference(pdf_clean)
        logger.info(f"  ✅ PDF IZJAVA: zemlja={pdf_clean}, pref={pref}")
        return CountryValidationResult(
            final_country=pdf_clean,
            final_preference=pref,
            confidence=ConfidenceLevel.HIGH,
            source="PDF_IZJAVA",
            has_origin_statement=True
        )

    # SLUČAJ 2: PDF ima samo OZNAKU (bez izjave) → zemlja DA, povlastica NE
    if pdf_clean and not has_origin_statement:
        logger.warning(f"  ⚠️ PDF OZNAKA (bez izjave): zemlja={pdf_clean}, BEZ povlastice")
        return CountryValidationResult(
            final_country=pdf_clean,
            final_preference="",  # ⚠️ NEMA automatske povlastice!
            confidence=ConfidenceLevel.MEDIUM,
            source="PDF_OZNAKA",
            has_origin_statement=False,
            conflict_details="PDF nema izjavu o poreklu - potrebna intervencija korisnika za povlasticu"
        )

    # SLUČAJ 3: PDF nema ništa → NE KORISTI BAZU automatski
    if not pdf_clean:
        # Čak i ako baza ima zemlju, ne uzimamo je automatski
        # Korisnik mora ručno da interveniše
        logger.info(f"  📋 PDF nema podataka → ostaje prazno (korisnik treba da unese)")
        return CountryValidationResult(
            final_country="",
            final_preference="",
            confidence=ConfidenceLevel.LOW,
            source="NONE",
            has_origin_statement=False,
            conflict_details="Nema podataka o poreklu - potreban manuelni unos ili EUR1 obrazac"
        )

    # SLUČAJ 4: Oba imaju (pdf_clean i baza_clean) → poredi
    # Ovo se dešava samo ako has_origin_statement=False ali pdf_clean postoji
    # (oznaka zemlje u PDF-u bez izjave)
    if pdf_clean and baza_clean:
        if pdf_clean == baza_clean:
            # POKLAPANJE
            pref = derive_preference(pdf_clean)
            logger.info(f"  ✅ POKLAPANJE: zemlja={pdf_clean}, pref={pref}")
            return CountryValidationResult(
                final_country=pdf_clean,
                final_preference=pref,
                confidence=ConfidenceLevel.HIGH,
                source="MATCH",
                has_origin_statement=False  # Nema izjavu, ali se poklapa
            )
        else:
            # KONFLIKT → PDF ima prioritet, ali flaguj
            pref = derive_preference(pdf_clean)
            conflict_msg = f"PDF: {pdf_clean} vs BAZA: {baza_clean}"
            logger.warning(f"  🚨 KONFLIKT: {conflict_msg} → koristim PDF ({pdf_clean})")
            return CountryValidationResult(
                final_country=pdf_clean,
                final_preference=pref,
                confidence=ConfidenceLevel.CONFLICT,
                source="CONFLICT",
                has_origin_statement=False,
                conflict_details=conflict_msg
            )

    # Fallback (trebalo bi da je pokriveno gore)
    logger.debug(f"  📋 Fallback: nema podataka")
    return CountryValidationResult(
        final_country="",
        final_preference="",
        confidence=ConfidenceLevel.LOW,
        source="NONE",
        has_origin_statement=False
    )


def get_confidence_color(confidence: ConfidenceLevel) -> str:
    """
    Vrati boju za vizuelnu indikaciju confidence nivoa.

    Args:
        confidence: Nivo pouzdanosti

    Returns:
        Hex kod boje
    """
    colors = {
        ConfidenceLevel.HIGH: "#28a745",      # 🟢 Zelena
        ConfidenceLevel.MEDIUM: "#ffc107",    # 🟡 Žuta
        ConfidenceLevel.LOW: "#fd7e14",       # 🟠 Narandžasta
        ConfidenceLevel.CONFLICT: "#dc3545",  # 🔴 Crvena
    }
    return colors.get(confidence, "#6c757d")  # Siva kao fallback


def get_confidence_tooltip(confidence: ConfidenceLevel, source: str, conflict_details: str = None) -> str:
    """
    Kreiraj tooltip opis za confidence nivo.

    Args:
        confidence: Nivo pouzdanosti
        source: Izvor podataka
        conflict_details: Detalji konflikta (ako postoji)

    Returns:
        Tooltip string
    """
    tooltips = {
        ConfidenceLevel.HIGH: {
            "PDF": "✅ Podatak iz PDF fakture (visoka pouzdanost)",
            "MATCH": "✅ PDF i baza se poklapaju (visoka pouzdanost)",
        },
        ConfidenceLevel.MEDIUM: "📋 Podatak iz baze znanja (srednja pouzdanost)",
        ConfidenceLevel.LOW: "⚠️ Nema podataka o poreklu (potreban manuelni unos)",
        ConfidenceLevel.CONFLICT: f"🚨 Konflikt porekla: {conflict_details or 'PDF i baza imaju različite vrednosti'}",
    }
    
    if confidence == ConfidenceLevel.HIGH and source in tooltips[ConfidenceLevel.HIGH]:
        return tooltips[ConfidenceLevel.HIGH][source]
    
    return tooltips.get(confidence, "❓ Nepoznata pouzdanost")


# ============================================================
# USAGE EXAMPLE / TEST
# ============================================================

if __name__ == "__main__":
    # Test scenarios
    test_cases = [
        # (pdf, baza, pref_baza, opis)
        ("SI", "SI", "EUP", "Poklapanje - oba SI"),
        ("SI", "DE", "EUP", "Konflikt - PDF:SI, BAZA:DE"),
        ("SI", "", "", "Samo PDF ima"),
        ("", "SI", "EUP", "Samo baza ima"),
        ("", "", "", "Nijedan nema"),
        ("US", "US", "", "Ne-EU zemlja - bez povlastice"),
        ("DE", "DE", "EUP", "EU zemlja - EUP povlastica"),
        ("CN", "CN", "EUP", "Ne-EU sa EUP → treba odbaciti EUP"),
    ]

    logger.debug("=" * 70)
    logger.debug("COUNTRY ORIGIN VALIDATOR - TEST SCENARIOS")
    logger.debug("=" * 70)

    for pdf, baza, pref, opis in test_cases:
        result = merge_country_origin(pdf, baza, pref)
        logger.debug(f"\n📋 {opis}")
        logger.debug(f"   Input: PDF='{pdf}', BAZA='{baza}', PREF='{pref}'")
        logger.debug(f"   Result: country='{result.final_country}', pref='{result.final_preference}'")
        logger.debug(f"   Confidence: {result.confidence.value} (source: {result.source})")
        if result.conflict_details:
            logger.warning(f"   ⚠️ Conflict: {result.conflict_details}")
        logger.debug(f"   Color: {get_confidence_color(result.confidence)}")
