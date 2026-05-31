-- ============================================================
-- ASYCUDA Pro - Migracija 002: Agent sesije
-- Premjestanje agent_sessions iz SQLite u PostgreSQL catalogs shemu
-- ============================================================

CREATE TABLE IF NOT EXISTS catalogs.agent_sessions (
    session_id          TEXT PRIMARY KEY,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    workflow_state      TEXT NOT NULL,
    selected_mode       TEXT,
    uploaded_files      TEXT,
    token_input         INTEGER DEFAULT 0,
    token_output        INTEGER DEFAULT 0,
    pending_confirmation TEXT
);

-- Index za brzo dohvatanje zadnje sesije
CREATE INDEX IF NOT EXISTS idx_agent_sessions_updated_at
    ON catalogs.agent_sessions (updated_at DESC);

-- Index za crash recovery (filtriranje po workflow_state)
CREATE INDEX IF NOT EXISTS idx_agent_sessions_workflow_state
    ON catalogs.agent_sessions (workflow_state);
