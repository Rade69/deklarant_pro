# ============================================================
# SECTION: mcp-facade
# PURPOSE: Centralized MCP integration point — wraps MCP tool calls
#          with transparent fallback to local services
# DOC: docs/sections/mcp-server-architecture.md
# ============================================================

"""
MCP Facade for Deklarant Pro services.

Provides a single entry point for MCP tool calls. If the MCP server
is not available, falls back to local service implementations.

Usage:
    from services.agent.mcp_facade import mcp_facade

    origin = mcp_facade.find_product_origin("kondenzator GCVC")
    declarations = mcp_facade.search_historical_declarations("kondenzator")
    tariff = mcp_facade.suggest_tariff_from_history("kondenzator")
    template = mcp_facade.find_exporter_xml_template("ENMON", jib="12345")
    preference = mcp_facade.suggest_preference("IT", exporter="ENMON")
    validation = mcp_facade.validate_declaration_summary({"item_count": 50})
"""

import logging
from typing import Any, Optional

logger = logging.getLogger("mcp_facade")


class McpFacade:
    """
    Centralized facade for MCP tool calls with local fallback.

    Thread-safe: MCP client is accessed via app.run.get_mcp_client().
    """

    def __init__(self):
        self._mcp_available: Optional[bool] = None

    # ─── Public API — matching MCP tool signatures ──────────────────────────

    def find_product_origin(
        self, product_name: str, limit: int = 10
    ) -> dict[str, Any]:
        """
        Find likely country of origin for a product.

        Tries MCP first, falls back to local historical search.
        """
        client = self._get_client()
        if client and client.is_ready and client.has_tool("find_product_origin"):
            result = client.call_tool(
                "find_product_origin",
                product_name=product_name,
                limit=limit,
            )
            if not result.get("fallback"):
                return result

        return self._local_find_product_origin(product_name, limit)

    def search_historical_declarations(
        self,
        query: str,
        filters: dict[str, str] | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """
        Search historical declaration items.

        Tries MCP first, falls back to local DeclarationSearchService.
        """
        client = self._get_client()
        if client and client.is_ready and client.has_tool("search_historical_declarations"):
            result = client.call_tool(
                "search_historical_declarations",
                query=query,
                filters=filters or {},
                limit=limit,
            )
            if not result.get("fallback"):
                return result

        return self._local_search_historical_declarations(query, filters, limit)

    def suggest_tariff_from_history(
        self,
        product_name: str,
        exporter_name: str = "",
        country_code: str = "",
        limit: int = 5,
    ) -> dict[str, Any]:
        """
        Suggest HS tariff codes from historical data.

        Tries MCP first, falls back to local hybrid matching.
        """
        client = self._get_client()
        if client and client.is_ready and client.has_tool("suggest_tariff_from_history"):
            result = client.call_tool(
                "suggest_tariff_from_history",
                product_name=product_name,
                exporter_name=exporter_name,
                country_code=country_code,
                limit=limit,
            )
            if not result.get("fallback"):
                return result

        return self._local_suggest_tariff(product_name, exporter_name, country_code, limit)

    def find_exporter_xml_template(
        self,
        exporter_name: str,
        consignee_jib: str = "",
        consignee_name: str = "",
    ) -> dict[str, Any]:
        """
        Find XML template for exporter-consignee pair.

        Tries MCP first, falls back to local exporter_xml_indexer.
        """
        client = self._get_client()
        if client and client.is_ready and client.has_tool("find_exporter_xml_template"):
            result = client.call_tool(
                "find_exporter_xml_template",
                exporter_name=exporter_name,
                consignee_jib=consignee_jib,
                consignee_name=consignee_name,
            )
            if not result.get("fallback"):
                return result

        return self._local_find_exporter_xml_template(exporter_name, consignee_jib, consignee_name)

    def suggest_preference(
        self, country_code: str, exporter_name: str = ""
    ) -> dict[str, Any]:
        """
        Suggest customs preference code.

        Tries MCP first, falls back to local preference lookup.
        """
        client = self._get_client()
        if client and client.is_ready and client.has_tool("suggest_preference"):
            result = client.call_tool(
                "suggest_preference",
                country_code=country_code,
                exporter_name=exporter_name,
            )
            if not result.get("fallback"):
                return result

        return self._local_suggest_preference(country_code, exporter_name)

    def validate_declaration_summary(
        self, draft_summary: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Validate declaration summary.

        Tries MCP first, falls back to local validation.
        """
        client = self._get_client()
        if client and client.is_ready and client.has_tool("validate_declaration_summary"):
            result = client.call_tool(
                "validate_declaration_summary",
                draft_summary=draft_summary,
            )
            if not result.get("fallback"):
                return result

        return self._local_validate_declaration_summary(draft_summary)

    # ─── Internal — MCP client access ───────────────────────────────────────

    def _get_client(self):
        """Get the global MCP client (may be None)."""
        try:
            from app.run import get_mcp_client
            return get_mcp_client()
        except ImportError:
            return None

    # ─── Local Fallbacks ────────────────────────────────────────────────────

    def _local_find_product_origin(self, product_name: str, limit: int) -> dict:
        """Fallback: use DeclarationSearchService for origin lookup."""
        try:
            from services.agent.chat.declaration_search_service import (
                DeclarationSearchService,
            )
            svc = DeclarationSearchService()
            results = svc.search_by_goods(product_name, limit=limit)

            if not results:
                return {"query": product_name, "found": False, "origins": [], "notes": []}

            # Group by country
            by_country: dict[str, list] = {}
            for r in results:
                cc = r.get("country_origin") or "XX"
                if cc not in by_country:
                    by_country[cc] = []
                by_country[cc].append(r)

            total = len(results)
            origins = []
            for cc, items in sorted(by_country.items(), key=lambda x: -len(x[1])):
                confidence = round(len(items) / total, 2) if total > 0 else 0
                origins.append({
                    "country_code": cc,
                    "count": len(items),
                    "confidence": confidence,
                    "examples": [{
                        "hs_code": items[0].get("hs_code", ""),
                        "commercial_desc": (items[0].get("commercial_desc") or "")[:100],
                    }],
                })

            return {
                "query": product_name,
                "found": True,
                "origins": origins[:limit],
                "notes": ["source: local SQLite index"],
            }
        except Exception as e:
            logger.warning("Local origin fallback failed: %s", e)
            return {"query": product_name, "found": False, "origins": [],
                    "notes": ["Local fallback unavailable"]}

    def _local_search_historical_declarations(
        self, query: str, filters: dict | None, limit: int
    ) -> dict:
        """Fallback: use DeclarationSearchService."""
        try:
            from services.agent.chat.declaration_search_service import (
                DeclarationSearchService,
            )
            svc = DeclarationSearchService()

            filters = filters or {}
            cc = filters.get("country_code", "")
            hs = filters.get("hs_code", "")
            exporter = filters.get("exporter_name", "")

            if cc:
                results = svc.search_by_country(cc, limit=limit)
            elif hs:
                results = svc.search_by_tariff(hs, limit=limit)
            elif exporter:
                results = svc.search_by_partner(exporter, limit=limit)
            else:
                results = svc.search_by_goods(query, limit=limit)

            mapped = []
            for r in results:
                mapped.append({
                    "hs_code": r.get("hs_code", ""),
                    "commercial_desc": r.get("commercial_desc", ""),
                    "country_origin": r.get("country_origin", ""),
                    "preference": r.get("preference", ""),
                    "exporter_name": r.get("exporter_name", ""),
                    "declaration_ref": r.get("filename", ""),
                })

            return {"results": mapped}
        except Exception as e:
            logger.warning("Local search fallback failed: %s", e)
            return {"results": [], "error": "Local fallback unavailable"}

    def _local_suggest_tariff(
        self, product_name: str, exporter: str, country: str, limit: int
    ) -> dict:
        """Fallback: use HybridMatchingService."""
        try:
            from services.agent.tariff.tariff_suggestion_service import (
                HybridMatchingService,
            )
            svc = HybridMatchingService()
            suggestions = svc.suggest(product_name, limit=limit)

            mapped = []
            for s in suggestions:
                mapped.append({
                    "hs_code": s.tariff_mapping.tarifni_broj,
                    "confidence": s.confidence,
                    "source": s.method,
                    "reason": s.explanation,
                })

            return {
                "suggestions": mapped,
                "needs_review": len(mapped) == 0 or max(
                    (x["confidence"] for x in mapped), default=0
                ) < 0.70,
                "notes": ["source: local hybrid matching"],
            }
        except Exception as e:
            logger.warning("Local tariff fallback failed: %s", e)
            return {"suggestions": [], "needs_review": True,
                    "notes": ["Local fallback unavailable"]}

    def _local_find_exporter_xml_template(
        self, exporter_name: str, jib: str, cons_name: str
    ) -> dict:
        """Fallback: use exporter_xml_indexer."""
        try:
            from services.agent.learning.exporter_xml_indexer import find_xml_for_pair
            result = find_xml_for_pair(exporter_name, consignee_jib=jib, consignee_hint=cons_name)
            if result:
                return {
                    "found": True,
                    "match_type": result.get("match_type", "local"),
                    "xml_template_id": result.get("xml_filepath", ""),
                    "source_filename": result.get("xml_filepath", ""),
                    "exporter_original": result.get("exporter_original", ""),
                    "consignee_original": result.get("consignee_original", ""),
                }
            return {"found": False, "match_type": "", "xml_template_id": "",
                    "source_filename": "", "notes": ["No local match"]}
        except Exception as e:
            logger.warning("Local exporter fallback failed: %s", e)
            return {"found": False, "match_type": "", "xml_template_id": "",
                    "source_filename": "", "notes": ["Local fallback unavailable"]}

    def _local_suggest_preference(
        self, country_code: str, exporter_name: str
    ) -> dict:
        """Fallback: query DB directly."""
        try:
            from database.db import get_db_connection
            cc = country_code.upper()
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT povlastica, COUNT(*) AS cnt
                        FROM catalogs.declaration_items
                        WHERE zemlja_porijekla = %s
                          AND povlastica IS NOT NULL AND povlastica != ''
                        GROUP BY povlastica
                        ORDER BY cnt DESC LIMIT 1
                    """, (cc,))
                    row = cur.fetchone()

            if row:
                return {
                    "preference": row["povlastica"],
                    "confidence": 0.8,
                    "source": "local_db_country",
                    "requires_origin_document": True,
                    "notes": ["source: local DB"],
                }
            return {
                "preference": "", "confidence": 0.0, "source": "",
                "requires_origin_document": False,
                "notes": ["No local preference data"],
            }
        except Exception as e:
            logger.warning("Local preference fallback failed: %s", e)
            return {"preference": "", "confidence": 0.0, "source": "",
                    "requires_origin_document": False,
                    "notes": ["Local fallback unavailable"]}

    def _local_validate_declaration_summary(
        self, draft_summary: dict
    ) -> dict:
        """Fallback: basic local validation."""
        errors = []
        warnings = []
        item_count = draft_summary.get("item_count", 0)

        if item_count > 99:
            errors.append(f"Broj naimenovanja ({item_count}) premašuje maksimum (99)")
        elif item_count >= 90:
            warnings.append(f"Broj naimenovanja ({item_count}) blizu maksimuma (99)")

        invoice_total = draft_summary.get("invoice_total", 0)
        if invoice_total is not None and invoice_total <= 0:
            warnings.append(f"Iznos fakture ({invoice_total}) je nula ili negativan")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }


# Singleton
mcp_facade = McpFacade()
