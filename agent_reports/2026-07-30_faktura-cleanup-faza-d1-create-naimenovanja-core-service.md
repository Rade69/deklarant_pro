## Datum

2026-07-30

## Agent

Codex

## Scope

- `services/faktura/create_naimenovanja_workflow_service.py`
- `services/faktura/models.py`
- `gui/tabs/faktura_controller.py`
- `gui/tabs/faktura_view.py`
- `dist_client/...` paritet kopije istih modula
- `tests/unit/test_faktura_create_naimenovanja_workflow_service.py`
- `tests/unit/test_faktura_controller.py`
- `docs/context/history.md`

## Status izvora

Aktivni izvori: `docs/CONTEXT.md`, `project_rooms/2026-07-30_faktura-cleanup-migracioni-manifest.md`, Cleanup Faza A/B/C reporti.

## GitNexus impact

GitNexus impact/context tool nije bio dostupan u trenutku ove podfaze; korišćen je read-only `rg` pozivalaca i `gitnexus_detect_changes(scope=unstaged)` prije commita. Detect je prijavio LOW rizik i 0 affected processes. Izlaz uključuje i ranije nepovezane lokalne izmjene, koje nisu dio commita.

## Šta je urađeno

- Dodati `CreateNaimenovanjaDraftResult` i `CreateNaimenovanjaWorkflowResult`.
- Dodan `CreateNaimenovanjaWorkflowService`.
- Core petlja u `FakturaView._on_create_naimenovanja` sada koristi servis za `create_smart_group` + tarifno učenje.
- `FakturaController.create_naimenovanja` koristi isti servisni core.
- Import service memory cleanup prebačen u servisni helper.
- Root/dist_client paritet proširen na novi servis.
- Dodati testovi za `draft_uid` learning, tolerantno ponašanje kad learning pukne i strukturisanu grešku kad create pukne.

## Zašto je urađeno

Manifest označava create-naimenovanja kao najrizičniji workflow. D1 zato ne mijenja cijeli tok, nego izdvaja samo core dio koji je čistiji i lakše testabilan, uz očuvanje svih UI/workflow ivica u View-u.

## Kako je urađeno

Servis prima listu draftova, za svaki draft poziva `CreateNaimenovanjaService.create_smart_group`, čita `last_split_info`, zatim poziva `TariffFacade.learn_from_draft(..., draft_uid=...)`. Greška u učenju se loguje i vraća u result, ali ne blokira kreiranje, kao i legacy ponašanje.

## Šta nije dirano

- Nije mijenjan `CreateNaimenovanjaService.create_smart_group`.
- Nije mijenjan split/preflight UI tok.
- Nisu mijenjani PE/header sync, inspection sync, reload tabova ni `naimenovanja_created` signal.
- Nije brisan `_on_create_naimenovanja`.
- Nije uklonjen Agent fallback.
- Nisu dirane nepovezane lokalne izmjene u worktree-u.

## Verifikacija

- `python -m py_compile ...` za izmijenjene root/dist/test fajlove — OK
- Ciljano bez DB ledger testa: `71 passed`
- Šire bez DB ledger testa: `165 passed`
- Pokušaj uključivanja `test_tariff_learning_ledger.py`: 78 passed, 2 errors zbog timeouta konekcije na PostgreSQL server `192.168.100.154`, potom DB circuit breaker aktivan.

## Pronađeni problemi

PostgreSQL server `192.168.100.154` nije odgovorio tokom ledger testova, pa DB-zavisna kapija nije mogla biti potvrđena u ovoj sesiji. D1 servisni testovi mockuju `TariffFacade` i pokrivaju `draft_uid` ugovor bez mrežne zavisnosti.

## Konflikti / kontradiktorni izvori

Nema kontradikcije. Manifest zabranjuje agresivno preuzimanje kompletnog create workflow-a prije pariteta; zato je ova podfaza ograničena na core servis.

## Commitovi

| Hash | Poruka |
| --- | --- |
| d79589b | `refactor(faktura): izdvoji create naimenovanja core servis` |

## Rizici / ograničenja

Create workflow još nije potpuno migriran u Controller. UI/workflow ivice su namjerno ostale u View-u do narednih podfaza i korisničkog E2E.

## Potreban follow-up

Cleanup Faza D2: izdvojiti post-create hooks/reload/sync u jasniji workflow adapter ili event rezultat, bez promjene ponašanja.

## Potrebna korisnička potvrda

Korisnik treba ručno potvrditi `Kreiraj Naimenovanja` na realnoj fakturi, uključujući pregled Naimenovanja i Zaglavlje taba poslije kreiranja.
