## Datum

2026-07-24

## Agent

Codex

## Scope

- `database/migrate_carinski_dokumenti.py`
- `dist_client/database/migrate_carinski_dokumenti.py`
- `docs/CONTEXT.md`
- live PostgreSQL provjera indeksa i query plana

## Status izvora

- Pi agent performansni izvještaj: aktivan kao audit polazna tačka, ali dio nalaza je već bio riješen ranijim migracijama.
- `docs/CONTEXT.md` §45: aktivan; potvrđuje da su dodatni `pg_trgm` indeksi za velike ILIKE tabele već dodani.
- Live PostgreSQL stanje: tretirano kao važeće za konačnu odluku.

## GitNexus impact

Prije izmjene je provjeren `database/migrate_carinski_dokumenti.py::migrate`.

- Rizik: LOW
- Pogođeno: 1 simbol
- Pogođeni execution flow-ovi: 0

Prije commita je pokrenut `gitnexus_detect_changes(scope="all")`.

- Rizik: LOW
- Izmijenjena 3 fajla
- Pogođeni execution flow-ovi: 0

## Šta je urađeno

- Pokrenuta je postojeća migracija za `catalogs.carinski_dokumenti`.
- Popravljen je završni `print()` u migraciji da bude Windows/cp1252-safe.
- Ista ispravka je mirrorovana u `dist_client`.
- U `docs/CONTEXT.md` je dodata projektna memorija o uzroku i verifikaciji.

## Zašto je urađeno

Pi agent je označio `carinski_dokumenti` kao preostali kandidat za FTS/indeks provjeru.
Kod je već imao `CREATE INDEX IF NOT EXISTS ix_carinski_dokumenti_fts`, ali live baza
nije imala indeks. Uzrok je bio Windows `UnicodeEncodeError` na emoji znaku u `print()`
poslije SQL-a, prije izlaska iz transakcionog `with psycopg2.connect(...)` bloka.

## Kako je urađeno

Promjena je namjerno minimalna:

- `print("✅ ...")` zamijenjen je ASCII-safe ispisom `print("OK: ...")`.
- Nije mijenjana SQL logika migracije.
- Migracija je zatim pokrenuta nad live PostgreSQL bazom.

## Šta nije dirano

- Nije mijenjan runtime servis `services/carinski_dokumenti_service.py`.
- Nisu dodavani novi ILIKE indeksi jer su veliki kandidati iz Pi izvještaja već pokriveni ranijim migracijama.
- Nije rađen paralelni import fajlova; to je veći behavior/refactor zahvat, ne mali DB performansni fix.
- Nisu mijenjani LLM pozivi ni startup učitavanje.

## Verifikacija

- `python database\migrate_carinski_dokumenti.py` prolazi i kreira/ostavlja indeks.
- Live PostgreSQL indeksi za `catalogs.carinski_dokumenti`:
  - `carinski_dokumenti_pkey`
  - `ix_carinski_dokumenti_fts`
- Normalni plan i dalje bira Seq Scan jer tabela ima samo 28 redova.
- Forsirani plan (`SET LOCAL enable_seqscan = off`) koristi `Bitmap Index Scan on ix_carinski_dokumenti_fts`.
- `python -m py_compile database\migrate_carinski_dokumenti.py dist_client\database\migrate_carinski_dokumenti.py` prolazi.
- `python -m pytest tests/ -q`:
  - 932 passed
  - 58 skipped
  - 5 xfailed
  - 1 failed, 1 error — nevezano za ovaj scope.

## Pronađeni problemi

- `tests/test_model_benchmark.py::test_model` očekuje fixture `model_name` koja nije definisana.
- `tests/test_xml_parser_fix.py::test_xml_parser` očekuje lokalni fajl `/home/radovan/Documents/Računi/1.xml`, koji ne postoji u ovom Windows okruženju.
- `catalogs.carinski_dokumenti` je trenutno mala tabela; zbog toga PostgreSQL legitimno bira Seq Scan i kada indeks postoji.

## Konflikti / kontradiktorni izvori

Pi izvještaj je sugerisao širi indeksni problem. Live DB audit je pokazao da su veliki
ILIKE kandidati već pokriveni ranijim migracijama, a da je stvarni preostali problem bio
samo neprimijenjen FTS indeks za `carinski_dokumenti`.

Potrebna korisnička potvrda: NE.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `991f6d9` | `fix(migracije): omoguci carinski dokumenti indeks` |

## Rizici / ograničenja

- Promjena je niskog rizika jer ne mijenja SQL ni runtime logiku.
- Performansni dobitak za `carinski_dokumenti` trenutno nije vidljiv u normalnom planu zbog male tabele.
- Ako tabela značajno poraste, postojeći GIN indeks je spreman i planner će ga koristiti kada postane isplativ.

## Potreban follow-up

- Odvojeno popraviti dva postojeća test problema ako se želi potpuno zelen puni test suite.
- Paralelni batch import tretirati kao zaseban refactor tek uz posebnu procjenu rizika.

## Potrebna korisnička potvrda

- Ručno provjeriti da aplikacija i dalje normalno otvara Šifrarnike / dokumente nakon spajanja grana.
