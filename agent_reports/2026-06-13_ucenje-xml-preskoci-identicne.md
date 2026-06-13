# Učenje iz XML-ova — preskoči identične fajlove pri uvozu

## Datum
2026-06-13

## Agent
Claude Sonnet 4.6 (Claude Code)

## Scope
- `gui/tabs/admin/panels/learning_panel.py`
- `dist_client/gui/tabs/admin/panels/learning_panel.py`

## GitNexus impact
Provjereno PRIJE izmjene:

- `Method:gui/tabs/admin/panels/learning_panel.py:LearningPanel._on_add_xml#0`
  (upstream, `target_uid`) → **risk: LOW**, `impactedCount: 0`, bez pogođenih
  procesa/modula (Qt-signal handler, nije u statičkom call graph-u).

`gitnexus_detect_changes(scope="unstaged")` PRIJE commita: `risk_level: "low"`,
`affected_processes: []`. Pored `_on_add_xml`, kao "touched" su prijavljeni i
`_is_valid_learning_xml`/`_is_duplicate_xml`/klasa `LearningPanel` u oba
fajla — to je artefakt line-diff detekcije (pomak linija unutar fajla zbog
duže metode), te metode NISU mijenjane. Detect_changes je takođe prikazao
nepovezane unstaged izmjene (AGENTS.md, CLAUDE.md, zaglavlje_view.py +
dist_client mirror, test_zaglavlje_isprava_delegate.py) — predmet su
prethodnog/paralelnog WIP-a korisnika i NISU staged-ovane u ovom zadatku.

## Šta je urađeno
U `_on_add_xml()` (obje kopije, gui/ + dist_client/):

1. Kad `dst.exists()` i fajl ima ISTO ime kao novi: prvo se poredi
   `_file_hash(dst) == _file_hash(src_path)` (SHA-256, postojeća helper
   funkcija `_file_hash`).
   - Ako je sadržaj identičan → tiho preskoči, BEZ dijaloga (brojač
     `identicni`, log na kraju: `"ℹ️ Već postoji (identičan sadržaj),
     preskočeno: N"`).
2. Ako se sadržaj razlikuje → dijalog "Prepiši?" sada nudi
   `Yes | No | YesToAll | NoToAll` (prije: samo `Yes | No`).
   - Nova lokalna varijabla `apply_to_all: bool | None` pamti
     YesToAll/NoToAll odluku za ostatak trenutnog batch-a uvoza, tako da se
     dijalog ne ponavlja za svaki sljedeći konfliktni fajl.

## Zašto je urađeno
Korisnikova primjedba (verbatim): kod uvoza velikog broja XML fajlova (npr.
500) kroz admin "Učenje iz XML-ova", svaki fajl čije ime već postoji u
`XML_FOLDER` prikazuje blokirajući "Prepiši?" dijalog — i kada je sadržaj
identičan (npr. ponovni uvoz istih deklaracija sa ASYCUDA servera), korisnik
mora klikati stotine puta.

Root cause: postojeći `_is_duplicate_xml()` namijenjen je detekciji duplikata
pod DRUGAČIJIM imenom (eksplicitno `if existing.name == xml_path.name:
continue`), pa za fajlove istog imena `_on_add_xml` nikad nije provjeravao
sadržaj — samo je pitao Yes/No.

Korisnik je pitao za mišljenje i bolju ideju; predloženo i odobreno
("Implementiraj"): (a) tih auto-skip za identičan sadržaj, (b) YesToAll/NoToAll
za genuine konflikte da se izbjegne ponavljanje klika i kod stvarnih razlika.

## Kako je urađeno
Izmjena je lokalizovana u `_on_add_xml()` — bez promjene signature, bez novih
metoda. Ponovo korištena postojeća `_file_hash()` (SHA-256, 1MB chunk-ovi),
koja je već postojala za `_is_duplicate_xml`. `QMessageBox` je
`SafeMessageBox` alias (`from gui.utils.safe_message_box import
SafeMessageBox as QMessageBox`) — `Yes/No/YesToAll/NoToAll` konstante su
nasljeđene direktno iz `QMessageBox.StandardButton`.

## Šta nije dirano
- `_is_duplicate_xml()` i `_file_hash()` — nepromijenjeni, samo ponovo
  korišteni.
- Nepovezane unstaged izmjene zatečene u radnom stablu (prethodni/paralelni
  WIP korisnika): `AGENTS.md`, `CLAUDE.md`, `gui/tabs/zaglavlje_view.py` i
  `dist_client/gui/tabs/zaglavlje_view.py` (IspravaDelegate), te untracked
  `tests/unit/test_zaglavlje_isprava_delegate.py` i `client.log.lck` — NISU
  staged-ovane niti commit-ovane u ovom zadatku.

## Verifikacija
- `python -m py_compile` na oba izmijenjena fajla → OK.
- Privremena offscreen skripta (`QT_QPA_PLATFORM=offscreen`,
  monkeypatch `QFileDialog.getOpenFileNames`, `QMessageBox.question`,
  `LearningPanel._is_valid_learning_xml`), 3 scenarija — sva 3 prošla
  (`SVE OK`), skripta obrisana nakon provjere:
  1. Isto ime + identičan sadržaj → `QMessageBox.question` pozvan 0 puta,
     `identicni=1`, fajl u `XML_FOLDER` ostao nepromijenjen.
  2. Isto ime + drugačiji sadržaj, 2 fajla, prvi odgovor `YesToAll` →
     `QMessageBox.question` pozvan tačno 1 put, OBA fajla prepisana novim
     sadržajem.
  3. Isto ime + drugačiji sadržaj, 2 fajla, prvi odgovor `NoToAll` →
     `QMessageBox.question` pozvan tačno 1 put, NIJEDAN fajl prepisan
     (originali ostali).

## Pronađeni problemi
Nema. Nema lažno pozitivnih nalaza.

## Commitovi
| Hash | Poruka |
|------|--------|
| `46fe2af` | `feat(admin): preskoci identicne XML fajlove pri uvozu u "Ucenje iz XML-ova"` |

## Rizici / ograničenja
- `apply_to_all` se resetuje na `None` na početku SVAKOG poziva
  `_on_add_xml()` (svaki put kad korisnik otvori file-picker) — namjeravano,
  da odluka ne "preživi" između nezavisnih sesija uvoza.
- Ako korisnik odabere `NoToAll` rano u velikom batch-u, SVI naredni
  konfliktni (drugačiji sadržaj, isto ime) fajlovi se preskaču bez daljeg
  pitanja — ovo je namjeravano ponašanje po zahtjevu, ali korisnik treba biti
  svjestan da YesToAll/NoToAll vrijedi za CIJELI ostatak trenutnog uvoza.

## Potreban follow-up
Nema otvorenih stavki za ovaj zadatak.

## Potrebna korisnička potvrda
- Pri sljedećem stvarnom uvozu većeg broja XML fajlova (npr. iz ASYCUDA
  servera) u admin "Učenje iz XML-ova" panelu, potvrditi da:
  1. Fajlovi sa istim imenom i istim sadržajem prolaze BEZ dijaloga i da se
     na kraju u logu prikazuje brojač "Već postoji (identičan sadržaj),
     preskočeno: N".
  2. Za fajlove sa istim imenom ali izmijenjenim sadržajem, dijalog sada ima
     4 dugmeta (Yes/No/YesToAll/NoToAll) i da YesToAll/NoToAll ispravno
     primjenjuju odluku na ostatak batch-a.
