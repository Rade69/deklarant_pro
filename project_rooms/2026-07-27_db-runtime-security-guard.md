# DB runtime security guard

## Cilj

Onemogućiti da Deklarant Pro runtime koristi PostgreSQL superuser nalog ili
nešifrovanu sesiju, čak i ako je `.env` kasnije pogrešno konfigurisan.

## Pogođeno

GitNexus: CRITICAL, 522 simbola i 33 procesa. Direktno pogođeni su
`get_connection`, `get_db_connection` i `DatabaseManager.get_pool`; tranzakcije,
tarifni servisi, agent i XML tokovi zavise posredno.

## Plan

1. Dodati izolovanu `_assert_connection_security(conn)` provjeru.
2. Pozvati je jednom nakon kreiranja pool-a.
3. Kod greške zatvoriti pool i odbiti runtime.
4. Dodati testove za TLS, superuser i siguran nalog.
5. Pokrenuti DB servisne i pune testove.

## Šta NE dirati

Pool veličinu, circuit breaker, statement timeout, transakcije, poslovne SQL
upite, migracione skripte i administratorske alate.

## Konflikti

Migracije mogu zahtijevati administratorski nalog, ali ne prolaze nužno kroz
runtime pool. Runtime guard namjerno štiti aplikacijski put; administracija
ostaje odvojena. Korisnička potvrda nije potrebna jer je cilj eksplicitno
odobren, a aktivni `.env` već koristi provjereni `deklarant_app`.
