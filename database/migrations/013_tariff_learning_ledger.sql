CREATE TABLE IF NOT EXISTS catalogs.tariff_learning_ledger (
    draft_uid      TEXT NOT NULL,
    line_key       TEXT NOT NULL,
    naziv_robe     TEXT NOT NULL,
    product_code   TEXT NOT NULL DEFAULT '',
    tarifni_broj   TEXT NOT NULL,
    learned_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (draft_uid, line_key)
);

CREATE INDEX IF NOT EXISTS idx_tariff_learning_ledger_draft
    ON catalogs.tariff_learning_ledger (draft_uid);

GRANT SELECT, INSERT, UPDATE, DELETE ON catalogs.tariff_learning_ledger TO deklarant_app;
