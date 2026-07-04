# Blagić-Attos: bruto/neto iz zbira stavki umjesto finalnog reda (paleta)

**Datum:** 2026-07-04
**Grana:** windows
**Scope:** `importers/vendors/blagic/blagic_attos_importer.py`

---

## Status izvora

Nastavak istrage iz [2026-07-04_test-real-fakture-mgm-neto-upozorenje.md](2026-07-04_test-real-fakture-mgm-neto-upozorenje.md), gdje je zabilježena "razlika u težinama" (144,26 vs 124,26 kg) kao otvoreno pitanje za korisnika. Ovaj izvještaj je zatvara.

## GitNexus impact

`parse_blagic_attos_with_auto_combine` — **HIGH** rizik (25 pogođenih simbola, 5 direktnih pozivača, funkcija je na glavnoj putanji `processing_worker.run` / `import_service.import_file`).

**Napomena o proceduri:** Prema CLAUDE.md, za HIGH rizik agent treba napraviti kratak plan **prije** izmjene. Izmjena je u ovom slučaju već bila napravljena kad je `gitnexus_impact` pokrenut (redoslijed obrnut od propisanog). Kompenzovano naknadnom detaljnom verifikacijom (vidi dolje) prije commita. Stvarni obim izmjene je uzak — `blagic_attos_importer.py` obrađuje isključivo ATTOS format (detekcija: "RAČUN-OTPREMNICA"/"LISTA PAKOVANJA" + "ATTOS"/"Novi Sad" + "Blagić"), ne dijeli logiku sa Loren/Šumaprom/MGM/Master Frigo parserima — HIGH je posljedica pozicije u pipeline-u (svaki fajl prolazi kroz `import_file`), ne širine stvarno pogođenih podataka.

## Šta je urađeno

Korisnik je ručno provjerio fakturu 720 i listu pakovanja i potvrdio da dokumenti **nisu** u nesuglasju — oba navode isti finalni total (Neto: 112,900 kg / Bruto: 144,260 kg). Dublja analiza sirovog teksta liste pakovanja je otkrila da dokument sadrži **dva** bruto totala:
- zbir tabele stavki (21 red): 124,260 kg
- finalni red na kraju dokumenta (nakon "Pakovanje: 1 paleta"): 144,260 kg

Razlika (20,00 kg) je paušalna procijenjena težina EUR transportne palete koju ATTOS dodaje u finalni red, van tabele stavki.

Korisnik je eksplicitno potvrdio poslovno pravilo: za ATTOS je **zbir po stavkama** relevantna težina za deklaraciju, ne finalni red sa paletom.

## Zašto

Glavni tok (faktura + lista pakovanja kombinovano — što je jedini realni tok jer faktura proaktivno "pojede" listu pakovanja) je do sada čitao `header.get("bruto_kg")` — finalni red iz zaglavlja **fakture** (koji se poklapa sa finalnim redom liste pakovanja, oba 144,26). Ovo je bilo pogrešno po poslovnom pravilu korisnika.

Zanimljivo: rijetka fallback grana (samostalni uvoz liste pakovanja bez fakture, `parse_blagic_attos_with_auto_combine` linije 552-584) je **već** računala `sum(i.bruto_kg for i in items)` — slučajno je već radila ono što je poslovno ispravno, bez namjere.

## Kako je urađeno

U `parse_blagic_attos_with_auto_combine` ([blagic_attos_importer.py:595-625](../importers/vendors/blagic/blagic_attos_importer.py#L595-L625)), grana koja kombinuje fakturu i listu pakovanja sada računa:

```python
bruto_kg = sum(p.get("bruto_kg", 0.0) for p in packing_items)
neto_kg = sum(p.get("neto_kg", 0.0) for p in packing_items)
```

umjesto `header.get("bruto_kg"/"neto_kg")`. Fallback grana (nema liste pakovanja) ostaje nepromijenjena — koristi header fakture jer nema drugog izvora.

## Verifikacija

Testirano na sve tri stvarne ATTOS fakture iz `najavauvoza/blagic-attos/`:

| Faktura | Zbir stavki (novo, koristi se) | Finalni red (staro) | Razlika |
|---|---|---|---|
| 720 | 124,26 kg | 144,26 kg | 20,00 kg (1 paleta) |
| 721 | 1.125,295 kg | 1.165,295 kg | 40,00 kg (2 palete) |
| 722 | 47,01 kg | 67,01 kg | 20,00 kg (1 paleta) |

Razlika je u sva tri slučaja tačan umnožak od 20 kg — potvrđuje hipotezu o paušalnoj težini palete, ne o grešci u dokumentu.

Pun test suite nakon izmjene: **589 prošlo, 0 palo, 3 preskočena** (nepromijenjeno u odnosu na prije fixa — nijedan postojeći test nije provjeravao tačnu vrijednost bruto/neto za ove tri fakture, pa fix nije mogao biti uhvaćen testovima; verifikacija je urađena ručno na stvarnim podacima).

`gitnexus_detect_changes` (unstaged): risk LOW, 0 affected processes.

## Šta nije dirano

- Loren, Šumaprom, MGM, Master Frigo importeri — potpuno odvojeni moduli, nije provjeravano da li imaju sličan problem (nije bilo naznaka da dodaju paušalnu težinu ambalaže).
- Fallback grana (uvoz liste pakovanja bez fakture) — već je računala zbir stavki, nije mijenjana.

## Commitovi

| Hash | Poruka |
|------|--------|
| `882a703` | fix(blagic-attos): koristi zbir stavki iz liste pakovanja umjesto finalnog Bruto/Neto reda |

## Rizici / ograničenja

Ako ATTOS promijeni format dokumenta (npr. prestane navoditi tabelu stavki, ili počne uključivati paletu u svaku stavku pojedinačno), ovaj fix bi trebalo revidirati. Nema automatskog testa koji bi to uhvatio — vrijedi razmotriti dodavanje regresionog testa sa fixture podacima (720/721/722) da se ubuduće ne izgubi ovo ponašanje.

## Potreban follow-up

- Zatvoreno: dodat regresioni test `tests/unit/test_blagic_attos_pallet_weight.py` (3 parametrizovana slučaja, 720/721/722), `skipif` kad fixture fakture nisu prisutne. Test suite: 592 prošlo, 0 palo.
- Nema.
