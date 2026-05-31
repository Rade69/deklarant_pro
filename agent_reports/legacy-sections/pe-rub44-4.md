# PE1/PE2/PE3 — Dokumenti porijekla (automatski iz Rb.44.4)

## Datum
2026-04-24

## Razlog
Korisnik želi da se podaci iz `le_rubrika44_4` (priložena isprava), koji sadrže šifre `PE1` (EUR.1 obrazac), `PE2` (izjava na fakturi) ili `PE3` (izjava ovlaštenog izvoznika) sa pripadajućim brojem, automatski prikažu u tabeli priloženih dokumenata u zaglavlju kao zasebni redovi. Format u `attached_document4` je `"{ŠIFRA} {broj}"` (npr. `"PE1 12345"`, `"PE2 INV-001"`).

Takođe, ovi unosi treba da ostanu i nakon ponovnog uvoza XML-a u zaglavlje.

## Sta je uradjeno

### 1. Automatsko dodavanje PE dokumenata pri unosu Rb.44.4
U `naimenovanja_view.py`, u `_on_rubrika44_4_finished`:
- Nakon što se tekst primijeni na sve iteme, poziva se `_sync_pe_docs_to_header()`
- Nova metoda `_sync_pe_docs_to_header()`:
  - Čita `attached_document4` sa svih naimenovanja
  - Parsira format `"ŠIFRA broj"` (npr. `"PE1 12345"`)
  - Skuplja samo PE1/PE2/PE3 unose, bez duplikata
  - Uklanja stare PE unose iz `draft.header_attached_documents`
  - Dodaje nove `AttachedDocument(code=šifra, name=naziv, number=broj, from_rule=PE1=True)`
  - Poziva `self.draft.mark_dirty()` da osvježi zaglavlje

### 2. Automatsko dodavanje pri kreiranju naimenovanja iz fakture
U `faktura_view.py`, u `_on_create_naimenovanja`:
- Nakon što se kreiraju naimenovanja (`create_smart_group`), poziva se `self._sync_pe_docs_to_header()`
- Ista logika kao u naimenovanjima — parsira `attached_document4` iz svih svježe kreiranih item-a

### 3. Automatsko dodavanje nakon PE2/EUR.1 dijaloga
U `import_pipeline_service.py`, u `_apply_eur1_to_naimenovanja`:
- Nakon što se `attached_document4` ažurira na stavkama, poziva se `_sync_pe_docs_to_header(ctrl)`
- Pomoćna funkcija `_sync_pe_docs_to_header` je dodata u isti fajl

### 4. PE dokumenti prilikom uvoza XML-a u zaglavlje
U `zaglavlje_controller.py`, u `_on_import_xml`:
- Dodata je logika koja čita PE1/PE2/PE3 iz `draft.header_attached_documents` i dodaje ih u `data['attached_documents']` prije nego se pozove `view.set_data(data)`

### 5. PE šifre zadržavaju referencu nakon uvoza XML-a
U `zaglavlje_view.py`, u `_populate_attached_table`:
- Dodate `"PE1"`, `"PE2"`, `"PE3"` u listu šifri koje zadržavaju referencu (pored `"DIS"`, `"N380"`, `"OST"`)
- Tako se prilikom ponovnog uvoza XML-a, PE reference ne resetuju na prazno

## Fajlovi
| Fajl | Izmjena |
|------|---------|
| `gui/tabs/naimenovanja_view.py` | Dodata `_sync_pe_docs_to_header()`; `_on_rubrika44_4_finished` poziva sinhronizaciju |
| `gui/tabs/faktura_view.py` | Dodata `_sync_pe_docs_to_header()`; poziva se nakon kreiranja naimenovanja |
| `gui/tabs/agent/services/import_pipeline_service.py` | Dodata `_sync_pe_docs_to_header(ctrl)`; poziva se nakon EUR.1/PE2 ažuriranja |
| `gui/tabs/zaglavlje_controller.py` | Dodato prenošenje PE1/PE2/PE3 u `data['attached_documents']` prilikom importa XML-a |
| `gui/tabs/zaglavlje_view.py` | Dodate `"PE1"`, `"PE2"`, `"PE3"` u listu šifri koje zadržavaju referencu |

## Medjuzavisnosti

### Unutar aplikacije
- `naimenovanja_view.py:_on_rubrika44_4_finished` → `_sync_pe_docs_to_header()` → dodaje PE u `draft.header_attached_documents`
- `faktura_view.py:_on_create_naimenovanja` → `_sync_pe_docs_to_header()` → dodaje PE u `draft.header_attached_documents`
- `import_pipeline_service.py:_apply_eur1_to_naimenovanja` → `_sync_pe_docs_to_header(ctrl)` → dodaje PE u `draft.header_attached_documents`
- `draft.mark_dirty()` → `MainWindow._on_draft_data_changed` → `zaglavlje_tab.load_from_draft()`
- `zaglavlje_service.py:load_from_draft()` → čita `draft.header_attached_documents` i dodaje u `data['attached_documents']`
- `zaglavlje_controller.py:_on_import_xml` → prenosi PE iz draft-a u `data['attached_documents']` prilikom uvoza XML-a
- `zaglavlje_view.py:_populate_attached_table` → prikazuje PE u tabeli (zadržava referencu)

### Reference u kodu
- `gui/tabs/naimenovanja_view.py:2730` — `_on_rubrika44_4_finished`
- `gui/tabs/naimenovanja_view.py:2759` — `_sync_pe_docs_to_header`
- `gui/tabs/faktura_view.py:2668` — poziv `_sync_pe_docs_to_header` nakon kreiranja naimenovanja
- `gui/tabs/faktura_view.py:3437` — `_sync_pe_docs_to_header` definicija
- `gui/tabs/agent/services/import_pipeline_service.py:334` — poziv `_sync_pe_docs_to_header` u `_apply_eur1_to_naimenovanja`
- `gui/tabs/agent/services/import_pipeline_service.py:338` — `_sync_pe_docs_to_header` definicija
- `gui/tabs/zaglavlje_controller.py:525` — PE logika u `_on_import_xml`
- `gui/tabs/zaglavlje_view.py:2043` — `_populate_attached_table` (šifre koje zadržavaju referencu)
- `services/zaglavlje_service.py:657` — `load_from_draft` (čitanje `header_attached_documents`)
- `core/draft/draft.py:440` — `header_attached_documents` polje

## Tok podataka

### Ručni unos u naimenovanjima
```
Korisnik unese "PE1 12345" u le_rubrika44_4
  → _on_rubrika44_4_finished
    → primijeni na sve iteme
    → _sync_pe_docs_to_header()
      → parsira "PE1 12345" → (šifra="PE1", broj="12345")
      → dodaje AttachedDocument(code="PE1", number="12345") u draft.header_attached_documents
      → draft.mark_dirty()
        → MainWindow._on_draft_data_changed
          → zaglavlje_tab.load_from_draft(draft)
            → zaglavlje_service.load_from_draft(draft) → data['attached_documents'] uključuje PE
              → zaglavlje_view.set_data(data)
                → _populate_attached_table() → prikazuje PE red u tabeli
```

### Automatski nakon kreiranja naimenovanja
```
Faktura → kreiraj naimenovanja
  → create_smart_group() → items[].attached_document4 = "PE1 12345"
  → _sync_pe_docs_to_header()
    → isti tok kao iznad
```

### Automatski nakon EUR.1/PE2 dijaloga
```
Import fakture → EUR.1/PE2 dijalog
  → _apply_eur1_to_naimenovanja → items[].attached_document4 = "..."
  → _sync_pe_docs_to_header(ctrl)
    → isti tok kao iznad
```
