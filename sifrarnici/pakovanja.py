"""
Šifrarnik – Vrsta pakiranja (Rubrika 31)

Izvor: ASYCUDA / BiH carinski šifrarnici
Napomena:
- koristi se u GUI dropdown-ovima
- dozvoljen je ručni unos šifre (uz upozorenje)
"""

from __future__ import annotations

from typing import Dict


# JEDINI JAVNI OBJEKAT KOJI APLIKACIJA KORISTI
PAKOVANJA: Dict[str, str] = {
    "AE": "AEROSOL",
    "AM": "AMPULA",
    "AT": "VREĆA NA PALETI",
    "BA": "BAČVA",
    "BB": "RINFUZA – BOKS",
    "BG": "VREĆA",
    "BI": "KANTA",
    "BL": "BALA",
    "BN": "BANDAŽA",
    "BR": "BURE",
    "BX": "KUTIJA",
    "CA": "KANISTER",
    "CG": "KAVEZ",
    "CH": "SANDUK",
    "CL": "KALEM",
    "CO": "KONTEJNER",
    "CR": "SANDUK (DRVENI)",
    "CS": "KASETA",
    "CT": "KARTON",
    "CY": "CILINDAR",
    "DR": "BURE (METALNO)",
    "EN": "KOVERTA",
    "FR": "RAM",
    "HG": "VJEŠALICA",
    "IB": "IBC KONTEJNER",
    "IN": "INGOT",
    "JR": "TEGLA",
    "LG": "CIJEV (VELIKA)",
    "LT": "LOT",
    "NE": "NEPAKOVANO",
    "PA": "PAKET",
    "PB": "PLASTIČNA BOCA",
    "PC": "PAKET SA PREGRADAMA",
    "PK": "PAKET (VIŠE)",
    "PL": "PALETA",
    "PO": "VREĆA (POLIETILEN)",
    "RL": "ROLA",
    "SA": "VREĆA (PAPIR)",
    "SK": "SANDUK (METALNI)",
    "TN": "TANK",
    "TR": "TRUPAC",
    "VG": "BIG BAG",
    "VO": "RASUTA TEKUĆINA",
}
