# importers/incoterm_utils.py

"""
Detekcija pariteta isporuke (Incoterms 2020) iz sirovog teksta fakture.

Koristi se u importers/vendors/*.py — svaki importer koji ekstraktuje puni
tekst fakture treba pozvati detect_incoterm(full_text) i proslijediti
rezultat kao ImportResult.incoterm_code (Rb.20 "Uslovi isporuke").

Namjerno SAMO label+kod obrasci (npr. "Paritet isporuke: CPT"), bez
pretrage samostalnog pojavljivanja koda bez konteksta — paritet je pravno
obavezan podatak u postupku carinjenja, pa je lažan pozitiv (pogrešan
paritet) gori od izostanka pogotka (prazno polje, deklarant unosi ručno).
"""

from __future__ import annotations

import re

# Incoterms 2020 — svih 11 važećih šifri (database/migrate_incoterms.py)
VALID_INCOTERM_CODES = frozenset({
    "EXW", "FCA", "FAS", "FOB", "CFR", "CIF", "CPT", "CIP", "DAP", "DPU", "DDP",
})

_LABEL_PATTERN = re.compile(
    r'(?:'
    r'Incoterms?(?:\s*20\d{2})?'
    r'|Paritet\w*(?:\s+isporuke)?'  # "paritetu:", "Paritet isporuke:", "paritetom isporuke:" ...
    r'|Uslovi\s+isporuke'
    r'|Delivery\s+terms?'
    r'|Termin\s+isporuke'
    r')\s*[:\-]?\s*([A-Za-z]{3})\b',
    re.IGNORECASE,
)


def detect_incoterm(text: str) -> str:
    """
    Vrati šifru pariteta isporuke (npr. "CPT") ako je prepoznata u tekstu
    uz jednu od poznatih oznaka ("Incoterms", "Paritet isporuke", "Uslovi
    isporuke", "Delivery terms", "Termin isporuke"), inače prazan string.
    """
    if not text:
        return ""
    for match in _LABEL_PATTERN.finditer(text):
        code = match.group(1).upper()
        if code in VALID_INCOTERM_CODES:
            return code
    return ""
