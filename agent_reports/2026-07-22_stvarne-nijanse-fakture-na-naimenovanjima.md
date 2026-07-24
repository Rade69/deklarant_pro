## Datum

2026-07-22

## Agent

Codex

## Scope

Renderovane boje akcijskih dugmadi na Fakturi i Naimenovanjima.

## Status izvora

Korisničke slike i lokalni stylesheet u `FakturaView._create_controls_section()` su aktivni izvori. Niži sloj `unified_color_system.qss` je za Fakturu zastario jer ga lokalni stil nadjačava.

## GitNexus impact

QSS-only izmjena, ručno procijenjeni rizik LOW. GitNexus nije mapirao stilske fajlove na izvršne tokove.

## Šta je urađeno

- Standardne akcije, uključujući `Dodaj`, koriste stvarnu Faktura nijansu `#52697A`.
- Brisanje koristi `#A6403D`.
- AI akcije koriste `#6A55A3`.
- Čuvanje koristi zelenu potvrde `#2F7D5A`.
- Usklađena su hover i pressed stanja.
- Dizajn dokument sada navodi stvarno renderovanu paletu.

## Zašto je urađeno

Prethodna korekcija je čitala niži zajednički QSS sloj. Faktura ima specifičniji inline stylesheet, zbog čega su stvarno prikazane nijanse bile drugačije i blaže.

## Kako je urađeno

Pročitan je kompletan lokalni `controlsContainer` stil Fakture i njegove vrijednosti su prenesene u specifične selektore Naimenovanja, bez promjene Python koda.

## Šta nije dirano

Nisu mijenjani fontovi, geometrija, layout, modalni prozori, tekstovi ili poslovna logika. Inline stil Fakture nije mijenjan.

## Verifikacija

Offscreen Qt provjera potvrdila je efektivne boje svih devet dugmadi. Ciljani pytest skup: 9 testova prošlo. `git diff --check`: bez grešaka.

## Pronađeni problemi

Postoji dupliran izvor palete: `unified_color_system.qss` i lokalni stylesheet Fakture. Lokalni stylesheet ima veću specifičnost i predstavlja stvarno renderovani izgled.

## Konflikti / kontradiktorni izvori

Konflikt između zajedničkog i lokalnog QSS-a riješen je u korist lokalnog Faktura stila jer se on vidi na korisničkoj slici i stvarno se primjenjuje u Qt-u.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `8366472` | `fix(naimenovanja): primijeni stvarne nijanse fakture` |

## Rizici / ograničenja

Dupliranje palete ostaje tehnički dug. Centralizacija bi zahtijevala poseban refaktor i vizuelnu provjeru svih tabova.

## Potreban follow-up

Kasnije razmotriti jedan centralni izvor palete, ali ne u okviru segmentnog redizajna.

## Potrebna korisnička potvrda

Vizuelno uporediti oba toolbara nakon ponovnog pokretanja aplikacije.
