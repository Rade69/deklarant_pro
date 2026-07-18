# Agent Report — Faza 3: Jedinstvene politike po polju

**Datum:** 2026-07-18  
**Agent:** Pi  
**Scope:** `services/decision/decision_policy.py`, `services/decision/evidence_adapters.py`, policy testovi  
**Commit:** `9d20ad2` + popravke

---

## Šta je urađeno u Fazi 3

Definisane su tri jedinstvene politike koje određuju redoslijed kandidata,
uslove za automatsku primjenu i zabrane za svako polje odluke:

### 1. Tarifna politika (`rank_tariff_candidates` + `can_auto_apply_tariff`)

| Prioritet | Izvor | Opis |
|-----------|-------|------|
| 1 | USER | Ručno potvrđena vrijednost |
| 2 | DOCUMENT | Tarifa iz dokumenta/drafta |
| 3 | EXPORTER_HISTORY | Istorija istog izvoznika |
| 4 | TARIFF_DATABASE | Baza znanja (samo ako confidence != UNKNOWN) |
| 5 | SIMILARITY | Fuzzy match |
| 6 | TARIFF_DATABASE (UNKNOWN) | Nepoznati izvor |
| 7 | None / ostalo | Bez dokaza |

**Pravila:**
- Istorija drugog izvoznika je zabranjena (nema fallback)
- LLM **nikad** ne stvara primjenjiv kandidat (eksplicitna zabrana u `can_auto_apply_tariff`)
- Auto-apply samo kroz `auto_fill_clicked` ili `dialog_confirmed` + score >= 85
- `requires_confirmation=True` blokira auto-apply osim za `dialog_confirmed`
- Sortiranje: negativni score za opadajuće rangiranje unutar istog prioriteta

### 2. Politika porijekla (`rank_origin_candidates` + `can_auto_apply_origin`)

| Prioritet | Izvor | Opis |
|-----------|-------|------|
| 1 | USER | Ručna potvrda |
| 2 | DOCUMENT | Eksplicitna zemlja iz dokumenta |
| 3 | PARSER | Parser kandidat |
| 4 | MAPPING | Baza/istorija (samo informativno) |

**Pravila:**
- Baza i istorija **ne smiju** prepisati dokument
- Dokument: score >= 85 može auto-apply
- Parser: score >= 70 može auto-apply
- Mapping/istorija **nikad** auto-apply
- Konflikt → CONFLICT status
- LLM zabranjen

### 3. Politika povlastice (`rank_preference_candidates` + `can_auto_apply_preference`)

**Stroga politika:**
- Samo PE1/PE2/PE3 dokument dokazi se rangiraju
- Zemlja porijekla **nije** dokaz povlastice
- Mapping baza **nije** dokaz povlastice
- Istorija **nije** dokaz povlastice
- Parser samo detektuje kandidat
- **Nikad** auto-apply bez `dialog_confirmed` (čak ni PE1 sa EUR.1 brojem)
- Tek CONFIRMED odluka upisuje povlasticu
- LLM zabranjen

---

## Zašto LLM nikad ne smije auto-apply

LLM je prezentacioni sloj, ne izvor dokaza. Čak i kad LLM vrati odgovor
sa visokom pouzdanošću, to nije zamjena za:
- Dokumentovani dokaz (faktura, PDF, EUR.1 obrazac)
- Istorijski validiranu tarifu iz odobrenih XML deklaracija
- Eksplicitnu potvrdu deklaranta

Sve tri `can_auto_apply_*` funkcije sada imaju eksplicitnu provjeru:
```python
if ev.source.value == "llm":
    return False
```
Ovo važi čak i kad LLM kandidat ima score=95 i `requires_confirmation=False`.

---

## Gdje je riješen fuzzy threshold 0.92

Threshold se primjenjuje u **adapter sloju** (`evidence_adapters.py`), ne u politici.
Politika ne duplira provjeru — prima već filtrirane kandidate.

Adapter `adapt_tariff_evidence()` poziva:
```python
mapping = svc.find_mapping(..., min_similarity=0.92, ...)
```

Projektni `TariffMappingService.find_mapping()` interno filtrira kandidate
sa `similarity < min_similarity` i ne vraća ih. Time kandidat sa
similarity < 0.92 **nikad ne dolazi** do policy sloja.

Test `test_fuzzy_threshold_is_enforced_in_adapter` dokumentuje ovu
arhitektonsku odluku — threshold ostaje odgovornost adaptera, politika
ga ne duplira.

---

## Test komande i rezultati

```powershell
python -m pytest tests/unit/test_decision_tariff_policy.py tests/unit/test_decision_origin_policy.py tests/unit/test_decision_preference_policy.py tests/unit/test_declaration_decision_service.py tests/unit/test_declaration_decision_model.py tests/unit/test_evidence_model.py -q
```

**124 passed** — uključujući:
- 16 tarifnih policy testova (dodata 3: LLM zabrana, fuzzy threshold 0.91, fuzzy threshold 0.92)
- 11 origin policy testova
- 14 preference policy testova
- 23 decision service testa
- 26 decision model testa
- 34 evidence model testa

---

## Šta nije dirano

- GUI — nijedan fajl
- Faza 4 migracije (Faktura tab, Agent pipeline, Validacija, Naimenovanja, XML export)
- Produkcijski parseri i importeri
- `PreferenceValidator.auto_fix_missing_eur1()` bug — i dalje dokumentovan kao xfail
- `find_batch_by_product_codes()` SQL bug — i dalje dokumentovan kao xfail
- PE1/PE2/PE3 `auto_applicable` u `evidence_from_preference()` — i dalje xfail (popravka u Fazi 4 kroz migraciju pozivalaca na decision servis)

---

## dist_client mirror

Root i dist_client fajlovi su identični:
- `services/decision/decision_policy.py` ↔ `dist_client/services/decision/decision_policy.py` ✅
- `services/decision/evidence_adapters.py` ↔ `dist_client/services/decision/evidence_adapters.py` ✅