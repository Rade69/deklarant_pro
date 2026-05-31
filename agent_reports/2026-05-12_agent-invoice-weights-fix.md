# Fix: Agent uvozni put nije punio invoice_weights — Agent Report

**Datum:** 2026-05-12  
**Commit:** 3c927b0

---

## Problem

Nakon implementacije per-invoice raspodjele težina (d143050), Codex analiza
je utvrdila da agent uvozni put **nije punio `draft.invoice_weights`**.

Konkretno: u `agent_controller.py` per-invoice petlja (linija 400) akumulira
`total_bruto_kg`/`total_neto_kg` (globalna suma), ali ne sprema per-invoice
mapu. Kad `_puna_auto_pipeline` pozove `fw._on_calculate_masses(auto=True)`,
metoda grupira stavke po `invoice_number` i traži težinu u `draft.invoice_weights`
— ali rječnik je prazan → sve fakture idu u fallback (toolbar total) = stari bug.

---

## Fix

Jedna linija u `agent_controller.py`, unutar per-invoice petlje, odmah
nakon akumulacije:

```python
# Zapamti per-invoice težinu — koristi se u _on_calculate_masses
if (bruto > 0 or neto > 0) and explicit_invoice_number:
    self.draft.invoice_weights[explicit_invoice_number] = (bruto, neto)
```

Ključ = `explicit_invoice_number` (isti string koji parser upisuje na
`line.invoice_number`) — konzistentno s GUI uvoznim putevima.

---

## Zašto `explicit_invoice_number`, ne `invoice_name`

```python
explicit_invoice_number = file_item.invoice_number   # parser string ili ""
invoice_name = explicit_invoice_number or Path(file_item.filepath).stem
```

- Ako parser ne izvuče broj: `explicit_invoice_number = ""`, linije nemaju
  `invoice_number` → idu u fallback (toolbar) u `_on_calculate_masses` → ispravno
- Ako parser izvuče broj: isti string u ključu i na linijama → konzistentno

---

## Stanje svih uvoznih puteva (poslije ovog fixa)

| Put | invoice_weights | Commit |
|-----|-----------------|--------|
| Single-file GUI (`_on_import_finished`) | ✅ | d143050 |
| Multi-file GUI (`_import_multiple_files`) | ✅ | d143050 |
| Agent petlja (`agent_controller.py`) | ✅ | 3c927b0 |

---

## Tabela commitova

| Hash | Opis |
|------|------|
| 3c927b0 | fix(agent): upiši invoice_weights pri agent uvozu faktura |
