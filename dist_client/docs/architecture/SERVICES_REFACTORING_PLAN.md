# Plan refaktorisanja services/ foldera

**Datum:** April 2026  
**Cilj:** Premjestiti 24 flat .py fajla iz `services/` root-a u logičke sub-pakete.  
**Metoda:** Ista kao Faza 3 za `agent/` — premještanje + stub fajlovi za backward compat.

---

## Trenutno stanje

```
services/
├── admin/              ✅ već sređeno
├── agent/              ✅ već sređeno (Faze 1–4)
├── faktura/            ✅ već postoji
├── knowledge_base/     ✅ već postoji
├── naimenovanja/       ✅ već postoji (djelimično)
│
└── [24 flat fajla — PROBLEM]
```

---

## Predložena finalna struktura

```
services/
├── admin/
├── agent/
├── faktura/
├── knowledge_base/
├── naimenovanja/
├── tariff/             ← NOVA
├── validation/         ← NOVA
└── core/               ← NOVA
```

---

## Faza A — Neukorišćeni fajlovi (brisanje, nula rizika)

Ovi fajlovi nemaju nijednog importera — mogu se obrisati odmah.

| Fajl | Razlog |
|------|--------|
| `base_service.py` | Nema importa |
| `autocomplete_service.py` | Nema importa |
| `audit_service.py` | Nema importa |
| `plugin_service.py` | Duplikat od `admin/plugin_service.py` |
| `demo_service.py` | Nema importa |
| `tariff_kb_ingestor.py` | Nema importa (CLI alat, ne servis) |

**Provjera prije brisanja:** `grep -r "from services.X"` da potvrdi 0 importa.

---

## Faza B — Tariff grupa → `services/tariff/`

**Fajlovi za premještanje:**

| Fajl | Calleri | Broj callera |
|------|---------|-------------|
| `tarifa_service.py` | agent_controller.py, declaration_validator_service.py | 2 |
| `tariff_mapping_service.py` | declaration_assembly.py, naimenovanja/tariff_service.py, auto_fill_service.py, tariff_suggestion_service.py, hybrid_tariff_agent.py, tariff_intent_service.py, tariff_suggestion_dialog.py, naimenovanja_view.py, faktura_view.py, chat_worker.py, tariff_llm_worker.py | **11** |
| `tariff_tree_service.py` | agent_controller.py | 1 |

**Fajlovi koji idu uz njih (dependency chain):**

| Fajl | Ko ga koristi |
|------|---------------|
| `country_origin_validator.py` | tariff_mapping_service.py, auto_fill_service.py |
| `origin_statement_detector.py` | tariff_mapping_service.py, naimenovanja_service.py, 7 importera |
| `product_master_list.py` | declaration_assembly.py |

> ⚠️ `tariff_mapping_service.py` ima 11 callera — **najviši rizik** — stub fajl obavezan.
> ⚠️ `origin_statement_detector.py` koristi 7 importera direktno — stub obavezan.

**Stub fajlovi:** `services/tariff_mapping_service.py`, `services/tarifa_service.py`, itd.

---

## Faza C — Validation grupa → `services/validation/`

| Fajl | Calleri | Broj |
|------|---------|------|
| `validation_service.py` | faktura/validation_cache.py, faktura/validation_service.py, faktura_view.py | 3 |
| `preference_validator.py` | faktura_view.py | 1 |

> Relativno mali broj callera — niži rizik.

---

## Faza D — Core grupa → `services/core/`

| Fajl | Calleri | Broj |
|------|---------|------|
| `exceptions.py` | zaglavlje_service.py | 1 |
| `error_handler.py` | importers/pdf/importer.py, importers/excel_importer.py | 2 |

---

## Faza E — Premještanje u postojeće sub-pakete

| Fajl | Destinacija | Calleri |
|------|-------------|---------|
| `naimenovanja_service.py` | `naimenovanja/` | naimenovanja_controller.py, tab_factory.py |
| `create_naimenovanja_service.py` | `naimenovanja/` | faktura_view.py |
| `declaration_assembly.py` | `naimenovanja/` | faktura_view.py |

---

## Faza F — Samostalni fajlovi (ostaju ili idu u admin/)

| Fajl | Calleri | Odluka |
|------|---------|--------|
| `zaglavlje_service.py` | 7 callera | Ostaje u root ili ide u novi `services/zaglavlje/` |
| `sifarnici_service.py` | 3 callera | Ostaje u root ili ide u `admin/` |
| `import_service.py` | 4 callera | Ostaje — `faktura/import_service.py` je nova verzija |
| `import_worker.py` | 2 callera | Prati `import_service.py` |
| `export_service.py` | 2 callera | Prati `faktura/export_service.py` |

> `import_service.py` i `faktura/import_service.py` su **dvije različite klase** —
> root verzija je starija orchestrator, `faktura/` verzija je refaktorisana.
> Treba razjasniti koji je "pravi" prije premještanja.

---

## Redoslijed izvođenja

```
Faza A  →  Faza B  →  Faza C  →  Faza D  →  Faza E  →  Faza F
(brisanje)  (tariff)  (valid.)   (core)    (naim.)   (ostalo)
  0 rizika   visok    nizak      nizak      nizak      procjena
```

Svaka faza:
1. Premjesti fajlove
2. Kreiraj stub na staroj putanji
3. Pokreni testove (110 mora proći)
4. Commit

---

## Napomena o duplikatima faktura/

`services/faktura/` već ima sopstvene verzije:
- `faktura_service.py`
- `import_service.py` (re-exportuje iz services.import_service)
- `export_service.py` (wraps services.export_service)
- `validation_service.py`
- `error_handler.py`

Root verzije su **starije/parent klase** koje `faktura/` verzije nasljeđuju ili re-exportuju.
Ove **ne treba premještati** — treba samo razumjeti hijerarhiju.
