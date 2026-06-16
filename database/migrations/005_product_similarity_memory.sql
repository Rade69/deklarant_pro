-- ============================================================
-- Deklarant Pro - PostgreSQL Migracije
-- Migracija 005: Vektorska memorija slicnih proizvoda
-- ============================================================

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS catalogs.product_similarity_memory (
    id BIGSERIAL PRIMARY KEY,
    source_table TEXT NOT NULL,
    source_id BIGINT NOT NULL,
    source_hash TEXT NOT NULL,
    supplier TEXT,
    product_name TEXT NOT NULL,
    origin_country VARCHAR(10),
    preference_code VARCHAR(30),
    tariff_code VARCHAR(20) NOT NULL,
    usage_count INTEGER NOT NULL DEFAULT 0,
    accepted_feedback_count INTEGER NOT NULL DEFAULT 0,
    rejected_feedback_count INTEGER NOT NULL DEFAULT 0,
    confidence DOUBLE PRECISION,
    text_for_embedding TEXT NOT NULL,
    embedding vector(1536),
    embedding_model TEXT,
    embedding_created_at TIMESTAMP,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source_table, source_id)
);

CREATE INDEX IF NOT EXISTS idx_product_similarity_source_hash
    ON catalogs.product_similarity_memory (source_hash);

CREATE INDEX IF NOT EXISTS idx_product_similarity_supplier
    ON catalogs.product_similarity_memory (supplier);

CREATE INDEX IF NOT EXISTS idx_product_similarity_tariff
    ON catalogs.product_similarity_memory (tariff_code);

CREATE INDEX IF NOT EXISTS idx_product_similarity_origin
    ON catalogs.product_similarity_memory (origin_country);

CREATE INDEX IF NOT EXISTS idx_product_similarity_usage
    ON catalogs.product_similarity_memory (usage_count DESC);

CREATE INDEX IF NOT EXISTS idx_product_similarity_embedding_hnsw
    ON catalogs.product_similarity_memory
    USING hnsw (embedding vector_cosine_ops)
    WHERE embedding IS NOT NULL;

COMMENT ON TABLE catalogs.product_similarity_memory IS
    'Embedding memorija za pronalazak slicnih ranijih proizvoda. Nije autoritet za automatsku odluku o tarifi.';

COMMENT ON COLUMN catalogs.product_similarity_memory.source_table IS
    'Izvor podataka, npr. catalogs.product_tariff_mapping.';

COMMENT ON COLUMN catalogs.product_similarity_memory.source_id IS
    'Primarni kljuc izvornog reda.';

COMMENT ON COLUMN catalogs.product_similarity_memory.source_hash IS
    'Stabilni hash teksta i metapodataka za detekciju promjena.';

COMMENT ON COLUMN catalogs.product_similarity_memory.text_for_embedding IS
    'Tekst koji se salje embedding modelu: naziv robe + dobavljac + zemlja + dodatni kontekst.';
