# DB Pool Fix - Connection pool exhaustion

## Svrha

Rješava problem `connection pool exhausted` koji se javlja nakon nekoliko upita
prema PostgreSQL bazi. Sve funkcije u `database/db.py` su koristile `get_connection()`
koja uzima konekciju iz pool-a ali je **nikad ne vraća** (`pool.putconn()` nije pozvan),
što dovodi do iscrpljivanja pool-a (max 10 konekcija).

## Zavisnosti i pretpostavke

- `get_db_connection()` context manager već postoji u `database/db.py` i pravilno
  vraća konekciju u pool u `finally` bloku (commit/rollback + putconn)
- Sve funkcije su zamijenile `get_connection()` → `get_db_connection()`

## Promjene

### 1. `search_izvoznike` — uklonjen `postanski_broj`

**Problem:** `catalogs.izvoznici` nema kolonu `postanski_broj` (za razliku od
`catalogs.uvoznici` koja je ima). PostgreSQL baca grešku pri svakom pozivu.

**Rješenje:** SELECT lista uklonjena na: `jib, naziv, adresa, grad, drzava`.
Dodat `NULLS LAST` u ORDER BY da izvoznici sa praznim nazivom ne budu na vrhu liste.
Dodata pretraga po JIB-u (`jib ILIKE %s`) uz postojeću pretragu po nazivu.

### 2. `search_uvoznike` — dodata pretraga po JIB-u

**Rješenje:** Dodata `OR jib ILIKE %s` u WHERE klauzulu, i `NULLS LAST` u ORDER BY.

### 3. `get_connection()` → `get_db_connection()` — 12 funkcija

**Problem:** `get_connection()` poziva `pool.getconn()` ali u svim funkcijama
se koristi `with get_connection() as conn:` koji samo zatvara konekciju na kraju
bloka (__exit__), **ne vraća je u pool**. Nakon 10 upita, pool je prazan i nijedan
novi upit ne može proći.

**Rješenje:** Sve funkcije koriste `with get_db_connection() as conn:` umjesto
`with get_connection() as conn:`. `get_db_connection()` je context manager koji
u `finally` bloku poziva `pool.putconn(conn)` i radi commit/rollback.

Pogođene funkcije (12):
- `get_tariff_description`, `find_tariff_by_prefix`, `search_tariffs`
- `search_izvoznike`, `search_uvoznike`, `search_partnere`
- `get_trader_by_code`, `get_all_izvoznici`, `get_all_uvoznici`
- `search_deklaranti`, `get_deklarant_by_code`, `find_company_by_jib`

## Zašto ovako

`get_db_connection()` je već postojao i bio dizajniran za ovo — samo ga niko nije koristio.
Umjesto da se pool povećava (što bi samo odložilo problem), ispravan pattern je da se
svaka konekcija vrati u pool nakon upotrebe.
