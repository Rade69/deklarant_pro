# ============================================================
# SECTION: mcp-preference-tool
# PURPOSE: Suggests customs preference code based on country and exporter history
# DOC: docs/sections/mcp-preference-tool.md
# ============================================================

"""
suggest_preference — determines likely preference (povlastica) code
for a given country and exporter based on historical data.

Rules:
- CBBH exchange rates and customs rules are NOT hardcoded here.
- If no history, return confidence=0 and preference="".
- Requires origin document flag is set for non-EU preferences.
"""

import logging
from typing import Any

from ..db import get_connection

logger = logging.getLogger("mcp_server.preference")

# Preferences that typically require an origin document
_REQUIRES_ORIGIN_DOC = {"TRP", "EUP", "CEFTA", "EFTA", "GSP"}


def suggest_preference(
    country_code: str,
    exporter_name: str = "",
) -> dict[str, Any]:
    """
    Suggest a customs preference code based on historical data.

    Args:
        country_code: ISO country code (e.g., "TR", "IT", "RS").
        exporter_name: Optional exporter name for more precise lookup.

    Returns:
        {"preference": str, "confidence": float, "source": str,
         "requires_origin_document": bool}
    """
    cc = (country_code or "").strip().upper()
    exp = (exporter_name or "").strip()

    if not cc:
        return {
            "preference": "",
            "confidence": 0.0,
            "source": "",
            "requires_origin_document": False,
            "notes": ["Empty country code"],
        }

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                if exp:
                    # Lookup with exporter filter
                    cur.execute("""
                        SELECT povlastica, COUNT(*) AS cnt
                        FROM catalogs.declaration_items di
                        JOIN catalogs.declarations d
                          ON di.declaration_id = d.id
                        WHERE di.zemlja_porijekla = %s
                          AND d.vendor ILIKE %s
                          AND di.povlastica IS NOT NULL
                          AND di.povlastica != ''
                        GROUP BY di.povlastica
                        ORDER BY cnt DESC
                        LIMIT 3
                    """, (cc, f"%{exp}%"))
                else:
                    # Country-only lookup
                    cur.execute("""
                        SELECT povlastica, COUNT(*) AS cnt
                        FROM catalogs.declaration_items
                        WHERE zemlja_porijekla = %s
                          AND povlastica IS NOT NULL
                          AND povlastica != ''
                        GROUP BY povlastica
                        ORDER BY cnt DESC
                        LIMIT 3
                    """, (cc,))

                rows = cur.fetchall()

        if not rows:
            return {
                "preference": "",
                "confidence": 0.0,
                "source": "",
                "requires_origin_document": False,
                "notes": [f"No historical preference data for country '{cc}'"],
            }

        # Top preference
        top = rows[0]
        total = sum(r["cnt"] for r in rows)
        confidence = round(top["cnt"] / total, 2) if total > 0 else 0.0
        pref = top["povlastica"]

        source = "historical_country"
        if exp:
            source = "historical_country_exporter"

        return {
            "preference": pref,
            "confidence": confidence,
            "source": source,
            "requires_origin_document": pref in _REQUIRES_ORIGIN_DOC,
            "notes": [],
        }

    except Exception as e:
        logger.exception("Preference lookup failed")
        return {
            "preference": "",
            "confidence": 0.0,
            "source": "",
            "requires_origin_document": False,
            "notes": ["Database unavailable"],
        }
