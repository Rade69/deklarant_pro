"""
Faktura Tab Constants - Sve hardkodovane vrijednosti
"""

from typing import Dict, List


class FakturaConstants:
    """Sve konstante za Faktura Tab"""

    # Validation
    MIN_SIMILARITY = 0.70

    # Column widths
    COLUMN_WIDTHS: Dict[str, int] = {
        "line_no": 60,
        "naimenov": 95,
        "naziv_robe": 430,
        "tarifni_broj": 140,
        "kolicina": 100,
        "iznos": 110,
        "bruto": 120,
        "neto": 120,
        "zemlja": 80,
        "povlastica": 100,
        "valuta": 65,
    }

    # Colors
    COLORS: Dict[str, str] = {
        "glavna": "#E3F2FD",
        "uvezi": "#E8F5E9",
        "uredi": "#FFF9C4",
        "izvezi": "#FFE0B2",
        "smart": "#F3E5F5",
    }

    # Validation colors
    VALIDATION_COLORS: Dict[str, str] = {
        "valid": "#ccffcc",
        "warning": "#ffffcc",
        "error": "#ffcccc",
        "unmatched": "#cce5ff",
    }

    # Section configuration for UI
    SECTIONS: List[Dict] = [
        {"name": "Glavna lista", "color": COLORS["glavna"], "stretch": 1},
        {"name": "Uvezi", "color": COLORS["uvezi"], "stretch": 3},
        {"name": "Uredi", "color": COLORS["uredi"], "stretch": 3},
        {"name": "Izvezi", "color": COLORS["izvezi"], "stretch": 5},
        {"name": "Pametna pomoć", "color": COLORS["smart"], "stretch": 3},
    ]
