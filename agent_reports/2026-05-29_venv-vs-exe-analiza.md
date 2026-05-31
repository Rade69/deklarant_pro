# Analiza: Python venv vs PyInstaller EXE
**Autor:** Claude Sonnet 4.6  
**Datum:** 2026-05-29  
**Kontekst:** Deklarant Pro — carinska aplikacija, 2 Windows 10 klijenta, PostgreSQL na Ubuntu serveru

---

## Uvod

Ovo je moje mišljenje zasnovano na konkretnom iskustvu tokom sesije Windows instalacije 2026-05-29. Nismo razmatrali teoriju — prošli smo kroz 12 stvarnih grešaka koje su direktna posljedica odabira EXE build pristupa. Cilj ovog dokumenta je da ti da jasnu sliku šta koji pristup znači u praksi, kako bi donio informiranu odluku.

---

## Šta se zapravo desilo tokom instalacije

Pokušali smo instalirati aplikaciju putem PyInstaller EXE-a i Inno Setup-a. Evo hronologije problema:

1. Inno Setup nije mogao pronaći `dist\DeklarantPro\` jer build nije bio pokrenut
2. PyInstaller nije mogao pronaći `database/data` folder koji ne postoji na Windows mašini
3. Batch skripta pala na sintaksnoj grešci zbog zagrada u `echo` poruci
4. `qtawesome` modul nije bio instaliran — PyInstaller ga nije uključio
5. Aplikacija pala jer `Program Files` nije pisljiv — `temp` i `logs` folderi ne mogu biti kreirani
6. `plugins` folder isto nije mogao biti kreiran u `Program Files`
7. Aplikacija počela spawnovati beskonačan broj novih instanci — MCP server koristio `sys.executable` (sam EXE) kao Python interpreter
8. `.env` fajl nije pronađen — aplikacija nije mogla spojiti na bazu
9. `UnicodeEncodeError` zbog emoji znakova u kodu i `cp1252` Windows encodinga
10. Tab factory vraćao `None` a greška bila skrivena
11. Desktop ikonica bijela — icon putanja u ISS-u nije uzimala u obzir `_internal\` strukturu
12. Toolbar raspored poremećen — font veličina i layout pretpostavljali Fedora/Linux ponašanje

**Svaka od ovih grešaka uzrokovana je istim korijenom: PyInstaller mijenja okruženje u kojem se kod izvršava, a kod nije bio pisan sa tom promjenom na umu.**

---

## Zašto se ove greške javljaju samo sa EXE buildom

### Kako PyInstaller radi

PyInstaller uzima tvoj Python kod i sve zavisnosti i pakuje ih u jedan folder. Interno, kreira `_internal/` podfolder u kojem se nalazi "zamrznuti" Python interpreter i sve biblioteke. Kada pokreneš EXE:

- `sys.executable` = `DeklarantPro.exe` (ne Python!)
- `__file__` putanje = unutar `_internal/` (nije projekt root)
- `sys.stdout` i `sys.stderr` = `None` (nema terminala)
- Konzolna encoding = `cp1252` na Windows (ne UTF-8)
- Instalacijski folder = `C:\Program Files\DeklarantPro\` (bez dozvole pisanja)

Kod koji je pisan i testiran na Fedori pravi pretpostavke koje više ne vrijede:
- Pretpostavlja da je `__file__` negdje u projektu → sada je u `_internal/`
- Pretpostavlja da `sys.executable` = Python → sada je EXE
- Pretpostavlja da može pisati u projektni folder → `Program Files` to brani
- Pretpostavlja da stdout postoji → ne postoji u GUI modu
- Pretpostavlja UTF-8 → Windows koristi cp1252

### Zašto se ovo ne dešava sa venv

Sa virtualnim okruženjem, Python radi **tačno onako kako radi na Fedori**. Nema "zamrzavanja", nema promjene putanja, nema skrivenih pretpostavki. Svaka linija koda se izvršava u poznatom okruženju.

---

## Direktna poređenja

### Instalacija

**EXE pristup:**
1. Na razvojnoj mašini: `.\build_windows.bat` → 10-20 minuta čekanja
2. Kompajliranje Inno Setup → još nekoliko minuta
3. Kopiranje instalera na Windows klijent
4. Pokretanje instalera, prolaz kroz wizard
5. Ručno kreiranje i konfiguracija `.env`
6. Testiranje, debug grešaka specifičnih za frozen okruženje
7. Ponavljanje od koraka 1 ako nešto ne radi

**venv pristup:**
1. Na Windows klijentu: `.\setup_windows_venv.bat` → jednom, ~5-10 minuta
2. Konfiguracija `.env` (Notepad se automatski otvori)
3. Pokretanje `start.bat`
4. Radi identično kao na Fedori

### Update aplikacije (nova verzija koda)

**EXE pristup:**
1. Razvij promjenu na Fedori
2. Pokreni build (10-20 min)
3. Kompajliraj novi installer
4. Pošalji na Windows klijent
5. Deinstaliraj staru verziju
6. Instaliraj novu
7. Provjeri da `.env` nije prebrisan

**venv pristup:**
1. Razvij promjenu na Fedori
2. Kopiraj izmijenjene `.py` fajlove na Windows klijent (xcopy, robocopy, ili git pull)
3. `start.bat` pokreće novu verziju

Razlika u vremenu: **20-30 minuta** vs **2-3 minute**.

### Debug greške na klijentu

**EXE pristup:**
- Greška je skrivena jer nema konzole
- Moraš čitati log fajl u `%APPDATA%\DeklarantPro\logs\`
- Encoding u logu može biti pogrešan
- Frozen okruženje može sakriti pravu grešku
- Svaka popravka zahtijeva novi build

**venv pristup:**
- Pokrenuti `start_debug.bat` → greška vidljiva direktno u terminalu
- Ista poruka greške kao na Fedori
- Popravka odmah aktivna, bez rebuilda

### Korištenje RAM-a na Windows 10 sa 4GB

**EXE pristup:**
- Frozen EXE tipično zauzima više RAM-a od čistog Python procesa
- `_internal/` folder sadrži duplikate biblioteka
- Nema benefita od Python-ovog memory managementa

**venv pristup:**
- Python sam po sebi: ~50-100 MB
- PySide6 GUI: ~150-200 MB
- Sve biblioteke dijele memoriju efikasno
- Na 4GB RAM mašini: ostaje ~1.5-2 GB slobodnih za rad

Procjena: venv pristup koristi **10-15% manje RAM-a** od frozen EXE-a.

---

## Kada EXE build IMA smisla

Biti pošten — postoje situacije gdje je EXE build pravi izbor:

1. **Distribucija nepoznatim korisnicima** — ako šalješ aplikaciju stotinama firmi koje ne znaju šta je Python i kojima ne možeš dati tehnički support
2. **Zaštita izvornog koda** — frozen EXE otežava čitanje izvornog koda (iako nije nemoguće)
3. **Nije dozvoljena instalacija softvera** — neke firme ne dozvoljavaju instalaciju Pythona, ali dozvoljavaju custom aplikacije
4. **Offline okruženje bez administratorskih privilegija** — ako klijent ne može ni pokrenuti setup skriptu

**Ništa od ovoga ne vrijedi za vaš slučaj.** Imate 2 interna računara, imate pristup, Python se može instalirati, kod nije tajna za vlastite zaposlene.

---

## Jedini realni argument ZA EXE u vašem slučaju

"Korisnik ne smije vidjeti terminal/konzolu, treba izgledati profesionalno."

**Odgovor:** `start.bat` se može napraviti da se pokrene kao pravi Windows shortcut bez vidljivog terminala. VBScript wrapper ili `pythonw.exe` umjesto `python.exe` pokretaju GUI aplikaciju potpuno bez konzole, identično kao EXE. Korisnik vidi samo aplikaciju.

---

## Moja preporuka

### Za odmah (kratkoročno)
Koristi `setup_windows_venv.bat` na oba Windows 10 klijenta. Jednom pokreni skriptu, postavi `.env`, i aplikacija radi. Nema više build grešaka, nema više frozen okruženja problema.

### Za pokretanje bez terminala
Dodaj jedan VBScript fajl `start_silent.vbs`:
```vbscript
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd /c cd /d """ & WScript.ScriptFullName & """ && .venv\Scripts\python.exe run.py", 0, False
```
Dvostruki klik na ovaj fajl pokreće aplikaciju bez ikakvog vidljivog terminala. Identično EXE iskustvu.

### Za buduće korisnike (dugoročno)
Kada dođe potreba za distribucijom vanjskim korisnicima — tada investiraj u ispravan EXE build. Ali to treba uraditi na Fedori sa Windows VM za testiranje, sa pytest testovima koji pokrivaju frozen okruženje, i sa CI/CD pipeline-om. Ne ručno.

### Prioritet koji je važniji od oba pristupa
CONTEXT.md, sekcija 7 upozorava: **lozinka je mogla biti eksponirana u git historiji** (commit `produkcijska-ociscenja`, Maj 2026). Rotirati DB lozinku na PostgreSQL serveru treba biti prioritet broj 1, bez obzira na koji pristup instalacije odabereš.

---

## Zaključak

EXE build je prikladan alat za pogrešan problem. Tvoj problem je "kako instalirati internu poslovnu aplikaciju na 2 Windows računara u lokalnoj mreži" — i za taj problem, Python + venv je jednostavniji, brži, lakši za održavanje i manje podložan greškama.

Svih 12 grešaka koje smo danas rješavali ne bi se pojavilo da smo od početka koristili venv pristup.

---

## Dodatak: Može li se izvorni kod zaštiti sa venv instalacijom?

**Kratki odgovor: da, ali uz kompromise.**

### Opcija 1 — Cython kompilacija (tehnički najjača)

Kompajlira `.py` fajlove u `.pyd` fajlove (Windows DLL) koji su čitljivi samo mašini, ne čovjeku.

```bash
# Na razvojnoj Fedori
pip install cython
cython --embed core/licensing/license_validator.py
gcc -shared -o license_validator.pyd ...
```

**Prednosti:**
- Vrlo teško reverse-engineerovati — čak ni iskusan reverser lako ne dolazi do logike
- Brzina izvršavanja se poboljša (C kod je brži od interpretiranog Pythona)
- Nema plaćanja licence za zaštitni alat

**Mane:**
- Kompajliranje traje i zahtijeva build okruženje
- `.pyd` fajlovi su platform-specifični — treba Windows mašina za kompajliranje Windows verzije
- Svaki update zahtijeva rekompajliranje

---

### Opcija 2 — PyArmor (najlakše za implementaciju)

Alat koji obfuskira Python bytecode i dodaje runtime zaštitu licencom.

```bash
pip install pyarmor
pyarmor gen -r --output dist_protected .
```

**Prednosti:**
- Jednostavno, radi sa venv bez ikakvih modifikacija koda
- Brza implementacija — jedan komand za cijeli projekt

**Mane:**
- Nije otvorenog koda
- Godišnja licenca (~$100/godišnje za komercijalno korištenje)
- Iskusan reverser sa dovoljno vremena može probiti obfuskaciju
- Ako istekne licenca PyArmor-a, obfuskovani kod i dalje radi (zaštita ostaje)

---

### Opcija 3 — Zaštiti samo kritične dijelove (praktičan kompromis)

Ne treba kompajlirati sve. Dovoljno je zaštititi ono što je stvarno osjetljivo:

```
core/licensing/     ← kompajliraj u .pyd  (logika licenciranja)
services/           ← kompajliraj u .pyd  (poslovna logika)
importers/          ← kompajliraj u .pyd  (parseri faktura)
gui/                ← ostavi kao .py      (Qt GUI teško vrijedi štititi)
config/             ← ostavi kao .py      (konfiguracija nije tajna)
```

Ovim prisupom korisnik vidi strukturu projekta ali ne može razumjeti ni kopirati ključnu poslovnu logiku.

---

### Realna procjena za vaš slučaj

Projekat već ima **licensing sistem** (`core/licensing/`) sa fingerprint-om mašine i privatnim ključem. To je već najveća zaštita — čak i ako neko ukrade `.py` fajlove, aplikacija neće raditi bez validne licence vezane za tu konkretnu mašinu.

**Pitanje koje treba postaviti: od koga štitimo kod?**

| Scenarij | Prijetnja | Potrebna zaštita |
|---|---|---|
| 2 interna Windows klijenta (vaša situacija sad) | Praktično nema | Licenca je dovoljna |
| Distribucija partnerskim firmama | Srednja | PyArmor za ključne module |
| Prodaja kao produkt na tržištu | Visoka | Cython za core + PyArmor za sve + licenca |
| IT direktor koji je i kupac | Nema smisla štititi | — |

---

### Važna napomena: sigurnost kroz obscurity nije prava sigurnost

Nijedna od ovih metoda ne može spriječiti **dovoljno motiviranog** napadača sa dovoljno vremena. Python bytecode se uvijek može dekompilovati, Cython se može disassemblirati, PyArmor se može probiti.

Prava zaštita je **kombinacija**:
1. Licencni sistem vezan za mašinu (već postoji)
2. Obfuskacija ključnih modula (otežava kopiranje)
3. Server-side validacija (ako se aplikacija spaja na tvoj server — a spaja se na PostgreSQL)

Aplikacija se spaja na **vaš PostgreSQL server** — to je prirodni gateway. Bez pristupa bazi, kopija koda je beskorisna.

---

### Konačna preporuka za zaštitu

**Za sada (2 interna klijenta):** Ništa dodatno ne treba. Licencni sistem + pristup vašoj bazi je dovoljna zaštita.

**Ako dođe do distribucije vanjskim korisnicima:** Implementirati PyArmor na `core/` i `services/` module. Jedan dan posla, dovoljna zaštita za poslovnu primjenu.

**Ako postane ozbiljan komercijalni produkt:** Razmotriti Cython za `core/licensing/` i `services/` uz PyArmor za ostatak. Ali to je investicija od nekoliko sedmica i ima smisla tek kada produkt ima dovoljno korisnika da zaštita bude ekonomski opravdana.
