"""
Naimenovanja Constants - Sve hardkodovane vrijednosti
"""

from typing import Dict


class NaimenovanjaConstants:
    """Sve konstante za Naimenovanja Tab"""

    # Validation
    MIN_SIMILARITY_THRESHOLD = 0.50

    # UI scaling
    SCALE_FACTOR = 1.30

    # Trading names
    MAX_TRADING_CHARS = 550

    # Package codes
    PACKAGE_CODES_DB = "pakovanja"

    # Tariff lookup
    TARIFF_CACHE_SIZE = 1000
    TARIFF_LOOKUP_TIMEOUT_MS = 400
