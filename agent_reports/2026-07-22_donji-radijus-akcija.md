## Datum

2026-07-22

## Agent

Codex

## Scope

Iscrtavanje donje ivice i border radijusa dugmadi u naslovnoj traci Naimenovanja.

## GitNexus impact

LOW. Izmjena je ograničena na scoped QSS pravilo i ne utiče na poslovne procese.

## Šta je urađeno

Dodata su lokalna pravila `min-height: 16px`, `padding: 3px 12px` i `border-radius: 4px` samo za dugmad unutar `sectionHeading`.

## Zašto je urađeno

Globalni QSS je nametao minimalnu sadržajnu visinu od 28 px i padding od 10 px, pa se dugme od približno 40 px iscrtavalo unutar widgeta visokog 26 px i donji dio je bio odsječen.

## Kako je urađeno

Specifičniji selektor `QWidget#sectionHeading QPushButton` nadjačava samo konfliktne dimenzije, dok boje po ID selektorima ostaju iste.

## Šta nije dirano

Nisu mijenjani položaj, visina widgeta, signali, funkcionalnost ni formular.

## Verifikacija

Sa učitanim globalnim i lokalnim QSS pravilima dugme ima `sizeHint` 22 px unutar visine 26 px, uz po 6 px prostora iznad i ispod. Prošlo je 9 ciljnih testova i `git diff --check`.

## Pronađeni problemi

Uzrok nije bila visina same trake nego globalni `min-height` zajedno sa paddingom.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `317f8ff` | `fix(naimenovanja): prikaži donji radijus akcija` |

## Rizici / ograničenja

Potrebna je vizuelna potvrda sa kompletnim produkcionim redoslijedom učitavanja stilova.

## Potreban follow-up

Nakon potvrde zaključati naslovnu traku i nastaviti dalje.

## Potrebna korisnička potvrda

Provjeriti da su donja ivica i oba donja zaobljena ugla sada potpuno vidljivi.
