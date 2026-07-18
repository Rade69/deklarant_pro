# Agent Report — Faza 0: Karakterizacija postojecih tokova odluka

**Datum:** 2026-07-18  
**Agent:** Pi  
**Scope:** `tests/unit/test_decision_characterization.py`, `agent_tasks/2026-07-18_writer-inventar.md`  
**Faza:** 0 (Karakterizacija)  
**Status:** OK  

---

## Sta je pregledano

1. Svi fajlovi navedeni u obaveznom citanju (AGENTS.md, CLAUDE.md, docs/CONTEXT.md, core/draft/draft.py, evidence_model.py, tariff_decision_model.py, tariff_mapping_service.py, auto_fill_service.py, tariff_suggestion_service.py, historical_tariff_search_service.py, declaration_validator_service.py, create_naimenovanja_service.py, faktura_view.py, import_pipeline_service.py, preference_validator.py)

2. `rg` pretraga svih direktnih writera za `tarifni_broj`, `zemlja_porijekla`, `povlastica`, `eur1_number` u `core/`, `services/`, `gui/`, `importers/`

3. Postojeci testovi: `test_evidence_model.py` (34 testa), `test_agent_decision_regression.py` (12 testova)

---

## Writer inventar — broj pronađenih writera po kategoriji

| Kategorija | Broj | Status |
|------------|------|--------|
| A1. Parser/Deserializer (dozvoljen sirovi unos) | 25 | DOZVOLJEN |
| A2. Inferred/Business Logic Writer | 11 | **MORA BITI MIGRIRAN** |
| A3. Manual Edit Adapter | 8 | **MORA kroz decision servis** |
| B. Setattr/Dict/Constructor (read-only strukture) | 10 | Nije writer |
| C. Read-only komponente sa bugom | 2 | **BUG** |

**Ukupno mjesta za migraciju: 21** (11 A2 + 8 A3 + 2 C)

### Kljucni bugovi pronadjeni:

1. **`PreferenceValidator.auto_fix_missing_eur1()`** (`services/validation/preference_validator.py:242`) — validator PIŠE `item.povlastica = 'PE1'`. Validator mora biti read-only.

2. **`evidence_from_preference()`** (`services/agent/validation/evidence_model.py`) — PE1/PE2/PE3 daju `auto_applicable=True`, ali prema novom ugovoru detekcija dokumenta daje samo CANDIDATE. Potvrda deklaranta je obavezna.

---

## Testovi — rezultati

| Rezultat | Broj |
|----------|------|
| PASSED | 18 |
| XFAIL | 4 |
| UKUPNO | 22 |

### Prolazni testovi (18):

Svi testovi pozivaju **stvarne postojece servise**:
- `evidence_from_tariff_decision()` — determinizam, isti izvoznik, razliciti izvoznici
- `evidence_from_preference()` — PE2/PE1/PE3 razlikovanje relevantnih stavki, EUR.1 brojevi po zemlji
- `PreferenceValidator.validate()` — read-only potvrda (scenario 10)
- `PreferenceValidator.validate_batch()` — read-only grupna validacija
- `PreferenceValidator.get_missing_eur1()` — read-only detekcija
- `PreferenceValidator.validate()` — PE2 bez izjave → greska, EUP sa EUR.1 → validno
- `build_evidence()` — LLM degradacija, evidence != permission

### XFAIL testovi (4):

| Test | Razlog | Faza ispravke |
|------|--------|---------------|
| `test_scenario_6_pe2_detection_is_candidate_not_confirmed` | PE2 detekcija daje `auto_applicable=True` umjesto CANDIDATE | Faza 1-3 |
| `test_scenario_6b_pe1_eur1_number_is_candidate_not_confirmed` | PE1/EUR.1 broj daje `auto_applicable=True` umjesto CANDIDATE | Faza 1-3 |
| `test_scenario_6c_pe3_authorized_exporter_is_candidate_not_confirmed` | PE3 daje `auto_applicable=True` umjesto CANDIDATE | Faza 1-3 |
| `test_scenario_10b_auto_fix_must_not_write` | `auto_fix_missing_eur1()` piše `item.povlastica = 'PE1'` | Faza 4.3 |

---

## Poznati rizici koji prelaze u Fazu 1

1. **PE1/PE2/PE3 auto_applicable** — `evidence_from_preference()` u `evidence_model.py` mora biti izmijenjena tako da svi PE dokazi budu CANDIDATE (ne CONFIRMED). Ovo mijenja semantiku postojeceg `Evidence.auto_applicable` — moze uticati na sve pozivaoce (FakturaView, Agent pipeline, Validacija).

2. **PreferenceValidator.auto_fix_missing_eur1()** — ima pozivaoce u kodu. Uklanjanje write operacije zahtijeva refaktor svih mjesta koja pozivaju ovu metodu.

3. **11 inferred writera** u servisnom sloju — svi nezavisno pišu u ista polja. Migracija na jedan decision servis je operacija visokog rizika (svaki writer ima svoje pozivaoce).

4. **Backward compatibility** — stari draftovi bez decision state-a moraju ostati čitljivi. Svaka izmjena `InvoiceLine` strukture mora proći kroz `from_any()` deserializaciju.

---

## Commitovi

| Hash | Poruka |
|------|--------|
| `055cd4d` | `test(decision): zabiljezi postojece tokove odluka` |

---

## Potreban follow-up

- Faza 1: Kanonski model odluke (`DecisionField`, `DecisionStatus`, `FieldDecision`, `LineDecisionState`)
- Faza 2: `DeclarationDecisionService` sa `evaluate_line()`, `apply_candidate()`, `confirm_manual_value()`, `reject_candidate()`
- Faza 3: Jedinstvene politike po polju (tarifa, porijeklo, povlastica)

---

## Potrebna korisnicka potvrda

- [ ] Pregledati writer inventar — da li ima propuštenih writera?
- [ ] Potvrditi da svi xfail razlozi odgovaraju željenom ugovoru (posebno PE1/PE2/PE3 = CANDIDATE)
- [ ] Odobriti prelazak na Fazu 1