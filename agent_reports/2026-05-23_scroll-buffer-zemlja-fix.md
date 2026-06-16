# Agent Report: Fix nestajanja reda pri unosu zemlja_porijekla

**Datum:** 2026-05-23  
**Commit:** 42a59fc

---

## Problem

Kada korisnik upiše nešto u kolonu `zemlja_porijekla` u Faktura tabu (npr. za kese stavke KG Fashion invoice 25-294/2026), jedan od redova nestane s ekrana čim se pritisne Enter/Tab.

## Uzrok

Dva koda u interakciji:

**1. `_install_bottom_scroll_buffer`** — proširuje `scrollbar.maximum()` za jedan `row_h` svaki put kad `rangeChanged` opali:
```python
def _extend_range(mn, mx):
    target = mx + row_h
    scrollbar.setMaximum(target)  # ← forsira extra scroll space
```

**2. `_on_selection_changed`** — zvao `scrollToBottom()` kad je odabran zadnji red:
```python
if current == self.table.rowCount() - 1:
    self.table.scrollToBottom()  # ← skroluje na prošireni max!
```

Za tablicu sa 2 reda koji stanu u viewport:
- Normalni `scrollbar.maximum()` = 0 (sadržaj stane)
- Buffer forsira maximum = 48px (jedan row_h)
- `scrollToBottom()` → `setValue(48)` → sadržaj se pomjera gore za 48px
- Gornji red (0-48px) nestaje s ekrana

Podaci u `invoice_lines` su bili netaknuti — čisto vizuelni scroll artefakt.

## Dijagnoza

Dodani privremeni debug printovi u `_load_data_from_draft` i `_on_item_changed`. Stack trace pokazao da nije bilo ponovnog poziva `_load_data_from_draft` pri editovanju — dakle nije reload problem. Uzrok je bio scroll ponašanje.

## Rješenje

```python
# Staro:
self.table.scrollToBottom()

# Novo:
from PySide6.QtWidgets import QAbstractItemView
self.table.scrollTo(self.table.currentIndex(), QAbstractItemView.EnsureVisible)
```

`EnsureVisible` skroluje minimum potrebno da tekući red bude vidljiv, bez da koristi prošireni scrollbar maximum.

## Fajlovi izmijenjeni

| Fajl | Promjena |
|------|----------|
| `gui/tabs/faktura_view.py` | `scrollToBottom()` → `scrollTo(EnsureVisible)` u `_on_selection_changed` |

## Commitovi

| Hash | Opis |
|------|------|
| `42a59fc` | fix(faktura): zamijeni scrollToBottom sa EnsureVisible u _on_selection_changed |
