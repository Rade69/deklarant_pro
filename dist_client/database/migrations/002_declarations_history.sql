-- ============================================================
-- ASYCUDA Pro - PostgreSQL Migracije
-- Migracija 001: Tabele za historiju deklaracija (catalogs shema)
-- ============================================================

-- Tabela za historiju deklaracija
CREATE TABLE IF NOT EXISTS catalogs.declarations (
    id SERIAL PRIMARY KEY,
    invoice_number VARCHAR(255) NOT NULL,
    vendor VARCHAR(500),
    buyer VARCHAR(500),
    datum DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index za brzu pretragu po broju fakture
CREATE INDEX IF NOT EXISTS idx_declarations_invoice 
ON catalogs.declarations(invoice_number);

-- Index za pretragu po datumu
CREATE INDEX IF NOT EXISTS idx_declarations_datum 
ON catalogs.declarations(datum);

-- Tabela za stavke deklaracija sa tarifnim brojevima
CREATE TABLE IF NOT EXISTS catalogs.declaration_items (
    id SERIAL PRIMARY KEY,
    declaration_id INTEGER NOT NULL REFERENCES catalogs.declarations(id) ON DELETE CASCADE,
    tarifni_broj VARCHAR(20),
    naziv_robe TEXT NOT NULL,
    zemlja_porijekla VARCHAR(100),
    povlastica VARCHAR(100),
    confidence REAL DEFAULT 0.5,
    ai_suggested BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexi za brzu pretragu
CREATE INDEX IF NOT EXISTS idx_items_declaration 
ON catalogs.declaration_items(declaration_id);

CREATE INDEX IF NOT EXISTS idx_items_tarifni_broj 
ON catalogs.declaration_items(tarifni_broj);

-- GIN index za full-text pretragu naziva robe
CREATE INDEX IF NOT EXISTS idx_items_naziv_robe_fts 
ON catalogs.declaration_items USING gin(to_tsvector('simple', naziv_robe));

CREATE INDEX IF NOT EXISTS idx_items_zemlja 
ON catalogs.declaration_items(zemlja_porijekla);
