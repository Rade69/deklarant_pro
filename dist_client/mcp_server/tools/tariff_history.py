# ============================================================
# SECTION: mcp-tariff-history-tool
# PURPOSE: Suggests HS tariff codes from historical declaration data
# DOC: docs/sections/mcp-tariff-history-tool.md
# ============================================================

"""
suggest_tariff_from_history — looks up historical declarations
and returns tariff code suggestions with confidence scores.

Rules:
- This is a suggestion, not an automatic decision.
- If confidence is low, set needs_review=true.
- Never return false certainty.
"""

import logging
from typing import Any

from ..db import get_connection
from .search_helpers import searchable_words

logger = logging.getLogger("mcp_server.tariff_history")


def suggest_tariff_from_history(
    product_name: str,
    exporter_name: str = "",
    country_code: str = "",
    limit: int = 5,
) -> dict[str, Any]:
    """
    Suggest HS tariff codes based on historical declaration data.

    Args:
        product_name: Product description to search for.
        exporter_name: Optional exporter filter.
        country_code: Optional country of origin filter.
        limit: Max suggestions.

    Returns:
        {"suggestions": [...], "needs_review": bool}
    """
    if not product_name or not product_name.strip():
        return {"suggestions": [], "needs_review": True,
                "notes": ["Empty product name"]}

    query_text = product_name.strip()
    words = searchable_words(query_text)

    if not words:
        return {"suggestions": [], "needs_review": True,
                "notes": ["No searchable words"]}

    exporter_pattern = f"%{exporter_name}%"

    sql = """
        SELECT
            di.tarifni_broj AS hs_code,
            COUNT(*) AS cnt,
            di.naziv_robe AS example_desc
        FROM catalogs.declaration_items di
        LEFT JOIN catalogs.declarations d ON di.declaration_id = d.id
        WHERE EXISTS (
            SELECT 1
            FROM unnest(%s::text[]) AS search_words(word)
            WHERE di.naziv_robe ILIKE '%%' || search_words.word || '%%'
        )
          AND (%s = '' OR d.vendor ILIKE %s)
          AND (%s = '' OR di.zemlja_porijekla = %s)
          AND di.tarifni_broj IS NOT NULL
          AND di.tarifni_broj != ''
        GROUP BY di.tarifni_broj, di.naziv_robe
        ORDER BY cnt DESC
        LIMIT %s
    """
    params = (
        words,
        exporter_name,
        exporter_pattern,
        country_code,
        country_code.upper(),
        limit,
    )

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
    except Exception as e:
        logger.exception("Tariff suggestion failed")
        return {"suggestions": [], "needs_review": True,
                "notes": ["Database unavailable"]}

    if not rows:
        return {
            "suggestions": [],
            "needs_review": True,
            "notes": ["No historical match found — manual review required"],
        }

    total = sum(r["cnt"] for r in rows)
    suggestions = []
    for r in rows:
        confidence = round(r["cnt"] / total, 2) if total > 0 else 0.0
        suggestions.append({
            "hs_code": r["hs_code"],
            "confidence": confidence,
            "source": "historical",
            "reason": (
                f"Found in {r['cnt']} historical declaration item(s)"
                f" matching '{product_name[:40]}...'"
                if len(product_name) > 40
                else f"Found in {r['cnt']} historical declaration item(s)"
                f" matching '{product_name}'"
            ),
        })

    # Determine if review is needed
    max_conf = max(s["confidence"] for s in suggestions) if suggestions else 0
    needs_review = max_conf < 0.70 or len(suggestions) > 1

    return {
        "suggestions": suggestions,
        "needs_review": needs_review,
        "notes": [],
    }
