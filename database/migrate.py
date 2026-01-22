"""Database migrations."""

import sqlite3
from pathlib import Path


class DatabaseMigration:
    """Upravlja database schema migracijama."""

    def __init__(self, db_path: str = "asycuda_pro.db"):
        """
        Inicijalizuje migration manager.

        Args:
            db_path: Putanja do database fajla
        """
        self.db_path = db_path

    def create_tables(self) -> None:
        """Kreira sve potrebne tabele."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Drafts tabela
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                broj_deklaracije TEXT NOT NULL,
                datum_kreiranja TIMESTAMP NOT NULL,
                datum_izmene TIMESTAMP NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                json_data TEXT NOT NULL
            )
        """)

        # Attachments tabela
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                draft_id INTEGER NOT NULL,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                datum_upload TIMESTAMP NOT NULL,
                FOREIGN KEY (draft_id) REFERENCES drafts(id) ON DELETE CASCADE
            )
        """)

        # Indeksi za brže pretraživanje
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_drafts_broj
            ON drafts(broj_deklaracije)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_drafts_status
            ON drafts(status)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_attachments_draft_id
            ON attachments(draft_id)
        """)

        conn.commit()
        conn.close()

    def drop_tables(self) -> None:
        """Briše sve tabele (pažljivo!)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DROP TABLE IF EXISTS attachments")
        cursor.execute("DROP TABLE IF EXISTS drafts")

        conn.commit()
        conn.close()

    def reset_database(self) -> None:
        """Briše i ponovo kreira sve tabele."""
        self.drop_tables()
        self.create_tables()


def init_database(db_path: str = "asycuda_pro.db") -> None:
    """
    Inicijalizuje database ako ne postoji.

    Args:
        db_path: Putanja do database fajla
    """
    migration = DatabaseMigration(db_path)
    migration.create_tables()
    print(f"Database inicijalizovana: {db_path}")


if __name__ == "__main__":
    # Pozovi za inicijalizaciju
    init_database()
