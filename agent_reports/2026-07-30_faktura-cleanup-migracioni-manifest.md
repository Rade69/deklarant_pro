# Faktura cleanup/migracioni manifest

## Datum

2026-07-30

## Agent

Codex

## Scope

- `project_rooms/2026-07-30_faktura-cleanup-migracioni-manifest.md`
- `docs/context/history.md`

## Status izvora

- `docs/CONTEXT.md` — aktivan evergreen kontekst, pročitan prije rada.
- `docs/context/history.md` — aktivan dated log, korišćen ciljano.
- `gui/tabs/faktura_tab.py`, `gui/tabs/faktura_view.py`, `gui/tabs/agent/services/import_pipeline_service.py` — korišćeni kao izvor stvarnog stanja javnih ulaza i legacy handlera.

## GitNexus impact

Nije mijenjan produkcioni simbol. Ovo je dokumentacioni/planerski artefakt. GitNexus nije potreban za blast radius koda, ali je korišćen refactoring workflow jer manifest priprema buduće refaktor i cleanup faze.

## Šta je urađeno

Napravljen je cleanup/migracioni manifest za Faktura legacy handlere:

- `Provjeri`
- `Auto-popuni`
- `Izračunaj mase`
- `Kreiraj Naimenovanja`

Manifest za svaki proces navodi:

- trenutne javne ulaze;
- legacy handler;
- šta handler još radi;
- šta treba migrirati u Service/Controller;
- testove prije brisanja;
- uslove kada je brisanje dozvoljeno.

## Zašto je urađeno

Nakon Faza 10-12 i stabilizacije, ručni toolbar je signalno uređen, ali poslovna logika za tri procesa još živi u legacy View handlerima. Direktno brisanje bi bilo rizično, posebno za `Kreiraj Naimenovanja`. Manifest postavlja sigurnu mapu rada prije bilo kakvog cleanup-a.

## Kako je urađeno

Korišćen je `rg` inventar javnih adaptera, signal handlera, Agent pipeline-a i legacy `_on_*` metoda. Manifest je zapisan u `project_rooms/` jer je radni plan za buduće faze, ne trajna krajnja dokumentacija.

## Šta nije dirano

- Nije mijenjan produkcioni kod.
- Nisu mijenjani testovi.
- Nisu brisani fallback-i.
- Nije mijenjan Agent pipeline.
- Nisu dirane nepovezane lokalne izmjene.

## Verifikacija

- Dokument je kreiran i ručno strukturisan prema stvarnom stanju koda.
- Nema produkcionog koda za testiranje u ovoj fazi.

## Pronađeni problemi

Manifest potvrđuje da `Kreiraj Naimenovanja` ostaje najveći rizik za dublju migraciju jer legacy View handler pokriva split draftove, preflight, PE/header sync, reload tabova, ASYCUDA 99 limit i `draft_uid` učenje.

## Konflikti / kontradiktorni izvori

Nema konflikta. Važeći izvor za trenutni runtime tok je kod poslije stabilizacione faze.

Potrebna korisnička potvrda: NE.

## Commitovi

| Hash | Poruka |
| --- | --- |
| pending | `docs(faktura): dodaj cleanup migracioni manifest` |

## Rizici / ograničenja

Manifest nije implementacija. Buduće faze moraju i dalje raditi sa GitNexus impact provjerom, ciljanim testovima i bez automatskog brisanja legacy metoda.

## Potreban follow-up

Sljedeći preporučeni korak: Cleanup Faza A iz manifesta — zaključavanje trenutnog stanja dodatnim characterization testovima, bez produkcionih izmjena.

## Potrebna korisnička potvrda

Nema obavezne potvrde za manifest. Prije stvarnog brisanja legacy handlera biće potrebna korisnička E2E potvrda na realnim fakturama.
