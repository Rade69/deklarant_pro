# Prenosivi XML nacrti deklaracije

## Datum

2026-06-14

## Agent

Codex

## Scope

- `services/declaration_draft_service.py`
- `dist_client/services/declaration_draft_service.py`
- `gui/tabs/naimenovanja_view.py`
- `dist_client/gui/tabs/naimenovanja_view.py`
- `tests/unit/test_declaration_draft_service.py`
- `docs/CONTEXT.md`

## Status izvora

Aktivni kod i `docs/CONTEXT.md` korišćeni su kao autoritativni izvori. Prethodna necommitovana PostgreSQL implementacija nacrta tretirana je kao rješenje za zamjenu.

## GitNexus impact

Rizik je LOW. `_on_save` ima jednog direktnog pozivaoca preko `keyPressEvent`, `_on_import_xml` nema detektovane zavisnosti, a `_position_section_heading_buttons` koristi samo `resizeEvent`.

## Šta je urađeno

- Dugme `Sačuvaj` otvara Windows dijalog i čuva kompletan draft u XML datoteku.
- Uklonjeno je posebno dugme `Otvori nacrt`.
- `Uvezi XML` sada otvara i Deklarant Pro radne nacrte i postojeće ASYCUDA XML datoteke.
- Posljednji korišćeni folder pamti se preko `QSettings`.
- Početna lokacija je `Documents/Deklarant Pro/Nacrti`.

## Zašto je urađeno

Korisnik mora kontrolisati lokaciju radnog dokumenta, nacrt mora biti prenosiv između terminala, a radni tok ne treba zavisiti od dostupnosti PostgreSQL servera. Posebno dugme za otvaranje nacrta dupliralo je postojeće dugme `Uvezi XML`.

## Kako je urađeno

Radni XML koristi korijen `DeklarantProDraft`, verziju formata i JSON payload unutar XML elementa. Time se čuva kompletna struktura `DeclarationDraft`, uključujući fakture, naimenovanja, dokumente i težine, bez miješanja sa ASYCUDA XML formatom.

## Šta nije dirano

Nisu mijenjani ASYCUDA exporter, validacija, parser standardnog ASYCUDA XML-a, PostgreSQL šema niti drugi tabovi.

## Verifikacija

- `py_compile` je prošao za oba servisa, oba GUI mirrora i test fajl.
- Statička provjera potvrdila je uklanjanje starih PostgreSQL i `Otvori nacrt` referenci.
- Testovi pokrivaju serijalizaciju, datotečni round-trip, prepoznavanje formata i odbijanje običnog XML-a.

## Pronađeni problemi

Izvršni round-trip test nije ponovljen nakon završne izmjene jer je terminal alat dosegao ograničenje izvršavanja. `pytest` ranije nije bio dostupan u projektnom `.venv` okruženju.

## Konflikti / kontradiktorni izvori

Prethodni pristup čuvanja u PostgreSQL-u bio je tehnički funkcionalan, ali se nije slagao sa željenim korisničkim tokom i zamijenjen je prenosivim XML nacrtom. Korisnička potvrda nije potrebna za ovu odluku jer je eksplicitno odobren novi plan.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `d1fedec` | `feat(nacrti): sačuvaj deklaraciju kao prenosivi XML` |

## Rizici / ograničenja

Deklarant Pro nacrt nije ASYCUDA XML i namijenjen je samo ponovnom otvaranju u ovoj aplikaciji. Postojeća tabela `catalogs.declaration_drafts`, ako je ranije kreirana, nije automatski obrisana.

## Potreban follow-up

Pokrenuti ciljani pytest kada `pytest` bude dostupan i ručno potvrditi dijaloge `Sačuvaj` i `Uvezi XML` u GUI-u.

## Potrebna korisnička potvrda

Provjeriti da se nacrt sačuva u odabrani folder i da se nakon `Uvezi XML` obnove Faktura, Naimenovanja i Zaglavlje tabovi.
