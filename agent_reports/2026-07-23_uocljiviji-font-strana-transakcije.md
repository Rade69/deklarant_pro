## Datum

2026-07-23

## Agent

Codex

## Scope

- `gui/tabs/zaglavlje_view.py`
- `dist_client/gui/tabs/zaglavlje_view.py`

## GitNexus impact

Impact za `ZaglavljeView._create_company_group` je LOW: jedan direktni pozivalac, tri posredno pogođena simbola i nijedan izvršni proces.

## Šta je urađeno

Tekst u poljima Pošiljaoca, Primaoca i Deklaranta dobio je težinu fonta 600 i nešto tamnije nijanse.

## Zašto je urađeno

Na korisničkom snimku unesene vrijednosti djelovale su pretanko i nedovoljno uočljivo na nijansiranim pozadinama.

## Kako je urađeno

Postojećim lokalnim QSS paletama polja dodan je `font-weight: 600`, uz korekciju boje teksta. Veličina fonta i geometrija nisu mijenjane.

## Šta nije dirano

Nisu mijenjani naslovi, placeholder tekstovi, visina i širina polja, padding, raspored, signali, validacija ni poslovna logika.

## Verifikacija

- Obje kopije prolaze `py_compile`.
- Ciljani testovi: 18 prošlo, 814 izostavljeno filterom.
- `git diff --check` je prošao.
- SHA-256 potvrđuje identične source i `dist_client` kopije.
- GitNexus provjere izvršene su prije commita.

## Pronađeni problemi

Nema novih problema.

## Konflikti / kontradiktorni izvori

Nema konflikta. Korisnički snimak je mjerodavan za čitljivost.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `bb6d79a` | `style(zaglavlje): pojačaj font strana transakcije` |

## Rizici / ograničenja

Rizik je nizak. Na sistemu bez Segoe UI Qt će koristiti odgovarajući fallback font iste težine.

## Potreban follow-up

Nema programskog follow-upa.

## Potrebna korisnička potvrda

Vizuelno potvrditi da je tekst dovoljno uočljiv bez potrebe za povećanjem veličine fonta.
