-- Migration 011: pg_trgm indeks za ILIKE '%dobavljac%' pretragu u
-- catalogs.product_similarity_memory (koristi je _find_vector_matches() u
-- services/agent/learning/product_similarity_embedding_service.py).
-- idx_product_similarity_supplier (iz migracije 005) je obican B-tree i ne
-- pomaze ILIKE '%...%' upitima - isti obrazac kao migracija 007 za
-- product_tariff_mapping (potvrdjeno EXPLAIN ANALYZE: Seq Scan, 76ms na
-- 26.404 reda prije ovog indeksa).

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_product_similarity_supplier_trgm
    ON catalogs.product_similarity_memory
    USING GIN (supplier gin_trgm_ops);
