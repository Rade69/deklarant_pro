# SECTION: Priloženi dokumenti — zaštita od gubitka podataka pri reload-u

## Svrha
Sprječava da `_on_draft_data_changed` (koji se okida kad naim/faktura tab uradi `mark_dirty`)
prepiše tabelu priloženih dokumenata u zaglavlju prije nego korisnik stigne snimiti svoje edite.

## Problem koji je riješen
Workflow koji je guobio podatke:
1. Korisnik uveze XML → tabela se popuni (VOZ, PZT, DV1 ref-ovi prazni)
2. Korisnik upiše reference za VOZ, PZT, DV1
3. Korisnik klikne nešto u naim/faktura tabu → `mark_dirty()` → `_on_draft_data_changed`
4. `load_from_draft(draft)` → `_populate_attached_table` → BRIŠE sve upisane ref-ove!

## Rješenje — dva fixa

### Fix 1: `main_window._on_draft_data_changed`
Prije `load_from_draft` uvijek poziva `zaglavlje_tab.save_to_draft()`.
Tako draft ima najnovije stanje UI-a prije reload-a.

### Fix 2: `_populate_attached_table(clear_refs_on_import=False)`
Novi flag koji kontroliše brisanje ref-ova:

| Poziv | `clear_refs_on_import` | Efekat |
|---|---|---|
| XML uvoz (`_on_import_xml`) | `True` | Briše stale ref-ove za sve osim DIS/N380/OST/PE |
| `load_from_draft` | `False` (default) | Čuva sve reference iz drafta |

`set_data(data, _from_import=False)` prosljeđuje flag u `_populate_attached_table`.

## Zavisnosti i pretpostavke
- `main_window._on_draft_data_changed` okida se za SVAKI `draft.mark_dirty()` poziv
- `mark_dirty()` se poziva iz: `naimenovanja_view`, `faktura_view`, `naimenovanja_controller`, `import_pipeline_service`
- `zaglavlje_tab.save_to_draft()` ne smije baciti exception (silent try/except u main_window)

## Kodovi koji zadržavaju ref pri XML uvozu
`_PRESERVE_REFS = {"DIS", "N380", "OST", "PE1", "PE2", "PE3"}`
- DIS (dispozicija) — isti broj za cijelu pošiljku
- N380 (faktura) — broj fakture
- OST (ostali prateći dokumenti) — unesen ručno u naim tabu
- PE1/PE2/PE3 — iz Rb.44.4

## Fajlovi
- `gui/main_window.py` → `_on_draft_data_changed`
- `gui/tabs/zaglavlje_view.py` → `set_data(_from_import)`, `_populate_attached_table(clear_refs_on_import)`
- `gui/tabs/zaglavlje_controller.py` → `_on_import_xml` (poziva `set_data(_from_import=True)`)
