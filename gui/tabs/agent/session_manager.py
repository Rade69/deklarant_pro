# gui/tabs/agent/session_manager.py
"""
AgentSessionManager — crash recovery za Agent tab.

Snima stanje sesije u SQLite nakon svakog važnog događaja:
  - upload fajla
  - pokretanje analize
  - završetak analize
  - greška / prekid
  - promjena workflow stanja

Pri sljedećem pokretanju: učitaj zadnju sesiju i upozori korisnika
ako je bila prekinuta u kritičnom stanju (ANALYZING / APPLYING).
"""

import json
import sqlite3
import uuid
import os
import logging
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger("asycuda_pro.session_manager")

_DB_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', 'database', 'asycuda_sistem.db')
)

_CRITICAL_STATES = {'analyzing', 'applying', 'failed'}


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


class AgentSessionManager:
    """
    Čuva i obnavlja stanje Agent tab sesije između restartova.

    Upotreba:
        session = AgentSessionManager()
        session.save(workflow_state=wf.state, ...)     # snimaj
        last = session.load_latest_interrupted()        # crash recovery
    """

    def __init__(self):
        self._session_id: str = str(uuid.uuid4())
        self._created_at: str = datetime.now().isoformat()
        self._ensure_table()

    @property
    def session_id(self) -> str:
        return self._session_id

    # ─────────────────────────────────────────────────
    # Snimanje
    # ─────────────────────────────────────────────────

    def save(
        self,
        workflow_state_value: str,
        selected_mode: str,
        uploaded_files: list,
        token_input: int,
        token_output: int,
        pending_confirmation: Optional[str] = None,
    ):
        """Snimi trenutno stanje sesije u DB."""
        try:
            conn = _get_conn()
            conn.execute("""
                INSERT OR REPLACE INTO agent_sessions
                    (session_id, created_at, updated_at, workflow_state,
                     selected_mode, uploaded_files, token_input, token_output,
                     pending_confirmation)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                self._session_id,
                self._created_at,
                datetime.now().isoformat(),
                workflow_state_value,
                selected_mode,
                json.dumps(uploaded_files, ensure_ascii=False),
                token_input,
                token_output,
                pending_confirmation,
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error("Greška pri snimanju sesije: %s", e)

    # ─────────────────────────────────────────────────
    # Učitavanje
    # ─────────────────────────────────────────────────

    def load_latest_interrupted(self) -> Optional[Dict[str, Any]]:
        """
        Vrati zadnju sesiju koja je prekinuta u kritičnom stanju.
        Koristi se za crash recovery pri pokretanju.
        """
        try:
            conn = _get_conn()
            row = conn.execute("""
                SELECT * FROM agent_sessions
                WHERE workflow_state IN ('analyzing', 'applying', 'failed')
                  AND session_id != ?
                ORDER BY updated_at DESC
                LIMIT 1
            """, (self._session_id,)).fetchone()
            conn.close()
            return _row_to_dict(row) if row else None
        except Exception as e:
            logger.error("Greška pri čitanju sesije: %s", e)
            return None

    def load_latest(self) -> Optional[Dict[str, Any]]:
        """Vrati najnoviju sesiju (za prikaz prethodnog stanja)."""
        try:
            conn = _get_conn()
            row = conn.execute("""
                SELECT * FROM agent_sessions
                WHERE session_id != ?
                ORDER BY updated_at DESC LIMIT 1
            """, (self._session_id,)).fetchone()
            conn.close()
            return _row_to_dict(row) if row else None
        except Exception as e:
            logger.error("Greška pri čitanju sesije: %s", e)
            return None

    # ─────────────────────────────────────────────────
    # Interno
    # ─────────────────────────────────────────────────

    def _ensure_table(self):
        try:
            conn = _get_conn()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_sessions (
                    session_id          TEXT PRIMARY KEY,
                    created_at          TEXT NOT NULL,
                    updated_at          TEXT NOT NULL,
                    workflow_state      TEXT NOT NULL,
                    selected_mode       TEXT,
                    uploaded_files      TEXT,
                    token_input         INTEGER DEFAULT 0,
                    token_output        INTEGER DEFAULT 0,
                    pending_confirmation TEXT
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error("DB init greška: %s", e)


def _row_to_dict(row) -> Dict[str, Any]:
    uploaded = []
    try:
        uploaded = json.loads(row['uploaded_files']) if row['uploaded_files'] else []
    except Exception:
        pass
    return {
        'session_id':           row['session_id'],
        'created_at':           row['created_at'],
        'updated_at':           row['updated_at'],
        'workflow_state':       row['workflow_state'],
        'selected_mode':        row['selected_mode'] or 'Analiza',
        'uploaded_files':       uploaded,
        'token_input':          row['token_input'] or 0,
        'token_output':         row['token_output'] or 0,
        'pending_confirmation': row['pending_confirmation'],
    }
