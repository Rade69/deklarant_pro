## Datum

2026-07-22

## Agent

Codex

## Scope

Oba Faktura PDF exportera, njihove `dist_client` kopije i testovi fontova.

## GitNexus impact

LOW: svaka od četiri `_register_fonts` metode ima jednog direktnog zavisnika, vlastiti
konstruktor; nema pogođenih evidentiranih procesa.

## Šta je urađeno

Dodata je registracija Windows Arial regular, bold, italic i bold-italic TTF fontova kada
Liberation Sans nije dostupan. Oba PDF izvještaja sada podržavaju `š, ž, č, ć, đ`.

## Zašto je urađeno

Windows instalacija nema Liberation Sans na očekivanoj putanji, pa je exporter koristio
ReportLab Helvetica. Taj ugrađeni font nije pouzdan Unicode font i kvario je dijakritike.

## Kako je urađeno

Postojeći Liberation Sans prioritet je sačuvan. Prije Helvetica fallbacka exporter sada
provjerava četiri Arial datoteke u `C:/Windows/Fonts` i registruje ih kao `DPArial` porodicu.

## Šta nije dirano

Nisu mijenjani PDF layout, kolone, grupisanje, podaci, Faktura GUI ni build specifikacija.

## Verifikacija

Svaki exporter pravi stvarni PDF. `pdfplumber` iz njega uspješno izvlači tačan tekst
`ŠEĆER, ČAJ, ŽITO I ĐEVREK`. Svih 17 relevantnih PDF/Faktura testova prolazi.

## Pronađeni problemi

Postojeći Linux font test koristio je separator putanje zavisan od platforme; provjera je
normalizovana tako da isti test prolazi i na Windowsu.

## Konflikti / kontradiktorni izvori

Nema.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `e434e38` | `fix(pdf): podrži dijakritike na Windowsu` |

## Rizici / ograničenja

Arial mora biti prisutan u standardnom Windows font direktoriju. Ako nema ni Liberation
Sans ni Arial, ostaje postojeći Helvetica fallback uz upozorenje u logu.

## Potreban follow-up

Nije potreban za `dist_client`; PyInstaller `.exe` zahtijeva rebuild da preuzme izmjenu.

## Potrebna korisnička potvrda

Nakon restarta aplikacije izvesti oba PDF izvještaja i vizuelno potvrditi dijakritike.
