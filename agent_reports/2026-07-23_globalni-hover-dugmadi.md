## Datum

2026-07-23

## Agent

OpenAI Codex

## Scope

- `styles/unified_color_system.qss`
- `dist_client/styles/unified_color_system.qss`
- `docs/CONTEXT.md`

## GitNexus impact

Promjena je QSS-only i ne mijenja indeksirane simbole ili izvršne procese.
Staged provjera prijavila je rizik `none`.

## Šta je urađeno

Pojačan je hover za sva standardna `QPushButton` i `QToolButton` dugmad.
Aktivna dugmad dobijaju zlatni akcentni obrub, a neutralna dugmad i izraženiju
promjenu pozadine. Obuhvaćene su semantičke klase, `btnType` atributi i
standardni ID selektori aplikacije.

## Zašto je urađeno

Prethodna promjena nijanse bila je preslaba da korisnik brzo prepozna dugme
ispod pokazivača miša.

## Kako je urađeno

Normalno stanje koristi transparentan obrub od dva piksela, dok hover mijenja
samo boju obruba. Time je spriječeno pomjeranje sadržaja i narušavanje layouta.
Pravila su dodata u centralni QSS sloj najvišeg prioriteta i runtime kopiju.

## Šta nije dirano

- Nisu mijenjane dimenzije dugmadi.
- Nisu mijenjane funkcije, signali ili klik ponašanje.
- Semantičke boje akcija ostale su iste.
- Onemogućena dugmad ne dobijaju hover akcenat.

## Verifikacija

- QSS je uspješno učitan kroz Qt bez parser greške.
- Broj otvorenih i zatvorenih QSS blokova je jednak.
- `git diff --check` i pre-commit provjera su prošli.

## Pronađeni problemi

Nema.

## Konflikti / kontradiktorni izvori

Izvorna i runtime QSS kopija imaju ranije namjerne razlike u stilu glavnih
tabova; te razlike nisu mijenjane.

## Commitovi

| Hash | Poruka |
|---|---|
| `aa305ec` | `feat(gui): pojačaj hover svih dugmadi` |

## Rizici / ograničenja

Dugme sa potpuno lokalnim inline stilom veće specifičnosti može zadržati svoju
lokalnu hover boju, ali standardna dugmad obuhvaćena centralnim klasama,
atributima i ID-evima dobijaju novi akcenat.

## Potreban follow-up

Po potrebi identifikovati rijetka nestandardna inline dugmad koja nemaju
semantičku klasu ili ID.

## Potrebna korisnička potvrda

Vizuelno provjeriti intenzitet akcentnog obruba na svijetlim i tamnim
pozadinama svih kartica.
