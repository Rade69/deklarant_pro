---
section: master_frigo_mapping
files:
  - importers/smart_pdf_importer.py
  - importers/master_frigo_importer.py
---

## Svrha

Pronalazi Excel fajl sa tarifnim brojevima i zemljama porijekla koji vrijedi za sve Master Frigo fakture u istom folderu. Excel fajl nije vezan za jednu fakturu — to je globalni "mapping".

Pored pronalaženja mappinga, `_parse_master_frigo()` osigurava da agent ne obrađuje mapping Excel kao zasebnu fakturu i da su `exporter`/`importer` pravilno postavljeni na sve stavke.

## Zavisnosti i pretpostavke

- Excel mora biti u **istom folderu** kao PDF faktura
- Ime Excel fajla mora sadržati prepoznatljiv marker kao `"tarife"`, `"podela"`,
  `"porekla"`, `"poreklu"`, `"poreklo"`, `"porijekla"` ili `"porijeklu"` (case-insensitive)
- Master Frigo PDF fakture ne sadrže tarifne šifre niti zemlja — sve dolazi iz ovog Excel-a
- `convert_to_invoice_lines()` u `master_frigo_importer.py` postavlja samo `exporter`, ne i `importer`

## Pravila i granice

### Detekcija mapping Excel-a (`_find_master_frigo_mapping_xlsx`)

- Traži `.xlsx` fajlove (ne `.xls` ili `.xlsm`) u istom folderu kao PDF
- Vraća prvi pronađeni matching fajl
- Ako nema matching fajla — vraća `None`, parser nastavlja bez mappinga (prazan `{}`)
- Greška pri čitanju Excel-a je non-fatal — `mapping = {}`

### `consumed_paths` — sprječavanje duplih stavki u agentu

Kada agent obrađuje cijeli folder, mapping Excel (ime sadrži `tarife`/`porijekla`) bi bio prepoznat kao zaseban fajl za uvoz i generisao bi prazne/lažne stavke ili grešku.

**Pravilo:** Čim se mapping xlsx uspješno učita, dodaje se u `consumed_paths` na `ImportResult`:

```python
consumed = [xlsx_path]  # agent preskače ovaj fajl pri uvozu
```

Agent u `processing_worker.py` vidi `consumed_paths` i:
- Dodaje fajl u `consumed_files` set — ne procesira ga
- Retroaktivno postavlja eventualni prethodni file_item na `status='Skipped'`

Greška pri čitanju → `consumed` ostaje `[]` → agent može pokušati uvesti xlsx zasebno (non-fatal).

### `importer` na stavkama

`convert_to_invoice_lines()` u `master_frigo_importer.py` postavlja samo `exporter` (iz headera PDF-a). `importer` mora biti ručno dodan u `_parse_master_frigo()`:

```python
_exp = Party(name="MASTER FRIGO")
_imp = Party(name="MASTER FRIGO D.O.O. BANJA LUKA")
for line in invoice_lines:
    line.exporter = _exp
    line.importer = _imp
```

**Zašto oba polja:** Agent XML template lookup traži po paru (exporter + importer). Bez `importer` polja biralo bi pogrešan XML template.

## Zašto ovako

Master Frigo periodično šalje ažurirani Excel sa svim šiframa. Umjesto da se Excel mora importovati posebno, auto-detekcija po imenu oslobađa korisnika od ručnog sparivanja. `consumed_paths` mehanizam je jedini siguran način da agent ne vidi mapping Excel kao fakturu — bez toga agent obrađuje oba fajla zasebno i generiše duplikate ili garbage stavke.
