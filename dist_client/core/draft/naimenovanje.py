"""Naimenovanje (stavka) model."""

from dataclasses import dataclass


@dataclass
class Naimenovanje:
    """Stavka robe na deklaraciji."""

    # Identifikacija
    redni_broj: int = 0
    tarifni_broj: str = ""
    opis: str = ""

    # Količina
    kolicina: float = 0.0
    jedinica_mere: str = ""
    neto_masa: float = 0.0
    bruto_masa: float = 0.0

    # Vrednost
    fakturna_vrednost: float = 0.0
    carinska_vrednost: float = 0.0
    valuta: str = "EUR"

    # Poreklo
    zemlja_porekla: str = ""
    zemlja_otpreme: str = ""

    # Povlastice
    povlastica: str = ""  # CEFTA, EFTA, SPP...

    # Pakovanje
    vrsta_pakovanja: str = ""
    broj_paketa: int = 0

    # Prateća dokumentacija
    dokumenti: list[str] | None = None

    def __post_init__(self):
        """Inicijalizuje prazne liste."""
        if self.dokumenti is None:
            self.dokumenti = []
