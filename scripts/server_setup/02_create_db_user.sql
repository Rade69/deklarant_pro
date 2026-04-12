-- ============================================================
-- ASYCUDA Pro — Kreiranje baze i korisnika na serveru
-- Pokrenuti kao postgres superuser:
--   sudo -u postgres psql -f 02_create_db_user.sql
-- ============================================================

-- Korisnik za aplikaciju (samo mu treba pristup asycuda_pro bazi)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'asycuda_app') THEN
        CREATE ROLE asycuda_app WITH LOGIN PASSWORD 'PROMIJENI_OVU_LOZINKU';
        RAISE NOTICE 'Korisnik asycuda_app kreiran.';
    ELSE
        RAISE NOTICE 'Korisnik asycuda_app već postoji.';
    END IF;
END
$$;

-- Baza podataka
SELECT 'CREATE DATABASE asycuda_pro OWNER asycuda_app ENCODING ''UTF8'' LC_COLLATE ''en_US.UTF-8'' LC_CTYPE ''en_US.UTF-8'' TEMPLATE template0'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'asycuda_pro')\gexec

-- Permisije
GRANT ALL PRIVILEGES ON DATABASE asycuda_pro TO asycuda_app;

-- Shema i permisije (pokrenuti unutar asycuda_pro baze)
\c asycuda_pro

CREATE SCHEMA IF NOT EXISTS catalogs AUTHORIZATION asycuda_app;
GRANT ALL ON SCHEMA catalogs TO asycuda_app;
GRANT ALL ON ALL TABLES IN SCHEMA catalogs TO asycuda_app;
GRANT ALL ON ALL SEQUENCES IN SCHEMA catalogs TO asycuda_app;

-- Automatske permisije za buduće tabele
ALTER DEFAULT PRIVILEGES IN SCHEMA catalogs
    GRANT ALL ON TABLES TO asycuda_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA catalogs
    GRANT ALL ON SEQUENCES TO asycuda_app;

\echo '============================================'
\echo 'Baza i korisnik su postavljeni.'
\echo 'VAŽNO: Promijeni lozinku asycuda_app!'
\echo '  ALTER ROLE asycuda_app PASSWORD '\''nova_lozinka'\'';'
\echo '============================================'
