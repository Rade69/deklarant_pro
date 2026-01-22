"""Šifarnik načina transporta."""

from dataclasses import dataclass
from typing import List


@dataclass
class NacinTransporta:
    """Način transporta."""

    kod: str
    naziv: str
    opis: str


# UN/ECE Recommendation 19 - Codes for Modes of Transport
NACINI_TRANSPORTA: List[NacinTransporta] = [
    NacinTransporta(
        kod="1",
        naziv="Pomorski transport",
        opis="Maritime transport",
    ),
    NacinTransporta(
        kod="2",
        naziv="Željeznički transport",
        opis="Rail transport",
    ),
    NacinTransporta(
        kod="3",
        naziv="Drumski transport",
        opis="Road transport",
    ),
    NacinTransporta(
        kod="4",
        naziv="Zračni transport",
        opis="Air transport",
    ),
    NacinTransporta(
        kod="5",
        naziv="Poštanski transport",
        opis="Mail",
    ),
    NacinTransporta(
        kod="7",
        naziv="Fiksna instalacija",
        opis="Fixed transport installations (pipeline)",
    ),
    NacinTransporta(
        kod="8",
        naziv="Unutrašnji vodni transport",
        opis="Inland water transport",
    ),
    NacinTransporta(
        kod="9",
        naziv="Vlastiti pogon",
        opis="Mode unknown (self-propelled)",
    ),
]


def get_transport_by_kod(kod: str) -> NacinTransporta | None:
    """
    Vraća način transporta po kodu.

    Args:
        kod: Kod transporta (npr. "3")

    Returns:
        NacinTransporta ili None ako ne postoji
    """
    for t in NACINI_TRANSPORTA:
        if t.kod == kod:
            return t
    return None


def get_all_transporti() -> List[NacinTransporta]:
    """Vraća sve načine transporta."""
    return NACINI_TRANSPORTA.copy()


def get_transport_kodovi() -> List[str]:
    """Vraća samo kodove svih transporta."""
    return [t.kod for t in NACINI_TRANSPORTA]


def get_transport_nazivi() -> List[str]:
    """Vraća samo nazive svih transporta."""
    return [t.naziv for t in NACINI_TRANSPORTA]
