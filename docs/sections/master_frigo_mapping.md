---
section: master_frigo_mapping
file: importers/smart_pdf_importer.py
---

## Svrha

Pronalazi Excel fajl sa tarifnim brojevima i zemljama porijekla koji vrijedi za sve Master Frigo fakture u istom folderu. Excel fajl nije vezan za jednu fakturu — to je globalni "mapping".

## Zavisnosti i pretpostavke

- Excel mora biti u **istom folderu** kao PDF faktura
- Ime Excel fajla mora sadržati `"tarife"` ili `"porekla"` ili `"porijekla"` (case-insensitive)
- Master Frigo PDF fakture ne sadrže tarifne šifre niti zemlja — sve dolazi iz ovog Excel-a

## Pravila i granice

- Traži `.xlsx` fajlove (ne `.xls` ili `.xlsm`)
- Vraća prvi pronađeni matching fajl
- Ako nema matching fajla — vraća `None`, parser nastavlja bez mappinga (prazan `{}`)
- Greška pri čitanju Excel-a je non-fatal — `mapping = {}`

## Zašto ovako

Master Frigo periodično šalje ažurirani Excel sa svim šiframa. Umjesto da se Excel mora importovati posebno, auto-detekcija po imenu oslobađa korisnika od ručnog sparivanja.
