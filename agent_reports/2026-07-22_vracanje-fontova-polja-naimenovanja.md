## Datum

2026-07-22

## Agent

Codex

## Scope

Fontovi polja formulara na tabu Naimenovanja u izvornoj i `dist_client` QSS kopiji.

## GitNexus impact

QSS-only izmjena, ručno procijenjeni rizik LOW. GitNexus ne mapira ova stilska pravila na izvršne tokove.

## Šta je urađeno

Vraćene su tačne vrijednosti prije commita `d031e16`: izvorni QSS koristi 14 px za `QLineEdit` i `QComboBox`, te 13 px za `QTextEdit`; `dist_client` koristi 13 px za sva tri tipa.

## Zašto je urađeno

Povećanje svih polja na 15 px bilo je nepotrebno i vizuelno preveliko. Prethodne veličine su već bile čitljive.

## Kako je urađeno

Vrijednosti su preuzete direktno iz Git historije, bez procjene prema slici.

## Šta nije dirano

Nisu mijenjani boje, modalni stilovi, layout, položaj ili dimenzije dugmadi i poslovna logika.

## Verifikacija

`pytest tests/unit/test_naimenovanja_view_display_values.py tests/unit/test_pe_rub44_consistency.py -q`: 9 testova prošlo. `git diff --check`: bez grešaka.

## Pronađeni problemi

Nema novih problema. GitNexus je prikazao nepovezane izmjene drugih agenata iz glavnog stabla; nisu uključene u commit.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `509cf6f` | `fix(naimenovanja): vrati prethodne fontove polja` |

## Rizici / ograničenja

`styles` i `dist_client/styles` zadržavaju raniju razliku od jednog piksela jer je zahtjev bio vraćanje prethodnog, provjerenog izgleda.

## Potreban follow-up

Kasnije se može zasebno razmotriti samo boja polja, bez promjene tipografije.

## Potrebna korisnička potvrda

Vizuelno provjeriti Rubriku 31 nakon ponovnog pokretanja aplikacije.
