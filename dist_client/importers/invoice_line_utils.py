# importers/invoice_line_utils.py
"""
Zajednički alati za parsiranje linija faktura.

Koriste se u svim specijalizovanim PDF importerima da osiguraju konzistentno
ponašanje bez obzira na dobavljača ili varijantu formata.
"""

import re
from typing import Optional


# ---------------------------------------------------------------------------
# Poznate jedinice mjere (JM)
# ---------------------------------------------------------------------------

KNOWN_JM: frozenset = frozenset({
    "kom", "kg", "g", "m", "m2", "m3", "l", "ml",
    "pcs", "par", "set", "kpl", "pak", "rol", "box",
    "sc", "fl",  # Medico Pharm: SC (plaster sheet), FL (flacon)
})


# ---------------------------------------------------------------------------
# Parsiranje brojeva
# ---------------------------------------------------------------------------

def parse_eu_number(s: str) -> float:
    """
    Parsira broj u evropskom formatu (1.234,56 → 1234.56).

    Auto-detekcija između EU i US formata:
    - Ako su prisutni i ',' i '.' → zadnji separator je decimalni
    - Ako je samo ',' → tretiramo kao decimalni zarez (EU stil)
    - Ako je samo '.' → tretiramo kao decimalni separator (US/neutralni stil)

    Args:
        s: String koji sadrži broj

    Returns:
        Float vrijednost, ili 0.0 ako parsiranje nije uspjelo
    """
    s = (s or "").strip().replace(" ", "")
    if not s:
        return 0.0

    if "," in s and "." in s:
        if s.rfind(".") > s.rfind(","):
            # US format: 1,234.56 → ukloni zareze
            s = s.replace(",", "")
        else:
            # EU format: 1.234,56 → ukloni tačke, zamijeni zarez tačkom
            s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        # EU bez hiljadarskog separatora: 1234,56
        s = s.replace(",", ".")
    # else: neutralni format s tačkom ili bez separatora

    try:
        return float(s)
    except ValueError:
        return 0.0


def parse_number_permissive(text: str) -> float:
    """
    Parsira broj iz teksta, uklanjajući sve osim cifara/tačke/zareza/minusa
    prije parsiranja (valutni simboli, razmaci i sl. se ignorišu).

    Zarez se uvijek tretira kao decimalni separator. Ako nakon zamjene
    ostane više od jedne tačke (izvorni tekst je imao i tačku i zarez),
    sve tačke osim zadnje se tretiraju kao separator hiljada.

    Args:
        text: String koji sadrži broj

    Returns:
        Float vrijednost, ili 0.0 ako parsiranje nije uspjelo
    """
    if not text:
        return 0.0

    text = re.sub(r'[^\d,.\-]', '', str(text))
    text = text.replace(',', '.')

    if text.count('.') > 1:
        parts = text.split('.')
        text = ''.join(parts[:-1]) + '.' + parts[-1]

    try:
        return float(text)
    except ValueError:
        return 0.0


def parse_number_thousands_heuristic(text: str) -> float:
    """
    Parsira broj iz teksta uz heuristiku za dvosmislen slučaj jednog separatora.

    Kad su prisutni i ',' i '.', zadnji separator je decimalni (isto kao
    parse_eu_number). Kad je prisutan SAMO jedan separator, dodatno provjerava
    broj cifara iza njega: tačno 3 cifre iza jedinog separatora → tretira se
    kao separator hiljada (npr. "1,234" → 1234.0), inače kao decimalni
    (npr. "1,5" → 1.5). Ovo namjerno odstupa od parse_eu_number-a, koji
    jedan zarez UVIJEK tretira kao decimalni — koristiti samo gdje je ova
    heuristika već dokazano ispravna za dati izvor podataka.

    Args:
        text: String koji sadrži broj

    Returns:
        Float vrijednost, ili 0.0 ako parsiranje nije uspjelo
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
        last_comma = text.rfind(',')
        last_dot = text.rfind('.')
        if last_dot > last_comma:
            text = text.replace(',', '')
        else:
            text = text.replace('.', '').replace(',', '.')
    elif has_comma and not has_dot:
        parts = text.split(',')
        if len(parts) == 2 and len(parts[1]) == 3 and parts[0].isdigit():
            text = text.replace(',', '')
        else:
            text = text.replace(',', '.')
    elif has_dot and not has_comma:
        parts = text.split('.')
        if len(parts) == 2 and len(parts[1]) == 3 and parts[0].isdigit():
            text = text.replace('.', '')
        elif text.count('.') > 1:
            text = text.replace('.', '')

    try:
        return float(text)
    except (ValueError, TypeError):
        return 0.0


# ---------------------------------------------------------------------------
# Parsiranje "repa" stavke (JM + numeričke kolone)
# ---------------------------------------------------------------------------

def parse_invoice_tail(parts: list) -> Optional[dict]:
    """
    Iz split() tokena linije fakture izvlači strukturirani "rep":
    JM, količina, cijena, (CC,) iznos.

    Podržava dva formata koji se automatski detektuju:

      Format A — sa kodom porekla (CC):
        ... NAZIV  JM  KOL  CENA  CC  IZNOS
        Primjer:  "...  kom  20,00  2,9300  SI  58,60"

      Format B — bez koda porekla:
        ... NAZIV  JM  KOL  CENA  IZNOS
        Primjer:  "...  kom  50,00  2,1500  107,50"

    JM se traži na pozicijama od desna: -4 ili -5.
    CC se prepoznaje kao tačno 2 velika latinična slova (npr. SI, HR, DE).

    Args:
        parts: Lista tokena iz `line.split()`

    Returns:
        Dict sa ključevima:
          jm         - jedinica mjere (string)
          jm_pos     - indeks JM u `parts`
          kolicina_str, cijena_str, iznos_str  - sirovi stringovi
          poreklo    - 2-slovna CC šifra ili "" ako nema
        None ako format nije prepoznatljiv ili linija nepotpuna
    """
    if not parts or len(parts) < 6:
        return None

    # Pretraga JM od desna: normalno je na poziciji -4 ili -5
    jm_pos = -1
    for offset in (4, 5):
        if len(parts) > offset and parts[-offset].lower() in KNOWN_JM:
            jm_pos = len(parts) - offset
            break

    if jm_pos < 0:
        return None

    jm = parts[jm_pos]
    remaining = parts[jm_pos + 1:]  # Sve iza JM

    if len(remaining) == 4 and re.match(r"^[A-Z]{2}$", remaining[2]):
        # Format A: KOL  CENA  CC  IZNOS
        kolicina_str, cijena_str, poreklo, iznos_str = remaining
    elif len(remaining) == 3:
        # Format B: KOL  CENA  IZNOS
        kolicina_str, cijena_str, iznos_str = remaining
        poreklo = ""
    else:
        # Nepotpuna linija (odsječena na kraju stranice) ili nepoznat format
        return None

    return {
        "jm": jm,
        "jm_pos": jm_pos,
        "kolicina_str": kolicina_str,
        "cijena_str": cijena_str,
        "iznos_str": iznos_str,
        "poreklo": poreklo,
    }


def parse_packing_tail(parts: list) -> Optional[dict]:
    """
    Iz split() tokena linije liste pakovanja izvlači strukturirani "rep":
    CC, JM, količina, neto_kg, bruto_kg.

    Format (Blagić Attos packing list):
      ... NAZIV  CC  JM  KOL  NETO  BRUTO
      Primjer:  "...  SI  kom  20,00  1,400  1,940"

    JM se traži na poziciji -4 (od desna), CC je na -5.

    Args:
        parts: Lista tokena iz `line.split()`

    Returns:
        Dict sa ključevima: cc, jm, jm_pos, kolicina_str, neto_str, bruto_str
        None ako format nije prepoznatljiv
    """
    if not parts or len(parts) < 7:
        return None

    # JM je na poziciji -4 (ispred kol, neto, bruto)
    if len(parts) < 4 or parts[-4].lower() not in KNOWN_JM:
        return None

    jm_pos = len(parts) - 4
    jm = parts[jm_pos]
    cc = parts[jm_pos - 1] if jm_pos > 0 else ""

    # Validacija CC: tačno 2 velika slova
    if not re.match(r"^[A-Z]{2}$", cc):
        cc = ""

    kolicina_str = parts[-3]
    neto_str = parts[-2]
    bruto_str = parts[-1]

    return {
        "cc": cc,
        "jm": jm,
        "jm_pos": jm_pos,
        "kolicina_str": kolicina_str,
        "neto_str": neto_str,
        "bruto_str": bruto_str,
    }


# ---------------------------------------------------------------------------
# Normalizacija tarifnih brojeva
# ---------------------------------------------------------------------------

def normalize_tariff_number(code: str) -> str:
    """
    Normalizuje tarifni broj na interni format od najviše 8 cifara.

    Pravila:
    - Ako kod sadrži '/', uzima se dio prije kose crte (npr. "21069098/9080" → "21069098")
    - Uklanjaju se svi ne-numerički znakovi (razmaci, slova poput "ex", tačke)
    - Više od 8 cifara → skraćuje se na prvih 8
    - < 8 cifara → ostaje kakvo jeste (djelimičan unos)

    Primjeri:
        "30051000000"      → "30051000"   (skraćeno na 8)
        "21069098/9080"    → "21069098"   (uzet dio prije /)
        "38249993"         → "38249993"   (već 8, ostaje)
        "ex 8511 80 00 10" → "85118000"   (interni CN format)
        "8511800000"       → "85118000"
        ""                 → ""
    """
    if not code:
        return ""
    # Ako ima '/', uzmi samo dio prije kose crte
    if "/" in code:
        code = code.split("/")[0]
    # Zadrži samo cifre (uklanja "ex", razmake, tačke itd.)
    digits = re.sub(r"\D", "", code)
    if not digits:
        return ""
    return digits[:8] if len(digits) > 8 else digits
