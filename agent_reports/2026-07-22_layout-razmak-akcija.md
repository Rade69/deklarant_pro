## Datum

2026-07-22

## Agent

Codex

## Scope

Konačno pomjeranje dugmadi „Sačuvaj nacrt“ i „Poništi“ postojećim Qt layoutom.

## GitNexus impact

LOW. Izmjena je ograničena na konstrukciju naslovne trake; nema pogođenih poslovnih procesa.

## Šta je urađeno

Fiksni razmak ispred grupe dugmadi smanjen je sa 1017 px na 863 px, čime je grupa pomjerena 154 px ulijevo do desnog ruba formulara.

## Zašto je urađeno

Qt layout nakon svakog `move()` vraća dugmad na layout poziciju. Prethodna provjera sa ručnim pozivom metode zato je davala lažno pozitivan rezultat.

## Kako je urađeno

Promijenjen je samo `addSpacing` u originalnom layoutu, u izvornoj i `dist_client` kopiji. Struktura, stil, visina i signali nisu mijenjani.

## Šta nije dirano

Nisu mijenjani formular, QSS, roditeljski widget, funkcionalnost dugmadi ni ostali segmenti kartice.

## Verifikacija

Offscreen provjera bez ručnog poziva metode na širini 1441 px potvrdila je `grid_right=1311` i `button_right=1311`. Prošlo je 9 ciljnih testova, `py_compile` i `git diff --check`.

## Pronađeni problemi

Direktno pomjeranje layout-managed widgeta nije trajno; layout ga poništava nakon event ciklusa. Stabilna korekcija mora biti dio samog layouta.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `e3241b1` | `fix(naimenovanja): pomjeri akcije layout razmakom` |

## Rizici / ograničenja

Raspored i dalje koristi originalni fiksni razmak, sada prilagođen korisnikovoj ciljnoj širini.

## Potreban follow-up

Nakon korisničke potvrde zaključati ovaj segment i nastaviti dalje.

## Potrebna korisnička potvrda

Provjeriti da se grupa stvarno pomjerila ulijevo i završava iznad desne crne linije formulara.
