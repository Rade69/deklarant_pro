# ============================================================
# SECTION: mcp-server-db
# PURPOSE: PostgreSQL connection pool for MCP server tools
# DOC: docs/sections/mcp-server-architecture.md
# ============================================================

"""
Database access layer for MCP server.
Uses the same connection pool pattern as the main application (database/db.py)
but as a standalone module that does not depend on the desktop app.
"""

import logging
from contextlib import contextmanager
from typing import Optional

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

from .config import get_db_settings

logger = logging.getLogger("mcp_server.db")

_pool: Optional[ThreadedConnectionPool] = None


def get_pool() -> ThreadedConnectionPool:
    """Get or create the connection pool (lazy init)."""
    global _pool
    if _pool is None:
        settings = get_db_settings()
        _pool = ThreadedConnectionPool(
            minconn=1,
            maxconn=5,
            host=settings.host,
            port=settings.port,
            database=settings.database,
            user=settings.user,
            password=settings.password,
            cursor_factory=RealDictCursor,
            connect_timeout=3,
        )
        logger.info("MCP DB pool created (min=1, max=5)")
    return _pool


@contextmanager
def get_connection():
    """
    Context manager that yields a connection and returns it to the pool.
    Auto-commits on success, rollback on exception.

    Usage:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT ...")
    """
    pool = get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def close_pool():
    """Close all connections. Call on shutdown."""
    global _pool
    if _pool:
        _pool.closeall()
        _pool = None
        logger.info("MCP DB pool closed")
