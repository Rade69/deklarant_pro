# importers/excel_column_utils.py

"""
Dijeljeni helperi za detekciju kolona u Excel fajlovima dobavljača.
"""

from __future__ import annotations

import re
import logging
from typing import Optional

logger = logging.getLogger("deklarant_pro.import.excel_column_utils")


def infer_origin_column(
    ws,
    after_col: int,
    anchor_col: int,
    max_rows: int = 30,
) -> Optional[int]:
    """
    Detektuje kolonu porijekla po sadržaju ćelija kad header nije prepoznat.

    Pretražuje kolone desno od after_col i broji ćelije čiji sadržaj
    prepoznaje kao naziv ili ISO kod države. Vraća kolonuu s najviše pogodaka
    ako ih ima >= 50% od provjerenih redova.

    Args:
        ws:          openpyxl Worksheet (ili kompatibilan objekt s .cell(row, col))
        after_col:   1-based indeks kolone — pretraživanje počinje DESNO od nje
        anchor_col:  1-based indeks kolone za provjeru da li red ima podatke
                     (preskačemo prazne redove)
        max_rows:    koliko redova pregledati (default 30)

    Returns:
        1-based indeks kolone, ili None ako nije pronađena.
    """
    from utils.country_normalizer import normalize_country_name

    best_col: Optional[int] = None
    best_hits = 0
    max_row = min(ws.max_row, max_rows + 1)

    for col in range(after_col + 1, ws.max_column + 1):
        hits = 0
        checked = 0
        for row in range(2, max_row + 1):
            if not ws.cell(row, anchor_col).value:
                continue
            value = ws.cell(row, col).value
            if value is None:
                continue
            checked += 1
            value_text = str(value).strip()
            normalized = normalize_country_name(value_text)
            if normalized and (
                normalized != value_text.upper()
                or bool(re.match(r"^[A-Z]{2}$", value_text.upper()))
            ):
                hits += 1

        if hits > best_hits and hits >= max(1, checked // 2):
            best_col = col
            best_hits = hits

    return best_col
