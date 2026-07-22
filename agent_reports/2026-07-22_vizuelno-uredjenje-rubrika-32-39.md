## Datum

2026-07-22

## Agent

Codex

## Scope

QSS prikaz bloka rubrika 32–39 na tabu Naimenovanja.

## GitNexus impact

QSS-only izmjena, ručno procijenjeni rizik LOW. Nema mapiranih izvršnih tokova.

## Šta je urađeno

- Blok 32–39 dobio je neutralniju zeleno-sivu podlogu i diskretan okvir.
- Naslovi rubrika imaju tamniju zelenu i jasniju težinu teksta.
- Polja imaju ujednačen obrub, hover, fokus i read-only stanje.
- Fokus koristi zelenu potvrde `#2F7D5A` iz palete Fakture.

## Zašto je urađeno

Blok s ključnim tarifnim i carinskim podacima nije imao dovoljno jasnu vizuelnu hijerarhiju u odnosu na ostatak formulara.

## Kako je urađeno

Svi selektori su ograničeni na `QGroupBox#group_32_39`; geometrija iz `.ui` fajla nije mijenjana.

## Šta nije dirano

Nisu mijenjani fontovi, dimenzije, raspored, separator linije, vrijednosti polja, signali ili poslovna logika.

## Verifikacija

Offscreen Qt provjera potvrdila je boju labela `#245F45`, bijelu osnovu polja, tekst `#26352D` i nepromijenjen font od 14 px. Ciljani pytest skup: 9 testova prošlo. `git diff --check`: bez grešaka.

## Pronađeni problemi

`QLabel` nasljeđuje `QFrame`, pa je početni opšti selektor separatora zahvatio i labele. Selektor je uklonjen prije commita.

## Konflikti / kontradiktorni izvori

Nema.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `80f0beb` | `style(naimenovanja): uredi blok rubrika 32 do 39` |

## Rizici / ograničenja

Pozadina `QGroupBox` zavisi od Qt renderovanja teme, ali su specifični label i input stilovi potvrđeni.

## Potreban follow-up

Sljedeći mogući segment je Rubrika 40 ili blok 41–46, nakon vizuelne potvrde.

## Potrebna korisnička potvrda

Provjeriti blok 32–39 na stvarnom ekranu, posebno fokus polja i kontrast read-only vrijednosti.
