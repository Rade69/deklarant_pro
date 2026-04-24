# OST — Ostali prateći dokumenti (automatski iz Rb.40.3)

## Datum
2026-04-23

## Commit
8c1a544

## Razlog
Korisnik želi da se sadržaj iz `le_rubrika40_3` (broj prethodnog dokumenta) automatski prikaže u tabeli priloženih dokumenata u zaglavlju, kao red sa šifrom `OST` (Ostali prateći dokumenti) i referencom = broj iz Rb.40.3. Takođe, OST treba da zadrži referencu nakon uvoza XML-a (kao DIS i N380).

## Sta je uradjeno

### 1. Automatsko dodavanje OST pri unosu Rb.40.3
U `naimenovanja_view.py`, u `_on_rubrika40_3_finished`:
- Kada korisnik unese broj u `le_rubrika40_3`, dodaje se `AttachedDocument(code="OST", name="Ostali prateći dokumenti", number=text)` u `draft.header_attached_documents`
- Ako OST već postoji, ažurira mu se `number`
- Nakon izmjene poziva se `self.draft.mark_dirty()` koji okida `_on_draft_data_changed` u `MainWindow`, a on poziva `zaglavlje_tab.load_from_draft()` da osvježi prikaz

### 2. OST prilikom uvoza XML-a u zaglavlje
U `zaglavlje_controller.py`, u `_on_import_xml`:
- Nakon N380, dodata je logika koja čita OST iz `draft.header_attached_documents` i dodaje ga u `data['attached_documents']` prije nego se pozove `view.set_data(data)`

### 3. OST zadržava referencu nakon uvoza XML-a
U `zaglavlje_view.py`, u `_populate_attached_table`:
- Dodat `"OST"` u listu šifri koje zadržavaju referencu (pored `"DIS"` i `"N380"`)
- Tako se prilikom ponovnog uvoza XML-a, OST referenca ne resetuje na prazno

### 4. Editabilnost te_r31_opis i te_r31_opis_2
U `naimenovanja_view.py`, u `_populate_tariff_description`:
- Uklonjene linije `setReadOnly(True)` za oba polja
- Sada su `te_r31_opis` i `te_r31_opis_2` editabilni uz zadržane boje (zelena za podbroj, plava za heading)

## Fajlovi
| Fajl | Izmjena |
|------|---------|
| `gui/tabs/naimenovanja_view.py` | Dodat OST u `_on_rubrika40_3_finished`; uklonjen `setReadOnly(True)` za te_r31_opis/te_r31_opis_2 |
| `gui/tabs/zaglavlje_controller.py` | Dodat OST u `data['attached_documents']` prilikom importa XML-a |
| `gui/tabs/zaglavlje_view.py` | Dodat `"OST"` u listu šifri koje zadržavaju referencu |

## Tok podataka
```
Korisnik unese broj u le_rubrika40_3
  → _on_rubrika40_3_finished
    → dodaje OST u draft.header_attached_documents
    → draft.mark_dirty()
      → MainWindow._on_draft_data_changed
        → zaglavlje_tab.load_from_draft(draft)
          → zaglavlje_service.load_from_draft(draft) → data['attached_documents'] uključuje OST
            → zaglavlje_view.set_data(data)
              → _populate_attached_table() → prikazuje OST red u tabeli
```
