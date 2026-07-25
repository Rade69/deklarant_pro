# Plan: ukloni pogrešnu lijevu dopunu (zfill) kratkih tarifnih brojeva

## Cilj

`ImportService._normalize_tariffs_in_result()` (`services/import_service.py:190`)
trenutno lijevo-dopunjava (zfill) SVAKI 4-7-cifreni tarifni broj nulama do 8
cifara. Otkriveno na stvarnoj fakturi (Medicopharm 1476/26, Rb.78): izvorni
kod `3304990` (7 cifara, izostavljena ZADNJA cifra — kozmetika, poglavlje 33)
postaje `03304990` (izmišljeno poglavlje 03 = riba). Funkcija ne može
razlikovati "izostavljena vodeća nula poglavlja 01-09" (jedini slučaj gdje je
lijeva dopuna ispravna) od bilo kog drugog nepotpunog unosa — a poglavlja
≥10 su velika većina realnih tarifa, pa je lijeva dopuna češće pogrešna nego
tačna. Odluka (potvrđena od korisnika): ukloniti auto-dopunu, ostaviti kod
nepromijenjen (nepotpun) da ga uhvati postojeća validacija.

## Pogođeno (iz gitnexus_impact, direction=upstream)

- **Risk: HIGH**, 12 impactedCount, 2 pogođena procesa, 3 pogođena modula
- Poziva se sa SVA 4 return mjesta u `ImportService.import_file()` (combined,
  packing, medicopharm, registry/generic put) — dakle svaki uvoz, svakog
  dobavljača, bez obzira na kanal (ručni/agent/batch).
- Postojeći sigurnosni mehanizam potvrđen PRIJE izmjene: `declaration_
  validator_service.py:344` baca `ERROR` ("nije pronađen u zvaničnoj
  tarifi") ako `tariff.isdigit()` i ne postoji u `catalogs.zvanicna_tarifa`.
  Uživo provjereno: izmišljeni `03304990` NE postoji u bazi → već bi bio
  uhvaćen ERROR-om i pod trenutnim (pogrešnim) ponašanjem. Uklanjanje
  zfill-a NE otvara rupu — samo prestaje da FABRIKUJE broj koji izgleda
  validan (8 cifara) umjesto da ostavi vidljivo nepotpun trag.

## Plan

1. `services/import_service.py::_normalize_tariffs_in_result()`: ukloniti
   `if normalized and normalized.isdigit() and 4 <= len(normalized) < 8:
   normalized = normalized.zfill(8)` blok u potpunosti — primijenjeno
   dosljedno za CIJELI opseg 4-7 cifara (ista greška postoji za sve te
   dužine, ne samo za 7 — testirano/potvrđeno da nijedna dužina u tom
   opsegu nema semantički siguran pravac dopune).
2. Mirrorati u `dist_client/services/import_service.py`.
3. Test: postojeći Medicopharm 1476 e2e test (`tests/integration/
   test_real_invoice_import_e2e.py`) mora i dalje prolaziti — Rb.78 sad
   treba da ostane `3304990` (ne `33049900` ni `03304990`) jer aplikacija
   više ne pogađa; dodati eksplicitnu asertaciju za to.
4. Novi jedinični test za `_normalize_tariffs_in_result`: potvrdi da 4-7
   cifara PROLAZI NEPROMIJENJENO, 10 cifara sa "00" i dalje skraćuje na 8,
   ">10" i dalje skraćuje na 10 (te dvije grane OSTAJU — nisu sporne, rade
   ispravno po dokumentovanom `normalize_tariff_number()` ponašanju).

## Šta NE dirati

- `normalize_tariff_number()` u `importers/invoice_line_utils.py` — već
  ispravno dokumentovano ponašanje ("< 8 cifara → ostaje kakvo jeste"),
  NIJE izvor buga, samo se ne smije nadjačati nakon poziva.
- Grane za 10-cifreni i >10-cifreni kod u `_normalize_tariffs_in_result`
  (skraćivanje) — netaknuto, van scope-a ove izmjene.
- `declaration_validator_service.py` — sigurnosni mehanizam koji hvata
  nepotpune/nevalidne tarife, netaknut (samo se oslanjamo na njega).

## Nivo dozvole

Odluka potvrđena od korisnika (AskUserQuestion, "Ukloni auto-dopunu za 7
cifara"). Primjena proširena na dosljedan 4-7 opseg jer je identičan bug —
navedeno eksplicitno u agent_report-u, ne skriveno.
