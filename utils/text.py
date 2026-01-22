"""Text processing utils - Qt verzija."""

from typing import Any


def to_str(v: Any) -> str:
    """
    Konvertuje vrednost u string.

    Args:
        v: Bilo koja vrednost

    Returns:
        String reprezentacija (ili prazan string)
    """
    if v is None:
        return ""
    return str(v).strip()


def normalize_text(text: str) -> str:
    """
    Normalizuje tekst - uklanja višestruke razmake, trimuje.

    Args:
        text: Input tekst

    Returns:
        Normalizovan tekst
    """
    if not text:
        return ""
    # Ukloni višestruke razmake
    import re
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Skraćuje tekst na zadatu dužinu.

    Args:
        text: Input tekst
        max_length: Maksimalna dužina
        suffix: Sufiks za dodavanje (default "...")

    Returns:
        Skraćeni tekst
    """
    if not text or len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)] + suffix


def split_lines(text: str, max_line_length: int = 80) -> list[str]:
    """
    Deli tekst na linije određene dužine.

    Args:
        text: Input tekst
        max_line_length: Maksimalna dužina linije

    Returns:
        Lista linija
    """
    if not text:
        return []

    words = text.split()
    lines = []
    current_line = []
    current_length = 0

    for word in words:
        word_length = len(word)
        if current_length + word_length + len(current_line) <= max_line_length:
            current_line.append(word)
            current_length += word_length
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
            current_length = word_length

    if current_line:
        lines.append(" ".join(current_line))

    return lines


def clean_string(s: str) -> str:
    """
    Čisti string - uklanja non-printable karaktere.

    Args:
        s: Input string

    Returns:
        Očišćen string
    """
    if not s:
        return ""
    return "".join(c for c in s if c.isprintable() or c in "\n\r\t").strip()
