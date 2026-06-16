# TariffFacade — Refaktoring tarifnih servisa

**Datum:** April 2026  
**Fajl:** `services/tariff_facade.py`

---

## Problem koji se rješava

Prije refaktora, 7 mjesta u GUI-u i servisnom sloju direktno instanziralo je
`TariffMappingService`, `TariffRAGService` ili `HybridTariffAgent`:

| Fajl | Koliko puta |
|------|-------------|
| `gui/tabs/naimenovanja_view.py` | 6× |
| `gui/tabs/faktura_view.py` | 3× |
| `gui/tabs/agent/widgets/tariff_llm_worker.py` | 2× |
| `gui/tabs/agent/widgets/chat_worker.py` | 1× |
| `services/naimenovanja/naimenovanja_service.py` | 1× |

**Posljedice:**
- Fuzzy indeks (`TariffMappingService`) se gradio iznova pri svakom pozivu — skupo
- GUI sloj je znao za internalne servise → teško mijenjanje
- Dodavanje novog izvora (npr. EU TARIC API) zahtijevalo bi izmjene u 7 fajlova

---

## Rješenje: Singleton fasada

```
TariffFacade (services/tariff_facade.py)
  │
  ├─ Level 1: TariffMappingService  — fuzzy baza znanja (brzo, bez mreže)
  ├─ Level 2: TariffRAGService      — PostgreSQL istorija + zvanična tarifa
  └─ Level 3: HybridTariffAgent     — Groq/Ollama AI (samo kad L1 i L2 nisu sigurni)
```

`TariffFacade` je singleton — gradi se jednom pri startu aplikacije. Fuzzy indeks
ostaje u memoriji između poziva.

---

## Javni API

```python
facade = TariffFacade.get_instance()

# Jedan prijedlog (za naimenovanja, chat)
result: TariffResult = facade.suggest(naziv_robe, product_code="", zemlja="")

# Batch (za auto-fill dugme u faktura_view)
results: list[TariffResult] = facade.batch_suggest(items)

# Validacija (provjera u zvanicna_tarifa, O(1) iz cache-a)
ok: bool = facade.validate(tarifni_broj)

# Učenje iz ručnih ispravki korisnika
facade.learn(product_code, naziv_robe, tarifni_broj, confidence)
```

### TariffResult dataclass

```python
@dataclass
class TariffResult:
    tarifni_broj: str        # npr. "84713000"
    confidence:   float      # 0.0 – 1.0
    source:       str        # "baza_znanja" | "rag" | "ai" | "nepoznat"
    needs_review: bool       # True ako confidence < THRESHOLD_REVIEW (0.60)
    valid_in_db:  bool       # True ako postoji u catalogs.zvanicna_tarifa
```

---

## Thresholds (pražnjevi pouzdanosti)

| Prag | Vrijednost | Značenje |
|------|-----------|----------|
| `THRESHOLD_DIRECT` | 0.85 | Prihvata bez pregleda |
| `THRESHOLD_REVIEW` | 0.60 | Ispod → `needs_review = True` |

Isti pragovi kao u `HybridTariffAgent` — fasada ih samo propagira.

---

## Tok odlučivanja u `suggest()`

```
1. TariffMappingService.find_mapping()
   ├─ confidence >= 0.85 → vrati odmah (source="baza_znanja")
   └─ confidence < 0.85 ili nema rezultata →

2. TariffRAGService.search(zemlja_porijekla=zemlja)
   ├─ top_result.confidence >= 0.80 → vrati (source="rag")
   └─ needs_ai=True →

3. HybridTariffAgent.decide_tariff()
      └─ vrati (source="ai")
```

---

## Izmijenjeni fajlovi (GUI)

Svi pozivi `TariffMappingService()` zamijenjeni su sa:

```python
from services.tariff_facade import TariffFacade
result = TariffFacade.get_instance().suggest(naziv, product_code, zemlja)
```

Pogođeni fajlovi:
- `gui/tabs/naimenovanja_view.py`
- `gui/tabs/faktura_view.py`
- `gui/tabs/agent/widgets/tariff_llm_worker.py`
- `gui/tabs/agent/widgets/chat_worker.py`
- `services/naimenovanja/naimenovanja_service.py`

---

## Šta nije promijenjeno

- `TariffMappingService`, `TariffRAGService`, `HybridTariffAgent` — interno nepromijenjeni
- Baza podataka — ništa se ne mijenja u shemi
- Logika parsiranja faktura — nema veze s ovim

---

## Backward compatibility

`services/tariff_mapping_service.py` (root stub) ostaje kao re-export
za stari kod koji još nije migriran. Može se ukloniti kada su svi
pozivači prešli na fasadu.
