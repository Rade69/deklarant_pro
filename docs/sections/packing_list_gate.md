---
section: packing_list_gate
file: services/import_service.py
---

## Svrha

Odlučuje da li je PDF datoteka "packing lista" (lista pakovanja) prije nego što se pošalje u registry. Ako jeste, čuva rezultat u memoriji i čeka odgovarajući invoice za kombinovanje.

## Zavisnosti i pretpostavke

- Poziva `_detect_pdf_format()` iz `smart_pdf_importer.py`
- Poziva `detect_packing_list()` iz `packing_list_parser.py`
- Pretpostavlja da packing lista dolazi **uz** odgovarajuću fakturu (ne samostalno)

## Pravila i granice

- Provjera se radi SAMO za PDF datoteke (Excel ne može biti packing lista)
- Ako je format PDF-a u `_KNOWN_VENDOR_FORMATS` → odmah vraća `None` (nije packing lista)
- `detect_packing_list()` radi keyword detekciju ("PACKING LIST", "P/L" itd.) u tekstu
- Ako je packing lista: `last_import_type = "packing_list"` — ovo triggera CASE 4 pri sljedećem importu

## Zašto ovako

Packing lista ima drugačiju strukturu od fakture (samo težine i paketi, bez cijena). Registry bi je tretirao kao nepoznati format i vratio bi loš rezultat. Kapija sprječava ovaj slučaj.
