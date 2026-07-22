## Datum

2026-07-22

## Agent

Codex

## Scope

Ispravka horizontalnog poravnanja dugmadi u naslovnoj traci Naimenovanja.

## GitNexus impact

LOW prema prethodnoj analizi ciljane metode; ručna provjera potvrđuje da se mijenja samo izvor geometrijske reference.

## Šta je urađeno

Desna ivica akcija sada se računa prema spoljašnjem okviru formulara `main_grid_frame`, odnosno vidljivoj desnoj liniji bloka polja 31–46.

## Zašto je urađeno

Prethodna referenca `group_32_39` prolazila je kroz dodatno skaliranje unutrašnjih grupa i na stvarnom prikazu pogrešno poravnala dugmad uz desni rub cijele kartice.

## Kako je urađeno

U `_align_section_heading_actions` zamijenjena je unutrašnja grupa stabilnim spoljašnjim okvirom. Zadržano je dinamičko prilagođavanje pri promjeni širine.

## Šta nije dirano

Visina trake i dugmadi, QSS, signali, funkcionalnost i formular nisu mijenjani.

## Verifikacija

Offscreen prikaz širine 1818 px izmjerio je desnu ivicu okvira na 1311 px i dugmeta na 1299 px: dugme je 12 px unutar okvira, a 518 px udaljeno od desnog ruba kartice. Prošlo je 9 ciljnih testova i `py_compile`.

## Pronađeni problemi

Prva implementacija koristila je nestabilnu unutrašnju geometriju; korisnička slika je ispravno otkrila razliku koju ranija provjera na drugoj širini nije pokazala.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `d422c0f` | `fix(naimenovanja): veži akcije za okvir formulara` |

## Rizici / ograničenja

Konačan prikaz zavisi od DPI skaliranja, ali se sada računa iz istog Qt koordinatnog sistema kao okvir formulara.

## Potreban follow-up

Nakon korisničke vizuelne potvrde nastaviti sljedeći segment.

## Potrebna korisnička potvrda

Provjeriti da „Poništi“ završava neposredno unutar desne crne linije bloka polja 31–46.
