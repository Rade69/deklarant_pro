# utils/country_normalizer.py

"""
Normalizacija naziva zemalja u ISO 3166-1 alpha-2 kodove.
Koristi se za ASYCUDA sistem koji zahteva 2-slovne kodove.
"""

import re
import unicodedata
from typing import Optional


def _strip_diacritics(text: str) -> str:
    """Skini dijakritičke znake (š→s, č→c, ć→c, ž→z, đ→d...) za fallback lookup."""
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


# Mapa naziva zemalja → ISO 3166-1 alpha-2 kodovi
COUNTRY_NAME_TO_CODE = {
    # Balkan region
    "bosna i hercegovina": "BA",
    "bosna": "BA",
    "bih": "BA",
    "srbija": "RS",
    "hrvatska": "HR",
    "slovenija": "SI",
    "crna gora": "ME",
    "makedonija": "MK",
    "severna makedonija": "MK",
    "sjeverna makedonija": "MK",
    "albanija": "AL",

    # Europe - West
    "nemacka": "DE",
    "nemačka": "DE",
    "njemacka": "DE",
    "njemačka": "DE",
    "germany": "DE",
    "austrija": "AT",
    "svajcarska": "CH",
    "švajcarska": "CH",
    "švicarska": "CH",
    "switzerland": "CH",
    "francuska": "FR",
    "france": "FR",
    "belgija": "BE",
    "holandija": "NL",
    "nizozemska": "NL",
    "netherlands": "NL",
    "luksemburg": "LU",

    # Europe - South
    "italija": "IT",
    "italy": "IT",
    "spanija": "ES",
    "spain": "ES",
    "portugal": "PT",
    "grcka": "GR",
    "grčka": "GR",
    "greece": "GR",

    # Europe - North
    "svedska": "SE",
    "švedska": "SE",
    "sweden": "SE",
    "norveska": "NO",
    "norveška": "NO",
    "norway": "NO",
    "danska": "DK",
    "denmark": "DK",
    "finska": "FI",
    "finland": "FI",

    # Europe - East
    "poljska": "PL",
    "polijska": "PL",  # Medico Pharm: greška u pisanju umjesto POLJSKA
    "poland": "PL",
    "ceska": "CZ",
    "češka": "CZ",
    "czech": "CZ",
    "slovacka": "SK",
    "slovačka": "SK",
    "slovakia": "SK",
    "madjarska": "HU",
    "mađarska": "HU",
    "hungary": "HU",
    "rumunija": "RO",
    "romania": "RO",
    "bugarska": "BG",
    "bulgaria": "BG",

    # Asia
    "kina": "CN",
    "china": "CN",
    "japan": "JP",
    "japan": "JP",
    "koreja": "KR",
    "juzna koreja": "KR",
    "južna koreja": "KR",
    "south korea": "KR",
    "indija": "IN",
    "india": "IN",
    "tajland": "TH",
    "thailand": "TH",
    "vijetnam": "VN",
    "vietnam": "VN",
    "malezija": "MY",
    "malaysia": "MY",
    "singapur": "SG",
    "singapore": "SG",
    "tajvan": "TW",
    "taiwan": "TW",
    "hong kong": "HK",
    "hongkong": "HK",
    "pakistan": "PK",
    "bangladesh": "BD",
    "indonesia": "ID",
    "filipini": "PH",
    "philippines": "PH",

    # Americas
    "amerika": "US",
    "sad": "US",
    "usa": "US",
    "united states": "US",
    "sjedinjene am": "US",    # Medico Pharm: "SJEDINJENE AM." = SAD
    "sjedinjene am.": "US",   # sa tačkom
    "kanada": "CA",
    "canada": "CA",
    "meksiko": "MX",
    "mexico": "MX",
    "brazil": "BR",
    "brazil": "BR",
    "argentina": "AR",
    "cile": "CL",
    "chile": "CL",

    # Middle East
    "turska": "TR",
    "turkey": "TR",
    "izrael": "IL",
    "israel": "IL",
    "uae": "AE",
    "ujedinjeni arapski emirati": "AE",
    "saudijska arabija": "SA",
    "saudi arabia": "SA",

    # Africa
    "juzna afrika": "ZA",
    "južna afrika": "ZA",
    "south africa": "ZA",
    "egipat": "EG",
    "egypt": "EG",

    # Oceania
    "australija": "AU",
    "australia": "AU",
    "novi zeland": "NZ",
    "new zealand": "NZ",

    # UK & Ireland
    "velika britanija": "GB",
    "united kingdom": "GB",
    "uk": "GB",
    "engleska": "GB",
    "england": "GB",
    "irska": "IE",
    "ireland": "IE",

    # Russia & neighbors
    "rusija": "RU",
    "russia": "RU",
    "ukrajina": "UA",
    "ukraine": "UA",
    "belorusija": "BY",
    "belarus": "BY",
}


def normalize_country_name(country_name: Optional[str]) -> str:
    """
    Normalizuje naziv zemlje u ISO 3166-1 alpha-2 kod (2 slova).

    Args:
        country_name: Naziv zemlje (pun naziv, skraćenica, ili ISO kod)

    Returns:
        ISO 3166-1 alpha-2 kod (npr. "CN", "IT", "CH")
        Vraća original ako nije pronađena normalizacija

    Examples:
        >>> normalize_country_name("KINA")
        'CN'
        >>> normalize_country_name("Italija")
        'IT'
        >>> normalize_country_name("ŠVAJCARSKA")
        'CH'
        >>> normalize_country_name("CN")  # Already ISO code
        'CN'
    """
    if not country_name:
        return ""

    # Trim whitespace
    country = str(country_name).strip()

    if not country:
        return ""

    # Already ISO code? (2 uppercase letters)
    if re.match(r"^[A-Z]{2}$", country):
        return country

    # Normalize to lowercase for lookup
    country_lower = country.lower()

    # Remove non-letter chars except spaces (keep Latin, Cyrillic, and special chars like č,ć,š,ž)
    # Remove only digits and punctuation
    country_lower = re.sub(r"[0-9.,;:!?()\[\]{}\"']", "", country_lower)
    country_lower = re.sub(r"\s+", " ", country_lower).strip()

    # Lookup in map
    iso_code = COUNTRY_NAME_TO_CODE.get(country_lower)

    if iso_code:
        return iso_code

    # Fallback: skini dijakritike (npr. iz Excel-a stiže "ŠPANIJA", a u mapi
    # postoji samo "spanija") — pokušaj ponovo bez š/č/ć/ž/đ
    stripped = _strip_diacritics(country_lower)
    if stripped != country_lower:
        iso_code = COUNTRY_NAME_TO_CODE.get(stripped)
        if iso_code:
            return iso_code

    # Not found - return original (uppercase if 2 letters)
    if len(country) == 2:
        return country.upper()

    return country


def normalize_country_batch(countries: list) -> dict:
    """
    Normalizuje listu naziva zemalja u ISO kodove.

    Args:
        countries: Lista naziva zemalja

    Returns:
        Dict: original → ISO kod
    """
    result = {}
    for country in countries:
        if country:
            result[country] = normalize_country_name(country)
    return result


# Test funkcija
if __name__ == "__main__":
    # Test sa primjerima iz Excel fajla
    test_countries = [
        "KINA", "Kina", "ITALIJA", "Italija", "ŠVAJCARSKA",
        "FRANCUSKA", "DANSKA", "NEMACKA", "RUMUNIJA",
        "SLOVACKA", "SLOVAČKA", "INDIJA", "Tajvan", "CN", "IT"
    ]

    print("=" * 60)
    print("Test normalizacije zemalja:")
    print("=" * 60)

    for country in test_countries:
        normalized = normalize_country_name(country)
        print(f"{country:20} → {normalized}")
