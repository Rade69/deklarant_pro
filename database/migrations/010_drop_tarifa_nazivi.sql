-- Migracija 010: Ukloni tarifa_nazivi (mrtav widget, nikad wired u GUI)
-- Kontekst: agent_reports/2026-07-19_baza-podataka-audit-katalog.md
-- GoodsNameEdit (gui/widgets/db_widgets.py) koristi ovu tabelu ali nikad nije
-- ubacen ni u jedan tab/dijalog (nije izvezen iz gui/widgets/__init__.py).
-- 0 redova, 0 FK zavisnosti, sekvenca ne dijeljena. Backup:
-- database/backups/2026-07-19_tarifa_nazivi/

DROP TABLE IF EXISTS catalogs.tarifa_nazivi;
