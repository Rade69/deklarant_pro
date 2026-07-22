## Datum

2026-07-22

## Agent

Codex

## Scope

`styles/naimenovanja_components.qss`, `dist_client/styles/naimenovanja_components.qss`, `styles/display_profiles.qss` i `dist_client/styles/display_profiles.qss`.

## Status izvora

Aktuelni kod i korisnička slika su tretirani kao važeći. Izvorni i `dist_client` QSS bili su neusaglašeni za fontove taba Naimenovanja.

## GitNexus impact

Promjena klase `SafeMessageBox` imala bi CRITICAL rizik: 45 direktnih uvoznika i 100 ukupnih zavisnosti. Zato Python simbol nije mijenjan. QSS izmjena nema mapirane simbole ili tokove; ručno procijenjeni rizik je LOW.

## Šta je urađeno

- Fontovi `QLineEdit`, `QTextEdit` i `QComboBox` elemenata unutar formulara Naimenovanja postavljeni su na 15 px.
- Modalni tekst i dugmad dobili su čitljive veličine, veći unutrašnji razmak i minimalne dimenzije.
- Usklađene su izvorna i `dist_client` kopija stilova.
- Ispravljen je nevažeći selektor `+QGroupBox#group_31`.

## Zašto je urađeno

Globalni i runtime stilovi su smanjivali efektivni font formulara i modalnih prozora. Centralna Python izmjena bi zahvatila veliki dio aplikacije, pa je odabrana ograničena QSS korekcija.

## Kako je urađeno

Pravila formulara ostala su ograničena na `QWidget#naimenovanjaUiWidget`. Pravila za `QMessageBox` smještena su u `display_profiles.qss`, koji se učitava posljednji i zato pouzdano vraća čitljive dimenzije.

## Šta nije dirano

Nisu mijenjani layout, geometrija, položaj dugmadi, tekst modalnih akcija, poslovna logika ni `SafeMessageBox` implementacija.

## Verifikacija

- Offscreen Qt provjera: `QLineEdit`, `QTextEdit` i `QComboBox` imaju efektivnih 15 px.
- Modalna dugmad imaju 16 px i minimalnu efektivnu veličinu 196 × 64 px; modalni tekst dobija minimalno 564 × 144 px prostora.
- `pytest tests/unit/test_naimenovanja_view_display_values.py tests/unit/test_pe_rub44_consistency.py -q`: 9 testova prošlo.
- `git diff --check`: bez grešaka.

## Pronađeni problemi

GitNexus indeks ne mapira QSS promjene i u `detect_changes` prikazuje nepovezane izmjene iz glavnog radnog stabla. Zato je scope dodatno potvrđen kroz staged diff.

## Konflikti / kontradiktorni izvori

`styles` je imao 14 px, a `dist_client/styles` 13 px za ista polja. Obje kopije su sada namjerno usklađene na 15 px. Korisnička potvrda za ovu odluku nije potrebna, ali je potrebna vizuelna provjera na stvarnom ekranu.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `d031e16` | `fix(naimenovanja): vrati čitljive fontove` |

## Rizici / ograničenja

Qt na Windowsu može prijaviti 14 px za tekst modalne poruke iako je QSS zadat na 16 px, zbog sistemskog font renderinga. Minimalne dimenzije i dugmad su potvrđeno povećani.

## Potreban follow-up

Nema programskog follow-upa prije korisničke vizuelne provjere.

## Potrebna korisnička potvrda

Provjeriti jedan modal iz taba Naimenovanja i nekoliko polja rubrika 31–46 pri uobičajenoj rezoluciji i Windows skaliranju.
