---
section: known_vendor_formats
file: services/import_service.py
---

## Svrha

`_KNOWN_VENDOR_FORMATS` je skup string-keyeva koji identificiraju poznate vendor formate. Njegova jedina svrha je da spriječi lažnu detekciju packing liste: ako `_detect_pdf_format()` vrati format koji je u ovom skupu, PDF se ne šalje na `detect_packing_list()`.

## Zavisnosti i pretpostavke

- String-keyevi moraju biti identični onima koje vraća `_detect_pdf_format()` u `smart_pdf_importer.py`
- Svaki novi vendor parser koji ima vlastit format mora biti dodan ovdje, inače bi mogao biti pogrešno klasificiran kao packing lista

## Pravila i granice

- Ovaj skup se ažurira **ručno** svaki put kad se doda novi specijalizovani parser
- Nikad ne dodavati "generic" ili "packing_list" — to su generički, ne vendor formati
- Provjera se radi u `_try_import_as_packing_list()` i `_try_combine_with_previous()`

## Zašto ovako

Packing list detekcija (keyword-based) može lažno prepoznati sekcije u normalnim fakturama. Za poznate vendore znamo tačno koji parser koristiti pa preskačemo ovu detekciju.
