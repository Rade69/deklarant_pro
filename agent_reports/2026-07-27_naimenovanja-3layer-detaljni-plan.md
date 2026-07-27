## Datum

2026-07-27

## Agent

Codex

## Scope

Nezavisna analiza postojećeg `NaimenovanjaView` monolita i izrada detaljnog
plana za bezbjedan 3-layer refaktor. Produkcijski Python kod nije mijenjan.

## Status izvora

- `AGENTS.md`: aktivan, kanonski izvor arhitektonskih pravila.
- `docs/CONTEXT.md`: aktivan, korišten za multi-draft, signal, DB, tarifna i
  `dist_client` ograničenja.
- Pi plan `project_rooms/2026-07-26_naimenovanja-3layer-refaktor-plan.md`:
  koristan polazni nacrt, ali nepotpun i trenutno necommitovan u worktreeu.
- Trenutni kod na `feature/agent-v2`: autoritativan za broj metoda, linija,
  postojeće servise i pozivaoce.
- GitNexus: korišten za impact; `detect_changes` i dalje agregira paralelne
  worktree izmjene pa je staged Git pregled korišten kao scope dokaz.

## GitNexus impact

- `NaimenovanjaView`: MEDIUM, 5 direktnih importera, 11 ukupno pogođenih.
- `_save_current_item`: MEDIUM, 11 direktnih i 25 ukupno pogođenih simbola.
- `_on_import_xml`: statički LOW, ručno podignut na MEDIUM zbog draft,
  dokument i Zaglavlje side-effecta.
- Plan zahtijeva novu impact provjeru prije svake implementacione faze.

## Šta je urađeno

- AST inventarom potvrđeno 108 metoda i 3.681 linija u View-u.
- Potvrđeno da postojeći `NaimenovanjaService` već ima 439 linija/17 metoda.
- Evidentirani svi signalni spojevi i spoljni wrapper pozivaoci.
- Identifikovane metode koje se moraju razbiti, a ne samo premjestiti.
- Definisana ciljna View–Controller–Service arhitektura.
- Definisano jedno autoritativno draft stanje bez Controller keširanja.
- Definisan signalni ugovor, DI wiring i kompatibilni wrapper API.
- Napravljen plan sa osam implementacionih faza, test-gateovima, rollback
  kriterijima, commit strategijom i realnom procjenom 29–48 sati.
- Implementacija je izričito ograničena na novu
  `refactor/naimenovanja-3layer` granu/worktree.

## Zašto je urađeno

Originalni plan je dobro prepoznao monolit, ali je predlagao direktne
View→Controller pozive, duplirano draft stanje i neke Qt/DB miješane metode kao
čist Service. Takva realizacija bi mogla uvesti tihe regresije u navigaciji,
multi-draft toku, tarifnom učenju i Rub.40/44 dokumentima.

## Kako je urađeno

- Pročitan je cijeli Pi plan.
- AST analizom izmjeren je stvarni kod.
- Pregledani su postojeći `ZaglavljeController`, `SifarniciController`,
  `BaseTabController`, `TabFactory`, wrapper i postojeći servisi.
- GitNexus impact je kombinovan sa ručnim pregledom pozivalaca i side-effecta.
- Plan je napisan kao fazni vertikalni refaktor sa zelenim checkpointom nakon
  svake faze.

## Šta nije dirano

- Nijedan Python produkcijski ili test fajl.
- Originalni Pi plan nije staged niti mijenjan.
- `windows` grana i njen prljavi worktree.
- Tuđe izmjene u `AGENTS.md`, `CLAUDE.md`, `upload_area.py`,
  `admin_service.py`, generisanim UI fajlovima i `test_ui_display_fixes.py`.
- Nije kreirana implementaciona grana; plan zahtijeva korisničku potvrdu prije
  toga.

## Verifikacija

- Novi plan: 801 linija.
- `git diff --check`: prolazi.
- Staged scope prije commita: samo novi plan.
- Provjerene ključne riječi i zabrane: grana, signali, jedan draft,
  `dist_client`, `blockSignals`, DB mock zabrana, stop/rollback.
- Produkcijski testovi nisu pokretani jer produkcijski kod nije mijenjan.

## Pronađeni problemi

- Pi inventar pokriva samo dio stvarnih 108 metoda.
- `_save_current_item` ima znatno veći blast radius od procijenjenog.
- U View-u postoje dvije definicije `_extract_short_code`.
- `TabFactory` registruje `NaimenovanjaService`, ali ga wrapper trenutno ne
  prima, pa postojeći DI nije stvarno iskorišten za ovaj tab.
- `_sync_tariff_to_source` ima rizičan 1:1 fallback preko `ordinal_no - 1`,
  koji nije dovoljan za grupisana naimenovanja.
- GitNexus `detect_changes` vidi paralelne worktree izmjene, pa nije pouzdan
  kao jedini scope dokaz.

## Konflikti / kontradiktorni izvori

Pi plan navodi 52 metode/3.888 linija, dok trenutni kod ima 108 metoda/3.681
liniju. Kod je tretiran kao važeći izvor. Korisnička potvrda nije potrebna za
ovu dokumentacionu korekciju, ali jeste prije početka implementacije.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `f561e55` | `docs(plan): detaljisi naimenovanja 3layer refaktor` |

## Rizici / ograničenja

Plan je zasnovan na stanju `feature/agent-v2` od 2026-07-27. Prije realizacije
mora se ponovo potvrditi base commit, jer drugi agenti paralelno mijenjaju
Faktura/Naimenovanja povezane tokove.

## Potreban follow-up

Nakon korisničkog odobrenja:

1. potvrditi integracioni base;
2. kreirati `refactor/naimenovanja-3layer` worktree;
3. realizovati samo Fazu 0;
4. predati baseline i karakterizacione testove na pregled prije Faze 1.

## Potrebna korisnička potvrda

Potvrditi da li se odobrava kreiranje posebne refaktor grane i početak samo
Faze 0. Nijedna produkcijska refaktor izmjena nije još napravljena.
