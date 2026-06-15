# Fix: uvoz XML u Naimenovanja pucao s WinError2 (Documents mkdir)

## Datum
2026-06-15

## Agent
Claude Sonnet 4.6

## Scope
- `services/declaration_draft_service.py`
- `dist_client/services/declaration_draft_service.py`

## GitNexus impact
`gitnexus_impact(target="default_drafts_directory", direction="upstream",
target_uid="Function:services/declaration_draft_service.py:default_drafts_directory")`
→ `risk: LOW`, 4 direktna pozivanja: `_on_save` i `_on_import_xml` u
`gui/tabs/naimenovanja_view.py` i `dist_client/gui/tabs/naimenovanja_view.py`.
`gitnexus_detect_changes(scope="unstaged")` (prije commit-a) →
`risk_level: low`, `affected_processes: []`.

## Šta je urađeno
`default_drafts_directory()` u oba `declaration_draft_service.py` (gui i
dist_client) sada hvata `OSError` iz `path.mkdir(parents=True,
exist_ok=True)` i, ako padne, fallback-uje na `Path.home() / "Deklarant Pro"
/ "Nacrti"` (umjesto `Path.home() / "Documents" / "Deklarant Pro" /
"Nacrti"`).

## Zašto je urađeno
Korisnik je prijavio grešku pri uvozu XML-a u Naimenovanja tab:
"Greška pri uvozu: [WinError 2] The system cannot find the file specified:
'C:\\Users\\38765\\Documents\\Deklarant Pro'".

**Provjera hipoteze**: dijagnostički skript je potvrdio da na ovom PC-u
(RADOVAN, `C:\Users\38765`) `Documents` folder POSTOJI i čita se normalno
(`os.path.exists`/`is_dir`=True, `os.listdir` vraća postojeće fajlove,
PowerShell `Get-Item` ne pokazuje symlink/junction), ALI `os.mkdir`/
`CreateDirectoryW` za BILO KOJI novi poddirektorijum unutar `Documents`
(testirano i generičkim test-imenom i sa "Deklarant Pro") puca sa
`FileNotFoundError(2, 'The system cannot find the file specified')`,
`GetLastError()=2`. Isti test pod `AppData\Local`, `Desktop` i direktno pod
`Path.home()` radi bez greške — problem je specifičan za `Documents` na ovoj
mašini (vjerovatno ostatak razbijenog Known-Folder/OneDrive redirecta).

Pošto `default_drafts_directory()` poziva `path.mkdir(...)` BEZ
try/except, a poziva se na SAMOM POČETKU `_on_import_xml` (linija ~3255,
za default vrijednost QFileDialog-a) — exception je prekidao CIJELU
`_on_import_xml` metodu PRIJE nego što je uopšte stigla do parsiranja XML-a
za naimenovanja. Time je novi "Sačuvaj kao Deklarant Pro nacrt" feature
(Codex, commit `d1fedec`) nenamjerno pokvario postojeću, nepovezanu
"Uvezi ASYCUDA XML naimenovanja" funkcionalnost — na ovoj konkretnoj
mašini.

## Kako je urađeno
Minimalna izmjena samo u `default_drafts_directory()` (2 fajla, identično):
```python
def default_drafts_directory() -> Path:
    path = Path.home() / "Documents" / "Deklarant Pro" / "Nacrti"
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        path = Path.home() / "Deklarant Pro" / "Nacrti"
        path.mkdir(parents=True, exist_ok=True)
    return path
```
Fix je u samoj funkciji, pa popravlja OBA pozivna mjesta (`_on_save` i
`_on_import_xml`, gui i dist_client) bez dodatnih izmjena u
`naimenovanja_view.py`.

## Šta nije dirano
- `gui/tabs/naimenovanja_view.py` / `dist_client/gui/tabs/naimenovanja_view.py`
  — pozivna mjesta `default_drafts_directory()` nisu mijenjana.
- Ostatak `services/declaration_draft_service.py` (save/load/serialize/
  deserialize, `is_draft_file`, `suggested_filename`) — nepromijenjeno.
- Necommitovane izmjene u `AGENTS.md`, `CLAUDE.md`,
  `agent_reports/2026-06-14_univerzalni-agent-md-template.md` (pre-postojeći
  WIP, van scope-a) — netaknuto.

## Verifikacija
- `python -m py_compile services/declaration_draft_service.py
  dist_client/services/declaration_draft_service.py` → OK.
- Direktan poziv `default_drafts_directory()` na ovoj mašini nakon fix-a →
  vraća `C:\Users\38765\Deklarant Pro\Nacrti`, `exists=True`, `is_dir=True`
  (fallback grana radi).
- `python -m pytest tests/unit/test_declaration_draft_service.py -q` →
  4 passed.

## Pronađeni problemi
- Bez novih problema u kodu nakon fix-a. Osnovni problem je
  okruženje-specifičan (Documents folder na ovom PC-u) — fix ga
  zaobilazi, ali NE rješava (Documents i dalje neće biti pisiv za ovu ili
  bilo koju buduću funkciju koja bi tu pisala).

## Konflikti / kontradiktorni izvori
Nema.

## Commitovi
| Hash | Poruka |
|------|--------|
| `b0a7c2c` | `fix(nacrti): default_drafts_directory fallback ako Documents nije pisiv` |

## Rizici / ograničenja
- Fallback putanja `~/Deklarant Pro/Nacrti` (direktno pod home, bez
  "Documents") je VIDLJIVA korisniku u file dialogu kao default lokacija —
  ako korisnik ranije već sačuvao nacrte u
  `Documents\Deklarant Pro\Nacrti` (ručno, izvan ove app, npr. ako je taj
  folder ranije postojao pa je naknadno postao nepisiv), novi nacrti idu na
  drugu lokaciju i postojeći se neće automatski vidjeti u "lastDirectory"
  podrazumjevanoj putanji (mogu se i dalje ručno otvoriti kroz dijalog).
- Fallback se aktivira samo kad PRVI `mkdir` baci `OSError`; ako i fallback
  putanja (`~/Deklarant Pro/Nacrti`) ne bude pisiva na nekoj drugoj mašini,
  greška će se i dalje propagirati (nije dodat treći nivo fallback-a —
  procijenjeno kao dovoljno za poznati slučaj).

## Potreban follow-up
- Nema poznatog follow-upa za ovaj fix. Opcionalno (van scope-a): istražiti
  i popraviti zašto `Documents` na ovom PC-u ne dozvoljava `mkdir` (npr.
  provjeriti OneDrive Known Folder Move podešavanja) — ali to je
  OS/environment podešavanje, ne app bug.

## Potrebna korisnička potvrda
U pokrenutoj aplikaciji: otvoriti Naimenovanja tab → "Uvezi ASYCUDA XML" →
izabrati standardni XML → potvrditi da se uvoz naimenovanja sada izvrši bez
greške (i da se, kao i ranije dogovoreno, Zaglavlje Rub.40 popuni).
Opcionalno i: dugme "Sačuvaj" (Codex nacrt-feature) → potvrditi da file
dialog za snimanje otvara `~/Deklarant Pro/Nacrti` bez greške.
