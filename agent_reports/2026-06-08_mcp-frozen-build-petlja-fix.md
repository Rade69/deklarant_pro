# Izvještaj: Fix beskonačne petlje pokretanja u frozen (PyInstaller) buildu

**Datum:** 2026-06-08
**Prijavio:** Radovan — primijetio da se aplikacija nakon pokretanja iz `DeklarantPro.exe` "konstantno otvarala, kao da je upala u petlju" (otkriveno tokom end-to-end build testa, vidi [2026-06-08_pyinstaller-build-test-i-stale-spec-fix.md](2026-06-08_pyinstaller-build-test-i-stale-spec-fix.md))

## Šta je urađeno

Ispravljen `McpClientAdapter.start()` u [mcp_server/client.py:59](../mcp_server/client.py#L59)
i identičnom mirror-u [dist_client/mcp_server/client.py:59](../dist_client/mcp_server/client.py#L59)
— dodata provjera koja sprečava pokretanje MCP server subprocess-a u
frozen (PyInstaller) buildu, gdje takav pokušaj uzrokuje rekurzivnu
petlju umnožavanja procesa cijele GUI aplikacije.

## Kako je urađeno

### Dijagnoza
Nakon pokretanja `DeklarantPro.exe` (test build iz commita `5a06813`),
log fajl `~/.deklarant_pro/logs/deklarant_pro.log` je pokazao **371**
ponovljenih `"⏱️ Startup"` zapisa, a `Get-Process DeklarantPro` je vratio
**9** aktivnih procesa — sve u svega par minuta nakon JEDNOG pokretanja.

Trag je vodio do `_start_mcp_server()` u `app/run.py:77`, koji u
pozadinskom thread-u poziva `McpClientAdapter.start()`
([mcp_server/client.py:59](../mcp_server/client.py#L59)):

```python
project_root = Path(__file__).resolve().parent.parent
venv_python = project_root / ".venv" / "bin" / "python3"
python_exe = str(venv_python) if venv_python.exists() else sys.executable
self._process = subprocess.Popen([python_exe, "-m", MCP_SERVER_MODULE], ...)
```

U **frozen** buildu `.venv` ne postoji (kod je raspakovan u `_internal/`),
pa se uzima `sys.executable` — ali to NIJE python interpreter, nego sam
`DeklarantPro.exe` (PyInstaller bundle nema bundlovan pravi Python
binarni fajl). Kod je dakle pokušavao da pokrene
`DeklarantPro.exe -m mcp_server.server` kao "MCP server" subprocess.
PyInstaller bootloader ignoriše argumente i uvijek pokreće isti entry
point (`run.py main()`) — taj novi proces ponovo pokušava da pokrene
SVOJ MCP server, koji opet pokreće novi `DeklarantPro.exe`...
eksponencijalna petlja spawn-ovanja.

### Fix
Provjera `getattr(sys, "frozen", False)` na samom početku `start()` —
preskače pokretanje subprocess-a i graceful degradira (postojeći
`server_error` Qt signal i UI fallback put već su pokrivali slučaj kad
MCP server ne uspije da se pokrene, pa nije trebalo dodavati novu
infrastrukturu):

```python
if getattr(sys, "frozen", False):
    logger.info("MCP server preskočen — frozen build nema python interpreter")
    self.server_error.emit("MCP server nije dostupan u frozen buildu")
    return False
```

### Verifikacija
Rebuild u test okruženju (`deklarant_pro_build_test/`) sa ispravljenim
`mcp_server/client.py`, zatim pokretanje novog `DeklarantPro.exe`:
- **Prije fixa:** 371 "Startup" zapisa, 9 procesa
- **Poslije fixa:** tačno **1** "Startup" zapis, **1** proces
- Log ispravno pokazuje: `"MCP server error: MCP server nije dostupan u frozen buildu"`

## Zašto

Ovo je generalni PyInstaller "gotcha" — `sys.executable` u frozen buildu
NIKAD nije plain python interpreter, nego sam distribuirani `.exe`. Svaki
kod koji koristi `sys.executable` da pokrene NOVI Python proces
(subprocess/multiprocessing/respawn šablon) mora prvo provjeriti
`sys.frozen`, inače dolazi do rekurzivnog pokretanja cijele aplikacije
umjesto namjeravanog helper procesa.

MCP server je razvojni alat (lokalni dev server za Claude integraciju) —
korisnicima distribuirane verzije nije potreban, pa je najjednostavnije i
najsigurnije rješenje jednostavno preskočiti pokretanje u frozen buildu,
bez pokušaja da se MCP server "ipak nekako" pokrene (npr. ugrađivanjem
pravog python interpretera ili pokretanjem in-process) — ta opcija bi
unijela nepotrebnu složenost za funkcionalnost koja krajnjem korisniku
ionako nije vidljiva niti potrebna.

## Tabela commitova

| Hash | Poruka | Status |
|------|--------|--------|
| `52a01d4` | fix(mcp): sprijeci beskonacnu petlju pokretanja u frozen (PyInstaller) buildu | ✅ verifikovano rebuild+run testom |

## Memorija

- `2026-06-08_mcp-frozen-build-petlja-pokretanja.md` (novi fajl — opisuje uzrok, fix i opštu PyInstaller pouku o `sys.executable`)
