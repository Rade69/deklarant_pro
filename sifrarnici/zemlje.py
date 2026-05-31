"""Šifarnik zemalja - ISO 3166-1 alpha-2."""

from dataclasses import dataclass
from typing import List


@dataclass
class Zemlja:
    """Država."""

    kod: str  # ISO 3166-1 alpha-2
    naziv: str
    naziv_en: str


# Najčešće korišćene zemlje u regionu
ZEMLJE: List[Zemlja] = [
    Zemlja(kod="BA", naziv="Bosna i Hercegovina", naziv_en="Bosnia and Herzegovina"),
    Zemlja(kod="RS", naziv="Srbija", naziv_en="Serbia"),
    Zemlja(kod="HR", naziv="Hrvatska", naziv_en="Croatia"),
    Zemlja(kod="SI", naziv="Slovenija", naziv_en="Slovenia"),
    Zemlja(kod="ME", naziv="Crna Gora", naziv_en="Montenegro"),
    Zemlja(kod="MK", naziv="Sjeverna Makedonija", naziv_en="North Macedonia"),
    Zemlja(kod="AL", naziv="Albanija", naziv_en="Albania"),
    Zemlja(kod="XK", naziv="Kosovo", naziv_en="Kosovo"),
    # EU zemlje
    Zemlja(kod="DE", naziv="Njemačka", naziv_en="Germany"),
    Zemlja(kod="IT", naziv="Italija", naziv_en="Italy"),
    Zemlja(kod="AT", naziv="Austrija", naziv_en="Austria"),
    Zemlja(kod="FR", naziv="Francuska", naziv_en="France"),
    Zemlja(kod="NL", naziv="Holandija", naziv_en="Netherlands"),
    Zemlja(kod="BE", naziv="Belgija", naziv_en="Belgium"),
    Zemlja(kod="ES", naziv="Španija", naziv_en="Spain"),
    Zemlja(kod="PT", naziv="Portugalija", naziv_en="Portugal"),
    Zemlja(kod="GR", naziv="Grčka", naziv_en="Greece"),
    Zemlja(kod="PL", naziv="Poljska", naziv_en="Poland"),
    Zemlja(kod="CZ", naziv="Češka", naziv_en="Czech Republic"),
    Zemlja(kod="SK", naziv="Slovačka", naziv_en="Slovakia"),
    Zemlja(kod="HU", naziv="Mađarska", naziv_en="Hungary"),
    Zemlja(kod="RO", naziv="Rumunija", naziv_en="Romania"),
    Zemlja(kod="BG", naziv="Bugarska", naziv_en="Bulgaria"),
    # Ostale važne zemlje
    Zemlja(kod="TR", naziv="Turska", naziv_en="Turkey"),
    Zemlja(kod="RU", naziv="Rusija", naziv_en="Russia"),
    Zemlja(kod="CN", naziv="Kina", naziv_en="China"),
    Zemlja(kod="US", naziv="Sjedinjene Američke Države", naziv_en="United States"),
    Zemlja(kod="GB", naziv="Ujedinjeno Kraljevstvo", naziv_en="United Kingdom"),
    Zemlja(kod="CH", naziv="Švicarska", naziv_en="Switzerland"),
    Zemlja(kod="NO", naziv="Norveška", naziv_en="Norway"),
    Zemlja(kod="SE", naziv="Švedska", naziv_en="Sweden"),
]


def get_zemlja_by_kod(kod: str) -> Zemlja | None:
    """
    Vraća zemlju po ISO kodu.

    Args:
        kod: ISO 3166-1 alpha-2 kod (npr. "BA")

    Returns:
        Zemlja ili None ako ne postoji
    """
    for z in ZEMLJE:
        if z.kod == kod:
            return z
    return None


def get_zemlja_by_naziv(naziv: str) -> Zemlja | None:
    """
    Vraća zemlju po nazivu (case-insensitive).

    Args:
        naziv: Naziv zemlje

    Returns:
        Zemlja ili None ako ne postoji
    """
    naziv_lower = naziv.lower()
    for z in ZEMLJE:
        if z.naziv.lower() == naziv_lower or z.naziv_en.lower() == naziv_lower:
            return z
    return None


def get_all_zemlje() -> List[Zemlja]:
    """Vraća sve zemlje."""
    return ZEMLJE.copy()


def get_zemlje_kodovi() -> List[str]:
    """Vraća samo ISO kodove svih zemalja."""
    return [z.kod for z in ZEMLJE]


def get_zemlje_nazivi() -> List[str]:
    """Vraća samo nazive svih zemalja."""
    return [z.naziv for z in ZEMLJE]
