CREATE TABLE IF NOT EXISTS catalogs.user_feedback (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR NOT NULL DEFAULT 'default',
    action_type VARCHAR NOT NULL,
    item_type VARCHAR NOT NULL,
    item_key VARCHAR NOT NULL,
    original_value TEXT,
    new_value TEXT,
    confidence DOUBLE PRECISION DEFAULT 1.0,
    context JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed BOOLEAN DEFAULT FALSE,
    UNIQUE(user_id, item_key, action_type, created_at)
);

CREATE INDEX IF NOT EXISTS idx_user_feedback_item_key
    ON catalogs.user_feedback (item_key);

CREATE INDEX IF NOT EXISTS idx_user_feedback_processed
    ON catalogs.user_feedback (processed)
    WHERE NOT processed;
