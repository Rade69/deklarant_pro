# Test importera na stvarnim fakturama + upozorenje za nedostajuću težinu

**Datum:** 2026-07-04
**Grana:** windows
**Scope:** `importers/import_result.py`, `tests/unit/test_master_frigo_mapping_detection.py`, `tests/unit/test_blagic_loren_agent_import.py`

---

## Šta je urađeno

1. Na zahtjev korisnika, testiran uvoz stvarnih faktura iz `najavauvoza/` (Master Frigo, Blagić-Attos, Medicopharm, MGM, Šumaprom) direktno kroz `ImportService.import_file()` — isti ulaz koji koristi GUI.
2. Otkriven i ispravljen gep: kad parser pronađe samo jednu od dvije težine (bruto ili neto), rezultat je tiho ostajao na 0.0 bez ikakvog upozorenja korisniku.
3. Usput otkrivena i ispravljena 2 testa koja su lažno padala zbog Windows path separator nesklada (backslash vs forward slash), sada kad su fixture fakture (koje su korišćene za ručno testiranje) prisutne na mašini.

## Zašto

Korisnik je tražio provjeru na realnim fakturama prije nastavka rada. Rezultati:

| Dobavljač | Nalaz |
|---|---|
| Master Frigo | 3/3 fakture čisto uvezene, tarife/zemlje smislene |
| Blagić-Attos | Auto-kombinacija radi; GUI duplikat-zaštita potvrđena u kodu (`processing_worker.py`); primijećena razlika bruto (144,26 vs 124,26 kg) između zaglavlja fakture i zbira liste pakovanja — nije popravljano, treba korisnikovo oko na dokumenta |
| Medicopharm | Čisto |
| MGM (Proton System) | 1 od 2 fakture: bruto pronađen (792,41 kg), neto **tiho** ostao 0 — bez upozorenja |
| Šumaprom | Excel: bruto 266,0 kg, neto tiho 0 (isti gep); PDF iz 2022 nije se parsirao (0 stavki, vjerovatno skenirana slika) — pao čisto sa jasnom greškom |

MGM i Šumaprom slučaj su **isti gep**: `sumaprom_excel_parser.py` i `proton_system_importer.py` oba čitaju bruto/neto regexom iz teksta zaglavlja (`_BRUTO_RE`/`_NETO_RE`), i kad jedan regex ne pogodi obrazac u konkretnom PDF-u/Excelu, vrijednost ostaje na defaultu (0.0) bez signala korisniku da nešto nije ekstraktovano.

## Kako je urađeno

Fix je stavljen u `ImportResult.validate()` ([importers/import_result.py](../importers/import_result.py)) — centralizovana provjera koju poziva `_validate_or_raise` iz `import_service.py` za **sve** importere, ne samo MGM/Šumaprom:

```python
if self.items and self.bruto_kg > 0 and self.neto_kg <= 0:
    warnings.append(f"Bruto težina pronađena ({self.bruto_kg} kg), ali Neto nije — provjerite fakturu")
elif self.items and self.neto_kg > 0 and self.bruto_kg <= 0:
    warnings.append(f"Neto težina pronađena ({self.neto_kg} kg), ali Bruto nije — provjerite fakturu")
```

Provjereno da ovo ne pravi lažna upozorenja za postojeće "pending" tokove (npr. Loren Excel koji čeka PDF par) — ti tokovi imaju **obje** težine na 0.0 (ne samo jednu), pa uslov `bruto>0 XOR neto>0` ih ne pogađa.

Upozorenje se automatski prikazuje na dva mjesta koja već postoje u kodu:
- `gui/tabs/agent/widgets/processing_worker.py` (progress log tokom uvoza)
- `services/import_validator.py` (`validate_batch` — sažetak "⚠️ N upozorenja")

### Test path-separator ispravke

Prilikom punog test run-a, 2 testa koja su ranije bila `skipif`-ovana (fixture fakture nisu postojale na mašini) sada su se izvršila (fakture su tu, korišćene za ručno testiranje iznad) i pala:

- `test_master_frigo_mapping_detection.py`: petlja koja prati "potrošene" fajlove je pravila `if path in consumed` bez normalizacije separatora — `consumed_paths` vraća Windows backslash putanje, a test lista koristi forward slash. Ispravljeno dodavanjem iste `canonical_path()` normalizacije koju već koristi produkcijski `ProcessingWorker` (`os.path.normcase(str(Path(value).resolve()))`).
- `test_blagic_loren_agent_import.py`: `assert pdf_result.consumed_paths == [EXCEL_46]` upoređivao je stringove direktno — promijenjeno na poređenje `Path` objekata.

**Produkcijski kod je već bio ispravan** (`ProcessingWorker.canonical_path` postoji i koristi se) — ovo je bio gep samo u pojednostavljenoj test logici koja ga nije replicirala.

## Verifikacija

- Standalone test: MGM faktura sad vraća `warnings: ['Bruto težina pronađena (792.41 kg), ali Neto nije — provjerite fakturu']`
- `gitnexus_impact` na `ImportResult.validate` (upstream): risk **LOW**, 4 pogođena simbola (svi u `services/import_validator.py`, koji već renderuje warnings)
- Pun test suite: 589 prošlo, 0 palo, 3 preskočena (Gemini dependency + 2 fajla bez fixtura)

## Šta nije dirano

- Blagić-Attos razlika u težinama (144,26 vs 124,26 kg) — ostavljeno korisniku da provjeri izvorna dokumenta, van scope-a automatskog fixa.
- Šumaprom PDF parsiranje 0 stavki (vjerovatno skenirana slika) — nije popravljano, van scope-a.

## Commitovi

| Hash | Poruka |
|------|--------|
| `bc1f040` | fix(import): upozori korisnika kad je pronadjena samo bruto ili samo neto tezina |
| `be38544` | fix(tests): normalizuj putanje pri poredjenju consumed_paths (Windows) |

## Rizici / ograničenja

Novo upozorenje je samo informativno (ne blokira uvoz) — ako korisnik ignoriše warning u GUI-ju, deklaracija i dalje može proći sa neto=0. Ne mijenja postojeće ponašanje (uvoz i dalje uspijeva), samo dodaje vidljivost.

## Potreban follow-up

- Blagić-Attos težinska razlika — korisnik treba ručno pregledati fakturu 720 i listu pakovanja.
- Šumaprom stari PDF (2022) — ako je ovaj format i dalje u upotrebi, trebalo bi istražiti OCR podršku.
