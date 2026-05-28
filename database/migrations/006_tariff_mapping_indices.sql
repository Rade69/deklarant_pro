-- Migration 006: Indeksi na catalogs.product_tariff_mapping
-- Ubrzava _majority_vote() upite koji filtriraju po supplieru i sortiraju po usage_count.

-- Filtriranje po dobavljaču (supplier IN (...)) — koristi se u sva 3 kruga majority vote
CREATE INDEX IF NOT EXISTS idx_ptm_supplier
    ON catalogs.product_tariff_mapping (supplier);

-- Kompozitni indeks za supplier + commodity_code grupiranje
-- Ubrzava GROUP BY commodity_code unutar supplier filtera
CREATE INDEX IF NOT EXISTS idx_ptm_supplier_commodity
    ON catalogs.product_tariff_mapping (supplier, commodity_code);

-- Sortiranje po usage_count DESC — ORDER BY u svim find_mapping upitima
CREATE INDEX IF NOT EXISTS idx_ptm_usage_count
    ON catalogs.product_tariff_mapping (usage_count DESC);

-- Tačan match po product_code (koristi se u find_batch_by_product_codes i find_mapping)
CREATE INDEX IF NOT EXISTS idx_ptm_product_code
    ON catalogs.product_tariff_mapping (product_code);
