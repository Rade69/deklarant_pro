"""Repository za CRUD operacije sa Draft-om."""

import json
import sqlite3
import logging
from typing import List, Optional
from datetime import datetime
from contextlib import contextmanager

from .models import DraftModel, AttachmentModel

logger = logging.getLogger(__name__)


class DraftRepository:
    """Repository za upravljanje Draft-ovima u bazi."""

    def __init__(self, db_path: str = "asycuda_pro.db"):
        """
        Inicijalizuje repository.

        Args:
            db_path: Putanja do SQLite database fajla
        """
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Inicijalizuje bazu i kreira tabele ako ne postoje."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Kreiraj drafts tabelu
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS drafts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    broj_deklaracije TEXT UNIQUE,
                    status TEXT DEFAULT 'draft',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    data TEXT  -- JSON serializovan draft
                )
            """)
            # Kreiraj attachments tabelu
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS attachments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    draft_id INTEGER,
                    filename TEXT,
                    filepath TEXT,
                    file_type TEXT,
                    size INTEGER,
                    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (draft_id) REFERENCES drafts (id) ON DELETE CASCADE
                )
            """)
            conn.commit()
            logger.info("Database initialized")

    @contextmanager
    def _get_connection(self):
        """Context manager za database konekciju."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()

    def create(self, draft: DraftModel) -> int:
        """
        Kreira novi draft u bazi.

        Args:
            draft: Draft model za čuvanje

        Returns:
            ID kreiranog draft-a
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO drafts (broj_deklaracije, status, data, updated_at)
                VALUES (?, ?, ?, ?)
            """, (
                draft.broj_deklaracije,
                draft.status,
                json.dumps(draft.to_dict() if hasattr(draft, 'to_dict') else {}),
                datetime.now().isoformat()
            ))
            conn.commit()
            draft_id = cursor.lastrowid
            logger.info(f"Created draft with ID: {draft_id}")
            return draft_id

    def get_by_id(self, draft_id: int) -> Optional[DraftModel]:
        """
        Vraća draft po ID-u.

        Args:
            draft_id: ID draft-a

        Returns:
            Draft model ili None ako ne postoji
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,))
            row = cursor.fetchone()

            if row:
                data = json.loads(row['data']) if row['data'] else {}
                return DraftModel(
                    id=row['id'],
                    broj_deklaracije=row['broj_deklaracije'],
                    status=row['status'],
                    data=data,
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                )
            return None

    def get_all(self) -> List[DraftModel]:
        """
        Vraća sve draft-ove.

        Returns:
            Lista svih draft-ova
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM drafts ORDER BY updated_at DESC")
            rows = cursor.fetchall()

            drafts = []
            for row in rows:
                data = json.loads(row['data']) if row['data'] else {}
                drafts.append(DraftModel(
                    id=row['id'],
                    broj_deklaracije=row['broj_deklaracije'],
                    status=row['status'],
                    data=data,
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                ))
            return drafts

    def update(self, draft: DraftModel) -> bool:
        """
        Ažurira postojeći draft.

        Args:
            draft: Draft model sa izmenjenim podacima

        Returns:
            True ako je uspešno ažurirano
        """
        if draft.id is None:
            logger.error("Cannot update draft without ID")
            return False

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE drafts 
                SET broj_deklaracije = ?, status = ?, data = ?, updated_at = ?
                WHERE id = ?
            """, (
                draft.broj_deklaracije,
                draft.status,
                json.dumps(draft.to_dict() if hasattr(draft, 'to_dict') else {}),
                datetime.now().isoformat(),
                draft.id
            ))
            conn.commit()
            updated = cursor.rowcount > 0
            if updated:
                logger.info(f"Updated draft with ID: {draft.id}")
            return updated

    def delete(self, draft_id: int) -> bool:
        """
        Briše draft iz baze.

        Args:
            draft_id: ID draft-a za brisanje

        Returns:
            True ako je uspešno obrisano
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM drafts WHERE id = ?", (draft_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"Deleted draft with ID: {draft_id}")
            return deleted

    def search(self, query: str) -> List[DraftModel]:
        """
        Pretražuje draft-ove.

        Args:
            query: Search query (broj deklaracije, status...)

        Returns:
            Lista pronađenih draft-ova
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            search_pattern = f"%{query}%"
            cursor.execute("""
                SELECT * FROM drafts 
                WHERE broj_deklaracije LIKE ? OR status LIKE ?
                ORDER BY updated_at DESC
            """, (search_pattern, search_pattern))
            rows = cursor.fetchall()

            drafts = []
            for row in rows:
                data = json.loads(row['data']) if row['data'] else {}
                drafts.append(DraftModel(
                    id=row['id'],
                    broj_deklaracije=row['broj_deklaracije'],
                    status=row['status'],
                    data=data,
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                ))
            return drafts


class AttachmentRepository:
    """Repository za upravljanje prilozima."""

    def __init__(self, db_path: str = "asycuda_pro.db"):
        """Inicijalizuje repository."""
        self.db_path = db_path

    @contextmanager
    def _get_connection(self):
        """Context manager za database konekciju."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()

    def create(self, attachment: AttachmentModel) -> int:
        """Kreira novi prilog."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO attachments (draft_id, filename, filepath, file_type, size)
                VALUES (?, ?, ?, ?, ?)
            """, (
                attachment.draft_id,
                attachment.filename,
                attachment.filepath,
                attachment.file_type,
                attachment.size
            ))
            conn.commit()
            attachment_id = cursor.lastrowid
            logger.info(f"Created attachment with ID: {attachment_id}")
            return attachment_id

    def get_by_draft_id(self, draft_id: int) -> List[AttachmentModel]:
        """Vraća sve priloge za draft."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM attachments 
                WHERE draft_id = ? 
                ORDER BY uploaded_at DESC
            """, (draft_id,))
            rows = cursor.fetchall()

            attachments = []
            for row in rows:
                attachments.append(AttachmentModel(
                    id=row['id'],
                    draft_id=row['draft_id'],
                    filename=row['filename'],
                    filepath=row['filepath'],
                    file_type=row['file_type'],
                    size=row['size'],
                    uploaded_at=row['uploaded_at']
                ))
            return attachments

    def delete(self, attachment_id: int) -> bool:
        """Briše prilog."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM attachments WHERE id = ?", (attachment_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"Deleted attachment with ID: {attachment_id}")
            return deleted
