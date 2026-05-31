# ============================================================
# SECTION: mcp-product-origin-tool
# PURPOSE: Exposes safe product origin lookup from historical declarations
# DOC: docs/sections/mcp-product-origin-tool.md
# ============================================================

"""
find_product_origin — determines likely country of origin for a product
by searching historical declaration items in PostgreSQL.

Rules:
- Search historical declaration_items by commercial description (ILIKE).
- Group by country, compute confidence = country_count / total_count.
- If no reliable matches, return found=false.
- Do NOT suggest tariff codes — only origin.
"""

import logging
from typing import Any

from ..db import get_connection

logger = logging.getLogger("mcp_server.product_origin")

# Minimum substring length for meaningful search
_MIN_WORD_LENGTH = 3
# Minimum total matches to consider "found"
_MIN_MATCHES = 1


# ============================================================
# SECTION: mcp-product-origin-tool
# PURPOSE: Exposes safe product origin lookup from historical declarations
# DOC: docs/sections/mcp-product-origin-tool.md
# ============================================================


def find_product_origin(product_name: str, limit: int = 10) -> dict[str, Any]:
    """
    Find likely country of origin for a product from historical data.

    Args:
        product_name: Product description to search for.
        limit: Max number of origin entries to return.

    Returns:
        {"query": ..., "found": bool, "origins": [...], "notes": [...]}
    """
    if not product_name or not product_name.strip():
        return {
            "query": product_name,
            "found": False,
            "origins": [],
            "notes": ["Empty product name"],
        }

    query_text = product_name.strip()
    words = [w for w in query_text.split() if len(w) >= _MIN_WORD_LENGTH]

    if not words:
        return {
            "query": query_text,
            "found": False,
            "origins": [],
            "notes": ["No searchable words (minimum 3 characters each)"],
        }

    # 1. Get all matches grouped by country
    sql = """
        SELECT
            zemlja_porijekla,
            COUNT(*) AS cnt,
            array_agg(DISTINCT tarifni_broj) FILTER (WHERE tarifni_broj IS NOT NULL AND tarifni_broj != '') AS hs_codes,
            array_agg(DISTINCT naziv_robe) FILTER (WHERE naziv_robe IS NOT NULL AND naziv_robe != '') AS examples
        FROM catalogs.declaration_items
        WHERE EXISTS (
            SELECT 1
            FROM unnest(%s::text[]) AS search_words(word)
            WHERE naziv_robe ILIKE '%%' || search_words.word || '%%'
        )
          AND zemlja_porijekla IS NOT NULL
          AND zemlja_porijekla != ''
        GROUP BY zemlja_porijekla
        ORDER BY cnt DESC
        LIMIT %s
    """

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (words, limit))
                rows = cur.fetchall()
    except Exception as e:
        logger.exception("Product origin query failed")
        return {
            "query": query_text,
            "found": False,
            "origins": [],
            "notes": ["Database unavailable"],
        }

    if not rows:
        return {
            "query": query_text,
            "found": False,
            "origins": [],
            "notes": ["No matching historical declarations found"],
        }

    total = sum(r["cnt"] for r in rows)
    origins = []
    for r in rows:
        country = r["zemlja_porijekla"]
        count = r["cnt"]
        confidence = round(count / total, 2) if total > 0 else 0.0

        # Limit examples to 3
        examples_list = (r["examples"] or [])[:3]
        hs_codes = (r["hs_codes"] or [])[:3]

        example_entries = []
        for i, ex in enumerate(examples_list):
            entry = {
                "hs_code": hs_codes[i] if i < len(hs_codes) else "",
                "commercial_desc": ex,
            }
            example_entries.append(entry)

        origins.append({
            "country_code": country,
            "count": count,
            "confidence": confidence,
            "examples": example_entries,
        })

    return {
        "query": query_text,
        "found": True,
        "origins": origins,
        "notes": [],
    }
