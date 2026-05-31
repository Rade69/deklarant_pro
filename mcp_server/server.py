# ============================================================
# SECTION: mcp-server-core
# PURPOSE: MCP transport layer — exposes tools via stdio JSON-RPC
# DOC: docs/sections/mcp-server-architecture.md
# ============================================================

"""
MCP (Model Context Protocol) server for Deklarant Pro.

Exposes read-only customs tools via stdio JSON-RPC.
Start with:
    python -m mcp_server.server
    uv run python -m mcp_server.server
"""

import json
import logging
import sys
from typing import Any

from .config import get_server_settings
from .db import close_pool
from .tools.declaration_search import search_historical_declarations
from .tools.exporter_template import find_exporter_xml_template
from .tools.preference import suggest_preference
from .tools.product_origin import find_product_origin
from .tools.tariff_history import suggest_tariff_from_history
from .tools.validation import validate_declaration_summary

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("mcp_server")

TOOLS = {
    "find_product_origin": {
        "function": find_product_origin,
        "description": (
            "Find likely country of origin for a product from historical "
            "declaration data. Returns country codes with confidence scores."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "product_name": {"type": "string"},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["product_name"],
        },
    },
    "search_historical_declarations": {
        "function": search_historical_declarations,
        "description": (
            "Search historical declaration items by product name with optional "
            "filters for country, HS code, and exporter."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "filters": {
                    "type": "object",
                    "properties": {
                        "country_code": {"type": "string"},
                        "hs_code": {"type": "string"},
                        "exporter_name": {"type": "string"},
                    },
                },
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["query"],
        },
    },
    "suggest_tariff_from_history": {
        "function": suggest_tariff_from_history,
        "description": (
            "Suggest HS tariff codes based on historical declaration data. "
            "This is a suggestion only and final decision requires human review."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "product_name": {"type": "string"},
                "exporter_name": {"type": "string"},
                "country_code": {"type": "string"},
                "limit": {"type": "integer", "default": 5},
            },
            "required": ["product_name"],
        },
    },
    "find_exporter_xml_template": {
        "function": find_exporter_xml_template,
        "description": (
            "Find a previously used XML declaration template for an "
            "exporter-consignee pair. Returns metadata only, not full XML."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "exporter_name": {"type": "string"},
                "consignee_jib": {"type": "string"},
                "consignee_name": {"type": "string"},
            },
            "required": ["exporter_name"],
        },
    },
    "suggest_preference": {
        "function": suggest_preference,
        "description": (
            "Suggest a customs preference code based on country and optionally "
            "exporter history."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "country_code": {"type": "string"},
                "exporter_name": {"type": "string"},
            },
            "required": ["country_code"],
        },
    },
    "validate_declaration_summary": {
        "function": validate_declaration_summary,
        "description": (
            "Validate a declaration draft summary against centralized rules. "
            "Blocks more than 99 items and warns on invalid HS codes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "draft_summary": {
                    "type": "object",
                    "properties": {
                        "item_count": {"type": "integer"},
                        "invoice_total": {"type": "number"},
                        "currency": {"type": "string"},
                        "items": {"type": "array"},
                    },
                },
            },
            "required": ["draft_summary"],
        },
    },
}


def _send(response: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(response, ensure_ascii=False, default=str) + "\n")
    sys.stdout.flush()


def _error(msg_id: Any, code: int, message: str) -> None:
    _send({"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}})


def handle_initialize(msg_id: Any) -> None:
    settings = get_server_settings()
    _send({
        "jsonrpc": "2.0",
        "id": msg_id,
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": settings.name, "version": "1.0.0"},
        },
    })


def handle_list_tools(msg_id: Any) -> None:
    tools_list = [
        {
            "name": name,
            "description": info["description"],
            "inputSchema": info["input_schema"],
        }
        for name, info in TOOLS.items()
    ]
    _send({"jsonrpc": "2.0", "id": msg_id, "result": {"tools": tools_list}})


def handle_call_tool(msg_id: Any, params: dict[str, Any]) -> None:
    tool_name = params.get("name", "")
    arguments = params.get("arguments", {})

    if tool_name not in TOOLS:
        _error(msg_id, -32601, f"Unknown tool: {tool_name}")
        return

    try:
        func = TOOLS[tool_name]["function"]
        result = func(**arguments)
        _send({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, default=str),
                    }
                ]
            },
        })
    except TypeError:
        _error(msg_id, -32602, f"Invalid arguments for {tool_name}")
    except Exception:
        logger.exception("Tool %s failed", tool_name)
        _error(msg_id, -32603, "Tool execution failed")


def run() -> None:
    logger.info("Deklarant Pro MCP server starting...")
    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON received")
                continue

            msg_id = msg.get("id")
            method = msg.get("method", "")
            params = msg.get("params", {})

            if method == "initialize":
                handle_initialize(msg_id)
            elif method == "notifications/initialized":
                pass
            elif method == "tools/list":
                handle_list_tools(msg_id)
            elif method == "tools/call":
                handle_call_tool(msg_id, params)
            elif method == "ping":
                _send({"jsonrpc": "2.0", "id": msg_id, "result": {}})
            else:
                _error(msg_id, -32601, f"Method not found: {method}")
    except KeyboardInterrupt:
        logger.info("MCP server shutting down...")
    except Exception:
        logger.exception("Fatal error in MCP server")
    finally:
        close_pool()
        logger.info("MCP server stopped")


if __name__ == "__main__":
    run()
