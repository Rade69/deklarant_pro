## Datum

2026-07-22

## Agent

Codex

## Scope

Minimalno horizontalno pomjeranje postojećih dugmadi „Sačuvaj nacrt“ i „Poništi“.

## GitNexus impact

LOW. Metodu poziva samo resize događaj; poslovni procesi nisu pogođeni.

## Šta je urađeno

Desna ivica dugmeta „Poništi“ poravnata je s desnom ivicom `main_grid_frame`, a „Sačuvaj nacrt“ ostaje 12 px lijevo od njega.

## Zašto je urađeno

Korisnička slika je jasno pokazala da grupa treba samo biti pomjerena ulijevo do desne crne linije formulara, bez izmjene njene strukture.

## Kako je urađeno

Zadržani su originalni layout, roditeljski widget, visina i stil. Izmijenjen je samo završni izračun `save_x` i `cancel_x` u postojećoj `_position_section_heading_buttons` metodi.

## Šta nije dirano

Nisu mijenjani `_add_section_heading`, QSS, dimenzije, signali, funkcionalnost ni formular.

## Verifikacija

Offscreen mjerenje na širini 1441 px potvrdilo je `grid_right=1311`, `button_right=1311`, oba dugmeta vidljiva. Prošlo je 9 ciljnih testova, `py_compile` i `git diff --check`.

## Pronađeni problemi

Prethodni pokušaji mijenjali su layout/kontejner i time unosili runtime razlike; ovaj pristup namjerno zadržava originalnu strukturu.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `65902fa` | `fix(naimenovanja): poravnaj dugmad s rubom formulara` |

## Rizici / ograničenja

Vizuelna potvrda je i dalje potrebna u stvarnoj aplikaciji, ali geometrija je provjerena na istoj širini kao priložena slika.

## Potreban follow-up

Nakon potvrde ovaj segment zaključati i nastaviti dalje.

## Potrebna korisnička potvrda

Provjeriti da desna ivica „Poništi“ završava tačno iznad desne crne linije polja 31–46.
