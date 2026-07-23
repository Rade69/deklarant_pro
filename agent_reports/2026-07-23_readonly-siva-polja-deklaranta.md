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

Siva paleta Deklaranta sada eksplicitno pokriva osnovno, hover i focus `read-only` stanje.

## Zašto je urađeno

Prethodno dodano osnovno sivo pravilo nije bilo dovoljno specifično. Globalni selektor `QLineEdit:read-only` imao je prednost i ponovo prikazivao zelenkastu pozadinu.

## Kako je urađeno

Lokalnoj QSS paleti za prefiks `deklarant` dodani su selektori `QLineEdit:read-only`, `QLineEdit:read-only:hover` i `QLineEdit:read-only:focus`.

## Šta nije dirano

Nisu mijenjani Pošiljalac, Primalac, read-only ponašanje, automatsko popunjavanje, signali, validacija, dimenzije ni raspored.

## Verifikacija

- Obje izmijenjene kopije prolaze `py_compile`.
- Ciljani testovi: 18 prošlo, 814 izostavljeno filterom.
- `git diff --check` je prošao.
- SHA-256 potvrđuje identične source i `dist_client` kopije.
- GitNexus impact i detect changes provjere izvršene su prije commita.

## Pronađeni problemi

Uzrok je bio prioritet specifičnijeg globalnog QSS pseudo-state selektora, a ne pogrešna vrijednost osnovne sive boje.

## Konflikti / kontradiktorni izvori

Nema konflikta. Korisničko vizuelno opažanje potvrdilo je da prethodna tehnička izmjena nije davala očekivani render.

## Commitovi

| Hash | Poruka |
| --- | --- |
| `bcaea57` | `fix(zaglavlje): zadrži sivu boju read-only deklaranta` |

## Rizici / ograničenja

Rizik je nizak i ograničen na lokalni stil polja Deklaranta.

## Potreban follow-up

Nema programskog follow-upa.

## Potrebna korisnička potvrda

Nakon ponovnog pokretanja aplikacije potvrditi da su sva polja Deklaranta neutralno siva.
