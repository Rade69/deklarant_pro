-- Migration 012: pg_trgm indeksi za ILIKE '%...%' pretragu na jos dvije
-- tabele koje su bile sekvencijalni scan (isti obrazac kao migracije 007/011).
--
-- catalogs.zvanicna_tarifa (12.686 redova) - "Trgovacki nazivi" pretraga u
-- sifarnici_service.py (load_trgovacki_nazivi_data) i tariff_rag_service.py.
-- Potvrdjeno EXPLAIN ANALYZE: Seq Scan, 38.6ms na opis ILIKE '%masina%'.
--
-- catalogs.declaration_items (9.798 redova) - naziv_robe ILIKE u
-- tariff_rag_service.py/tariff_history_analysis_service.py. Postojeci
-- idx_items_naziv_robe_fts je FTS (to_tsvector/@@) indeks - ne pomaze
-- ILIKE '%...%' (~~* operator), drugaciji tip pretrage.
-- Potvrdjeno EXPLAIN ANALYZE: Seq Scan, 25.5ms na naziv_robe ILIKE '%masina%'.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_zvanicna_tarifa_opis_trgm
    ON catalogs.zvanicna_tarifa
    USING GIN (opis gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_zvanicna_tarifa_kod_trgm
    ON catalogs.zvanicna_tarifa
    USING GIN (tarifni_kod gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_declaration_items_naziv_robe_trgm
    ON catalogs.declaration_items
    USING GIN (naziv_robe gin_trgm_ops);
