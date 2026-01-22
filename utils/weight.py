"""Weight utils - rad sa težinama."""

from decimal import Decimal, ROUND_HALF_UP


def kg_to_g(kg: float) -> float:
    """
    Konvertuje kilograme u grame.

    Args:
        kg: Težina u kilogramima

    Returns:
        Težina u gramima
    """
    return kg * 1000


def g_to_kg(g: float) -> float:
    """
    Konvertuje grame u kilograme.

    Args:
        g: Težina u gramima

    Returns:
        Težina u kilogramima
    """
    return g / 1000


def kg_to_ton(kg: float) -> float:
    """
    Konvertuje kilograme u tone.

    Args:
        kg: Težina u kilogramima

    Returns:
        Težina u tonama
    """
    return kg / 1000


def ton_to_kg(ton: float) -> float:
    """
    Konvertuje tone u kilograme.

    Args:
        ton: Težina u tonama

    Returns:
        Težina u kilogramima
    """
    return ton * 1000


def format_weight(kg: float, decimals: int = 3) -> str:
    """
    Formatira težinu u kilograme sa zadatim brojem decimala.

    Args:
        kg: Težina u kilogramima
        decimals: Broj decimala

    Returns:
        Formatiran string (npr. "123.456 kg")
    """
    d = Decimal(str(kg)).quantize(
        Decimal(10) ** -decimals,
        rounding=ROUND_HALF_UP
    )
    return f"{d} kg"


def parse_weight(value: str) -> float:
    """
    Parsira težinu iz stringa.

    Args:
        value: String sa težinom (npr. "123.45 kg", "100g", "1.5t")

    Returns:
        Težina u kilogramima
    """
    if not value:
        return 0.0

    value = value.strip().lower()

    # Ukloni razmake
    value = value.replace(" ", "")

    # Detektuj jedinicu mere
    if "kg" in value:
        value = value.replace("kg", "")
        multiplier = 1.0
    elif "g" in value:
        value = value.replace("g", "")
        multiplier = 0.001
    elif "t" in value or "ton" in value:
        value = value.replace("t", "").replace("on", "")
        multiplier = 1000.0
    else:
        # Default: pretpostavka kg
        multiplier = 1.0

    try:
        return float(value) * multiplier
    except ValueError:
        return 0.0


def round_weight(kg: float, decimals: int = 3) -> float:
    """
    Zaokružuje težinu na zadati broj decimala.

    Args:
        kg: Težina u kilogramima
        decimals: Broj decimala

    Returns:
        Zaokružena težina
    """
    d = Decimal(str(kg)).quantize(
        Decimal(10) ** -decimals,
        rounding=ROUND_HALF_UP
    )
    return float(d)
