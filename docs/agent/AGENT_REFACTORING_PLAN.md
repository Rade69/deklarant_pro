# Plan refaktorisanja `services/agent/`

**Kreiran:** April 2026  
**Kontekst:** Podsjetnik za Claude — nastavak refaktorisanja agent foldera  
**Trenutno stanje:** 22 fajla, ~8,057 linija, jedan ravan folder

---

## Trenutna analiza

### Veličine fajlova

| Fajl | Linija | Status |
|------|--------|--------|
| `declaration_validator_service.py` | 898 | aktivan |
| `historical_learning_service_safe.py` | 727 | aktivan, najviše korišten |
| `exporter_xml_indexer.py` | 760 | aktivan |
| `feedback_loop_service.py` | 602 | **MRTAV KOD** — niko ne uvozi |
| `enhanced_tariff_suggestion_service.py` | 600 | aktivan |
| `hybrid_matching_service.py` | 589 | aktivan |
| `supplier_profiling_service.py` | 477 | aktivan |
| `tariff_intent_service.py` | 438 | aktivan |
| `xml_template_service.py` | 342 | aktivan |
| `declaration_search_service.py` | 320 | aktivan |
| `naimenovanja_intent_service.py` | 284 | aktivan |
| `tariff_rag_service.py` | 269 | aktivan |
| `naimenovanja_review_service.py` | 251 | aktivan |
| `chat_memory_service.py` | 248 | aktivan |
| `hybrid_tariff_agent.py` | 228 | aktivan |
| `ai_decision_service.py` | 222 | jedini korisnik: hybrid_tariff_agent |
| `merge_intent_service.py` | 185 | aktivan |
| `compliance_check_service.py` | 234 | aktivan |
| `intent_classifier.py` | 141 | aktivan |
| `batch_processor.py` | 139 | **MRTAV KOD** — niko ne uvozi |
| `text_normalizer.py` | 103 | jedini korisnik: tariff_rag_service |
| `__init__.py` | 0 | prazan |

### Mapa zavisnosti (ko koga uvozi)

```
UNUTAR services/agent/:
batch_processor         → hybrid_tariff_agent        [MRTAV]
enhanced_tariff_sug.    → hybrid_tariff_agent
                        → historical_learning_safe
                        → supplier_profiling_service
                        → hybrid_matching_service
hybrid_matching_service → historical_learning_safe
hybrid_tariff_agent     → tariff_rag_service
                        → ai_decision_service
supplier_profiling      → historical_learning_safe (2x)
tariff_rag_service      → text_normalizer
declaration_validator   → supplier_profiling_service
                        → historical_learning_safe

IZVANA (gui/ i services/):
historical_learning_safe    ← 6 mjesta (najviše korišten)
declaration_validator       ← 3 mjesta
tariff_rag_service          ← 2 mjesta
supplier_profiling_service  ← 2 mjesta
naimenovanja_review_service ← 2 mjesta
exporter_xml_indexer        ← 2 mjesta
ostali                      ← po 1 mjesto svaki
```

---

## Problemi koje treba riješiti

1. **Mrtav kod** — `feedback_loop_service.py` (602 linije) i `batch_processor.py` (139) niko ne uvozi
2. **Mikrofajlovi** — `text_normalizer.py` (103 linije) postoji samo za jednog korisnika
3. **Parcijalna duplikacija** — `ai_decision_service.py` jedino koristi `hybrid_tariff_agent.py`
4. **Ravan folder** bez strukture — 22 fajla u jednom direktorijumu teško je pratiti
5. `enhanced_tariff_suggestion_service.py` i `hybrid_matching_service.py` su usko vezani (isti concern)
6. `declaration_validator_service.py` (898 linija) + `compliance_check_service.py` (234) — isti concern, dva fajla

---

## Plan refaktorisanja (4 faze)

### Faza 1 — Brisanje mrtvog koda
**Rizik: NULTI | Trajanje: 15 minuta**

Brisati:
- `feedback_loop_service.py` — 602 linije, niko ga ne uvozi, nema git historije korišćenja
- `batch_processor.py` — 139 linija, niko ga ne uvozi

**Provjera prije brisanja:**
```bash
grep -rn "feedback_loop_service\|FeedbackLoop\|batch_processor\|BatchProcessor" \
  --include="*.py" . | grep -v "__pycache__" | grep -v "services/agent/feedback\|services/agent/batch"
```
Rezultat mora biti prazan.

---

### Faza 2 — Konsolidacija mikrofajlova
**Rizik: NIZAK | Trajanje: 30 minuta**

#### 2a. `text_normalizer.py` → u `tariff_rag_service.py`

`TextNormalizer` klasa (103 linije) jedino koristi `tariff_rag_service.py`.  
Premjestiti klasu na početak `tariff_rag_service.py`, obrisati `text_normalizer.py`.

Jedina promjena importa:
```python
# tariff_rag_service.py — ukloniti:
from services.agent.text_normalizer import TextNormalizer
# Klasa seli se direktno u ovaj fajl
```

#### 2b. `ai_decision_service.py` → u `hybrid_tariff_agent.py`

`AIDecisionService` klasa (222 linije) jedino koristi `hybrid_tariff_agent.py`.  
Premjestiti klasu na početak `hybrid_tariff_agent.py`, obrisati `ai_decision_service.py`.

Jedina promjena importa:
```python
# hybrid_tariff_agent.py — ukloniti:
from services.agent.ai_decision_service import AIDecisionService
# Klasa seli se direktno u ovaj fajl
```

#### 2c. `compliance_check_service.py` → u `declaration_validator_service.py`

`ComplianceCheckService` (234 linije) i `DeclarationValidatorService` (898 linija) rade isti posao.  
Agent controller uvozi `ComplianceCheckService` direktno — import ostaje isti zahvaljujući aliasu.

Na kraju `declaration_validator_service.py` dodati:
```python
# Backward compat alias
ComplianceCheckService = DeclarationValidatorService
```

**Provjera:**
```bash
grep -rn "ComplianceCheckService" --include="*.py" gui/ services/ | grep -v "__pycache__"
# Mora raditi i dalje bez promjena u agent_controller.py
```

---

### Faza 3 — Reorganizacija u sub-pakete
**Rizik: SREDNJI | Trajanje: 2-3 sata**

Ciljna struktura:

```
services/agent/
│
├── __init__.py              ← Javni API (re-exports)
│
├── chat/                    ← Chat pipeline (sve koristi agent_controller)
│   ├── __init__.py
│   ├── intent_classifier.py
│   ├── chat_memory_service.py
│   ├── tariff_intent_service.py
│   ├── naimenovanja_intent_service.py
│   ├── merge_intent_service.py
│   └── declaration_search_service.py
│
├── tariff/                  ← Tariff suggestion pipeline
│   ├── __init__.py
│   ├── hybrid_tariff_agent.py    (+ ai_decision inlined)
│   ├── tariff_rag_service.py     (+ text_normalizer inlined)
│   ├── hybrid_matching_service.py
│   └── enhanced_tariff_suggestion_service.py
│
├── learning/                ← Supplier learning i historija
│   ├── __init__.py
│   ├── historical_learning_service_safe.py
│   ├── exporter_xml_indexer.py
│   └── supplier_profiling_service.py
│
└── validation/              ← Validacija i review
    ├── __init__.py
    ├── declaration_validator_service.py  (+ compliance inlined)
    ├── naimenovanja_review_service.py
    └── xml_template_service.py
```

#### Kritično pravilo za Fazu 3

**Svi importi izvana moraju ostati nepromijenjeni.**  
To se postiže kroz `services/agent/__init__.py` koji re-exportuje sve:

```python
# services/agent/__init__.py
from services.agent.chat.intent_classifier import IntentClassifier
from services.agent.chat.chat_memory_service import ChatMemoryService
from services.agent.tariff.hybrid_tariff_agent import HybridTariffAgent
from services.agent.learning.historical_learning_service_safe import (
    HistoricalLearningServiceSafe,
    HistoricalLearningService,
    enhance_preference_logic,
    get_historical_service,
)
# ... itd.
```

Alternativno — u svakom sub-paketu `__init__.py` dodati compat importse:
```python
# services/agent/chat/__init__.py
# Ništa (importi idu direktno na modul)

# Ali stari import "from services.agent.intent_classifier import ..." NEĆE raditi!
# Mora se dodati proxy u services/agent/__init__.py
```

#### Redoslijed premještanja (bezbjedan)

1. Kreirati foldere i prazne `__init__.py`
2. Premjestiti `chat/` fajlove (najmanje zavisnosti)
3. Premjestiti `learning/` fajlove
4. Premjestiti `validation/` fajlove
5. Premjestiti `tariff/` fajlove (najviše internih zavisnosti)
6. Ažurirati `services/agent/__init__.py` sa svim re-exportima
7. Pokrenuti testove i provjeru importa

**Provjera između svakog koraka:**
```bash
python3 -c "from services.agent.X import Y; print('OK')"
```

---

### Faza 4 — Konsolidacija tariff suggestion (opciono)
**Rizik: SREDNJI-VISOK | Trajanje: 4-6 sati**

`enhanced_tariff_suggestion_service.py` (600) i `hybrid_matching_service.py` (589)  
su usko vezani — `enhanced` uvozi `hybrid` i dodaje sloj iznad njega.

Opcija A — Spojiti u jedan fajl `tariff_suggestion_service.py` (~900 linija):
- Eliminira jedan nivo indirekcije
- Lakše debugovati
- Jedan import za sve callere

Opcija B — Ostaviti kao jest (dva fajla, jasna hijerarhija):
- Manje rizika
- Svaki ima svoju odgovornost

**Preporuka:** Opcija B dok ne bude konkretnog razloga za spajanje.

---

## Metrike cilja

| Metrika | Sada | Nakon Faze 1+2 | Nakon Faze 3 |
|---------|------|-----------------|--------------|
| Broj fajlova u agent/ | 22 | 17 | 17 (raspoređeno) |
| Ukupno linija | 8,057 | ~7,200 | ~7,200 |
| Mrtav kod | 741 linija | 0 | 0 |
| Mikrofajlovi (<150 linija) | 3 | 0 | 0 |
| Max dubina foldera | 1 | 1 | 2 |

---

## Redoslijed prioriteta

| Faza | Trajanje | Rizik | Preporuka |
|------|----------|-------|-----------|
| 1 — Brisanje mrtvog koda | 15 min | Nulti | **Odmah** |
| 2 — Konsolidacija mikrofajlova | 30 min | Nizak | **Odmah** |
| 3 — Sub-paketi | 2-3 h | Srednji | Kad ima vremena |
| 4 — Tariff konsolidacija | 4-6 h | Srednji-visok | Samo ako bude potrebe |

---

## Kako pokrenuti po povratku

1. Pročitaj ovaj fajl
2. Pokreni: `grep -rn "feedback_loop_service\|batch_processor" --include="*.py" . | grep -v "__pycache__"` da potvrdiš da su još uvijek nekorišćeni
3. Kreni od Faze 1

---

## Napomena o testovima

Prije Faze 3 pokrenuti postojeće testove:
```bash
python3 -m pytest tests/ -x -q 2>&1 | tail -20
```

I provjeriti da aplikacija startuje:
```bash
./launch.sh  # ili python3 run.py
```
