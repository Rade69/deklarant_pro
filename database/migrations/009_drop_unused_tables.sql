-- Migracija 009: Ukloni 6 nekorišćenih tabela iz catalogs seme
-- Kontekst: agent_reports/2026-07-19_baza-podataka-audit-katalog.md
-- Svaka tabela nezavisno provjerena: 0 referenci u aktivnom kodu, 0 FK zavisnosti,
-- 0 dijeljenih sekvenci sa zivim tabelama, podaci zamrznuti mjesecima.
-- Pun backup (DDL + CSV podaci) prije brisanja:
-- database/backups/2026-07-19_pre_cleanup/

DROP TABLE IF EXISTS catalogs.product_tariff_mapping_backup;
DROP TABLE IF EXISTS catalogs.tariff_knowledge_base_backup;
DROP TABLE IF EXISTS catalogs.supplier_profiles;
DROP TABLE IF EXISTS catalogs.supplier_historical_profiles;
DROP TABLE IF EXISTS catalogs.postupci_rb37;
DROP TABLE IF EXISTS catalogs.declaration_drafts;
