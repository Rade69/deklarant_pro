# Faza 0 — Sigurnosna analiza (Jedinstveni import workflow)

**Datum**: 2026-07-24
**Plan**: `docs/architecture/JEDINSTVENI_IMPORT_WORKFLOW_IMPLEMENTATION_PLAN.md`
**Status**: Završena — rizik LOW za sve simbole, implementacija može početi

---

## Cilj Faze 0

Potvrditi blast radius, scope lock i listu aktivnih pozivalaca za sve simbole
koje će zajednički import workflow mijenjati ili zamijeniti.

## Početno stanje

- Grana: `windows` (commit `0d1a5d5`)
- GitNexus indeks: svjež (24.7.2026 09:21, commit `0d1a5d5`)
- `git status`: samo untracked fajlovi, nema modificiranih
- Testovi: 932 passed, 58 skipped, 5 xfailed, 1 failed + 1 error (oba nepovezana)
- Fakture za testiranje: `H:\New folder\najavauvoza` (28 stavki, različiti dobavljači)

## Impact analiza — 8 simbola

Svi simboli su **LOW rizik** — nema HIGH/CRITICAL. Prema planu §16 Faza 0 korak 5,
obavezni `project_rooms` zapis se ne zahtijeva (pravi se samo za HIGH/CRITICAL).
Ovaj zapis je referenca za buduće faze.

### 1. `FakturaView._on_import_finished` (faktura_view.py:3263)

- **GitNexus impact**: LOW, 0 upstream
- **Stvarni pozivaoci** (ručna pretraga):
  - Qt signal: `self.import_worker.finished.connect(self._on_import_finished)` (faktura_view.py:2374)
- **Napomena**: GitNexus ne vidi Qt signal konekcije. Ovo je završni handler za
  pojedinačni ručni uvoz. Nema Python pozivalaca — aktivira ga samo worker signal.

### 2. `FakturaView._process_batch_records` (faktura_view.py)

- **GitNexus impact**: LOW, 1 upstream
- **Direktni pozivaoci**:
  - `_on_batch_done` (faktura_view.py) — CALLS
- **Napomena**: Ovo je handler za ručni grupni uvoz. Aktivira ga batch worker signal.

### 3. `AgentController._on_all_completed` (agent_controller.py:422)

- **GitNexus impact**: LOW, 0 upstream (DEGRADIRANO — propušta 2 pozivaoca!)
- **Stvarni pozivaoci** (ručna pretraga — plan §16 Faza 0 korak 4):
  - Qt signal: `self._worker.all_completed.connect(self._on_all_completed)` (agent_controller.py:300)
  - `_analiza_uvezi_action` (import_pipeline_service.py:188) — DIREKTNI poziv
  - `_analiza_auto_action` (import_pipeline_service.py:199) — DIREKTNI poziv
- **Napomena**: 2 od 3 pozivaoca nisu u GitNexus indeksu. Potvrđuje planovu napomenu
  o degradiranom indeksu i potrebi za ručnom pretragom.

### 4. `FakturaView._distribute_invoice_weights` (faktura_view.py)

- **GitNexus impact**: LOW, 3 upstream (2 direktna)
- **Direktni pozivaoci** (svi CALLS):
  - `_process_batch_records` (faktura_view.py) — grupni import
  - `_on_import_finished` (faktura_view.py) — pojedinačni import
  - `_on_batch_done` (faktura_view.py) — batch završetak

### 5. `FakturaView._check_partner_consistency` (faktura_view.py)

- **GitNexus impact**: LOW, 1 upstream
- **Direktni pozivaoci** (CALLS):
  - `_on_import_finished` (faktura_view.py) — samo pojedinačni import

### 6. `FakturaView._apply_import_result_to_header` (faktura_view.py)

- **GitNexus impact**: LOW, 3 upstream (2 direktna)
- **Direktni pozivaoci** (svi CALLS):
  - `_process_batch_records` (faktura_view.py) — grupni import
  - `_on_import_finished` (faktura_view.py) — pojedinačni import
  - `_on_batch_done` (faktura_view.py) — batch završetak
- **Napomena**: Agent poziva ovu metodu i direktno:
  `agent_controller.py:474`: `fw._apply_import_result_to_header(file_item)`
  (nije u GitNexus indeksu jer prelazi modul granicu preko getattr-like pristupa)

### 7. `FakturaView._is_same_combined_invoice` (faktura_view.py)

- **GitNexus impact**: LOW, 1 upstream
- **Direktni pozivaoci** (CALLS):
  - `_on_import_finished` (faktura_view.py) — samo pojedinačni import

### 8. `_puna_auto_pipeline` (import_pipeline_service.py)

- **GitNexus impact**: LOW, 1 upstream
- **Direktni pozivaoci** (CALLS):
  - `puna_auto_pipeline` (import_pipeline_service.py) — public wrapper

## Mapa aktivnih ulaza u završnu obradu importa

Tri pozivaoca moraju biti migrirana na zajednički tok:

```
Ručni pojedinačni:  worker.finished → _on_import_finished
                        ├── _check_partner_consistency
                        ├── _normalize_item_tariffs
                        ├── _distribute_invoice_weights
                        ├── _apply_import_result_to_header
                        ├── _is_same_combined_invoice
                        └── REPLACE/EXTEND logika + EUR1/PE2 dijalog

Ručni grupni:       worker batch → _on_batch_done → _process_batch_records
                        ├── _distribute_invoice_weights
                        └── _apply_import_result_to_header

Agent uvoz:         worker.all_completed → _on_all_completed
                    ili _analiza_uvezi_action / _analiza_auto_action (direktni poziv)
                        ├── _normalize_item_tariffs
                        ├── _apply_import_result_to_header (direktno preko fw)
                        ├── PE2/PE3/EUR1 dijalog po fakturi
                        └── _puna_auto_pipeline (puna automatizacija)
```

## Scope lock (šta se NE mijenja)

Prema planu §19:
- Specijalizovani parseri i detekcije
- Redoslijed ImportService parser pipeline-a
- Format InvoiceLine polja
- Pravila grupisanja naimenovanja
- Tarifni fuzzy threshold (0.92)
- Historijsko tarifno učenje
- XML builder
- Agent LLM provider i fallback
- QThread lifecycle politika
- Baza podataka i migracije

## Rizici i zaštite

| Rizik | Nivo | Zaštita |
|-------|------|---------|
| Agent poziva `_apply_import_result_to_header` direktno (van GitNexus) | MEDIUM | Faza 8 mora ukloniti i ovaj direktni poziv |
| `_on_all_completed` ima 2 skrivena pozivaoca (analiza→uvezi/auto) | LOW | Faza 8 migrira i analiza akcije |
| 3 različita ulaza u završnu obradu | MEDIUM | Svi moraju na zajednički servis (Faze 6,7,8) |
| Qt signal konekcije nisu u indeksu | LOW | Ručna pretraga završena za sve 8 simbola |

## Zaključak

Blast radius je uzak i kontrolisan:
- Sve 8 simbola je LOW rizik
- 0 procesa pogođeno
- 3 aktivna ulaza (pojedinačni, grupni, agent) jasno identifikovana
- Nema HIGH/CRITICAL — plan se može nastaviti Fazom 1 (karakterizacioni testovi)

Sljedeći korak: **Faza 1 — karakterizacioni i regresioni testovi** (testovi koji
dokumentuju trenutno i željeno stanje prije bilo kakve izmjene ponašanja).
