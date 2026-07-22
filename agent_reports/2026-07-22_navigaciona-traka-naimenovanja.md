## Datum

2026-07-22

## Agent

Codex

## Scope

Navigaciona traka kartice Naimenovanja u izvornom i `dist_client` prikazu.

## GitNexus impact

LOW. Metodu `_add_navigation_controls` direktno poziva samo konstruktor `NaimenovanjaView`; nisu pronađeni pogođeni poslovni procesi.

## Šta je urađeno

Traka je povećana sa 38 na 46 px, kontrole su ujednačene na 32 px, a razmaci i unutrašnje margine su blago povećani. Pozadina, granice, tipografija dugmadi i fokus selektora dobili su jači kontrast.

## Zašto je urađeno

Prethodna traka je bila zbijena i slabo odvojena od formulara. Izmjena poboljšava hijerarhiju i čitljivost bez promjene rasporeda funkcija.

## Kako je urađeno

Dimenzije su promijenjene u `NaimenovanjaView._add_navigation_controls`, a izgled u `naimenovanja_components.qss`. Izvorna i runtime kopija su ažurirane zajedno.

## Šta nije dirano

Nisu mijenjani signali, funkcionalnost dugmadi, redoslijed kontrola, formular naimenovanja, sekcija naslova ni poslovna logika.

## Verifikacija

Prošlo je 9 ciljnih unit testova i `py_compile` za obje kopije `naimenovanja_view.py`. Git diff je provjeren prije commita.

## Pronađeni problemi

GitNexus `detect_changes` je prijavio zastarjele/nepovezane promjene iz glavnog radnog stabla. Lokalni git diff izdvojenog stabla potvrđuje da commit sadrži samo četiri ciljna fajla.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `ece6110` | `style(naimenovanja): istakni navigacionu traku` |

## Rizici / ograničenja

Potrebna je ručna vizuelna provjera na korisnikovoj rezoluciji i DPI postavci; širina i redoslijed kontrola nisu mijenjani.

## Potreban follow-up

Nakon korisničke potvrde može se nastaviti na sljedeći, odvojeni segment kartice Naimenovanja.

## Potrebna korisnička potvrda

Provjeriti da su sva dugmad vidljiva i da traka ne zauzima previše vertikalnog prostora.
