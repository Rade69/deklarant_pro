## Datum

2026-07-22

## Agent

Codex

## Scope

Runtime stilovi rubrike 31 u `gui/tabs/naimenovanja_view.py` i `dist_client/gui/tabs/naimenovanja_view.py`, te odgovarajuća pravila u `dist_client/styles/naimenovanja_components.qss`.

## Status izvora

Aktivni View i stylesheet tretirani su kao važeći. Ranije uređeni layout i poslovna pravila iz `docs/CONTEXT.md` ostali su autoritativni i netaknuti.

## GitNexus impact

`_setup_package_dropdown` je LOW: jedan direktni pozivalac, bez pogođenih procesa. `_populate_tariff_description` je LOW: dva direktna poziva i jedan prijavljeni tok. Zbirni `detect_changes` je MEDIUM zbog paralelnih PDF izmjena van scope-a; one nisu stageovane.

## Šta je urađeno

Ublažene su runtime zelena i plava nijansa tarifnih opisa, uz jedinstven plavi fokus. Tip pakovanja je usklađen s plavosivim obrubima rubrike 31. Kasnije duplirano QSS pravilo navigacionog selektora usklađeno je s prethodno uvedenim izgledom, pa ga više ne poništava.

## Zašto je urađeno

Runtime inline stilovi su nakon popunjavanja vraćali jarke boje i poništavali mirniji izgled rubrike 31. Duplirana QSS pravila su stvarala zavisnost izgleda od redosljeda učitavanja.

## Kako je urađeno

Promijenjeni su samo literalni stilovi postojećih widgeta i odgovarajući QSS selektori. Izvorna i runtime View kopija održane su identičnim.

## Šta nije dirano

Nisu mijenjani geometrija, fontovi, sadržaj, auto-popunjavanje, tarifni lookup, navigacija, model, Controller, Service, baza ni ASYCUDA ograničenja.

## Verifikacija

- `py_compile` uspješan za obje View kopije.
- QSS zagrade su uparene.
- Ciljani testovi: 9/9 prošlo.
- `git diff --check` i staged provjera prošli.
- Commit sadrži samo tri ciljana fajla.

## Pronađeni problemi

Kasnije QSS pravilo za `nav-combo` prepisivalo je dio ranijeg redizajna. Inline stil tipa pakovanja prepisivao je QSS i zadržavao jarkozeleni obrub.

## Konflikti / kontradiktorni izvori

Zbirni GitNexus rezultat uključuje nepovezane PDF izmjene. Ciljani impact i staged diff korišćeni su kao mjerodavni za ovaj zadatak.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `fb43757` | `style(naimenovanja): završi usklađivanje polja rubrike 31` |

## Rizici / ograničenja

Rizik je nizak i vizuelan. Završni izgled zavisi od Windows DPI skaliranja i zahtijeva korisnički pregled stvarnih podataka.

## Potreban follow-up

Planirani redizajn taba Naimenovanja je završen. Dalje korekcije raditi samo prema konkretnoj vizuelnoj povratnoj informaciji.

## Potrebna korisnička potvrda

Provjeriti tarifne opise prije i poslije automatskog popunjavanja, fokus tipa pakovanja i navigacioni selektor.
