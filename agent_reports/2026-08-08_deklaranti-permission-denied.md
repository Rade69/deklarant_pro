## Datum
2026-08-08

## Agent
Claude Code (Sonnet 5)

## Scope
`services/sifarnici_service.py`, `dist_client/services/sifarnici_service.py`

## Reprodukcija prije izmjene
Korisnik prijavio: čuvanje deklaranta u tabu Šifarnici baca "Podaci nisu
sačuvani... Detalj: permission denied for database deklarant_pro" (screenshot
GUI dijaloga). Reprodukovano direktno na `dmserver` bazi sa `deklarant_app`
kredencijalima (isti nalog koji koristi aplikacija):
- `SELECT`/DML na `catalogs.deklaranti` radi (potvrđeno `information_schema.role_table_grants`
  — `deklarant_app` ima INSERT/SELECT/UPDATE/DELETE/TRUNCATE/REFERENCES/TRIGGER).
- `CREATE SCHEMA IF NOT EXISTS catalogs` baca `InsufficientPrivilege:
  permission denied for database deklarant_pro` — iako schema, tabela i sve
  kolone (uključujući `postanski_broj`) već postoje.

## Šta je urađeno
`_ensure_deklaranti_schema()` (poziva se na SVAKI `load_deklaranti_data()` i
`add_deklarant()`) sad prvo provjerava postojanje kolona preko
`information_schema.columns` (SELECT, ne treba CREATE privilegiju). DDL
(`CREATE SCHEMA`/`CREATE TABLE`/`ALTER TABLE ADD COLUMN`) se pokreće SAMO
ako tabela ili `postanski_broj` kolona stvarno nedostaju — u normalnom radu
(tabela već postoji) funkcija sada ne pokreće nikakav DDL.

## Zašto je urađeno
PostgreSQL provjerava CREATE privilegiju na bazi za `CREATE SCHEMA IF NOT
EXISTS` PRIJE same "IF NOT EXISTS" provjere postojanja objekta — poznat
gotcha, ne bug u logici koda per se, nego pogrešna pretpostavka da je "IF
NOT EXISTS" bezopasno za least-privilege runtime rolu.

## Kako je urađeno
`cur.fetchall()` sa `RealDictCursor` (default za `get_db_connection()`) —
`row['column_name']`, ne `row[0]` (provjereno, RealDictRow nije tuple).

## Šta nije dirano
Same DML upiti (INSERT/SELECT/DELETE) u `add_deklarant`/`load_deklaranti_data`/
`delete_deklarant` — nepromijenjeni, problem nikad nije bio u njima.
GRANT-ovi na bazi — nisu mijenjani (nemam superuser/owner kredencijale;
rješenje je izbjeglo potrebu za njima).

## Verifikacija
End-to-end test direktno protiv `dmserver` preko `SifarniciService`:
`add_deklarant()` → `True`, `last_error=''`; `load_deklaranti_data()` pronašao
upisan zapis; `delete_deklarant()` očistio test zapis. `pytest tests/unit -k
"sifarnici or deklarant"` — 6/6 prošlo.

## Nezavisna provjera
Nije rađena posebno (druga sesija/model) — self-verified end-to-end protiv
stvarne produkcijske baze (jedini pouzdan dokaz za permission-nivo bug).

## Pronađeni problemi
Isti "self-healing schema" pattern (DDL u runtime servisnom sloju umjesto u
`database/migrate_*.py`) može postojati i na drugim tabelama — nije
sistematski pretražen cijeli `services/` folder (van scope-a ovog zadatka,
korisnik prijavio samo deklarante).

## Commitovi
| Hash | Poruka |
| --- | --- |
| `df8af5a` | `fix(sifarnici): deklaranti se ne mogu sačuvati — permission denied for database` |

## Rizici / ograničenja
Nizak rizik — promjena je čisto defanzivna (dodaje provjeru prije DDL-a, ne
mijenja postojeću DML logiku). Ako se ikad NAMJERNO promijeni šema
`catalogs.deklaranti` (npr. doda nova kolona), DDL grana ovog koda i dalje
zahtijeva CREATE privilegiju — to ostaje zadatak za pravu migraciju
(`database/migrate_deklaranti.py`), ne za ovaj runtime fallback.

## Potreban follow-up
Razmotriti grep cijelog `services/` foldera za isti pattern
(`CREATE SCHEMA IF NOT EXISTS` / `CREATE TABLE IF NOT EXISTS` van
`database/migrate_*.py`) da se preventivno otkriju slični skriveni bugovi na
drugim šifarnicima prije nego ih korisnik prijavi.

## Potrebna korisnička potvrda
Ručna provjera u GUI (Šifarnici → Deklaranti → dodaj/izmijeni) da potvrdi da
dijalog "Podaci nisu sačuvani" više ne izlazi u stvarnoj upotrebi.
