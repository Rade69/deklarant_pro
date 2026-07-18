-- Migration 008: Proširi VARCHAR kolone u product_tariff_mapping na TEXT
-- Uzrok: kolone dodate naknadno s CHARACTER VARYING(10) — predugački product_code
-- vrijednosti (farmaceutski kodovi, kompleksni šifarski nizovi) uzrokuju grešku.
ALTER TABLE catalogs.product_tariff_mapping
    ALTER COLUMN product_code    TYPE TEXT,
    ALTER COLUMN zemlja_porijekla TYPE TEXT,
    ALTER COLUMN povlastica      TYPE TEXT,
    ALTER COLUMN precision_1     TYPE TEXT,
    ALTER COLUMN supplier        TYPE TEXT;
