## Datum

2026-07-22

## Agent

Codex

## Scope

`gui/tabs/naimenovanja_view.py` i `dist_client/gui/tabs/naimenovanja_view.py`.

## GitNexus impact

Impact metode `_add_status_bar` je LOW za obje kopije: jedan direktni pozivalac (`__init__`) i nijedan pogođeni proces. Završni pregled cijelog radnog stabla prikazao je MEDIUM zbog nepovezanih izmjena u PDF exporterima i projektnim uputstvima; ti fajlovi nisu stageovani niti mijenjani u ovom zadatku.

## Šta je urađeno

Font četiri statusne metrike i indikatora kompletnosti povećan je sa 12 px na 14 px.

## Zašto je urađeno

Korisnik je nakon vizuelne provjere potvrdio da je panel uredan, ali da je tekst premalen.

## Kako je urađeno

Promijenjena je samo vrijednost `font-size` u postojećim inline stilovima metode `_add_status_bar`, u izvornoj i runtime kopiji.

## Šta nije dirano

Nisu mijenjani visina, širine, položaji, padding, tekstovi, boje, validaciona logika, Controller, Service ni generisani UI fajlovi.

## Verifikacija

- `py_compile` uspješan za oba View fajla.
- Ciljani testovi: 9/9 prošlo.
- `git diff --check` i staged provjera prošli.
- Staged diff: dva fajla, četiri zamjene `12px` u `14px`.

## Pronađeni problemi

GitNexus pregled cijelog stabla uključuje nepovezane promjene drugih zadataka; ciljani impact korišćen je kao autoritativna procjena ove izmjene.

## Konflikti / kontradiktorni izvori

Nema konflikta u ciljnom kodu. Tuđe lokalne izmjene su ostavljene netaknute.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `30050f3` | `style(naimenovanja): povećaj font statusnog panela` |

## Rizici / ograničenja

Rizik je nizak. Prikaz pri neuobičajeno visokom Windows DPI skaliranju zahtijeva ručnu vizuelnu potvrdu.

## Potreban follow-up

Nema programskog follow-upa.

## Potrebna korisnička potvrda

Provjeriti čitljivost i da tekst kompletnosti staje u indikator pri uobičajenoj veličini prozora.
