# Agent Report — Windows Deploy Sesija 2
**Datum:** 2026-05-31  
**Mašina:** Windows 11, `C:\Users\38765\Desktop\deklarant_pro`  
**Cilj:** Nastavak deploy sesije — otklanjanje bugova koji su onemogućavali pokretanje i ispravno funkcionisanje aplikacije

---

## Šta je urađeno

### 1. UTF-8 BOM u `.env` fajlu — app se spajala na localhost
**Problem:** Desktop ikonica pokretala aplikaciju ali se spajala na `localhost` umjesto na PostgreSQL server.  
**Uzrok:** Windows Notepad snimio `.env` fajl sa UTF-8 BOM (`\xef\xbb\xbf`) — python-dotenv ignorisao cijeli fajl, `DB_HOST` ostajao prazan, `pydantic-settings` koristio default `localhost`.  
**Fix:** BOM uklonjen sa `content[3:]`, `.env` zapisan bez BOM.  
**Dodatno:** Promijenjen `DB_HOST=localhost` jer je server .41 privremeno nedostupan.

---

### 2. `sys.stderr = None` crash pri pokretanju via `pythonw.exe`
**Problem:** Desktop ikonica otvarala app ali bez sadržaja (prazan prozor), bez ikakve poruke greške.  
**Uzrok:** `pythonw.exe` ne dodjeljuje terminal — `sys.stderr` je `None`. Preostalih 9 `sys.stderr.write()` poziva u `zaglavlje_view.py` i `naimenovanja_view.py` izazivali `AttributeError: 'NoneType' object has no attribute 'write'` pri inicijalizaciji tabova.  
**Fajlovi ispravljeni:**
- `dist_client/gui/tabs/zaglavlje_view.py` — 5 poziva → `logger.warning()`
- `dist_client/gui/tabs/naimenovanja_view.py` — 4 poziva → `logger.warning()` / `logger.error()`

---

### 3. Generička ikona u taskbaru
**Problem:** App u taskbaru prikazivala Python genericku ikonu, ne Deklarant Pro ikonu.  
**Uzrok:** `pythonw.exe` nema vlastiti AppUserModelID — Windows ga grupira pod Python.  
**Fix:** Dodano u `run.py` (root i dist_client):
```python
if os.name == 'nt':
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Carina.DeklarantPro.1")
```
**Dodatno:** Font 11pt za Windows (bio hardkodiran 13pt).  
**Dodatno:** `setup_windows_venv.bat` ispravio pogrešan naziv ikone (`app_icon.ico` → `deklarant_icon.ico`).

---

### 4. Duplikati PE1/PE2/PE3 u priloženim dokumentima
**Problem:** Zaglavlje tab prikazivao dva identična "PE1 EUR.1 obrazac" unosa.  
**Uzrok:** Tri `_sync_pe_docs_*` funkcije dedupliciraju po `(šifra, broj)` — dva naimenovanja sa istom šifrom ali različitim brojem dobijaju dva unosa. U `_merge_import_docs_add_only_missing`, `existing_docs` se nikad nije deduplicirao.  
**Fix:**
1. `zaglavlje_controller._merge_import_docs_add_only_missing` — dodana deduplicacija za `existing_docs` po šifri
2. `naimenovanja_view._sync_pe_docs_to_header` — dedup promijenjen sa `(sifra, broj)` na `sifra`
3. `faktura_view._sync_pe_docs_to_header` — isto
4. `zaglavlje_controller._sync_pe_docs_from_items_to_header` — isto  
**Logika:** Jedna deklaracija = jedan EUR.1 certifikat = jedan PE1 unos.

---

### 5. Izvoznik/Uvoznik se ne učitavaju iz XML-a
**Problem:** XML import ne popunjava polja Izvoznika i Primaoca.  
**Uzrok:** `load_from_xml` uvijek koristi "world" parser (`_parse_xml` koji traži `<ASYCUDA>/<Traders>/<Exporter>`). Kada se importuje XML koji je Deklarant Pro exportovao (`<AsycudaDocument>` root), parser ne nalazi `Traders` i preskače izvoznika/primaoca.  
**Fix:** Auto-detekcija formata u `zaglavlje_service.load_from_xml`:
```python
root_tag = root.tag.split('}')[-1] if '}' in root.tag else root.tag
if format_type.lower() == "world" and root_tag == "AsycudaDocument":
    format_type = "pro"
```

---

### 6. FAK i CMR — blokada starih šifara dokumenata
**Problem:** Stari ASYCUDA XML fajlovi sadrže `FAK` (Faktura) i `CMR` — šifre koje su zamijenjene novim šiframa. Import ih preuzima i miješa sa novim šiframa.  
**Fix na dva mjesta:**
- `zaglavlje_controller.py` — filter odmah po XML učitavanju: `{"FAK", "CMR"}` → skip
- `zaglavlje_service._parse_xml` — skip pri parsiranju ASYCUDA World XML-a

---

## Poznati problemi koji ostaju
- Server PostgreSQL na 192.168.0.41 trenutno nedostupan — `.env` podešen na `localhost`
- Git repozitorij ne postoji na Windows mašini (deployment, ne dev)
- `load_dotenv` u `config/settings.py` nema `override=True` (može biti problem ako sistem ima env varijable)

---

## Napomene
- Sve izmjene rađene direktno u `dist_client/` (Windows deploy folder)
- Root `deklarant_pro/` fajlovi ažurirani paralelno za `run.py` i `setup_windows_venv.bat`
- Nema git repozitorija na ovoj mašini — promjene treba ručno kopirati na dev mašinu (Fedora .131)
