# Agent report: Blagić-Loren multi-par import fix

**Datum**: 2026-05-19  
**Grana**: dev  
**Zadatak**: Istraži i popravi bug gdje samo 2 od 7 Blagić-Loren faktura parova biva uvezeno

---

## Šta je urađeno

1. **Identificiran root cause**: race condition između worker threada i main threada oko singleton `ImportService` instance
2. **Fix**: `ProcessingWorker` sada kreira privatnu `ImportService` instancu umjesto singleton-a
3. **Safety net**: dodata `_normalize_finished_file_statuses` metoda u `AgentController`
4. **Guard poboljšanje**: `_on_file_started` provjerava da li je fajl već Completed/Skipped/Error prije ažuriranja na Processing
5. **Testovi**: dodana 2 nova test fajla, ukupno 9 novih testova

---

## Kako je urađeno

### Root cause analiza

`get_import_service()` vraća modul-level singleton:
```python
_import_service_instance: Optional[ImportService] = None

def get_import_service() -> ImportService:
    global _import_service_instance
    if _import_service_instance is None:
        _import_service_instance = ImportService()
    return _import_service_instance
```

`ImportService` ima dijeljeno stanje:
```python
self.last_import_result: Optional[...] = None
self.last_import_path: Optional[str] = None
self.last_import_type: Optional[str] = None
```

`ProcessingWorker.run()` je pozivao `get_import_service()` — ista instanca kao u main threadu (FakturaTab, dijalozi, itd.). Tok za kombinovanje parova je:
1. xlsx import → `last_import_type = "loren_excel"`
2. pdf import → CASE 1 provjeri `last_import_type == "loren_excel"` → kombinuje

Ako main thread između koraka 1 i 2 pozove `svc.import_file()` (npr. kroz `QApplication.processEvents()` unutar pipeline petlje), `last_import_type` se mijenja → CASE 1 ne prepoznaje par → standalone import → može proizvoditi 0 stavki → Error ili nepotpun import.

### Fix

```python
# PRIJE (race condition):
svc = get_import_service()
svc.clear_memory()

# POSLIJE (thread-safe):
svc = ImportService()  # privatna instanca
svc.clear_memory()
```

### Safety net: _normalize_finished_file_statuses

Dodana kao odbrana od stale stanja iz prethodnih run-ova. Ako fajl ima `status='Processing'` ALI ima `invoice_lines` (uvezene u prethodnom run-u), promoviše se u Completed:

```python
def _normalize_finished_file_statuses(self, files: list):
    for file_item in files:
        if file_item.status == 'Processing' and file_item.invoice_lines:
            file_item.status = 'Completed'
```

---

## Zašto

`ImportService` singleton je dizajniran za serijsku upotrebu (jedan fajl za drugim u main threadu). Worker thread koji ga koristi paralelno narušava pretpostavku serijske upotrebe. `last_import_type` je statefull mehanizam koji mora biti privatan za svaki import sesiju.

**Alternativa koja nije odabrana**: threading.Lock() oko singleton pristupa — previše kompleksno, mogući deadlock, i nepotrebno jer worker ne treba dijeliti stanje sa main threadom.

---

## Commitovi

| Hash | Opis |
|------|------|
| `4976f71` | fix(agent): ispravi race condition u worker importu — privatna ImportService instanca |
| `b1fb15f` | fix(importers): audit i popravka parsera — sigurnost i konzistentnost |
| `2535f6a` | docs: ažuriraj AGENTS.md, CLAUDE.md i korisničko uputstvo |

---

## Testovi

```
tests/unit/test_blagic_loren_agent_import.py::test_worker_private_instance_combines_all_three_pairs
  — 3 uzastopna para sa privatnom instancom, svi combined=True

tests/unit/test_agent_file_status_normalization.py::test_all_completed_normalizes_processing_file_with_lines
tests/unit/test_agent_file_status_normalization.py::test_all_completed_does_not_complete_processing_file_without_lines
  — _normalize_finished_file_statuses logika
```
