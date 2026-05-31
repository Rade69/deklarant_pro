# Windows instalacija — log popravki

**Datum:** 2026-05-29  
**OS:** Windows 11 Pro (razvoj), Windows 10 (klijent)  
**Cilj:** Izgradnja i instalacija `DeklarantPro.exe` putem PyInstaller + Inno Setup

---

## Infrastruktura (pojašnjeno tokom sesije)

| Mašina | OS | IP |
|---|---|---|
| Razvojna mašina | Fedora OS | 192.168.100.131 |
| Baza podataka | Ubuntu (PostgreSQL) | 192.168.0.41 |
| Windows klijent | Windows 10/11 | 192.168.100.55 |

---

## Greška 1 — Inno Setup: "No files found" (Line 43)

**Simptom:** Inno Setup prijavljuje grešku jer `dist\DeklarantPro\` ne postoji.  
**Uzrok:** Inno Setup je pokrenut prije PyInstaller build-a.  
**Rješenje:** Uvijek pokrenuti `build_windows.bat` PRIJE Inno Setup kompajliranja.

---

## Greška 2 — PyInstaller: `database\data` folder ne postoji

**Simptom:** `ERROR: Unable to find 'database\data' when adding binary and data files`  
**Uzrok:** `deklarant_pro.spec` referisao na `database/data` podfolder koji ne postoji na Windows mašini (JSON fajlovi su direktno u `database/`).  
**Fajl:** `deklarant_pro.spec`, linija 102  
**Popravka:** Zakomentarisana linija u spec fajlu.

---

## Greška 3 — `build_windows.bat`: batch syntax error sa zagradama

**Simptom:** `je was unexpected at this time` pri kraju builda.  
**Uzrok:** `echo` poruka unutar `if` bloka sadržala `(NOVA ASIKUDA)` — CMD tumači zagrade kao kraj `if` bloka.  
**Fajl:** `build_windows.bat`  
**Popravka:** Zagrade escapovane sa `^(` i `^)`.

---

## Greška 4 — `qtawesome` nije instaliran

**Simptom:** `ModuleNotFoundError: No module named 'qtawesome'`  
**Uzrok:** `qtawesome` nije bio u `requirements.txt` i nije instaliran na Windows mašini.  
**Popravka:**
- `pip install qtawesome`
- Dodat `collect_submodules('qtawesome')` u `deklarant_pro.spec`
- Dodati u `setup_windows_venv.bat` skriptu

---

## Greška 5 — `PermissionError`: pisanje u `Program Files`

**Simptom:** `PermissionError: [WinError 5] Access is denied: 'C:\Program Files\DeklarantPro\_internal\temp'`  
**Uzrok:** `config/settings.py` računao `PROJECT_ROOT` iz lokacije `__file__` što u frozen EXE-u postaje `_internal\` folder unutar `Program Files` — nije pisljiv bez admin prava.  
**Fajl:** `config/settings.py`  
**Popravka:** Dodat `USER_DATA_DIR` koji u frozen modu koristi `%APPDATA%\DeklarantPro\`:
```python
def _user_data_dir() -> Path:
    if getattr(sys, 'frozen', False):
        if os.name == 'nt':
            return Path(os.environ.get('APPDATA', Path.home())) / 'DeklarantPro'
        return Path.home() / '.deklarant_pro'
    return PROJECT_ROOT
```
`temp`, `logs`, `imports`, `exports` → `USER_DATA_DIR`  
`styles`, `ui`, `sifrarnici` → ostali na `PROJECT_ROOT` (read-only)

---

## Greška 6 — `PermissionError`: `plugins` folder u `Program Files`

**Simptom:** `PermissionError: [WinError 5] Access is denied: 'C:\Program Files\DeklarantPro\plugins'`  
**Uzrok:** `plugin_loader.py` stavljao `plugins/` folder pored EXE-a, što je `Program Files` — nije pisljivo.  
**Fajl:** `importers/plugin_loader.py`  
**Popravka:** U frozen modu koristi `%APPDATA%\DeklarantPro\plugins\`.

---

## Greška 7 — Beskonačno spawning novih procesa

**Simptom:** GUI se pojavio ali se otvarale nove i nove instance aplikacije bez prestanka.  
**Uzrok:** `mcp_server/client.py` pokretao MCP server kao subprocess koristeći `sys.executable`. U frozen EXE-u `sys.executable` je `DeklarantPro.exe` → svaki subprocess pokreće novu instancu EXE-a → beskonačna petlja.  
**Fajl:** `app/run.py`  
**Popravka:** Skip MCP server kada je `sys.frozen == True`:
```python
if getattr(sys, 'frozen', False):
    logger.info("MCP server preskočen u production buildu")
    return
```

---

## Greška 8 — `.env` nije pronađen (DB_PASSWORD missing)

**Simptom:** `DB_PASSWORD Field required [type=missing]` — aplikacija ne može spojiti na bazu.  
**Uzrok:** `settings.py` tražio `.env` u `PROJECT_ROOT` = `_internal\`, ali Inno Setup kopira `.env` pored EXE-a (jedan nivo iznad).  
**Fajl:** `config/settings.py`  
**Popravka:**
```python
if getattr(sys, 'frozen', False):
    _env_file = Path(sys.executable).parent / ".env"
else:
    _env_file = PROJECT_ROOT / ".env"
```

---

## Greška 9 — `UnicodeEncodeError` pri pokretanju tabova

**Simptom:** `UnicodeEncodeError: 'charmap' codec can't encode character '✅'`  
**Uzrok A:** Windows koristi `cp1252` encoding za konzolu. `faktura_view.py`, `naimenovanja_view.py`, `zaglavlje_view.py` imali direktne `sys.stderr.write()` pozive sa emoji znakovima (✅, ❌, ⚠️) na nivou modula.  
**Uzrok B:** `sys.stdout/stderr` su `None` u frozen EXE-u sa `console=False`.  
**Fajlovi:** `gui/tabs/faktura_view.py`, `naimenovanja_view.py`, `zaglavlje_view.py`, `run.py`  
**Popravka:**
- Svi `sys.stderr.write(emoji...)` zamijenjeni sa `logger.warning(...)`
- U `run.py` dodano preusmjeravanje na devnull sa UTF-8:
```python
if getattr(sys, 'frozen', False):
    if sys.stdout is None:
        sys.stdout = open(os.devnull, 'w', encoding='utf-8', errors='replace')
    if sys.stderr is None:
        sys.stderr = open(os.devnull, 'w', encoding='utf-8', errors='replace')
```

---

## Greška 10 — Tab factory vraćao `None` (greška bila skrivena)

**Simptom:** `RuntimeError: Invalid parameter None passed to addLayoutOwnership()`  
**Uzrok:** `tab_factory.py` hvatao sve iznimke i vraćao `None` bez traceback-a. `LazyTab` bi dobio `None` i pao pri dodavanju u layout.  
**Fajl:** `gui/tabs/tab_factory.py`  
**Popravka:** `return None` zamijenjeno sa `raise` da greška bude vidljiva.

---

## Greška 11 — Ikonica na desktopu je bijela

**Simptom:** Prečica na desktopu prikazuje bijelu (praznu) ikonicu.  
**Uzrok:** `setup.iss` tražio icon na `{app}\assets\icons\deklarant_icon.ico`, ali PyInstaller stavlja sve data fajlove u `{app}\_internal\`.  
**Fajl:** `installer/setup.iss`  
**Popravka:** Putanje ikona promijenjene na `{app}\_internal\assets\icons\deklarant_icon.ico`.

---

## Problem 12 — Toolbar raspored poremećen (u toku)

**Simptom:** Dugmad u "Izvezi" sekciji se preklapaju, Bruto/Neto i Validacija su odsječeni.  
**Uzrok:** Sekcija "Izvezi" imala 6 elemenata (Excel, PDF, Pregled, "Kreiraj Naimenovanja", Bruto/Neto, Validacija) u jednom `HBoxLayout`. Na Windows-u sa Segoe UI fontom dugmad su šira nego na Fedori.  
**Fajlovi:** `gui/tabs/faktura_view.py`, `run.py`  
**Urađeno:**
- "Kreiraj Naimenovanja" skraćeno na "Naimenovanja"
- "Validacija" premještena u "Pametna pomoć" sekciju
- Column stretch podešen: Uvezi/Uredi 2, Izvezi 4, Pametna pomoć 4
- Font smanjen na 11pt za Windows (`os.name == 'nt'`)
- HiDPI atributi dodani u `run.py`

**Status:** ⚠️ Rebuild nije potvrđen — potrebno testirati nakon sljedećeg builda.

---

## Dodano: `setup_windows_venv.bat`

Alternativna instalacija bez PyInstaller-a (preporučeno za interne korisnike):
- Instalira Python venv sa svim zavisnostima
- Kreira `start.bat` i `start_debug.bat`
- Kreira `.env` iz predloška i otvara Notepad za konfiguraciju
- Pogodan za Windows 10 računare sa 4GB RAM

---

## Preporučeni sljedeći koraci

1. Pokrenuti `.\build_windows.bat` sa svim najnovijim izmjenama
2. Kompajlirati `installer\setup.iss` u Inno Setup
3. Testirati instalaciju — provjeriti toolbar izgled
4. Ako toolbar i dalje ne odgovara: razmotriti prelaz na `setup_windows_venv.bat` pristup
5. Rotirati DB lozinku (vidi CONTEXT.md sekcija 7 — lozinka u git historiji!)
