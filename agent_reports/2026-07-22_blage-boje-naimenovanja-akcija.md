## Datum

2026-07-22

## Agent

Codex

## Scope

Boje sedam dugmadi u gornjoj navigacionoj traci kartice Naimenovanja.

## GitNexus impact

LOW. Izmjena je isključivo lokalni QSS i ne utiče na poslovne procese.

## Šta je urađeno

Dugmad su dobila prigušene semantičke tonove: bež za prethodno, teal za sljedeće, zeleno za dodavanje, crvenkasto za brisanje, ljubičasto za tarifni prijedlog, teal za XML i plavo za inspekcije.

## Zašto je urađeno

Jednolična siva dugmad djelovala su sterilno i nisu jasno razlikovala vrste akcija.

## Kako je urađeno

Dodati su selektori visoke specifičnosti pod `QWidget#navBar`, pa ne utiču na dugmad istih ID-jeva u drugim karticama. Bijeli tekst i ikone zadržani su radi kontrasta.

## Šta nije dirano

Nisu mijenjani položaj, dimenzije, tekst, ikone, signali ni funkcionalnost dugmadi.

## Verifikacija

Offscreen pixel provjera potvrdila je svih sedam novih RGB boja. Prošlo je 9 ciljnih testova i `git diff --check`.

## Pronađeni problemi

Prva QSS zakrpa sadržala je samostalni znak `+`, zbog čega je Qt preskakao novi blok. Znak je uklonjen prije commita i render ponovo provjeren.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `93e0b1c` | `style(naimenovanja): dodaj blage boje akcijama` |

## Rizici / ograničenja

Nijanse treba potvrditi na stvarnom monitoru; tehnički kontrast s bijelim sadržajem je sačuvan.

## Potreban follow-up

Nakon potvrde nastaviti na blok Rub.32–39.

## Potrebna korisnička potvrda

Procijeniti da li su boje dovoljno blage, ali ipak jasnije od prethodne sive varijante.
