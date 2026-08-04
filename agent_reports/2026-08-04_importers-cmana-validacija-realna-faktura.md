## Datum
2026-08-04

## Agent
Claude Code (Sonnet 5)

## Scope
Validacija (bez izmjene koda) CMANA parsera na realnoj fakturi — nadovezuje se na
`agent_reports/2026-08-04_importers-cmana-fuzzy-prag-fix.md`, koji je naveo "nema realne CMANA
fakture za end-to-end test" kao poznato ograničenje. Korisnik je dostavio pristup
`H:\New folder\najavauvoza\CMANA\`.

## Šta je urađeno
1. Ponovo pregledan `CMANA` folder — pored ranije poznatih XML/Leburić fajlova, pronađena 4 nova
   fajla (dodana istog dana, `fwd30_07_2026_.zip`): `leb amb.PDF`, `leb otp.pdf`, `leb pak.PDF`,
   `Scan1.PDF`. Prefiks "leb" je ime KUPCA (Leburić Komerc d.o.o.), NE dobavljača — sam dokument
   je izdat od CMANA DOO Krnjevo (Srbija) prema kupcu Leburić Komerc (BiH).
2. Identifikovan `leb otp.pdf` kao prava komercijalna faktura ("RAČUN INO KUPCU br.
   255950600136 od 30.07.2026") — tačan format koji `cmana_pdf_parser.py` očekuje. `leb amb.PDF`
   je carinska deklaracija za privremeni uvoz/izvoz ambalaže (drugi format), `leb pak.PDF` je
   pakting lista + atest o bezbjednosti (drugi format), `Scan1.PDF` je CEFTA veterinarski
   sertifikat (drugi format, OCR-garbled).
3. **`parse_cmana_pdf()` pokrenut direktno na `leb otp.pdf`** — REZULTAT: 7/7 stavki tačno
   parsirano (šifra, naziv, količina, cijena, iznos, neto/bruto po stavci), footer
   bruto_kg=7941.55/neto_kg=7611.95 tačno poklapa sa fakturom, invoice_name tačan. Svi tarifni
   brojevi ispravno pronađeni preko statičkog `_CMANA_PRODUCT_TARIFFS` rječnika (šifre
   120002-120056 su tačno one koje su već u tom rječniku).
4. **`parse_smart_pdf()` (stvaran GUI entry point) pokrenut na istom fajlu** — identičan rezultat,
   `import_type='cmana'` potvrđuje tačnu dispatch rutu (ne generic fallback).
5. **Provjereno da `detect_cmana_pdf()` ispravno ODBIJA `leb amb.PDF` i `leb pak.PDF`**
   (vraća `False` za oba) — nema lažno-pozitivne detekcije kad korisnik importuje prateća
   dokumenta umjesto glavne fakture.

## Zaključak
**CMANA parser je sada potvrđen na realnoj fakturi — radi ispravno, end-to-end, kroz stvaran GUI
ulaz.** Ovo zatvara jedino preostalo ograničenje iz prethodnog fuzzy-prag fix-a.

**Važna napomena o obimu ove validacije**: dostupna faktura je koristila ISKLJUČIVO šifre
proizvoda koje su već u statičkom `_CMANA_PRODUCT_TARIFFS` rječniku — fuzzy-match po nazivu
proizvoda (funkcija `get_tariff_codes_for_product_name()`, čiji je prag ovom sesijom podignut na
0.92) NIJE bio okinut ovim testom, jer nije bilo nepoznatih šifri koje bi ga aktivirale. Fix
ostaje verifikovan čitanjem koda + regresionom test svitom, ne stvarnim fuzzy-match scenarijem na
CMANA katalogu. Ako se u budućnosti pojavi CMANA faktura sa NOVOM šifrom proizvoda (van
rječnika), to bi bio idealan test slučaj za taj specifičan dio koda.

## Verifikacija
Direktan poziv `parse_cmana_pdf()` i `parse_smart_pdf()` na stvarnom PDF-u — vidi rezultate gore.
Nema izmjene koda ovim zadatkom (čisto čitanje/pokretanje), pa nema py_compile/test-suite koraka.

## Rizici / ograničenja
Fuzzy-match putanja (0.92 prag) i dalje nije validirana na realnom "nepoznata šifra" scenariju.

## Potreban follow-up
Nema hitnog — CMANA je sada u istom statusu potvrđenosti kao ostali validirani dobavljači
(Blagić, Master Frigo, Medicopharm, MGM/Proton, PIP Food, Leburić, Šumaprom-logika).

## Potrebna korisnička potvrda
Nema.
