"""
Agent Actions — sistem za predlaganje i izvršavanje akcija nad podacima.

Tok: korisnik traži → agent analizira → prijedlog → korisnik odobri → izvršavanje
"""

from dataclasses import dataclass, field
from typing import List, Any


@dataclass
class TariffProposal:
    """Prijedlog tarifnog broja za jednu stavku."""
    line_index: int
    naziv_robe: str
    product_code: str
    proposed_tariff: str
    confidence: float        # 0.0 – 1.0
    source: str              # "baza_znanja" / "rag"


@dataclass
class NaimenovanjaSpajanje:
    """Prijedlog spajanja dvije ili više naimenovanja."""
    indices: List[int]       # indeksi u draft.items
    tariff_code: str
    merged_naziv: str
    merged_kolicina: float
    merged_bruto: float
    merged_neto: float
    merged_iznos: float


@dataclass
class PendingAction:
    """Akcija koja čeka potvrdu korisnika."""
    action_type: str         # "fill_tariff" | "merge_naimenovanja"
    proposals: List[Any]     # lista TariffProposal ili NaimenovanjaSpajanje
    description: str         # kratki opis za prikaz
