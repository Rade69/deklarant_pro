# ============================================================
# SECTION: mcp-exporter-template-tool
# PURPOSE: Looks up XML templates by exporter-consignee pair from PostgreSQL index
# DOC: docs/sections/mcp-exporter-template-tool.md
# ============================================================

"""
find_exporter_xml_template — looks up previously used XML declaration
templates for a given exporter-consignee pair.

Uses catalogs.exporter_xml_index table populated by exporter_xml_indexer.
"""

import logging
from typing import Any

from ..db import get_connection

logger = logging.getLogger("mcp_server.exporter_template")


def find_exporter_xml_template(
    exporter_name: str,
    consignee_jib: str = "",
    consignee_name: str = "",
) -> dict[str, Any]:
    """
    Find an XML template previously used for this exporter-consignee pair.

    Lookup priority:
    1. Exact match by exporter + consignee_jib
    2. Exact match by exporter + consignee_name (normalized)
    3. Exact match by exporter only (any consignee)

    Args:
        exporter_name: Exporter name from invoice.
        consignee_jib: Consignee JIB (preferred — unique identifier).
        consignee_name: Consignee name (fallback).

    Returns:
        {"found": bool, "match_type": str, "xml_template_id": str,
         "source_filename": str}
    """
    if not exporter_name or not exporter_name.strip():
        return {
            "found": False,
            "match_type": "",
            "xml_template_id": "",
            "source_filename": "",
            "notes": ["Empty exporter name"],
        }

    exp = exporter_name.strip()
    jib = consignee_jib.strip() if consignee_jib else ""
    cons = consignee_name.strip() if consignee_name else ""

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # 1. Exact match by exporter + JIB
                if jib:
                    cur.execute("""
                        SELECT exporter_original, consignee_original,
                               xml_filepath, declaration_date
                        FROM catalogs.exporter_xml_index
                        WHERE exporter_normalized = %s
                          AND consignee_jib = %s
                        ORDER BY use_count DESC, declaration_date DESC
                        LIMIT 1
                    """, (exp.upper(), jib))

                    row = cur.fetchone()
                    if row:
                        return _build_result(
                            found=True,
                            match_type="exporter_consignee_jib",
                            xml_path=row["xml_filepath"],
                            exporter=row["exporter_original"],
                            consignee=row["consignee_original"],
                        )

                # 2. Exact match by exporter + consignee name
                if cons:
                    cur.execute("""
                        SELECT exporter_original, consignee_original,
                               xml_filepath, declaration_date
                        FROM catalogs.exporter_xml_index
                        WHERE exporter_normalized = %s
                          AND consignee_normalized = %s
                        ORDER BY use_count DESC, declaration_date DESC
                        LIMIT 1
                    """, (exp.upper(), cons.upper()))

                    row = cur.fetchone()
                    if row:
                        return _build_result(
                            found=True,
                            match_type="exporter_consignee",
                            xml_path=row["xml_filepath"],
                            exporter=row["exporter_original"],
                            consignee=row["consignee_original"],
                        )

                # 3. Match by exporter only
                cur.execute("""
                    SELECT exporter_original, consignee_original,
                           xml_filepath, declaration_date
                    FROM catalogs.exporter_xml_index
                    WHERE exporter_normalized = %s
                    ORDER BY use_count DESC, declaration_date DESC
                    LIMIT 1
                """, (exp.upper(),))

                row = cur.fetchone()
                if row:
                    return _build_result(
                        found=True,
                        match_type="exporter_only",
                        xml_path=row["xml_filepath"],
                        exporter=row["exporter_original"],
                        consignee=row["consignee_original"],
                    )

        # No match found
        return {
            "found": False,
            "match_type": "",
            "xml_template_id": "",
            "source_filename": "",
            "notes": ["No matching XML template found for this exporter"],
        }

    except Exception as e:
        logger.exception("Exporter template lookup failed")
        return {
            "found": False,
            "match_type": "",
            "xml_template_id": "",
            "source_filename": "",
            "notes": ["Database unavailable"],
        }


def _build_result(
    found: bool,
    match_type: str,
    xml_path: str,
    exporter: str,
    consignee: str,
) -> dict[str, Any]:
    """Build standardized result dict."""
    import os
    filename = os.path.basename(xml_path) if xml_path else ""
    return {
        "found": found,
        "match_type": match_type,
        "xml_template_id": filename,
        "source_filename": filename,
        "exporter_original": exporter or "",
        "consignee_original": consignee or "",
    }
