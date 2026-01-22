"""Money utils - rad sa valutama i iznosima."""

from decimal import Decimal, ROUND_HALF_UP


def format_money(amount: float, currency: str = "EUR", decimals: int = 2) -> str:
    """
    Formatira novčani iznos.

    Args:
        amount: Iznos
        currency: Valuta (EUR, USD, BAM...)
        decimals: Broj decimala

    Returns:
        Formatirani string (npr. "1,234.56 EUR")
    """
    d = Decimal(str(amount)).quantize(
        Decimal(10) ** -decimals,
        rounding=ROUND_HALF_UP
    )
    formatted = f"{d:,.{decimals}f}"
    return f"{formatted} {currency}"


def parse_money(value: str) -> float:
    """
    Parsira novčani iznos iz stringa.

    Args:
        value: String sa iznosom (npr. "1,234.56")

    Returns:
        Float vrednost
    """
    if not value:
        return 0.0

    # Ukloni valute i razmake
    cleaned = value.strip()
    for curr in ["EUR", "USD", "BAM", "RSD", "€", "$"]:
        cleaned = cleaned.replace(curr, "")

    # Ukloni separatore hiljada
    cleaned = cleaned.replace(",", "").replace(" ", "")

    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def convert_currency(
    amount: float,
    from_currency: str,
    to_currency: str,
    exchange_rate: float
) -> float:
    """
    Konvertuje iznos iz jedne valute u drugu.

    Args:
        amount: Iznos za konverziju
        from_currency: Polazna valuta
        to_currency: Ciljna valuta
        exchange_rate: Kurs konverzije

    Returns:
        Konvertovani iznos
    """
    if from_currency == to_currency:
        return amount

    return amount * exchange_rate


def round_money(amount: float, decimals: int = 2) -> float:
    """
    Zaokružuje novčani iznos na zadati broj decimala.

    Args:
        amount: Iznos
        decimals: Broj decimala

    Returns:
        Zaokruženi iznos
    """
    d = Decimal(str(amount)).quantize(
        Decimal(10) ** -decimals,
        rounding=ROUND_HALF_UP
    )
    return float(d)
