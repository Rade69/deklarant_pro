# ============================================================
# SECTION: mcp-validation-tool
# PURPOSE: Validates declaration summary against central rules
# DOC: docs/sections/mcp-validation-tool.md
# ============================================================

"""
validate_declaration_summary — validates basic declaration rules
that depend on the centralized database.

Rules (v1):
- Block more than 99 nomenclature items per declaration.
- Validate that referenced HS codes exist in the official tariff.
- Warning if item count approaches the limit.
"""

import logging
from typing import Any

from ..config import get_server_settings
from ..db import get_connection

logger = logging.getLogger("mcp_server.validation")


def validate_declaration_summary(draft_summary: dict[str, Any]) -> dict[str, Any]:
    """
    Validate a declaration draft summary.

    Args:
        draft_summary: {
            "item_count": int,
            "invoice_total": float,
            "currency": str,
            "items": [{"hs_code": str, "description": str, ...}, ...]
        }

    Returns:
        {"valid": bool, "errors": [...], "warnings": [...]}
    """
    settings = get_server_settings()
    errors: list[str] = []
    warnings: list[str] = []

    item_count = draft_summary.get("item_count", 0)
    items = draft_summary.get("items", [])

    # Rule 1: Max 99 items
    if item_count > settings.max_declaration_items:
        errors.append(
            f"Broj naimenovanja ({item_count}) premašuje dozvoljeni maksimum "
            f"({settings.max_declaration_items})"
        )

    # Warning: approaching the limit
    remaining_items = settings.max_declaration_items - item_count
    if 0 <= remaining_items <= 10 and item_count > 0:
        warnings.append(
            f"Broj naimenovanja ({item_count}) je blizu maksimuma "
            f"({settings.max_declaration_items}). Preostalo: {remaining_items}"
        )

    # Rule 2: Validate HS codes against official tariff (if items provided)
    if items:
        hs_codes = [
            "".join(c for c in (item.get("hs_code") or ""))
            for item in items
            if item.get("hs_code")
        ]
        if hs_codes:
            try:
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT tarifni_kod
                            FROM catalogs.zvanicna_tarifa
                            WHERE tarifni_kod = ANY(%s)
                        """, (hs_codes,))
                        valid_codes = {r["tarifni_kod"] for r in cur.fetchall()}

                invalid_codes = [c for c in hs_codes if c not in valid_codes]
                if invalid_codes:
                    warnings.append(
                        f"Tarifni brojevi nisu pronađeni u zvaničnoj tarifi: "
                        f"{', '.join(invalid_codes[:5])}"
                        + ("..." if len(invalid_codes) > 5 else "")
                    )
            except Exception as e:
                logger.warning("Tariff validation skipped: %s", e)
                warnings.append("Validacija tarifnih brojeva nije izvršena (DB nedostupna)")

    # Rule 3: Invoice total should be positive
    invoice_total = draft_summary.get("invoice_total", 0)
    if invoice_total is not None and invoice_total <= 0:
        warnings.append(f"Iznos fakture ({invoice_total}) je nula ili negativan")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }
