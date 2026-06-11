# Faza 3 - istorijski prijedlozi tarifa: izvor i pouzdanost

## Kontekst

Realizovan je handoff iz `agent_tasks/2026-06-10_faza3-handoff.md`.
Problem je bio u tome sto se placeholder izvori istorije (`HISTORIJA`, `+`, `A`, prazan string) u validacionom dijalogu mogu prikazati kao da su legitiman istorijski izvor.

## Sta je promijenjeno

- `services/agent/validation/evidence_model.py`
- `dist_client/services/agent/validation/evidence_model.py`
- `gui/tabs/agent/widgets/tariff_validation_dialog.py`
- `dist_client/gui/tabs/agent/widgets/tariff_validation_dialog.py`
- `tests/unit/test_evidence_model.py`
- `tests/unit/test_historical_tariff_validation.py`
- `tests/unit/test_tariff_validation_dialog.py`

## Odluke

`evidence_from_tariff_decision()` sada prvo provjerava `has_meaningful_source(source)`.
Ako izvor nije smislen, evidence ostaje `DecisionConfidence.UNKNOWN` i koristi `DecisionSource.TARIFF_DATABASE`, bez obzira na to sto decision model moze vratiti `show_strong`.

Ova odluka je namjerna: decision model govori da li prijedlog vrijedi prikazati korisniku, ali evidence model govori koliko smijemo vjerovati porijeklu tog prijedloga. Placeholder poput `HISTORIJA` nije dokaz istog izvoznika.

Dodan je helper `tariff_confidence_label()` za UI prevod:

- `CONFIRMED_FROM_SAME_EXPORTER_HISTORY` -> `jak`
- `SUGGESTED_BY_SIMILARITY` -> `srednji`
- `WEAK_GUESS` -> `slab`
- `UNKNOWN` -> `nepoznat`

Validacioni dijalog sada za UNKNOWN evidence prikazuje:

`izvor nepoznat - nije potvrdjena historija`

i blokira dugme "Svi jaki prihvaceni" za takve prijedloge. Rucno prihvatanje pojedinacnog prijedloga ostaje moguce, jer korisnik i dalje moze svjesno odluciti.

## Sta nije dirano

Namjerno nisu mijenjani:

- `services/agent/validation/historical_tariff_search_service.py::_search_one()`
- `services/agent/validation/historical_tariff_search_service.py::_execute()`
- `services/agent/validation/tariff_decision_model.py`
- exporter-scoped learning servisi

Razlog: handoff je vec potvrdio da su hard filter po izvozniku i exporter-scoped ucenje ranije rijeseni. Ova faza je samo zatvarala UI/evidence rupu za nepoznat izvor.

## Provjere

Pokrenuto:

```powershell
python -m pytest tests/unit/test_evidence_model.py tests/unit/test_historical_tariff_validation.py tests/unit/test_tariff_validation_dialog.py -v
```

Rezultat:

```text
54 passed
```

Pokrenuto:

```powershell
.\dist_client\.venv\Scripts\python.exe -m py_compile services\agent\validation\evidence_model.py gui\tabs\agent\widgets\tariff_validation_dialog.py dist_client\services\agent\validation\evidence_model.py dist_client\gui\tabs\agent\widgets\tariff_validation_dialog.py tests\unit\test_evidence_model.py tests\unit\test_historical_tariff_validation.py tests\unit\test_tariff_validation_dialog.py
```

Rezultat: bez greske.

GitNexus:

- Pre-change impact za `evidence_from_tariff_decision`: CRITICAL, jer je centralna funkcija za evidence mapping.
- Pre-change impact za `_can_accept_all`: LOW.
- `detect_changes(scope="all")`: medium, affected processes 2. U izvjestaju se vide i ranije nevezane promjene u radnom stablu, zato se commit treba raditi selektivno samo za Faza 3 fajlove.

## Commiti

| Commit | Opis |
| --- | --- |
| `b265350` | Evidence mapping: nepoznati/placeholder izvori postaju UNKNOWN + testovi |
| `b2d786e` | UI dijalog: prikaz jak/srednji/slab/nepoznat i blokada "Svi jaki" za UNKNOWN |
