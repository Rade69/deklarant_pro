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
5. Migracija `database/migrations/013_tariff_learning_ledger.sql` napisana, NIJE primijenjena (vidi Blokada).
6. Root+dist_client paritet za svih 5 dotaknutih fajlova.

## Blokada
`deklarant_app` runtime nalog nema DDL privilegiju na `catalogs` shemi (namjerno, sigurnosni hardening). Migracija čeka nekog sa admin/owner pravima na `dmserver`. Do tada `learn_with_dedup` fail-safe vraća `False` bez pada — postojeće (nezaštićeno) ponašanje ostaje nepromijenjeno.

## Sporedan nalaz
Kopiranje punog `services/tariff/tariff_mapping_service.py` u `dist_client` (radi nove metode) je usput popravilo pre-postojeći bug iz §92 (dist_client kopija bila 1-linijski pokvaren shim) — potvrđeno, standalone import test sad prolazi.

## Verifikacija
Puna svita: 1512 passed. 5 failed: 3 pre-postojeća nepovezana + 2 nova `@pytest.mark.integration` testa koja čekaju migraciju (očekivano, ne bug). `tests/unit/test_tariff_learning_ledger.py`: 7/9 prolazi bez baze.

## Commitovi
| Hash | Poruka |
| --- | --- |
| (sledeći commit) | feat(tarifa): implementiraj dedup ledger za usage_count |

## Potreban follow-up
Primijeniti `database/migrations/013_tariff_learning_ledger.sql` na PostgreSQL (admin pristup potreban), zatim pokrenuti 2 integration testa da se potvrdi ledger radi end-to-end.

## Potrebna korisnička potvrda
Ko će primijeniti migraciju i kada.
