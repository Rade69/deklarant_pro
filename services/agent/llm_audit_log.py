"""
LLM Audit Log + Session Token Budget

Loguje svaki LLM poziv u SQLite (bez osjetljivog sadržaja).
Prati potrošnju tokena i blokira kad se pređe SESSION_TOKEN_BUDGET.

Tabela: llm_calls
  id, timestamp, provider, approx_tokens_in, approx_tokens_out, blocked

Baza: database/llm_audit.db (uz ostale SQLite baze projekta)
"""

import sqlite3
import os
from datetime import datetime
from pathlib import Path

_DB_PATH = Path(__file__).parent.parent.parent / "database" / "llm_audit.db"

# In-memory brojač tokena za trenutnu sesiju (resetuje se pri pokretanju app)
_session_tokens: int = 0


def _get_budget() -> int:
    """Čita SESSION_TOKEN_BUDGET iz env (default 50000)."""
    try:
        return int(os.getenv("SESSION_TOKEN_BUDGET", "50000"))
    except ValueError:
        return 50_000


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS llm_calls (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp        TEXT    NOT NULL,
            provider         TEXT    NOT NULL,
            approx_tokens_in INTEGER NOT NULL,
            approx_tokens_out INTEGER NOT NULL,
            blocked          INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.commit()
    return conn


def estimate_tokens(text: str) -> int:
    """Grubo: 1 token ≈ 4 karaktera."""
    return max(1, len(text) // 4)


def estimate_tokens_messages(messages: list) -> int:
    """Procjena tokena za listu messages dicts."""
    total = 0
    for m in messages:
        total += estimate_tokens(m.get("content", ""))
    return total


def check_budget(tokens_needed: int) -> str | None:
    """
    Provjeri da li sesija ima dovoljno tokena.

    Returns:
        None  — OK, može se nastaviti
        str   — poruka o prekoračenju (prikaži korisniku)
    """
    global _session_tokens
    budget = _get_budget()
    used_pct = (_session_tokens / budget * 100) if budget > 0 else 0

    if _session_tokens + tokens_needed > budget:
        return (
            f"⛔ Sesijski limit tokena je dostignut "
            f"({_session_tokens:,} / {budget:,} tokena).\n"
            "Ponovo pokreni aplikaciju da resetuješ limit, "
            "ili povećaj SESSION_TOKEN_BUDGET u .env fajlu."
        )

    if used_pct >= 80:
        remaining = budget - _session_tokens
        print(
            f"[TokenBudget] ⚠️ Upozorenje: {used_pct:.0f}% sesijskog budžeta potrošeno "
            f"({_session_tokens:,}/{budget:,}). Preostalo: ~{remaining:,} tokena."
        )
    return None


def log_call(
    provider: str,
    tokens_in: int,
    tokens_out: int,
    blocked: bool = False,
) -> None:
    """
    Logiraj LLM poziv — bez sadržaja, samo metapodaci.
    Ažurira in-memory session brojač.
    """
    global _session_tokens

    if not blocked:
        _session_tokens += tokens_in + tokens_out

    try:
        with _conn() as conn:
            conn.execute(
                "INSERT INTO llm_calls "
                "(timestamp, provider, approx_tokens_in, approx_tokens_out, blocked) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    datetime.now().isoformat(timespec="seconds"),
                    provider,
                    tokens_in,
                    tokens_out,
                    int(blocked),
                ),
            )
    except Exception as e:
        print(f"[AuditLog] Greška pri upisu: {e}")


def get_session_stats() -> dict:
    """Statistika trenutne sesije (iz in-memory brojača)."""
    budget = _get_budget()
    return {
        "session_tokens_used": _session_tokens,
        "session_budget":      budget,
        "session_pct":         round(_session_tokens / budget * 100, 1) if budget else 0,
    }


def get_today_stats() -> dict:
    """Statistika iz baze za danas."""
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        with _conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*), SUM(approx_tokens_in + approx_tokens_out), "
                "       SUM(blocked) "
                "FROM llm_calls WHERE timestamp LIKE ?",
                (f"{today}%",),
            ).fetchone()
        return {
            "calls_today":   row[0] or 0,
            "tokens_today":  row[1] or 0,
            "blocked_today": row[2] or 0,
        }
    except Exception:
        return {"calls_today": 0, "tokens_today": 0, "blocked_today": 0}
