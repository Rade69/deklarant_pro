# Faktura — kontrast statusne trake

## Datum

2026-07-21

## Agent

OpenAI Codex

## Scope

- `gui/tabs/faktura_view.py`

## GitNexus impact

Impact za `_create_status_bar` je LOW: jedan direktni pozivalac, dva povezana
simbola, jedan modul i nijedan pogođeni izvršni proces. Detect changes je prijavio
LOW rizik i 0 pogođenih procesa.

## Šta je urađeno

- Povećan je kontrast osnovnog teksta statusne trake.
- Stavke i ukupan iznos označeni su kao primarne metrike.
- Bruto i neto mase dobile su ujednačeno svijetloplavo isticanje.
- Validacioni status prikazuje se kao kompaktna statusna oznaka sa neutralnim,
  crvenim, žutim ili zelenim stanjem.
- Diskretni separatori su učinjeni čitljivijim.

## Zašto je urađeno

Donja traka sadrži mnogo važnih podataka u jednom redu. Jasna hijerarhija omogućava
brže čitanje brojki i trenutno prepoznavanje statusa provjere.

## Kako je urađeno

Promijenjen je samo lokalni QSS u `_create_status_bar` i dodijeljeni su objektni nazivi
postojećim QLabel kontrolama. Visina, redoslijed i logika ažuriranja nisu mijenjani.

## Šta nije dirano

- Sadržaj, računanje i formatiranje statusnih vrijednosti.
- Visina statusne trake i raspored widgeta.
- Tabela, toolbar i poslovna logika.
- `dist_client`, frozen build i ostali tabovi.
- Paralelne lokalne izmjene drugih autora.

## Verifikacija

- `python -m py_compile gui/tabs/faktura_view.py` — prolazi.
- Tri ciljana Faktura test fajla — 33 passed.
- `git diff --check` — bez grešaka.
- GitNexus detect changes — LOW, 0 pogođenih procesa.

## Pronađeni problemi

Nisu pronađene funkcionalne regresije.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `b803ac6` | `style(faktura): istakni ključne statuse u donjoj traci` |

## Rizici / ograničenja

Statusna oznaka zauzima nekoliko piksela više horizontalnog prostora zbog unutrašnjeg
razmaka, ali visina trake ostaje nepromijenjena.

## Potreban follow-up

Nema obaveznog tehničkog follow-upa.

## Potrebna korisnička potvrda

Potvrditi da su ključne metrike i oznaka `Neprovjereno` dovoljno jasne na monitoru.
