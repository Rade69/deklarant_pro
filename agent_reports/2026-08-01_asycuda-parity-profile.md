# ASYCUDA parity profil

## Datum

2026-08-01

## Agent

Codex

## Scope

- `docs/asycuda_parity_profile_2026-08-01.md`
- Referentni XML fajlovi koje je korisnik naveo iz `C:\Users\38765\Desktop\DV1`

## Status izvora

Aktivni izvori:

- `proba-refaktor.xml` — Deklarant Pro export poslije Faktura refaktora;
- `proba-refaktor-asycuda-provjera.xml` — isti tok nakon ASYCUDA provjere;
- `BLAGIĆ-LOREN-17-7.xml` — ASYCUDA referentni XML;
- `MEDIKO-20-7.xml` — ASYCUDA referentni XML.

Korisnik je potvrdio da je PE1 zapis sa samostalnim navodnikom najvjerovatnije
greška pri unosu, pa nije tretiran kao sistemski bug exportera.

## GitNexus impact

Nije mijenjan produkcioni kod niti simboli. Izmjena je dokumentaciona.

## Reprodukcija prije izmjene

Nije bugfix. Prije dokumentovanja su lokalno parsirani XML fajlovi i provjereni:

- broj stavki;
- ukupna faktura;
- bruto/neto mase;
- `Total_CIF`;
- `Total_cost`;
- broj i kodovi dokumenata;
- dužina Rub.31 opisa;
- dužina tarifnih brojeva.

## Šta je urađeno

Kreiran je početni ASYCUDA parity profil u `docs/asycuda_parity_profile_2026-08-01.md`.
Profil bilježi šta je već stabilno, šta ASYCUDA normalizuje sama i koje razlike
treba ciljano istražiti.

## Zašto je urađeno

Nakon što je Faktura refaktor prošao realan ručni test i XML import/provjeru u
ASYCUDA-i, sljedeći rizik nije UI refaktor nego paritet XML obračuna i dokumenata.
Profil sprečava da se dalje radi naslijepo.

## Kako je urađeno

Nalazi iz tri ASYCUDA XML-a i jednog Deklarant Pro exporta su objedinjeni u
jedan MD dokument sa prioritetima:

- P1 CIF/zavisni troškovi;
- P1 broj obrazaca;
- P2 item-level dokumenti;
- P2 opisi robe;
- P3 pre-export validacioni izvještaj.

## Šta nije dirano

- Nije diran produkcioni kod.
- Nisu dirane `.env` lokalne postavke.
- Nisu dirani postojeći WIP fajlovi drugih agenata.
- Nije mijenjana CIF formula.
- Nije mijenjana XML dokument logika.

## Verifikacija

Verifikacija je dokumentacioni audit baziran na lokalnom parsiranju XML fajlova.
Svi XML fajlovi su se parsirali bez greške. U profilu su navedeni konkretni
brojevi koji se mogu ponovo provjeriti.

## Nezavisna provjera

Nije rađena jer nije bilo produkcionih code izmjena. Za kasniju izmjenu CIF ili
XML export logike biće potrebna nezavisna provjera.

## Pronađeni problemi

Najvažniji otvoreni nalaz je razlika u probnom paru:

- `Total_CIF`: Deklarant Pro 37,434.25 vs ASYCUDA 37,479.24;
- `Total_cost`: Deklarant Pro 983.00 vs ASYCUDA 904.99.

Broj obrazaca takođe traži dodatnu provjeru na većem skupu jer primjeri ne daju
potpuno trivijalno pravilo.

## Odbačene opcije

Odbačeno je trenutno mijenjanje produkcionog XML exporta bez dodatnog dokaznog
para i ručnog obračuna CIF-a. Razlog: razlike su stvarne, ali uzrok još nije
izolovan.

## Konflikti / kontradiktorni izvori

PE1 zapis sa navodnikom je inicijalno izgledao kao mogući export bug. Korisnik
je naknadno naveo da je to najvjerovatnije greška pri unosu, pa je profil to
tretirao kao unosni izuzetak, ne sistemski kvar.

## Commitovi

| Hash | Poruka |
| --- | --- |
| pending | `docs(asycuda): dodaj parity profil` |

## Kontekst korišćen

- `docs/CONTEXT.md` sekcija o ASYCUDA XML exportu;
- lokalno parsiranje XML fajlova koje je korisnik naveo.

## Rizici / ograničenja

Profil je baziran na malom skupu. Dovoljan je za smjer rada, ali nije dovoljan
za automatsku promjenu CIF formule ili pravila item-level dokumenata.

## Potreban follow-up

Sljedeći preporučeni korak je P1 audit CIF/zavisnih troškova na malom dokaznom
paru gdje su poznati ulazni DV1/PZT podaci.

## Potrebna korisnička potvrda

Korisnik treba izabrati da li prvo radimo CIF/zavisne troškove ili mapiranje
item-level dokumenata.
