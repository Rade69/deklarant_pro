# Scenario snimanja korisničkog toka

## Datum

2026-07-26

## Agent

Codex

## Scope

- `docs/user-guide/scenario-snimanja-korisnickog-toka.md`

## GitNexus impact

Staged provjera prijavila je LOW rizik, bez promijenjenih simbola i bez pogođenih
izvršnih procesa. Izmjena dodaje samo dokumentaciju.

## Šta je urađeno

Napravljen je scenario za snimanje kompletnog korisničkog toka, sa pripremom,
redoslijedom rada, obaveznim slikama, dodatnim situacijama i pravilima privatnosti.

## Zašto je urađeno

Scenario treba da omogući dosljedno prikupljanje video i slikovnog materijala koji
će kasnije biti osnova za korisničko uputstvo aplikacije.

## Kako je urađeno

Dokument je organizovan kao kratka kontrolna lista koja prati tok od pokretanja
aplikacije i uvoza fakture do završne provjere i ASYCUDA XML izvoza.

## Šta nije dirano

Nisu mijenjani aplikacijski kod, konfiguracija, poslovna logika, postojeća
dokumentacija niti `dist_client`.

## Verifikacija

- pregledan kompletan sadržaj novog dokumenta;
- `git diff --check` nije prijavio formatne greške;
- GitNexus staged provjera: LOW rizik, 0 pogođenih procesa;
- pre-commit hook završen uspješno.

## Pronađeni problemi

Nema problema u okviru ovog zadatka.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `2b7385d` | `docs(uputstvo): dodaj scenario snimanja korisnickog toka` |

## Rizici / ograničenja

Scenario je namjerno opšti. Konačni redoslijed i izbor slika mogu se prilagoditi
nakon pregleda stvarnog snimljenog toka.

## Potreban follow-up

Nakon što korisnik pripremi snimak i slike, izdvojiti reprezentativne kadrove i
napisati korisničko uputstvo u `docs/user-guide/`.

## Potrebna korisnička potvrda

Korisnik treba potvrditi izabranu testnu fakturu i da materijal ne sadrži podatke
koji se ne smiju objaviti u dokumentaciji.
