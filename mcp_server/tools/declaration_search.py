# ============================================================
# SECTION: mcp-declaration-search-tool
# PURPOSE: Exposes safe historical declaration search from PostgreSQL
# DOC: docs/sections/mcp-declaration-search-tool.md
# ============================================================

"""
search_historical_declarations — full-text search across historical
declaration items with optional filters (country, HS code, exporter).
"""

import logging
from typing import Any

from ..db import get_connection

logger = logging.getLogger("mcp_server.declaration_search")


def search_historical_declarations(
    query: str,
    filters: dict[str, str] | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """
    Search historical declarations by product name with optional filters.

    Args:
        query: Search query (product name or description).
        filters: Optional dict with keys: country_code, hs_code, exporter_name.
        limit: Max results.

    Returns:
        {"results": [{hs_code, commercial_desc, country_origin, preference,
                      exporter_name, declaration_ref}]}
    """
    if not query or not query.strip():
        return {"results": []}

    filters = filters or {}
    query_text = query.strip()
    words = [w for w in query_text.split() if len(w) >= 3]

    if not words:
        return {"results": []}

    country_code = (filters.get("country_code") or "").strip()
    hs_code = (filters.get("hs_code") or "").strip()
    exporter_name = (filters.get("exporter_name") or "").strip()
    clean_hs = "".join(c for c in hs_code if c.isdigit())
    hs_pattern = f"{clean_hs}%"
    exporter_pattern = f"%{exporter_name}%"

    sql = """
        SELECT
            di.tarifni_broj AS hs_code,
            di.naziv_robe AS commercial_desc,
            di.zemlja_porijekla AS country_origin,
            di.povlastica AS preference,
            COALESCE(d.vendor, '') AS exporter_name,
            COALESCE(di.declaration_id::text, '') AS declaration_ref
        FROM catalogs.declaration_items di
        LEFT JOIN catalogs.declarations d ON di.declaration_id = d.id
        WHERE EXISTS (
            SELECT 1
            FROM unnest(%s::text[]) AS search_words(word)
            WHERE di.naziv_robe ILIKE '%%' || search_words.word || '%%'
        )
          AND (%s = '' OR di.zemlja_porijekla = %s)
          AND (%s = '' OR di.tarifni_broj LIKE %s)
          AND (%s = '' OR d.vendor ILIKE %s)
        ORDER BY di.naziv_robe
        LIMIT %s
    """
    params = (
        words,
        country_code,
        country_code.upper(),
        clean_hs,
        hs_pattern,
        exporter_name,
        exporter_pattern,
        limit,
    )

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
    except Exception as e:
        logger.exception("Declaration search failed")
        return {"results": [], "error": "Database unavailable"}

    results = []
    for r in rows:
        results.append({
            "hs_code": r["hs_code"] or "",
            "commercial_desc": r["commercial_desc"] or "",
            "country_origin": r["country_origin"] or "",
            "preference": r["preference"] or "",
            "exporter_name": r["exporter_name"] or "",
            "declaration_ref": r["declaration_ref"] or "",
        })

    return {"results": results}
