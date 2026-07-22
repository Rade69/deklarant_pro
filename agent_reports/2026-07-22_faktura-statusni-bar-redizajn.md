## Datum

2026-07-22

## Agent

Codex

## Scope

Donji statusni bar Faktura taba u izvornom i `dist_client` prikazu.

## GitNexus impact

LOW: `_create_status_bar` ima jednog direktnog pozivaoca (`_setup_ui`) i dva ukupno
pogođena simbola po kopiji, bez pogođenih evidentiranih procesa.

## Šta je urađeno

Zbirni podaci i validacioni bedž ostaju lijevo, sažetak porijekla je odvojen na desnu
stranu, a `Assembly` je prikazan kao sekundarna informacija manjeg kontrasta.

## Zašto je urađeno

Prethodni prikaz je svim informacijama davao sličan prioritet i zbijao sažetak zemalja uz
ostale metrike. Novi raspored olakšava brzo očitavanje bez povećanja statusnog bara.

## Kako je urađeno

Dodani su QSS identiteti za sekundarnu metriku i sažetak analize, a postojeći horizontalni
stretch je postavljen između lijeve grupe i sažetka porijekla. `dist_client` kopija je
usklađena sa izvornim prikazom.

## Šta nije dirano

Nisu mijenjani visina statusnog bara, podaci, validacija, tabela, toolbar ni poslovna logika.

## Verifikacija

Offscreen Qt test provjerava visinu, identitete stilova i spacer između dvije zone.
Ukupno osam relevantnih Faktura testova prolazi.

## Pronađeni problemi

`dist_client` statusni bar je zaostajao za već postojećim stilom iz izvornog prikaza;
usklađen je u istom ograničenom scope-u.

## Konflikti / kontradiktorni izvori

Nema.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `22d4f2d` | `style(faktura): razdvoji cjeline statusnog bara` |

## Rizici / ograničenja

Vrlo dugačak automatski sažetak porijekla i dalje može biti skraćen na uskom prozoru,
ali ne mijenja visinu niti potiskuje primarne metrike.

## Potreban follow-up

Sljedeći redizajn segment odabrati tek nakon korisničke vizuelne provjere.

## Potrebna korisnička potvrda

Restartovati aplikaciju i potvrditi da su lijeve metrike i desni sažetak jasno odvojeni.
