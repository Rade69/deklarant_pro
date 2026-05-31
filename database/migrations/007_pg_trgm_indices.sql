-- Migration 007: pg_trgm indeksi za ILIKE '%keyword%' pretrage
-- B-tree indeksi ne pomažu za %prefiks% pretragu; pg_trgm GIN indeksi je rješavaju.

-- Aktiviraj pg_trgm ekstenziju (idempotentan poziv)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- naziv_robe — najčešće pretraživan kolona (fuzzy matching, majority vote, ILIKE pretrage)
CREATE INDEX IF NOT EXISTS idx_ptm_naziv_trgm
    ON catalogs.product_tariff_mapping
    USING GIN (naziv_robe gin_trgm_ops);

-- product_code — ILIKE pretraga u find_mapping() i find_batch_by_product_codes()
CREATE INDEX IF NOT EXISTS idx_ptm_product_code_trgm
    ON catalogs.product_tariff_mapping
    USING GIN (product_code gin_trgm_ops);

-- supplier — ILIKE '%supplier_key%' u _majority_vote() i _execute()
CREATE INDEX IF NOT EXISTS idx_ptm_supplier_trgm
    ON catalogs.product_tariff_mapping
    USING GIN (supplier gin_trgm_ops);
