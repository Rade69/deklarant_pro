## Datum

2026-07-29

## Agent

Claude Code (Sonnet 5)

## Scope

Implementacija arhiviranog plana `project_rooms/2026-07-28_tarifno-ucenje-dedup-po-deklaraciji.md`.

## GitNexus impact

`save_mapping` upstream: HIGH, 8 direktnih pozivalaca (ponovo provjereno protiv koda nakon faktura-3layer merge-a — identično kao prije, refaktor nije pomjerio pozive). Izmjena je aditivna (nova `learn_with_dedup` metoda), postojeći `save_mapping` netaknut.

## Šta je urađeno

1. `DeclarationDraft.draft_uid` — nov UUID field, generisan po draftu, preživljava nacrt save/load (generički serializer, bez dodatnog koda).
2. `TariffMappingService.learn_with_dedup()` — piše u `catalogs.tariff_learning_ledger`, sprječava dupli `usage_count`; ispravka tarife skida bod sa stare, dodaje novoj (korisnikova potvrđena odluka).
3. Ozičeno na "dva ključna mjesta" koja je korisnik naveo: `_auto_learn_edits` (Faktura ispravka) i `learn_from_draft` (poziva se iz `_on_create_naimenovanja`, "Kreiraj naimenovanja").
4. `_izvezi_xml` — završno idempotentno usklađivanje (sigurnosna mreža pri XML izvozu, korisnikov predlog).
5. Migracija `database/migrations/013_tariff_learning_ledger.sql` napisana i primijenjena (vidi Blokada).
6. Root+dist_client paritet za svih 5 dotaknutih fajlova.

## Blokada (RIJEŠENO isti dan)

`deklarant_app` runtime nalog nema DDL privilegiju na `catalogs` shemi (namjerno, sigurnosni hardening). Korisnik je imao SSH pristup `dmserver`-u (Ubuntu laptop, nalog `dmpromet`) iz ranije memorije — primijenio je migraciju preko `sudo -u postgres psql -d deklarant_pro`. Dodatno je trebao eksplicitan `GRANT SELECT, INSERT, UPDATE, DELETE ... TO deklarant_app` jer `CREATE TABLE` kao `postgres` ne prenosi automatski prava na runtime nalog — dodano u migraciju 013. Migracija je sada primijenjena i potvrđena.

## Sporedan nalaz

Kopiranje punog `services/tariff/tariff_mapping_service.py` u `dist_client` (radi nove metode) je usput popravilo pre-postojeći bug iz §92 (dist_client kopija bila 1-linijski pokvaren shim) — potvrđeno, standalone import test sad prolazi.

## Verifikacija

Prije migracije: 1512 passed, 5 failed (3 pre-postojeća nepovezana + 2 integration testa koja čekaju migraciju). Poslije migracije + GRANT-a + fixa test izolacije (vidi Pronađeni problemi): `tests/unit/test_tariff_learning_ledger.py` 9/9 prolazi, provjereno dva uzastopna pokretanja (idempotentno). Puna svita: 1514 passed, isti 3 pre-postojeća nepovezana pada + 1 pre-postojeća greška, nula novih regresija.

## Pronađeni problemi

Prvo pokretanje integration testova poslije GRANT-a je pokazalo test-izolacijski bug: testovi koriste fiksne `draft_uid`/`naziv_robe` vrijednosti bez čišćenja, pa je izolovani run ostavio red u `tariff_learning_ledger` koji je drugi run (u punoj svici) lažno protumačio kao "već naučeno". Popravljeno dodavanjem `clean_ledger_rows` fixture-a (stvaran `DELETE` prije/poslije testa, ne mock — u skladu sa AGENTS.md zabranom mockovanja DB-a).

## Commitovi

| Hash | Poruka |
| --- | --- |
| `9409005` | `feat(tarifa): implementiraj dedup ledger za usage_count po deklaraciji` |
| (sledeći commit) | `fix(tarifa): GRANT za ledger tabelu + test izolacija dedup testova` |

## Potreban follow-up

Nema — dedup ledger je potpuno operativan. Sljedeći korak je Codexov plan aktivne Faktura 3-layer migracije (`project_rooms/2026-07-29_faktura-stvarna-3layer-migracija-i-ciscenje-plan.md`), Faza 0, koja ovaj ledger tretira kao zaštićenu invarijantu.

## Potrebna korisnička potvrda

Nema — migracija primijenjena i potvrđena od strane korisnika uživo.
