# Kako radi Python venv na Windows sistemima

**Autor:** Claude Sonnet 4.6  
**Datum:** 2026-05-29  
**Namjena:** Objašnjenje za Radovana — šta je venv, kako smo ga koristili i zašto

---

## 1. Šta je Python virtualno okruženje (venv)

Zamišli da imaš kompjuter na kojem radiš više različitih projekata. Jedan projekat treba `PySide6` verziju 6.5, drugi treba `PySide6` verziju 6.7. Ako instaliraš oba na isti sistem, jedan će pregaziti drugog i nešto će se pokvariti.

**venv (virtual environment)** rješava ovaj problem tako što za svaki projekat pravi **izolovanu kopiju** Python okruženja — sa sopstvenim paketima, sopstvenom verzijom biblioteka, odvojenu od sistema i od ostalih projekata.

```
C:\Users\dm promet\Desktop\deklarant_pro\
│
├── .venv\                    ← virtualno okruženje (izolovani Python)
│   ├── Scripts\
│   │   ├── python.exe        ← Python samo za ovaj projekat
│   │   ├── pythonw.exe       ← Python bez prozora konzole
│   │   ├── pip.exe           ← instalater paketa samo za ovaj projekat
│   │   └── activate.bat      ← aktivacija okruženja
│   │
│   └── Lib\
│       └── site-packages\    ← sve biblioteke (PySide6, psycopg2, itd.)
│           ├── PySide6\
│           ├── psycopg2\
│           ├── pdfplumber\
│           └── ...
│
├── run.py                    ← naša aplikacija
├── setup_windows_venv.bat    ← skripta za postavljanje (jednom)
├── start_debug.bat           ← pokretanje sa terminalom
└── start_silent.vbs          ← pokretanje bez terminala (za korisnike)
```

---

## 2. Razlika između sistemskog Python-a i venv Python-a

Kada instaliraš Python sa python.org, on se instalira "globalno" na sistem:

```
C:\Users\DM PROMET\AppData\Local\Programs\Python\Python311\python.exe
```

Ovaj Python je dostupan svuda na računaru. Problem je što ako instaliraš neki paket globalno (`pip install nešto`), on postaje dostupan svim projektima — što može uzrokovati konflikte.

Sa venv-om, **svaki projekat ima sopstveni Python**:

```
C:\Users\dm promet\Desktop\deklarant_pro\.venv\Scripts\python.exe
```

Ovaj Python zna samo za pakete instalirane **u tom konkretnom .venv folderu**.

---

## 3. Šta smo tačno uradili — korak po korak

### Korak A: Instalacija Python-a na Windows

Python je instaliran putem `winget` (Windows paket menadžer):

```powershell
winget install Python.Python.3.11 --silent --accept-package-agreements
```

Ovo je preuzelo i instaliralo **Python 3.11.9** sa python.org. Python je instaliran u:
```
C:\Users\DM PROMET\AppData\Local\Programs\Python\Python311\
```

I dodat je u Windows PATH — što znači da naredba `python` radi iz bilo kojeg foldera.

### Korak B: Kopiranje fajlova projekta

Cijeli projekat (source kod) je kopiran sa Linux laptopa na Windows Desktop:

```
C:\Users\dm promet\Desktop\deklarant_pro\
```

Kopiran je **samo izvorni kod** — bez `.venv` foldera (koji je specifičan za Linux i ne radi na Windows-u) i bez `docs/NOVA ASIKUDA` (prevelik XML arhiv).

### Korak C: Kreiranje virtualnog okruženja

Naredba koja kreira venv:

```cmd
python -m venv .venv
```

**Šta se dešava iznutra:**
1. Python uzima svoju kopiju executablea
2. Pravi folder strukturu `.venv\Scripts\` i `.venv\Lib\`
3. Upisuje `python.exe` i `pythonw.exe` u `.venv\Scripts\`
4. Pravi `pip.exe` koji će instalirati pakete **samo u ovaj .venv**
5. Pravi `activate.bat` skriptu (nije nam potrebna — direktno pozivamo python iz .venv)

Ova naredba je dio `setup_windows_venv.bat` koji smo napravili.

### Korak D: Instalacija paketa

```cmd
.venv\Scripts\pip install -r requirements.txt
```

`pip` čita `requirements.txt` i instalira sve navedene pakete:

| Paket | Namjena |
|---|---|
| `PySide6` | GUI framework — prozori, tabele, dugmad |
| `psycopg2-binary` | Konekcija na PostgreSQL bazu |
| `pdfplumber` | Čitanje PDF faktura |
| `openpyxl` | Čitanje Excel (.xlsx) faktura |
| `xlrd` | Čitanje starih Excel (.xls) faktura |
| `python-dotenv` | Čitanje `.env` konfiguracionog fajla |
| `qtawesome` | Ikone u toolbar-u i dugmadima |
| `rapidfuzz` | Fuzzy matching (traženje sličnih naziva roba) |
| `lxml` | XML parsiranje (ASYCUDA XML) |
| `requests` | HTTP pozivi |
| `anthropic` | AI agent (Claude API) |
| `groq` | AI agent (Groq API) |
| `google-generativeai` | AI agent (Gemini API) |
| `pydantic` | Validacija podataka |
| `colorama` | Boje u konzoli |
| `reportlab` | Generisanje PDF izvještaja |

Svaki paket se preuzima sa PyPI (Python Package Index — globalni repozitorij paketa) i instalira u:
```
.venv\Lib\site-packages\naziv_paketa\
```

### Korak E: Konfiguracija (.env fajl)

Aplikacija koristi `.env` fajl za konfiguraciju — baza podataka, API ključevi, itd. Ovaj fajl se nikad ne commituje u git (sadrži lozinke).

Sadržaj `.env` za Windows klijent:
```
DB_HOST=192.168.0.41        ← IP adresa Ubuntu servera sa bazom
DB_PORT=5432                ← PostgreSQL port
DB_NAME=deklarant_pro       ← naziv baze
DB_USER=radovan             ← korisnik baze
DB_PASSWORD=postgres        ← lozinka baze
CLIENT_NAME=dmwindows       ← identifikator ovog računara
```

Aplikacija čita ovaj fajl pri pokretanju pomoću `python-dotenv` biblioteke.

---

## 4. Kako se aplikacija pokreće

### Način 1: sa terminalom (za developere)

```cmd
start_debug.bat
```

Ova batch skripta:
1. Ide u folder projekta (`cd /d "%~dp0"`)
2. Provjerava da li `.venv` postoji
3. Pokreće: `.venv\Scripts\python.exe run.py`

Terminal ostaje otvoren — sve greške i `print()` poruke su vidljive.

### Način 2: bez terminala (za korisnike)

```
start_silent.vbs  ← dvostruki klik
```

Ova VBScript datoteka:
1. Pronalazi folder gdje se nalazi (ne oslanja se na radni direktorij)
2. Gradi putanje do `pythonw.exe` i `run.py`
3. Pokreće: `.venv\Scripts\pythonw.exe run.py` sa parametrom `0` (skriven prozor)

**Ključna razlika:** `pythonw.exe` umjesto `python.exe`

- `python.exe` → otvara crni CMD prozor pored aplikacije
- `pythonw.exe` → pokreće aplikaciju BEZ ikakvog terminala

Korisnik vidi samo prozor Deklarant Pro — identično kao da je u pitanju "pravi" EXE program.

---

## 5. Zašto venv, a ne PyInstaller EXE

Pokušali smo PyInstaller pristup i naišli na 12 različitih grešaka. Sve su imale isti korijen:

**PyInstaller "zamrzava" Python** — pretvara ga u statičnu strukturu koja se ponaša drugačije od normalnog Python-a:

| Problem | PyInstaller EXE | venv |
|---|---|---|
| `sys.executable` | vraća putanju do EXE-a | vraća putanju do python.exe |
| Putanje do fajlova | unutar `_internal/` foldera | normalne projektne putanje |
| Pisanje u folder | `Program Files` je zaštićen | Desktop folder je pisljiv |
| MCP server spawn | pokušava pokrenuti EXE kao Python | radi normalno |
| Unicode/emoji | `cp1252` encoding problemi | UTF-8 radi |
| Update aplikacije | rebuild + reinstalacija (20-30 min) | kopiranje .py fajlova (2-3 min) |
| Debug greške | skrivene, mora se čitati log | vidljive u terminalu odmah |

---

## 6. Kako funkcioniše update aplikacije

Kada se kod promijeni na Linux laptopu (novi parser, bug fix, nova funkcija):

**Sa venv pristupom:**
1. Na Linux laptopu: commituj i push promjene
2. Na Windows računaru: kopiraj izmijenjene `.py` fajlove

Ili — još jednostavnije — postoji skripta `nadogradi_windows.sh` (analogna `nadogradi_server.sh`) koja to radi automatski putem SSH:

```bash
# Sa Linux laptopa:
bash nadogradi_windows.sh
```

Nema rebuilda, nema instaliranja, nema čekanja. Nova verzija je aktivna čim se aplikacija ponovo pokrene.

---

## 7. Šta se dešava sa licencom

Deklarant Pro ima sistem licenciranja koji veže svaku instalaciju za konkretan računar (hardware fingerprint). Ovo funkcioniše isto bez obzira da li je venv ili EXE.

Pri pokretanju aplikacija:
1. Čita `C:\ProgramData\DeklarantPro\license.dat`
2. Uzima hardware fingerprint ovog računara (CPU, disk, MAC adresa, hostname)
3. Poredi sa fingerprintom u licenci
4. Ako score ≥ 70% → aplikacija radi
5. Ako score < 70% → traži licencu

Za Windows klijent treba generisati licencu na razvojnom laptopu (vidi `WINDOWS_SETUP.md`).

---

## 8. Struktura skripti koje smo napravili

### `setup_windows_venv.bat` (jednom, pri instalaciji)
```
[1/5] Provjera Python instalacije
[2/5] Kreiranje .venv foldera
[3/5] Instalacija svih paketa iz requirements.txt
[4/5] Provjera/kreiranje .env fajla
[5/5] Test konekcije na PostgreSQL server
```

### `start_debug.bat` (za developere)
```
cd u folder projekta
provjera .venv
.venv\Scripts\python.exe run.py
```

### `start_silent.vbs` (za korisnike — bez terminala)
```
pronađi folder skripte
provjera .venv postoji
.venv\Scripts\pythonw.exe run.py  (bez konzole)
```

---

## 9. Česte greške i rješenja

| Greška | Uzrok | Rješenje |
|---|---|---|
| `python nije prepoznat` | Python nije u PATH | Reinstalirati Python sa "Add to PATH" |
| `Nije moguće kreirati .venv` | Nedovoljna prava | Pokrenuti CMD kao Administrator |
| `ModuleNotFoundError: PySide6` | Paketi nisu instalirani | Pokrenuti `setup_windows_venv.bat` |
| `Konekcija na bazu odbijena` | Server nedostupan ili pogrešna lozinka | Provjeriti `.env` i mrežu na 192.168.0.41 |
| `Licenca nije pronađena` | `license.dat` ne postoji | Generisati i kopirati licencu (vidi `WINDOWS_SETUP.md`) |
| `UnicodeDecodeError` | Encoding problem sa PDF-om | Dodati `encoding='utf-8'` ili `errors='replace'` |

---

## 10. Kratki glossary

| Termin | Objašnjenje |
|---|---|
| **venv** | Virtualno Python okruženje — izolovani prostor sa sopstvenim paketima |
| **pip** | Python instalater paketa — preuzima biblioteke sa PyPI |
| **PyPI** | Python Package Index — globalni repozitorij Python biblioteka |
| **requirements.txt** | Lista svih paketa koji su potrebni projektu |
| **python.exe** | Python interpreter sa konzolinim prozorom |
| **pythonw.exe** | Python interpreter BEZ konzolnog prozora (za GUI aplikacije) |
| **PATH** | Windows varijabla — lista foldera gdje se traže izvršne naredbe |
| **`.env`** | Konfiguracioni fajl sa lozinkama i postavkama (nikad u git) |
| **fingerprint** | Digitalni otisak računara (CPU + disk + MAC + hostname) |
