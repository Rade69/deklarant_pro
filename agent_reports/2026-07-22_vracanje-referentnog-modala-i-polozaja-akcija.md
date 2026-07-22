## Datum

2026-07-22

## Agent

Codex

## Scope

Modalni QSS i naslovne akcije `Sačuvaj nacrt` / `Poništi` na tabu Naimenovanja.

## Status izvora

Korisnička slika je referenca za modal. Git stanje neposredno prije commita palete `a2f0135` je referenca za položaj naslovnih akcija.

## GitNexus impact

QSS-only promjena, ručno procijenjeni rizik LOW. `detect_changes` nije mapirao stilske fajlove na izvršne tokove.

## Šta je urađeno

- Uklonjena su dodatna modalna pravila iz `display_profiles.qss` koja su previše povećala prozor.
- Vraćen je postojeći modalni stil iz `button_system.qss`.
- Uklonjene su naknadno dodane minimalne širine 142 px i 89 px sa naslovnih akcija.
- Zadržane su nove funkcionalne boje i fontovi polja od 15 px.

## Zašto je urađeno

Modal je nakon posljednje korekcije postao veći od korisničke reference. Dugmad su bila pomjerena zato što je commit `7e975ff`, poslije promjene boje, nametnuo nove minimalne širine.

## Kako je urađeno

Git historija je upoređena sa stanjem prije `a2f0135`. Potvrđeno je da Python layout nije promijenjen u trenutku bojenja, pa su uklonjene samo naknadne QSS dimenzije.

## Šta nije dirano

Nisu mijenjani Python layout, fiksni razmak od 917 px, visina naslovne trake, boje dugmadi, poslovna logika ni veličina fontova polja.

## Verifikacija

- Offscreen Qt potvrđuje povratak postojećeg modalnog fonta od 16 px i dugmeta 240 × 80 px.
- `pytest tests/unit/test_naimenovanja_view_display_values.py tests/unit/test_pe_rub44_consistency.py -q`: 9 testova prošlo.
- `git diff --check`: bez grešaka.

## Pronađeni problemi

Ranija procjena položaja bila je pogrešna jer su minimalne širine tretirane kao vraćanje starog stanja, iako nisu postojale prije promjene boje.

## Konflikti / kontradiktorni izvori

Nema. Git historija i korisničko opažanje pokazuju isti uzrok.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `73010ca` | `fix(naimenovanja): vrati modal i položaj akcija` |

## Rizici / ograničenja

Tačna fizička veličina modala zavisi od Windows DPI skaliranja, ali se sada ponovo koristi isto pravilo kao na korisničkoj referentnoj slici.

## Potreban follow-up

Nema prije vizuelne provjere.

## Potrebna korisnička potvrda

Provjeriti modal i položaj naslovnih akcija nakon ponovnog pokretanja aplikacije.
