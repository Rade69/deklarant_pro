# Agent Report — Faza 2 popravke (verifikacija)

**Datum:** 2026-07-18
**Agent:** Pi
**Scope:** Faza 2 — `services/decision/`, `core/decision/evidence.py`
**Referenca:** `dbacdf9` feat(decision): centralizuj procjenu i primjenu kandidata

---

## Problemi i popravke

### Problem 1: Test sa zivom bazom

**Test:** `test_evaluate_line_with_existing_tariff_in_db` je zavisio od PostgreSQL baze i
ocekivao konkretan zapis `6002-2Z → 84821000`.

**Popravka:** Test sada koristi `monkeypatch` na `TariffMappingService.find_mapping()`
sa dummy `TariffMapping` objektom. Test provjerava da `DeclarationDecisionService`
korektno adaptira mapping kandidat, ne da baza sadrzi odredjeni zapis.

**Izmjene:**
- `tests/unit/test_declaration_decision_service.py:69-91` — monkeypatch sa dummy mappingom
- Test sada assert-uje konkretnu vrijednost `"84821000"` umjesto `!= ""`

### Problem 2: evaluate_line mutacija postojeceg decision_state

**Problem:** `evaluate_line()` je direktno mutirao `line.decision_state` (postavljao
`state.tariff = fd` itd.), iako je dokumentovan kao read-only.

**Popravka:** `evaluate_line()` sada:
1. Ako `line.decision_state` postoji, pravi kopiju preko `copy.deepcopy()`
2. Evaluaciju radi na kopiji
3. Vraca kopiju — ne mijenja `line.decision_state`

**Izmjene:**
- `services/decision/declaration_decision_service.py:91-96` — `copy.deepcopy(existing)`
- Komentar preciziran: "ne mijenja InvoiceLine niti njegov decision_state"

**Novi test:** `test_evaluate_line_does_not_mutate_existing_decision_state`:
- Kreira potvrdjeni state na liniji
- Poziva evaluate_line()
- Potvrdjuje da originalni `line.decision_state` nije promijenjen (status, vrijednost, broj kandidata)
- Potvrdjuje da je vraceni state NOVI objekat (`is not existing_state`)

### Problem 3: Core sloj zavisi od services.agent

**Problem:** `core/decision/evidence.py` je importovao:
```python
from services.agent.validation.tariff_decision_model import has_meaningful_source
```
Ovo rusi cilj "neutralni core model".

**Popravka:** `has_meaningful_source()` je lokalno implementirana u `core/decision/evidence.py`.
Funkcija je trivijalna (4 linije) i nema potrebe za posebnim utility modulom.

**Izmjene:**
- `core/decision/evidence.py` — import uklonjen, funkcija dodata inline (linije 9-11)
- `dist_client/core/decision/evidence.py` — sinkronizovano

---

## Test rezultati

```
tests/unit/test_declaration_decision_service.py ..... 23 passed
tests/unit/test_declaration_decision_model.py ........ 26 passed
tests/unit/test_evidence_model.py .................... 34 passed
tests/unit/test_agent_decision_regression.py ........ 12 passed
tests/unit/test_decision_characterization.py ........ 29 passed, 5 xfail
                                                    ---
                                            UKUPNO: 124 passed, 5 xfailed
```

Svi testovi prolaze bez žive baze (bazni testovi koriste monkeypatch).

---

## Provjera dist_client mirror-a

```powershell
diff core/decision/evidence.py dist_client/core/decision/evidence.py  # identicno
diff services/decision/declaration_decision_service.py dist_client/services/decision/declaration_decision_service.py  # identicno
```

---

## Sta nije dirano

- GUI — nijedan fajl
- Faza 4 integracije
- Auto-popuni / validacija ponašanje
- `tariff_decision_model.py` — `has_meaningful_source` i dalje postoji tamo (koristi se interno u `decide_tariff_match`)
- Ostali pozivaoci `has_meaningful_source` iz `services.agent.validation.tariff_decision_model` — njihovi importi nisu mijenjani

---

## Commit

| Hash | Poruka |
|------|--------|
| (pending) | fix(decision): Faza 2 popravke — read-only evaluate, core izolacija, mock testovi |
