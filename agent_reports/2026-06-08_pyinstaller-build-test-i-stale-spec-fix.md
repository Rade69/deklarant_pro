# Izvještaj: End-to-end build test (clone → exe) i fix zaostalog reda u spec fajlu

**Datum:** 2026-06-08
**Inicijator:** Radovan — ideja da se `windows` grana klonira u čist folder i proba PyInstaller build, kao provjera da je sinhronizovani kod zaista samostalan i buildable

## Šta je urađeno

1. Klonirana `windows` grana sa GitHub-a u zaseban folder (`deklarant_pro_build_test/`, van glavnog repoa — eksperimentalni prostor).
2. Postavljen `.venv` sa Python 3.13.10, instalirane sve zavisnosti iz `requirements.txt` + `pyinstaller`.
3. Pokrenut PyInstaller build prema `deklarant_pro.spec`.
4. **Rezultat: build je uspio u potpunosti.** `DeklarantPro.exe` (14.4 MB / 877 MB ukupno sa zavisnostima) generisan i pokrenut bez grešaka — prozor "Deklarant Pro" se otvorio (provjereno preko `Get-Process` — više `DeklarantPro` procesa sa `MainWindowTitle = "Deklarant Pro"`).
5. Otkriven i uklonjen zaostali (stale) red u `deklarant_pro.spec` — vidi ispod.

## Kako je urađeno

### Build proces
- Klon: `git clone -b windows <repo-url> deklarant_pro_build_test`
- `.venv` + `pip install -r requirements.txt pyinstaller`
- `python -m PyInstaller deklarant_pro.spec --noconfirm`
- Build pokrenut kao detached `nohup` proces (zaobilazi harness ograničenje da prati spoljašnji bash wrapper umjesto stvarnog dugotrajnog procesa)

### Fajlovi koje je trebalo ručno dodati (sve namjerno `.gitignore`-ovane, očekivano)
- `database/*.db` — `deklarant_sistem.db`, `inspection_rules.db`, `llm_audit.db`, `zvanicna_tarifa.db` (kopirano iz glavnog repoa)
- `data/knowledge_base/` — 142 MB PDF-ova zakonske regulative (kopirano iz glavnog repoa)

### Otkriven bug: `database/data` referenca u `deklarant_pro.spec:102`
Build je prvo padao na `ERROR: Unable to find '...\database\data'`. Provjera
(`grep` kroz sve `.py` fajlove projekta) pokazala je da **nijedan modul ne
referiše `database/data`** — folder ne postoji ni lokalno, ni igdje u git
istoriji. Vjerovatno zaostatak iz commita `4e65775` ("chore: dodaj
preostale projektne datoteke u windows granu").

**Fix:** uklonjen red `(str(ROOT / 'database' / 'data'), 'database/data')`
iz `datas` liste — [deklarant_pro.spec:102](../deklarant_pro.spec#L102) (commit `5a06813`).

## Zašto

Korisnik je potvrdio da je baza podataka **fizički na serveru, odvojena na
drugom računaru** — dakle lokalni `database/data` folder sa podacima nikad
nije ni trebao biti dio klijentskog build-a. To je definitivno potvrdilo da
je red zaostao greškom (kopiran/ostavljen iz nekog ranijeg eksperimenta), a
ne nedostajući resurs koji treba kreirati.

Bez ovog fixa, build bi padao na bilo kojoj čistoj mašini koja nema ručno
kreiran prazan placeholder folder — što je nevidljiv "works on my machine"
problem dok se ne proba pravi clean-build test, baš kao što je ovaj
eksperiment i otkrio.

## Tabela commitova

| Hash | Poruka | Status |
|------|--------|--------|
| `5a06813` | fix(build): ukloni zaostalu referencu na database/data iz spec fajla | ✅ |

## Memorija

- `2026-06-08_pyinstaller-build-test-i-stale-spec-red.md` (novi fajl, dokumentuje uspješan build test i otkriće stale spec reda)
