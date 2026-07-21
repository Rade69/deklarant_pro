# Agent Report — 2026-07-21: Rebuild DeklarantPro.exe + audit_log.extra fix

## Datum
2026-07-21

## Agent
Claude Sonnet 5

## Scope
- `deklarant_pro.spec` (root, korišten za build) — nepromijenjen
- `dist_client/deklarant_pro.spec` — obrisan
- `dist/DeklarantPro/` — rebuildovan
- `services/agent/chat/audit_log.py` + dist_client mirror
- `tests/unit/test_audit_log.py`
- `docs/CONTEXT.md` §26

## Status izvora

- Moja vlastita tehnička analiza distribucije (ova sesija, ranije poruke) — aktivna,
  identifikovala je `.exe` kao jedini realan isporučni artefakat.
- Codex-ova dopuna `docs/architecture/DEKLARANT_PRO_TEHNICKA_ANALIZA_2026-07-20.md` §6.0/§6.11
  i `agent_reports/2026-07-21_opus-review-dopuna-tehnicke-analize.md` — aktivni, potvrdili
  isti nalaz o `.pyd`/`.py` rezoluciji nezavisnom metodom (behavioral proba + SHA-256),
  i otkrili `AuditEvent.extra` bug u mom Faza D kodu.

## GitNexus impact

- `deklarant_pro.spec` izmjena: nije programski simbol, build-only, GitNexus provjera
  nije relevantna.
- `audit_log.py::record()`: **HIGH** prije izmjene (34 pozivaoca, fan-in kroz sve audit
  pozive), ali izmjena čisto aditivna (jedan `%s` dodat u format string, bez promjene
  signature/ponašanja). Nakon izmjene: `risk_level: low`, 7 promijenjenih simbola,
  0 affected_processes.

## Šta je urađeno

### 1. Obrisan `dist_client/deklarant_pro.spec`

Postojala su dva PyInstaller spec fajla (root, 8. jun; dist_client, 3. jun,
različitih veličina) — izvor korisnikove zabune "koja distribucija je prava".
Root spec (noviji, builda iz čistog source stabla preko `run.py`) proglašen
kanonskim; dist_client kopija obrisana.

### 2. Rebuild `dist/DeklarantPro.exe`

Zatečeni `.exe` je bio od 9. juna (250 commitova zaostatka — nula od Faza A-D,
autosave, ili bilo koje ove sesije). Rebuild izveden:
- `Remove-Item -Recurse dist\DeklarantPro`, `build\` (čisto stanje);
- `pip install -r requirements.txt` (sve već zadovoljeno globalnim Python 3.14 env-om);
- `pyinstaller deklarant_pro.spec --noconfirm` (root spec, ~7.5 min, exit 0);
- `.env.example` kopiran u `dist/DeklarantPro/.env.example`;
- `NOVA ASIKUDA` XML arhiv provjeren — prazan lokalno, `data/knowledge_base` regulativa
  već ubačena preko spec-ovog `datas` popisa.

Rezultat: `DeklarantPro.exe` 78MB, cio folder 1.5GB (torch bundle zbog
`sentence-transformers`/embeddings extra-a — očekivano, ne greška).

### 3. Smoke test

`.exe` pokrenut (`Start-Process`), potvrđeno da proces preživi (`HasExited: False`),
`MainWindowTitle` = "Deklarant Pro". Screenshot potvrđuje GUI se ispravno renderuje —
štaviše, aplikacija je učitala prethodnu sesiju (autosave/session state) i prikazala
stvaran EUR.1 dijalog sa realnim podacima fakture (1476/26, više zemalja/EUR1 kodova) —
dokaz da je i autosave/session-restore funkcionalnost iz ove sesije stvarno u
rebuildovanom artefaktu.

### 4. `audit_log.py::record()` — `extra` polje fix

`AuditEvent.extra` dict (nosi npr. `operation_id` iz `_on_proposal_confirmed`/
`_on_proposal_rejected`) je bio konstruisan ispravno i dostupan u memoriji, ali
`record()` ga nikad nije referencirao u `logger.info()` format stringu — operation_id
je bio nevidljiv u stvarno emitovanom audit zapisu, iako je Faza D izvještaj
obećavao suprotno. Otkriveno u Codex-ovoj dopuni analize, potvrđeno čitanjem koda.
Fix: dodat `extra=%s` u format string + argument. Dodat regresioni test.

## Zašto je urađeno

Korisnik je eksplicitno tražio "uradi rebuild i izbriši spec fajl koji samo pravi
pometnju" (nakon zajedničke analize da je `.exe` jedini realan isporučni put), a
zatim eksplicitno "popravi audit bug" nakon što sam mu predstavio Codex-ov nalaz.

## Kako je urađeno

Build izveden preko PowerShell-a (ne `.bat` skripta direktno — `build_windows.bat`
ima `pause` na kraju koji bi blokirao neinteraktivnu sesiju; repliciran isti
redoslijed koraka ručno, bez pauze). Audit fix minimalan i aditivan — nije mijenjan
signature `record()` ni bilo koji od 34 pozivaoca.

## Šta nije dirano

- `AuditEvent` dataclass definicija — nepromijenjena (polje `extra` je već postojalo).
- Nijedan od 34 pozivaoca `record()` — nisu morali znati za izmjenu.
- `dist_client/build_windows.bat` — i dalje referencira `deklarant_pro.spec` relativno
  (sad ne postoji u `dist_client/`) — orphaned, ali van eksplicitnog scope-a ovog
  zadatka (korisnik je tražio samo brisanje spec fajla, ne i build skripte).
- Ostatak tehničke analize (Faza -1, DB fixture, `_decide_free`) — čeka odluku
  korisnika o prioritetu.

## Verifikacija

```
python -m pytest tests/unit/test_audit_log.py -v → 4 passed (uklj. novi regresioni test)
python -m pytest tests/unit tests/test_tool_use_offline.py tests/test_tool_use.py -q
  --ignore=tests/unit/test_decision_characterization.py → 711 passed, 43 skipped, 0 failed

python -m py_compile services/agent/chat/audit_log.py dist_client/... → OK
diff (bez BOM) root/dist_client audit_log.py → IDENTIČNI

mcp__gitnexus__detect_changes() nakon audit fix commita → risk_level: low, 0 affected_processes

PyInstaller build: exit code 0, "Build complete!" u logu
dist/DeklarantPro/DeklarantPro.exe: 78111980 bytes, datum rebuild-a potvrđen

Smoke test: proces preživi >10s, MainWindowTitle="Deklarant Pro",
screenshot potvrđuje ispravan render (GUI + učitana sesija + EUR.1 dijalog)
```

## Pronađeni problemi

- `dist_client/build_windows.bat` je sada orphaned (referencira obrisani lokalni
  spec) — nije popravljeno, van scope-a eksplicitnog zahtjeva.
- Frozen `.exe` bundle je 1.5GB zbog torch/sentence-transformers zavisnosti za
  embeddings — nije bug, ali vrijedi razmotriti u budućnosti da li je embeddings
  extra zaista potreban u svakoj klijentskoj instalaciji (potencijalna optimizacija
  veličine distribucije, van scope-a ovog zadatka).

## Konflikti / kontradiktorni izvori

Nema. Codex-ov nalaz o `AuditEvent.extra` je nezavisno potvrđen čitanjem
moje vlastite Faza D implementacije — nije bilo kontradikcije, samo previd
koji je Codex-ova dopuna otkrila.

## Commitovi

| Hash | Poruka |
|------|--------|
| `c9711ea` | fix(agent): serijalizuj AuditEvent.extra u audit log zapis (uklj. brisanje dist_client/deklarant_pro.spec) |

## Rizici / ograničenja

- Rebuild nije automatizovan (nema CI/CD koraka) — svaka buduća izmjena zahtijeva
  ručni rebuild + smoke test prije nego se smatra "isporučivom".
- `dist/` folder (build izlaz) nije git-tracked (očekivano, .gitignore) — rebuild
  treba ponoviti na svakoj mašini koja pravi release.
- Smoke test je bio vizuelni (screenshot), ne funkcionalan end-to-end (uvoz→XML) —
  puni funkcionalni smoke test (uvoz stvarne fakture, kreiranje naimenovanja, XML
  izvoz) preporučen kao follow-up prije stvarne distribucije klijentu.

## Potreban follow-up

- Pun funkcionalni smoke test na rebuildovanom `.exe`-u (uvoz prave fakture iz
  `najavauvoza/` → naimenovanja → XML izvoz).
- Odluka o `dist_client/build_windows.bat` (popraviti referencu ili obrisati fajl).
- Ostatak tehničke analize: Faza -1 (dokaz runtime-a na klijentskoj mašini, DB test
  preduslovi), zatim Faza 0 (`_decide_free` uklanjanje) — čeka korisnikovu odluku
  o prioritetu i redoslijedu.

## Potrebna korisnička potvrda

- Da li embeddings/torch zavisnost treba ostati u svakoj distribuciji (utiče na
  veličinu instalacije ~1.5GB).
- Prioritet sljedećeg koraka: funkcionalni smoke test, ili nastavak na Faza -1/0
  iz dopunjene tehničke analize.
