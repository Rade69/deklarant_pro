"""Prilozi (dokumenti) model."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Prilog:
    """Prateći dokument uz deklaraciju."""

    tip: str = ""  # Faktura, CMR, EUR1, Certifikat...
    broj: str = ""
    datum: datetime | None = None
    izdavalac: str = ""
    napomena: str = ""

    # Za fajl attachment (opciono)
    file_path: str = ""
    file_name: str = ""


@dataclass
class Prilozi:
    """Kolekcija priloga."""

    dokumenti: list[Prilog] | None = None

    def __post_init__(self):
        """Inicijalizuje praznu listu."""
        if self.dokumenti is None:
            self.dokumenti = []

    def add(self, prilog: Prilog) -> None:
        """Dodaje novi prilog."""
        if self.dokumenti is None:
            self.dokumenti = []
        self.dokumenti.append(prilog)

    def remove(self, index: int) -> None:
        """Uklanja prilog po indeksu."""
        if self.dokumenti and 0 <= index < len(self.dokumenti):
            self.dokumenti.pop(index)

    def get_all(self) -> list[Prilog]:
        """Vraća sve priloge."""
        return self.dokumenti or []
