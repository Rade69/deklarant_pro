# Normalizacija tarifnih brojeva

## Cilj

Uskladiti ulaznu normalizaciju sa kanonskim internim formatom: tarifni broj u
`InvoiceLine` mora imati najviše 8 cifara, dok se 10-cifreni PostgreSQL oblik
koristi samo pri upitu prema bazi.

## Pogođeno

GitNexus impact za `importers.invoice_line_utils.normalize_tariff_number` je
CRITICAL: 67 simbola, 12 direktnih pozivalaca, 5 procesnih tokova i 10 modula.
Direktno su pogođeni ImportService, FakturaView, import workflow i pojedini
vendor parseri.

## Plan

1. Promijeniti zajednički normalizator da sve kodove duže od 8 cifara skrati na
   prvih 8 cifara.
2. Uskladiti root i `dist_client` kopiju.
3. Ažurirati regresione testove i dodati primjere uočene u Faktura tabeli.
4. Pokrenuti ciljane i pune testove te provjeriti GitNexus affected scope.

## Šta NE dirati

Ne mijenjati grupisanje naimenovanja, Rub.31, mase, porijeklo, povlastice,
mapiranje proizvoda niti način PostgreSQL lookup-a koji 8-cifrenom kodu dodaje
`00`.

## Konflikti

Postojeći normalizator i raniji testovi dozvoljavaju 10-cifrenu TARIC
subdiviziju. `AGENTS.md` i korisnikova potvrda zahtijevaju interni format od 8
cifara, pa se oni tretiraju kao važeći izvor. Dodatna korisnička potvrda: NE.
