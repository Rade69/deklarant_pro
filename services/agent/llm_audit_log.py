"""
LLM Audit Log + Session Token Budget

Loguje svaki LLM poziv bez osjetljivog sadržaja.
Prati potrošnju tokena i blokira kad se pređe SESSION_TOKEN_BUDGET.

Storage:
  Primarno:  PostgreSQL — public.llm_audit (centralno za sve klijente)
  Fallback:  SQLite     — database/llm_audit.db (kad server nije dostupan)

Tabela llm_audit:
  id, timestamp, client_name, provider,
  approx_tokens_in, approx_tokens_out, blocked
"""

import os
import sqlite3
from datetime import datetime
from pathlib import Path

_SQLITE_PATH = Path(__file__).parent.parent.parent / "database" / "llm_audit.db"

_session_tokens: int = 0


# ── Helpers ──────────────────────────────────────────────────────────────────

def _client_name() -> str:
    return os.getenv("CLIENT_NAME", "klijent1")


def _get_budget() -> int:
    try:
        return int(os.getenv("SESSION_TOKEN_BUDGET", "50000"))
    except ValueError:
        return 50_000


# ── PostgreSQL ────────────────────────────────────────────────────────────────

_PG_TABLE_CREATED = False


def _ensure_pg_table(conn) -> None:
    global _PG_TABLE_CREATED
    if _PG_TABLE_CREATED:
        return
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.llm_audit (
                id                SERIAL PRIMARY KEY,
                timestamp         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                client_name       TEXT        NOT NULL,
                provider          TEXT        NOT NULL,
                approx_tokens_in  INTEGER     NOT NULL,
                approx_tokens_out INTEGER     NOT NULL,
                blocked           BOOLEAN     NOT NULL DEFAULT FALSE
            )
        """)
    conn.commit()
    _PG_TABLE_CREATED = True


def _pg_log(provider: str, tokens_in: int, tokens_out: int, blocked: bool) -> bool:
    """Upiši u PostgreSQL. Vraća True ako uspije."""
    try:
        from database.db import get_db_connection
        with get_db_connection() as conn:
            _ensure_pg_table(conn)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.llm_audit
                        (client_name, provider, approx_tokens_in, approx_tokens_out, blocked)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (_client_name(), provider, tokens_in, tokens_out, blocked),
                )
        return True
    except Exception as e:
        print(f"[AuditLog] PG greška, prelazim na SQLite: {e}")
        return False


def _pg_today_stats() -> dict | None:
    """Statistika za danas iz PostgreSQL (svi klijenti)."""
    try:
        from database.db import get_db_connection
        today = datetime.now().strftime("%Y-%m-%d")
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        COUNT(*)                                    AS calls_today,
                        COALESCE(SUM(approx_tokens_in
                                   + approx_tokens_out), 0)        AS tokens_today,
                        COUNT(*) FILTER (WHERE blocked)            AS blocked_today,
                        client_name,
                        COUNT(*) FILTER (WHERE client_name = %s)   AS my_calls
                    FROM public.llm_audit
                    WHERE timestamp::date = %s
                    GROUP BY GROUPING SETS ((), (client_name))
                    ORDER BY client_name NULLS FIRST
                    """,
                    (_client_name(), today),
                )
                rows = cur.fetchall()
        if not rows:
            return {"calls_today": 0, "tokens_today": 0, "blocked_today": 0, "by_client": {}}
        total = dict(rows[0])
        by_client = {r["client_name"]: r["calls_today"] for r in rows[1:] if r["client_name"]}
        return {
            "calls_today":   total.get("calls_today", 0),
            "tokens_today":  total.get("tokens_today", 0),
            "blocked_today": total.get("blocked_today", 0),
            "by_client":     by_client,
        }
    except Exception:
        return None


# ── SQLite fallback ───────────────────────────────────────────────────────────

def _sqlite_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_SQLITE_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS llm_audit (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp         TEXT    NOT NULL,
            client_name       TEXT    NOT NULL,
            provider          TEXT    NOT NULL,
            approx_tokens_in  INTEGER NOT NULL,
            approx_tokens_out INTEGER NOT NULL,
            blocked           INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.commit()
    return conn


def _sqlite_log(provider: str, tokens_in: int, tokens_out: int, blocked: bool) -> None:
    try:
        with _sqlite_conn() as conn:
            conn.execute(
                "INSERT INTO llm_audit "
                "(timestamp, client_name, provider, approx_tokens_in, approx_tokens_out, blocked) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    datetime.now().isoformat(timespec="seconds"),
                    _client_name(),
                    provider,
                    tokens_in,
                    tokens_out,
                    int(blocked),
                ),
            )
    except Exception as e:
        print(f"[AuditLog] SQLite greška: {e}")


def _sqlite_today_stats() -> dict:
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        conn = _sqlite_conn()
        row = conn.execute(
            "SELECT COUNT(*), SUM(approx_tokens_in + approx_tokens_out), SUM(blocked) "
            "FROM llm_audit WHERE timestamp LIKE ?",
            (f"{today}%",),
        ).fetchone()
        conn.close()
        return {
            "calls_today":   row[0] or 0,
            "tokens_today":  row[1] or 0,
            "blocked_today": row[2] or 0,
            "by_client":     {},
        }
    except Exception:
        return {"calls_today": 0, "tokens_today": 0, "blocked_today": 0, "by_client": {}}


# ── Javni API ─────────────────────────────────────────────────────────────────

def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def estimate_tokens_messages(messages: list) -> int:
    return sum(estimate_tokens(m.get("content", "")) for m in messages)


def check_budget(tokens_needed: int) -> str | None:
    global _session_tokens
    budget = _get_budget()
    if _session_tokens + tokens_needed > budget:
        return (
            f"⛔ Sesijski limit tokena je dostignut "
            f"({_session_tokens:,} / {budget:,} tokena).\n"
            "Ponovo pokreni aplikaciju da resetuješ limit, "
            "ili povećaj SESSION_TOKEN_BUDGET u .env fajlu."
        )
    used_pct = _session_tokens / budget * 100 if budget else 0
    if used_pct >= 80:
        print(
            f"[TokenBudget] ⚠️ {used_pct:.0f}% sesijskog budžeta potrošeno "
            f"({_session_tokens:,}/{budget:,})."
        )
    return None


def log_call(
    provider: str,
    tokens_in: int,
    tokens_out: int,
    blocked: bool = False,
) -> None:
    global _session_tokens
    if not blocked:
        _session_tokens += tokens_in + tokens_out

    if not _pg_log(provider, tokens_in, tokens_out, blocked):
        _sqlite_log(provider, tokens_in, tokens_out, blocked)


def get_session_stats() -> dict:
    budget = _get_budget()
    return {
        "session_tokens_used": _session_tokens,
        "session_budget":      budget,
        "session_pct":         round(_session_tokens / budget * 100, 1) if budget else 0,
    }


def get_today_stats() -> dict:
    stats = _pg_today_stats()
    if stats is not None:
        return stats
    return _sqlite_today_stats()
