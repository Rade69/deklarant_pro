# Plan stvarne Faktura migracije — izvještaj

## Datum

2026-07-29

## Agent

Codex

## Scope

Analiza trenutnog Faktura scaffolding refaktora, Claudeovog tarifnog dedup
ledger commita `9409005` i izrada novog plana aktivne View → Controller →
Service migracije sa zasebnom cleanup fazom.

## Status izvora

- `AGENTS.md`: aktivan i kanonski.
- `docs/CONTEXT.md`: aktivan.
- `windows` commit `9409005`: autoritativni početni kod.
- `project_rooms/2026-07-27_faktura-3layer-refaktor-detaljni-plan.md`:
  koristan, ali zastario jer Faze 1–2 postoje samo kao pasivni scaffold i ne
  uključuje završeni dedup ledger.
- `agent_reports/2026-07-29_faktura-refaktor-merge-i-paritet.md`: aktivan;
  potvrđuje pasivno stanje nakon spajanja.

## GitNexus impact

`_on_import_finished()` je `MEDIUM` sa 14 direktnih testnih zavisnosti.
`_on_create_naimenovanja()` formalno je `LOW`, ali rezultat ne obuhvata Qt
wiring i dinamičke Agent `hasattr()` pozive. Ručni impact je HIGH za import,
naimenovanja, mase, validaciju, auto-fill, multi-draft i Punu automatizaciju.

## Šta je urađeno

- Pregledan je Claude commit `9409005`.
- Evidentirane su `draft_uid`, ledger, Faktura učenje, Naimenovanja učenje,
  XML završna sinhronizacija i migracija 013.
- Potvrđeno je da result modeli nemaju produkcione pozivaoce.
- Potvrđeno je da `FakturaService.sync_table_to_draft()` ima prazan `pass`.
- Mapirani su direktni Agent pozivi privatnih Faktura metoda.
- Napravljen je novi plan aktivne migracije i preciznog brisanja.
- Migracija i cleanup razdvojeni su na dvije grane i dva korisnička checkpointa.

## Zašto je urađeno

Prethodni rad je povećao infrastrukturu, ali nije zamijenio aktivni View tok.
Novi plan zato ne mjeri napredak postojanjem klasa i signala, nego stvarnim
produkcijskim emiterom, jednim izvršnim putem, uklonjenim starim wiringom i
naknadno obrisanim zamijenjenim kodom.

## Kako je urađeno

Korišćeni su Git historija, GitNexus impact, ručna pretraga Qt i dinamičkih
pozivalaca, čitanje Controller/Tab/Service scaffolding koda, prethodni plan,
Claude report i ciljani test baseline.

## Šta nije dirano

- Nije mijenjan aplikacioni kod.
- Nije kreirana implementaciona grana.
- Nije primijenjena DB migracija 013.
- Nije brisan postojeći scaffold.
- Nije mijenjan `dist_client` produkcioni model.
- Nisu dirane postojeće korisničke izmjene.

## Verifikacija

Ciljani baseline:

```text
64 passed, 2 failed
```

Dva pada su ledger integracioni testovi jer
`catalogs.tariff_learning_ledger` još ne postoji. Novi plan zahtijeva primjenu
migracije 013 i `9/9` ledger testova prije početka aktivnog refaktora.

## Pronađeni problemi

- Faktura signali su pasivni.
- Agent Puna automatizacija direktno poziva privatne View metode.
- Postojeći result modeli se ne koriste.
- Dio `FakturaService` scaffolding API-ja se ne koristi.
- Jedna scaffold metoda ima prazno tijelo.
- GitNexus podcjenjuje Qt/dinamičke pozivaoce.

## Konflikti / kontradiktorni izvori

Nazivi ranijih commitova sugerišu završene faze, dok produkcioni wiring
potvrđuje pasivnu infrastrukturu. Kod i stvarni pozivaoci tretirani su kao
autoritativni. Claudeov ledger je noviji od prethodnog plana i obavezno je
ugrađen u novi plan.

## Commitovi

Ovaj zadatak dodaje samo plan, zajedničku memoriju i izvještaj. Hash
dokumentacionog commita nalazi se u Git historiji uz poruku zadatka.

## Rizici / ograničenja

- DB migracija 013 zahtijeva admin/owner nalog.
- Import i Puna automatizacija imaju HIGH ručni blast radius.
- Statička pretraga nije dovoljna za Qt i dinamičke pozive.
- Stari kod se ne smije brisati prije korisničkog E2E checkpointa.
- `dist_client` ostaje produkciona kopija i mora zadržati paritet.

## Potreban follow-up

1. Primijeniti migraciju 013.
2. Potvrditi `9/9` ledger testova.
3. Kreirati čisti migracioni worktree.
4. Realizovati samo Fazu 0.
5. Predati Fazu 0 na pregled prije prvog aktivnog prespajanja.

## Potrebna korisnička potvrda

Korisnik treba odobriti početak realizacije poslije DB kapije. Kasnije su
obavezne dvije ručne potvrde: poslije aktivne migracije i poslije cleanup
brisanja, prije mergea u `windows`.
