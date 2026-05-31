"""
Migracija: Kreiranje tabela za Knowledge Base (zakonska regulativa).

Tabele:
  - public.knowledge_base_docs   — metadata PDF dokumenata
  - public.knowledge_base_chunks — tekstualni odlomci za BM25 pretragu

Pokretanje:
    python database/migrate_knowledge_base.py
"""

from database.db import get_db_connection


def run():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS public.knowledge_base_docs (
                    id          SERIAL PRIMARY KEY,
                    filename    VARCHAR(500)  NOT NULL,
                    title       VARCHAR(500),
                    file_path   TEXT,
                    file_hash   VARCHAR(64),
                    page_count  INTEGER DEFAULT 0,
                    chunk_count INTEGER DEFAULT 0,
                    ingested_at TIMESTAMP DEFAULT NOW(),
                    updated_at  TIMESTAMP DEFAULT NOW()
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS public.knowledge_base_chunks (
                    id          SERIAL PRIMARY KEY,
                    doc_id      INTEGER NOT NULL
                                    REFERENCES public.knowledge_base_docs(id)
                                    ON DELETE CASCADE,
                    chunk_index INTEGER NOT NULL,
                    page_number INTEGER,
                    chunk_text  TEXT    NOT NULL,
                    created_at  TIMESTAMP DEFAULT NOW()
                );
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_kb_chunks_doc_id
                    ON public.knowledge_base_chunks(doc_id);
            """)

        conn.commit()
        print("✅ Knowledge Base tabele kreirane (knowledge_base_docs, knowledge_base_chunks)")


if __name__ == "__main__":
    run()
