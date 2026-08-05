-- 014: Full-text search na catalogs.zvanicna_tarifa.opis
-- GIN indeks na tsvector izrazu (bez ALTER TABLE — ne treba nova kolona)
-- Brzina: 50-200× brže od ILIKE '%text%' za pretragu po riječima
--
-- Korištenje:
--   SELECT * FROM catalogs.zvanicna_tarifa
--   WHERE to_tsvector('simple', opis) @@ plainto_tsquery('simple', 'krompir')
--   ORDER BY ts_rank(to_tsvector('simple', opis), plainto_tsquery('simple', 'krompir')) DESC;

CREATE INDEX IF NOT EXISTS idx_zvanicna_tarifa_fts_opis
ON catalogs.zvanicna_tarifa
USING GIN (to_tsvector('simple', opis));
