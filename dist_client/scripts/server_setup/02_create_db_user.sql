-- ============================================================
-- Deklarant Pro — Kreiranje baze i korisnika na serveru
-- Pokrenuti kao postgres superuser:
--   sudo -u postgres psql -f 02_create_db_user.sql
-- ============================================================

-- Korisnik za aplikaciju (samo mu treba pristup deklarant_pro bazi)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'deklarant_app') THEN
        CREATE ROLE deklarant_app WITH LOGIN PASSWORD 'PROMIJENI_OVU_LOZINKU';
        RAISE NOTICE 'Korisnik deklarant_app kreiran.';
    ELSE
        RAISE NOTICE 'Korisnik deklarant_app već postoji.';
    END IF;
END
$$;

-- Baza podataka
SELECT 'CREATE DATABASE deklarant_pro OWNER deklarant_app ENCODING ''UTF8'' LC_COLLATE ''en_US.UTF-8'' LC_CTYPE ''en_US.UTF-8'' TEMPLATE template0'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'deklarant_pro')\gexec

-- Permisije
GRANT ALL PRIVILEGES ON DATABASE deklarant_pro TO deklarant_app;

-- Shema i permisije (pokrenuti unutar deklarant_pro baze)
\c deklarant_pro

CREATE SCHEMA IF NOT EXISTS catalogs AUTHORIZATION deklarant_app;
GRANT ALL ON SCHEMA catalogs TO deklarant_app;
GRANT ALL ON ALL TABLES IN SCHEMA catalogs TO deklarant_app;
GRANT ALL ON ALL SEQUENCES IN SCHEMA catalogs TO deklarant_app;

-- Automatske permisije za buduće tabele
ALTER DEFAULT PRIVILEGES IN SCHEMA catalogs
    GRANT ALL ON TABLES TO deklarant_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA catalogs
    GRANT ALL ON SEQUENCES TO deklarant_app;

\echo '============================================'
\echo 'Baza i korisnik su postavljeni.'
\echo 'VAŽNO: Promijeni lozinku deklarant_app!'
\echo '  ALTER ROLE deklarant_app PASSWORD '\''nova_lozinka'\'';'
\echo '============================================'
