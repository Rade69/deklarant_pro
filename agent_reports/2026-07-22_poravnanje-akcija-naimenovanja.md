## Datum

2026-07-22

## Agent

Codex

## Scope

Položaj i vertikalni prostor dugmadi „Sačuvaj nacrt“ i „Poništi“.

## GitNexus impact

LOW. Izmijenjeni prikaz ima jednog direktnog pozivaoca i ne utiče na poslovne procese.

## Šta je urađeno

Naslovna traka je povećana na 42 px. Dugmad visine 30 px sada imaju po 6 px stvarnog prostora iznad i ispod, a desna ivica akcija prati desnu ivicu bloka `group_32_39` sa približno 10 px unutrašnje margine.

## Zašto je urađeno

Na korisnikovom prikazu gornje i donje ivice dugmadi bile su stisnute, a akcije nisu djelovale poravnato sa tabelarnim blokom polja 31–46.

## Kako je urađeno

Qt layout margina se računa iz stvarne geometrije `group_32_39` nakon prikaza i pri svakom resize događaju. Nema fiksne horizontalne koordinate.

## Šta nije dirano

Nisu mijenjani stilovi drugih kontrola, signali, funkcije čuvanja i poništavanja, formular ni poslovna logika.

## Verifikacija

Prošlo je 9 ciljnih unit testova i `py_compile`. Offscreen mjerenje na prikazu 1600×900 potvrdilo je visinu trake 42 px, dugmad 30 px, po 6 px vertikalnog prostora i 12 px izmjerenog unutrašnjeg odmaka od desne ivice bloka (uključujući Qt koordinatnu ivicu).

## Pronađeni problemi

Offscreen konstrukcija bez `.env` prijavila je očekivano nedostajući `DB_PASSWORD`; to nije povezano sa izmjenom i nije spriječilo provjeru geometrije.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `a32ee65` | `fix(naimenovanja): poravnaj akcije naslovne trake` |

## Rizici / ograničenja

Konačan vizuelni utisak treba potvrditi na korisnikovoj DPI postavci.

## Potreban follow-up

Nakon potvrde nastaviti redizajn sljedećeg segmenta.

## Potrebna korisnička potvrda

Provjeriti da su sve ivice dugmadi jasno vidljive i da je desno poravnanje prirodno u odnosu na blok polja 31–46.
