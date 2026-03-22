# importers/pdf/utils.py

"""
Utility funkcije za PDF parsing:
- normalizacija brojeva
- identifikacija kolona
"""

import re
from typing import Dict, Iterable


def normalize_number(value: str) -> float:
    """
    Normalizuje broj iz PDF-a u float.

    Podržava formate:
    - 1,234.56
    - 1.234,56
    - 1234,56
    - 1234.56
    - 1 234,56
    """

    if not value:
        return 0.0

    value = str(value).strip()

    if not value:
        return 0.0

    # ukloni razmake
    value = value.replace(" ", "")

    # ukloni sve osim brojeva, . , -
    value = re.sub(r"[^\d,.\-]", "", value)

    # evropski vs US format
    if "," in value and "." in value:
        # decimalni separator je onaj koji je zadnji
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    else:
        value = value.replace(",", ".")

    try:
        return float(value)
    except ValueError:
        return 0.0


def identify_columns(
    columns: Iterable[str],
    column_map_def: Dict[str, list],
) -> Dict[str, str]:
    """
    Identifikuje kolone tabele na osnovu fuzzy matchinga,
    bez dozvoljavanja konflikata (jedna kolona = jedno značenje).

    Args:
        columns: Kolone iz pandas DataFrame-a
        column_map_def: Definicija standardnih kolona i njihovih aliasa

    Returns:
        Dict: standard_name -> actual_column_name
    """

    mapping: Dict[str, str] = {}
    used_columns = set()

    for standard_name, aliases in column_map_def.items():
        for col in columns:
            if col in used_columns:
                continue

            col_lower = str(col).lower().strip()

            # exact ili partial match
            for alias in aliases:
                alias_lower = alias.lower()
                if alias_lower == col_lower or alias_lower in col_lower:
                    mapping[standard_name] = col
                    used_columns.add(col)
                    break

            if standard_name in mapping:
                break

    return mapping
