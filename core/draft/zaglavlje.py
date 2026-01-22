"""Zaglavlje deklaracije model."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Zaglavlje:
    """Zaglavlje carinske deklaracije."""

    # Osnovno
    broj_deklaracije: str = ""
    datum_deklaracije: datetime | None = None
    vrsta_deklaracije: str = "IM4"  # IM4, IM7, EX1...

    # Carinarnica
    carinarnica_uvoza: str = ""
    carinarnica_izvoza: str = ""

    # Režim
    procedura: str = ""  # 40 00, 42 00...
    prethodni_dokument: str = ""

    # Ostalo
    nacin_placanja: str = ""
    valuta_fakture: str = "EUR"
    kurs: float = 1.0

    # Napomene
    napomena: str = ""
