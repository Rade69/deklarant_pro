"""
Šifrarnik – Povlastice (Rubrika 36)

Izvor: ASYCUDA / BiH carinski šifrarnici

Ovo je "compiled view" (code -> opis) koji koristi aplikacija.
UI prikazuje:  ŠIFRA — OPIS
U Draft / XML se upisuje: samo ŠIFRA

Napomena iz prakse:
- ASYCUDAWorld dozvoljava ručni unos povlastice
- Naša aplikacija: dropdown + ručni unos
- Nepoznata šifra -> upozorenje, NE blokira rad
"""

from __future__ import annotations

from typing import Dict


# JEDINI JAVNI OBJEKAT KOJI APLIKACIJA TREBA DA KORISTI
POVLASTICE: Dict[str, str] = {
    "NO": "Bez povlastice",
    "MFN": "Najpovlaštenija nacija",
    # CEFTA
    "CEFTA": "CEFTA – preferencijalni tretman",
    "CEFTAK": "CEFTA – kumulacija porijekla",
    "CEFTAP": "CEFTA + PEM konvencija",
    # EFTA
    "EFTA": "Sporazum BiH – EFTA",
    "EFTAP": "EFTA + PEM konvencija",
    # Evropska unija
    "EU": "EU – SSP",
    "EUP": "EU + PEM konvencija",
    # Turska
    "TR": "Sporazum BiH – Turska",
    "TRP": "Turska + PEM konvencija",
    # GSP
    "GSP": "Opšti sistem povlastica",
    "GSPP": "GSP + kumulacija",
}
