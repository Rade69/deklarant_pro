## Datum

2026-07-22

## Agent

Codex

## Scope

Vraćanje naslovne trake Naimenovanja i akcija „Sačuvaj nacrt“ / „Poništi“.

## GitNexus impact

LOW. Ciljana metoda ima jednog direktnog pozivaoca i nema pogođenih poslovnih procesa.

## Šta je urađeno

U potpunosti su poništene sve izmjene naslovne trake i pozicioniranja dugmadi nastale nakon commita `9805772`.

## Zašto je urađeno

Korisnik je zatražio povratak na prvobitno stanje nakon što pokušaji pomjeranja nisu dali stabilan rezultat u stvarnom runtime-u.

## Kako je urađeno

Četiri ciljna fajla vraćena su na sadržaj iz commita `9805772`: izvorna i `dist_client` kopija prikaza te oba QSS fajla.

## Šta nije dirano

Navigaciona traka Naimenovanja iznad naslovne trake, formular, Faktura tab i poslovna logika ostali su netaknuti.

## Verifikacija

`git diff 9805772 -- <četiri ciljna fajla>` vratio je prazan rezultat. Prošlo je 9 ciljnih testova, `py_compile` i `git diff --check`.

## Pronađeni problemi

Izdvojeni worktree i glavni `dist_client` imaju različite fajlove; pri vizuelnoj provjeri mora se paziti koji entrypoint je pokrenut.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `401b9b8` | `revert(naimenovanja): vrati izvorni položaj akcija` |

## Rizici / ograničenja

Vraćeni su i originalna visina i originalni QSS naslovne trake, uključujući ranije vizuelne nedostatke koje je korisnik prihvatio radi stabilnosti.

## Potreban follow-up

Nastaviti na drugi, nezavisan segment kartice bez daljeg pomjeranja ovih dugmadi.

## Potrebna korisnička potvrda

Potvrditi da su „Sačuvaj nacrt“ i „Poništi“ ponovo vidljivi na prvobitnom mjestu.
