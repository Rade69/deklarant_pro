# Oporavak test suite-a + bugfix sinhronizacije EUR.1/PE dokumenata

**Datum:** 2026-07-03
**Grana:** windows
**Zadatak:** Verifikacija testova u sklopu privođenja aplikacije kraju

---

## Šta je urađeno (kratki pregled)

Test suite je bio **potpuno neupotrebljiv** — 18 grešaka pri kolekciji
(`No module named 'gui.tabs'`) blokiralo je i samo pokretanje pytest-a.
Nakon oporavka: **457 testova prolazi, 0 pada, 41 uredno preskočeno**.

Usput je otkriven i ispravljen **jedan pravi bug u produkcionom kodu**
(NameError u sinhronizaciji povlastičnih dokumenata) i verifikovan Blagić
importer na 9 stvarnih faktura.

---

## Kako je urađeno (tehnički pristup)

### 1. Dijagnoza 18 collection grešaka
Simptom: `No module named 'gui.tabs'` u punom runu, ali čista kolekcija
pri pokretanju po pojedinačnom folderu. Bisekcijom (`test_large_batch_processing.py`
+ `test_weight_guards.py`) reprodukovan minimalni slučaj koji je pokazao
pravi izvor: `gui.__path__` je pokazivao na `tests/gui/` umjesto na root `gui/`.

Dva uzroka:
- **`tests/gui/__init__.py`** — prazan stub (0 bajtova), slučajno dodat u
  masovnom `chore` commitu, sjenčio je pravi `gui` paket.
- **`tests/integration/test_large_batch_processing.py`** — `ROOT` računat
  kao `Path(__file__).parent.parent` = `tests/` (fali jedan nivo), pa je
  ubacivao `tests/` na `sys.path[0]`, čime je `import gui` nalazio `tests/gui`.

Popravke: obrisan `tests/gui/`, ROOT ispravljen na `parent.parent.parent`.

### 2. Nedostajući `__init__.py`
`gui/utils/` (importuje se 33×), `importers/pdf/` (importuje se) i `core/`
(72× `from core.draft`) nisu imali `__init__.py`. Radili su kao PEP 420
namespace paketi, ali nestabilno — ovisno o redoslijedu importa `gui.utils`
je čas prolazio čas ne. Dodata tri `__init__.py`.

### 3. Mrtav test
`tests/unit/test_demo_service.py` importovao `services.demo_service` koji
nikad nije postojao u repou (template ostatak iz istog `chore` commita).
Obrisan — 10 testova za nepostojeći modul.

### 4. Windows encoding bug u testu
`test_parse_naimenovanja_xml.py` pisao XML sa `č` u `NamedTemporaryFile`
bez `encoding`, pa na Windows cp1252 konzoli pucao `UnicodeEncodeError`.
Dodat `encoding="utf-8"` (4 mjesta).

### 5. Graceful skip za env-zavisne testove
8 Blagić + 1 Master Frigo test zavise od privatnih faktura van repoa;
1 Gemini test zavisi od opcionog `google.genai`. Umjesto pada, sada
`pytest.mark.skipif` / `pytest.importorskip`.

### 6. Pravi bug — `gui/tabs/zaglavlje_controller.py:621`
U `_sync_pe_docs_from_items_to_header`:
```python
pe_entries.append(key)   # `key` nije definisan → NameError
```
Petlja nekoliko redova niže radi `for sifra, broj in pe_entries`, pa je
tačna vrijednost `(sifra, broj)`. **Posljedica buga:** svaki put kad bi se
povlastični dokumenti (EUR.1/PE1/PE2/PE3) sinhronizovali iz stavki u
zaglavlje, funkcija bi pukla sa NameError. Ispravljeno; test
`test_pe_rub44_consistency.py` sada prolazi (7/7).

### 7. Verifikacija Blagić importera (stvarni podaci)
Pokrenut `import_blagic_combined` na 9 parova iz `D:\MREŽA\BLAGIĆ`
(367–382VP-2026). Svih **9/9** uspješno, svaki sa `consumed_paths=True`
(sprječava duplikate stavki — CLAUDE.md pravilo #5). Potvrđeno da su
pytest failovi bili čisto zbog nedostajućih fixture fajlova, ne zbog koda.

---

## Zašto (poslovni razlog)

Bez pokretljivog test suite-a nema pouzdanog signala spremnosti za
produkciju. Cilj je bio pretvoriti "crveno/nepokretljivo" u čisto zeleno
koje radi na svakoj mašini (uklj. Windows i eventualni CI), da regresije
budu vidljive. Bug u zaglavlju je usputni ali stvaran nalaz — direktno je
kvario sinhronizaciju povlastica.

---

## Commitovi

| Hash | Poruka |
|------|--------|
| (bugfix) | fix(zaglavlje): ispravi NameError pri sinhronizaciji EUR.1/PE dokumenata |
| (mcp) | fix(mcp): preskoči pokretanje MCP servera u frozen (PyInstaller) buildu |
| (test infra) | test(infra): popravi kolekciju testova — 18 collection grešaka → 0 |
| (gitignore) | chore(gitignore): ignoriši lokalne data/ foldere |

*(Tačni hashovi vidljivi u `git log` nakon push-a na granu `windows`.)*

---

## Preostalo (van ovog zadatka)

- Operativni go-live (backup PostgreSQL, rotacija lozinke) — ručni posao.
- Threading/pool hardening (pool_timeout, graceful QThread shutdown) —
  otvorena srednja stavka iz majske analize.
- Nema CI/CD pipeline-a — sada kad je suite zelen, isplati se dodati.
