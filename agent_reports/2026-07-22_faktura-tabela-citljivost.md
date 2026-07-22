## Datum

2026-07-22

## Agent

Codex

## Scope

Vizuelni stil glavne Faktura tabele u izvornom i `dist_client` prikazu.

## GitNexus impact

LOW: `_create_table` ima jednog direktnog pozivaoca (`_setup_ui`) i dva ukupno pogođena
simbola po kopiji, bez pogođenih evidentiranih procesa.

## Šta je urađeno

Pojačan je kontrast zaglavlja, uvedeno uočljivije ali diskretno naizmjenično sjenčenje
redova i hover stanje. Tamnoplava selekcija cijelog reda je zadržana.

## Zašto je urađeno

Kod većeg broja stavki bilo je teško pratiti jedan red kroz široku tabelu. Novi kontrast
pomaže praćenju bez povećanja redova ili promjene rasporeda kolona.

## Kako je urađeno

Izmijenjene su samo boje inline QSS-a u `_create_table`, uključeno je mouse tracking
stanje i usklađena je `dist_client` kopija.

## Šta nije dirano

Nisu mijenjani širine kolona, visina redova, editovanje, selekcioni model, validacioni
podaci, delegat niti poslovna logika.

## Verifikacija

Offscreen Qt test potvrđuje alternating rows, mouse tracking, hover, selekciju i stil
zaglavlja. Svih devet relevantnih Faktura testova prolazi.

## Pronađeni problemi

`dist_client` je imao isključene alternating rows i stariji, slabiji stil tabele; sada je
usklađen sa izvornom kopijom.

## Konflikti / kontradiktorni izvori

Nema.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `061ca42` | `style(faktura): poboljšaj čitljivost tabele` |

## Rizici / ograničenja

Hover je privremeno vizuelno stanje; trajne validacione vrijednosti i boje nisu mijenjane.

## Potreban follow-up

Sljedeći segment odabrati nakon korisničke vizuelne provjere.

## Potrebna korisnička potvrda

Restartovati aplikaciju i provjeriti kontrast zaglavlja, susjednih redova i hover.
