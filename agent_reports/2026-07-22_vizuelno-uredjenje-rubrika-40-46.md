## Datum

2026-07-22

## Agent

Codex

## Scope

QSS prikaz grupa rubrika 40, 41–43, 44 i 45–46 na tabu Naimenovanja.

## Status izvora

Aktivni `.ui` raspored i inline cyan stilovi master polja tretirani su kao važeći i zaštićeni od izmjene.

## GitNexus impact

QSS-only izmjena, ručno procijenjeni rizik LOW. Nema mapiranih izvršnih tokova.

## Šta je urađeno

- Rubrike 40 i 44 dobile su dokumentnu plavo-sivu zonu.
- Rubrike 41–43 dobile su istu zeleno-sivu hijerarhiju kao blok 32–39.
- Rubrike 45–46 dobile su neutralnu završnu zonu.
- Ujednačeni su obrubi, hover, fokus i read-only stanje polja.
- Zadržani su cyan master indikatori Rubrika 40 i 44.

## Zašto je urađeno

Donji dio formulara je bio vizuelno ravan i teže se razlikovala namjena dokumentnih, vrijednosnih i završnih rubrika.

## Kako je urađeno

Stilovi su ograničeni na četiri postojeća `QGroupBox` objekta. Nisu mijenjani `.ui` fajlovi ni Python metode.

## Šta nije dirano

Nisu mijenjani fontovi, geometrija, separator linije, master inline stilovi, tab redoslijed, signali, podaci ili poslovna logika.

## Verifikacija

- Sve četiri grupe imaju identičnu geometriju prije i poslije stila: 40 `(560,180,440,60)`, 41–43 `(560,240,440,140)`, 44 `(0,380,760,170)`, 45–46 `(760,380,240,170)`.
- Fontovi labela i polja ostali su 14 px.
- Read-only Rubrika 44 koristi `#F2F5F3`, dok obična polja ostaju bijela.
- Ciljani pytest skup: 9 testova prošlo.
- `git diff --check`: bez grešaka.

## Pronađeni problemi

Master polja koriste inline QSS i namjerno imaju veći prioritet od novog grupnog stila.

## Konflikti / kontradiktorni izvori

Nema. Inline master indikatori su sačuvani kao funkcionalno važan vizuelni signal.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `af1ba4c` | `style(naimenovanja): uredi blok rubrika 40 do 46` |

## Rizici / ograničenja

Promjena je vizuelna i zavisi od Windows DPI renderovanja, ali geometrija i funkcionalni testovi su potvrđeni.

## Potreban follow-up

Nakon korisničke potvrde može se urediti donji statusni panel ili preći na sljedeći tab.

## Potrebna korisnička potvrda

Vizuelno provjeriti razliku između dokumentnih grupa 40/44 i vrijednosnih grupa 41–43/45–46.
