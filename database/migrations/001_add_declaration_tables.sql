-- ============================================================
-- ASYCUDA Pro - SQLite Migracije
-- Migracija 001: Tabele za deklaracije i stavke
-- ============================================================

-- Tabela za historiju deklaracija
CREATE TABLE IF NOT EXISTS declarations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number TEXT NOT NULL,
    vendor TEXT,
    buyer TEXT,
    datum TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Index za brzu pretragu po broju fakture
CREATE INDEX IF NOT EXISTS idx_declarations_invoice 
ON declarations(invoice_number);

-- Tabela za stavke deklaracija sa tarifnim brojevima
CREATE TABLE IF NOT EXISTS declaration_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    declaration_id INTEGER NOT NULL,
    tarifni_broj TEXT,
    naziv_robe TEXT NOT NULL,
    zemlja_porijekla TEXT,
    povlastica TEXT,
    confidence REAL DEFAULT 0.5,
    ai_suggested INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (declaration_id) REFERENCES declarations(id) ON DELETE CASCADE
);

-- Indexi za brzu pretragu
CREATE INDEX IF NOT EXISTS idx_items_declaration 
ON declaration_items(declaration_id);

CREATE INDEX IF NOT EXISTS idx_items_tarifni_broj 
ON declaration_items(tarifni_broj);

CREATE INDEX IF NOT EXISTS idx_items_naziv_robe 
ON declaration_items(naziv_robe);

CREATE INDEX IF NOT EXISTS idx_items_zemlja 
ON declaration_items(zemlja_porijekla);
