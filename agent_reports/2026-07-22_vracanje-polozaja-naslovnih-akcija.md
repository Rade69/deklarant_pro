## Datum

2026-07-22

## Agent

Codex

## Scope

Položaj i širina dugmadi „Sačuvaj nacrt“ i „Poništi“ nakon uvođenja palete.

## GitNexus impact

LOW. Izmjena je ograničena na scoped QSS dimenzije i nema pogođenih poslovnih procesa.

## Šta je urađeno

Vraćene su prethodne efektivne širine: 168 px za „Sačuvaj nacrt“ i 115 px za „Poništi“.

## Zašto je urađeno

Nova scoped paleta smanjila je `sizeHint` dugmadi na 152/107 px, pa je grupa uz isti layout razmak vizuelno otišla ulijevo.

## Kako je urađeno

Dodate su odgovarajuće minimalne sadržajne širine unutar postojećih `sectionHeading` selektora. Boje i layout razmak nisu mijenjani.

## Šta nije dirano

Nisu mijenjani Python kod, položaj formulara, visina, signali ni funkcionalnost.

## Verifikacija

Render poređenje s prethodnim commitom potvrđuje iste geometrije: Save `(1145, 168)`, Cancel `(1323, 115)`. Prošlo je 9 ciljnih testova i `git diff --check`.

## Pronađeni problemi

Promjena paddinga/bordera u QSS može posredno promijeniti ukupnu širinu layout-managed dugmeta čak i kada se horizontalna koordinata u Pythonu ne mijenja.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `7e975ff` | `fix(naimenovanja): vrati širine naslovnih akcija` |

## Rizici / ograničenja

Minimalne širine su namjerno lokalne za ova dva dugmeta i ne utiču na ostale tabove.

## Potreban follow-up

Nakon vizuelne potvrde nastaviti dalje bez izmjene geometrije naslovnih akcija.

## Potrebna korisnička potvrda

Provjeriti da su dugmad na istom mjestu kao prije promjene palete.
