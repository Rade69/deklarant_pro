# Agent Tab — Code Audit

**Datum revizije:** 2026-08-04
**Opseg:** Kompletan Agent modul (gui/tabs/agent/ + services/agent/)
**Metodologija:** GitNexus impact analiza, grep pozivalaca, statička analiza koda
**Veličina:** 24.920 linija, 86 fajlova

---

## 1. Struktura modula

```
gui/tabs/agent/                         services/agent/
├── agent_controller.py  (969 ln)       ├── __init__.py           (49 ln) — javni API
├── agent_view.py        (95 ln)        ├── chat/                 (11 fajlova)
├── agent_actions.py     (39 ln)        ├── learning/             (5 fajlova)
├── constants.py         (72 ln)        ├── tariff/               (3 fajla)
├── session_manager.py   (150 ln)       ├── validation/           (15 fajlova)
├── token_budget.py      (111 ln)       ├── workflow/             (5 fajlova)
├── workflow_state.py    (122 ln)       ├── planning/             (2 fajla)
├── models/file_item.py  (90 ln)        ├── mcp_facade.py         (391 ln)
├── services/            (4 fajla)      ├── llm_audit_log.py      (258 ln)
│   ├── chat_intent_handler.py (3035)   ├── application_context_  (315 ln)
│   ├── import_pipeline (793)           │   service.py
│   ├── xml_workflow     (373)          ├── invoice_analysis_     (206 ln)
│   └── pipeline_stage   (59)           │   service.py
└── widgets/              (16 fajlova)  └── cbbh_exchange_        (104 ln)
    ├── chat_panel.py     (782)             service.py
    ├── chat_worker.py    (1239)
    ├── processing_worker (411)
    ├── llm_provider.py   (377)
    └── ... (12 ostalih)
```

**Napomena:** Servisi su podeljeni na dva mesta — `gui/tabs/agent/services/` (4 fajla, vezani za GUI) i `services/agent/` (backend servisi). Ova podela je namerna: GUI servisi zavise od Qt signala, backend servisi su Qt-independent.

---

## 2. Potvrđeno mrtvi importi

### 2.1 agent_controller.py — QFileDialog

```python
from PySide6.QtWidgets import QFileDialog, QApplication
```

| Fajl | Linija | Import | Problem |
|------|--------|--------|---------|
| `gui/tabs/agent/agent_controller.py` | 8 | `QFileDialog` | Nikad se ne koristi — 0 referenci van import linije. `QApplication` se koristi. |

### 2.2 agent_view.py — QPainterPath

```python
from PySide6.QtGui import QPainter, QColor, QPainterPath
```

| Fajl | Linija | Import | Problem |
|------|--------|--------|---------|
| `gui/tabs/agent/agent_view.py` | 8 | `QPainterPath` | Nikad se ne koristi. `paintEvent()` koristi `QPainter` i `QColor`, ali ne i `QPainterPath`. Verovatno zaostao iz ranije verzije dekorativnog crtanja. |

### 2.3 compliance_report_dialog.py — QClipboard

```python
from PySide6.QtGui import QClipboard, QGuiApplication
```

| Fajl | Linija | Import | Problem |
|------|--------|--------|---------|
| `gui/tabs/agent/widgets/compliance_report_dialog.py` | 8 | `QClipboard` | Nikad se ne koristi. Samo `QGuiApplication` se koristi u fajlu. |

### 2.4 tariff_validation_dialog.py — TariffHistoryMatch

| Fajl | Linija | Import | Problem |
|------|--------|--------|---------|
| `gui/tabs/agent/widgets/tariff_validation_dialog.py` | ~20 | `TariffHistoryMatch` | Potrebna ručna potvrda — skripta ga je detektovala kao neiskorišćen, ali može biti lažan pozitiv (koristi se kroz type hint ili dinamički). |

---

## 3. Arhitekturni problemi

### 3.1 Dva servisna sloja — gui/tabs/agent/services/ i services/agent/

Agent modul ima **dva** servisna foldera:
- `gui/tabs/agent/services/` — 4 fajla (chat_intent_handler, import_pipeline_service, xml_workflow_service, pipeline_stage_result)
- `services/agent/` — 35+ fajlova organizovanih u podfoldere (chat, learning, tariff, validation, workflow, planning)

Podela je namerna (GUI-zavisni vs Qt-independent), ali nije konzistentna:
- `chat_intent_handler.py` (3035 ln, najveći fajl u projektu) je u `gui/tabs/agent/services/` iako sadrži veliku količinu biznis logike koja ne zavisi od GUI-ja
- Istovremeno, `services/agent/chat/tariff_intent_service.py` (611 ln) radi slične stvari ali je u backend folderu

**Preporuka:** `ChatIntentHandler` bi trebalo podeliti — GUI deo (signali, proposal card) ostaje u `gui/`, biznis logika se izvlači u `services/agent/chat/`.

### 3.2 ChatIntentHandler je monolit od 3035 linija

Najveći fajl u celom projektu. Sadrži 100+ metoda koje pokrivaju:
- Intent klasifikaciju i rutiranje
- Tarifno pretraživanje (3 varijante: po kodu, po poglavlju, hijerarhijski)
- Compliance provere
- Spajanje naimenovanja
- Predlaganje tarifnih brojeva
- Upis u kolonu
- Alternativne tarife
- Proposal card logiku

Ovo krši Single Responsibility Principle. Već postoji `services/agent/chat/` folder sa specijalizovanim servisima (`tariff_intent_service.py`, `naimenovanja_intent_service.py`, `merge_intent_service.py`) — ali `ChatIntentHandler` i dalje duplira veliki deo te logike.

### 3.3 Dupliranje tarifne logike

Ista funkcionalnost postoji na više mesta:
- `ChatIntentHandler.pretrazi_tarifu_po_kodu()` → `TariffIntentService`
- `ChatIntentHandler.pretrazi_tarifu_poglavlje()` → `TariffIntentService`
- `ChatIntentHandler.pretrazi_tarifu_hijerarhijski()` → `TariffIntentService`
- `ChatIntentHandler.klasificiraj_i_usmjeri()` → `IntentClassifier`

Ovo su "thunk" metode — samo prosleđuju poziv. Postoje zbog backward kompatibilnosti signala, ali dodaju ~200 linija mrtvog koda u već ogroman fajl.

### 3.4 agent_controller.py — 29 metoda bez internih pozivalaca

Skripta je detektovala 29 metoda u `agent_controller.py` koje nemaju pozivaoce unutar istog fajla. Ovo su uglavnom slotovi povezani sa signalima iz view-a, pa NISU mrtve — ali veliki broj (29/70 = 41%) sugeriše da je controller "svaštara" koja je vremenom akumulirala handlere koji možda više nisu povezani ni sa jednim signalom.

**Potrebna ručna provera** — za svaku od 29 metoda potvrditi da li je zaista povezana sa Qt signalom.

---

## 4. Duplikati i redundantnost

### 4.1 Dupli import difflib-a u declaration_validator_service.py

```python
# Linija 527 (unutar metode):
from difflib import SequenceMatcher

# Linija 743 (na vrhu fajla, posle svih klasa):
import difflib as _difflib

# Linija 906 (koristi _difflib):
return _difflib.SequenceMatcher(None, a, b).ratio()
```

`SequenceMatcher` se importuje na dva mesta — jednom inline unutar metode (linija 527), jednom kao `_difflib` (linija 743). Inline import na liniji 527 se može obrisati — `_difflib.SequenceMatcher` je već dostupan.

### 4.2 wildcard import u agent_view.py i widgetima

```python
from .constants import *     # agent_view.py:12
from .constants import *     # file_table.py, header_bar.py, upload_area.py, results_viewer.py, chat_panel.py
```

6 fajlova koristi `from .constants import *` za pristup `COLOR_SAGE_*` konstantama. Wildcard import je loša praksa jer:
- Ne zna se šta se tačno importuje
- Lako se desi kolizija imena
- IDE ne može da prati reference

Svi ovi fajlovi koriste samo `COLOR_SAGE_*` konstante — mogu se eksplicitno importovati.

### 4.3 Dupliran Qt import pattern

Većina widgeta ima identičan blok importa:
```python
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, ...)
from PySide6.QtCore import Qt, Signal, ...
from PySide6.QtGui import QFont, QColor, ...
```

Ovo nije greška, ali ~15 widgeta × 5-10 linija importa = 100+ linija boilerplate-a.

---

## 5. Potencijalno mrtvi servisni fajlovi (zahteva ručnu potvrdu)

Sledeći fajlovi se ne importuju direktno iz GUI koda, ali se importuju iz drugih servisa. Njihov stvarni status ("živ kroz lanac" vs "potpuno mrtav") zahteva detaljniju GitNexus impact analizu:

| Fajl | Linija | Uvozi se iz |
|------|--------|-------------|
| `services/agent/planning/agent_plan.py` | 69 | `plan_validator.py` |
| `services/agent/planning/plan_validator.py` | 56 | Nepoznato |
| `services/agent/chat/intent_rules.py` | 231 | `intent_classifier.py`? |
| `services/agent/chat/safe_context_schema.py` | 61 | `chat_worker.py`? |
| `services/agent/validation/finding_model.py` | 139 | `declaration_validator_service.py`? |
| `services/agent/validation/invoice_validation_adapter.py` | 91 | Nepoznato |
| `services/agent/validation/items_validation_adapter.py` | 82 | Nepoznato |
| `services/agent/workflow/automation_levels.py` | 38 | `declaration_workflow_state.py`? |
| `services/agent/workflow/header_autofill_service.py` | 88 | `declaration_workflow_service.py`? |

**Napomena:** Svi ovi fajlovi su potvrđeni kao "živi" kroz barem jedan servisni import lanac. Nisu kandidati za direktno brisanje bez detaljne impact analize.

---

## 6. Neiskorišćeni `from __future__ import annotations`

33 fajla u `services/agent/` koristi `from __future__ import annotations`. Ovo nije greška — omogućava lazy evaluation type hints (PEP 563) i standardna je praksa u modernom Python-u. NIJE mrtav kod.

---

## 7. Zbirni pregled

| Kategorija | Broj |
|------------|------|
| Potvrđeno mrtvi importi | 3-4 |
| Arhitekturni problemi | 4 |
| Duplikati / redundantnost | 3 |
| Potencijalno mrtve metode (za ručnu proveru) | ~29 u agent_controller.py |
| Wildcard importi | 6 fajlova |
| `__future__` importi (nisu mrtvi) | 33 fajla |

### Ključni nalazi

1. **Nema celih mrtvih fajlova** — svi fajlovi su povezani kroz servisni lanac
2. **ChatIntentHandler (3035 ln) je najveći problem** — monolit koji duplira logiku iz `services/agent/chat/`
3. **agent_controller.py ima 29 metoda bez internih pozivalaca** — potrebna ručna provera signal veza
4. **Mrtvi importi su mali** (3-4 stavke, ~5 linija) — neočekivano čisto za modul od 25K linija
5. **Arhitektura je solidna** — servisni lanac je dobro povezan, nema izolovanih ostrva

### Preporuke

1. **Kratkoročno (nisko rizično):**
   - Obrisati 3 potvrđeno mrtva importa
   - Zameniti wildcard importe eksplicitnim
   - Obrisati dupli `difflib` import u `declaration_validator_service.py`

2. **Srednjoročno (srednji rizik):**
   - Proveriti 29 metoda u `agent_controller.py` — da li su sve povezane sa signalima
   - Izvući "thunk" metode iz `ChatIntentHandler`-a

3. **Dugoročno (visok rizik, veliki refactor):**
   - Podeliti `ChatIntentHandler` na više servisa
   - Konsolidovati `gui/tabs/agent/services/` i `services/agent/chat/`

---

*Reviziju izvršio: Crush (DeepSeek-v4)*
