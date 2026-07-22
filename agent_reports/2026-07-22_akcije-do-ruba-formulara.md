## Datum

2026-07-22

## Agent

Codex

## Scope

Pouzdano pozicioniranje akcija naslovne trake do desnog ruba formulara polja 31–46.

## GitNexus impact

LOW. Ciljana metoda ima jednog direktnog pozivaoca i nema pogođenih poslovnih procesa.

## Šta je urađeno

Dugmad su izdvojena iz rastegljivog layouta u vlastiti kontejner. Kontejner ostaje u tamnoj traci, a njegova desna ivica se direktno postavlja na desnu ivicu `main_grid_frame`.

## Zašto je urađeno

Promjena desne layout margine davala je ispravan rezultat u offscreen mjerenju, ali je stvarni runtime zadržavao akcije uz desni rub cijele kartice.

## Kako je urađeno

`heading_actions` je direktno dijete `section_heading`; pri prikazu i resize događaju dobija koordinatu `grid_right - actions_width`. Dugmad nisu umetnuta u glavni rastegljivi layout.

## Šta nije dirano

Nisu mijenjani izgled, visina, signali, funkcionalnost dugmadi ni formular.

## Verifikacija

Offscreen mjerenje na 1818 px potvrdilo je `grid_right=1311` i `actions_right=1311`, razlika 0 px. Prošlo je 9 ciljnih testova, `py_compile` i `git diff --check`.

## Pronađeni problemi

GitNexus `detect_changes` prikazuje nepovezane izmjene drugog radnog stabla; staged diff je potvrdio da commit sadrži samo dvije ciljane kopije prikaza.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `721e324` | `fix(naimenovanja): postavi akcije uz rub formulara` |

## Rizici / ograničenja

Korisnik mora pokrenuti aplikaciju iz izdvojenog worktree korijena, jer glavni `dist_client` ne sadrži ove commitove.

## Potreban follow-up

Vizuelna potvrda u stvarnoj aplikaciji prije nastavka redizajna.

## Potrebna korisnička potvrda

Provjeriti da grupa dugmadi završava tačno iznad desne crne linije formulara.
