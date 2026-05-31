# weight_guards servis — Agent Report

**Datum:** 2026-05-12  
**Commit:** dd86d86  
**Autor:** Codex (prihvatio Claude)

---

## Šta je urađeno

Codex je dodao novi helper servis `services/faktura/weight_guards.py` koji
rješava rubne slučajeve per-invoice raspodjele težina — ključevi faktura
koji se formalno razlikuju ali semantički su isti (" AB 123 " vs "ab123"),
sumnjivi fallback na toolbar total, i provjera konzistentnosti zbira masa.

---

## Novi servis: `weight_guards.py`

### `normalize_invoice_key(invoice_number) -> str`
Uklanja whitespace i pretvara u lowercase: `" AB 123 "` → `"ab123"`.
Koristi se pri svakom upisu i lookup-u u `draft.invoice_weights`.

### `normalized_invoice_weights(invoice_weights) -> dict`
Normalizuje sve ključeve u dictu — koristi se pri lookup-u u `_on_calculate_masses`.

### `group_lines_by_invoice(lines) -> (groups, no_invoice_lines, labels)`
Zamjenjuje inline `defaultdict` logiku u `_on_calculate_masses`. Čuva
originalni string u `labels` za prikaz korisniku.

### `is_suspicious_fallback(invoice_groups, no_invoice_lines) -> bool`
True ako deklaracija ima i fakturisane grupe i stavke bez broja fakture.
U manual modu: pita korisnika. U auto modu: preskače.

### `find_mass_total_mismatches(groups, weights, labels) -> list`
Provjera konzistentnosti — da li zbir bruto/neto stavki po fakturi
odstupa od `invoice_weights[key]`. Tolerancija: `max(0.05, n*0.001)` kg.
Rezultat se prikazuje kao upozorenje korisniku.

---

## Integrisano u

| Fajl | Promjena |
|------|----------|
| `faktura_view.py` | Upis s `normalize_invoice_key`; `_on_calculate_masses` koristi sve 4 guard funkcije |
| `agent_controller.py` | Upis s `normalize_invoice_key` |
| `services/faktura/__init__.py` | Eksportuje `normalize_invoice_key` |

---

## Testovi

`tests/unit/test_weight_guards.py` — 6 novih testova:
- normalize_invoice_key edge cases
- normalized_invoice_weights
- group_lines_by_invoice
- is_suspicious_fallback
- find_mass_total_mismatches

**Rezultat:** 19/19 prolaze (weight_guards + mass_calculator)

---

## Tabela commitova

| Hash | Opis |
|------|------|
| dd86d86 | feat(weight): weight_guards — normalizacija ključa, grupiranje i provjera zbira |
