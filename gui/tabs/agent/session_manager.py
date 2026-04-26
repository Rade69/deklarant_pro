# gui/tabs/agent/session_manager.py
"""
AgentSessionManager — crash recovery za Agent tab.

Snima stanje sesije u PostgreSQL (catalogs.agent_sessions) nakon
svakog važnog događaja:
  - upload fajla
  - pokretanje analize
  - završetak analize
  - greška / prekid
  - promjena workflow stanja

Pri sljedećem pokretanju: učitaj zadnju sesiju i upozori korisnika
ako je bila prekinuta u kritičnom stanju (ANALYZING / APPLYING).
"""

import json
import uuid
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from database.db import get_db_connection

logger = logging.getLogger("deklarant_pro.session_manager")

_CRITICAL_STATES = {'analyzing', 'applying', 'failed'}


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
        """Snimi trenutno stanje sesije u bazu."""
        try:
            with get_db_connection() as conn:
                conn.cursor().execute("""
                    INSERT INTO catalogs.agent_sessions
                        (session_id, created_at, updated_at, workflow_state,
                         selected_mode, uploaded_files, token_input, token_output,
                         pending_confirmation)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (session_id) DO UPDATE SET
                        updated_at          = EXCLUDED.updated_at,
                        workflow_state      = EXCLUDED.workflow_state,
                        selected_mode       = EXCLUDED.selected_mode,
                        uploaded_files      = EXCLUDED.uploaded_files,
                        token_input         = EXCLUDED.token_input,
                        token_output        = EXCLUDED.token_output,
                        pending_confirmation = EXCLUDED.pending_confirmation
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
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT * FROM catalogs.agent_sessions
                    WHERE workflow_state IN ('analyzing', 'applying', 'failed')
                      AND session_id != %s
                    ORDER BY updated_at DESC
                    LIMIT 1
                """, (self._session_id,))
                row = cur.fetchone()
                return _row_to_dict(row) if row else None
        except Exception as e:
            logger.error("Greška pri čitanju sesije: %s", e)
            return None

    def load_latest(self) -> Optional[Dict[str, Any]]:
        """Vrati najnoviju sesiju (za prikaz prethodnog stanja)."""
        try:
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT * FROM catalogs.agent_sessions
                    WHERE session_id != %s
                    ORDER BY updated_at DESC LIMIT 1
                """, (self._session_id,))
                row = cur.fetchone()
                return _row_to_dict(row) if row else None
        except Exception as e:
            logger.error("Greška pri čitanju sesije: %s", e)
            return None


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
